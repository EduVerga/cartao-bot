"""
Bot do Telegram para controle de gastos do cartão de crédito
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from database import Database
from gemini_processor import ComprovanteProcessor

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicializa banco de dados e processador
db = Database()
processor = ComprovanteProcessor(api_key=os.getenv('GEMINI_API_KEY'))

# ID do usuário autorizado (deixe vazio para permitir todos)
ALLOWED_USER_ID = os.getenv('ALLOWED_USER_ID')


def is_authorized(user_id: int) -> bool:
    """Verifica se o usuário está autorizado"""
    if not ALLOWED_USER_ID:
        return True  # Se não configurado, permite todos
    return str(user_id) == str(ALLOWED_USER_ID)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    user = update.effective_user

    # Se ALLOWED_USER_ID não está configurado, mostra o ID do usuário
    if not ALLOWED_USER_ID:
        await update.message.reply_text(
            f"⚠️ **Bot sem restrição de acesso!**\n\n"
            f"Seu ID do Telegram: `{user.id}`\n\n"
            f"Para restringir o acesso somente a você:\n"
            f"1. Copie o ID acima\n"
            f"2. Edite o arquivo .env\n"
            f"3. Adicione: ALLOWED_USER_ID={user.id}\n"
            f"4. Reinicie o bot\n\n"
            f"Depois disso, apenas você poderá usar o bot! 🔒"
        )
        return

    # Verifica autorização
    if not is_authorized(user.id):
        await update.message.reply_text(
            f"🚫 Acesso não autorizado.\n\n"
            f"Seu ID: {user.id}\n"
            f"Entre em contato com o administrador do bot."
        )
        logger.warning(f"Tentativa de acesso não autorizado: {user.id} - {user.username}")
        return

    mensagem = f"""
🤖 Olá {user.first_name}! Bem-vindo ao seu assistente de gastos!

📸 **Como usar:**
Envie uma foto do comprovante do Samsung Pay e eu vou:
• Extrair automaticamente o valor, estabelecimento e data
• Categorizar o gasto
• Atualizar sua caixinha correspondente
• Te avisar quanto sobrou do limite

💰 **Comandos disponíveis:**

/caixinhas - Ver todas as suas caixinhas
/criar <nome> <limite> - Criar nova caixinha
  Exemplo: /criar Alimentação 1000

/historico - Ver últimas 10 transações
/relatorio - Resumo do mês atual
/ajuda - Ver esta mensagem novamente

🚀 **Comece criando sua primeira caixinha!**
"""
    await update.message.reply_text(mensagem)


async def criar_caixinha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /criar <nome> <limite>"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Uso correto: /criar <nome> <limite>\n"
            "Exemplo: /criar Alimentação 1000"
        )
        return

    try:
        nome = ' '.join(context.args[:-1])
        limite = float(context.args[-1])

        if limite <= 0:
            await update.message.reply_text("❌ O limite deve ser maior que zero!")
            return

        caixinha = db.criar_caixinha(user_id, nome, limite)

        await update.message.reply_text(
            f"✅ Caixinha criada com sucesso!\n\n"
            f"📦 **{caixinha.nome}**\n"
            f"💰 Limite: R$ {caixinha.limite:.2f}\n"
            f"📊 Gasto atual: R$ 0,00"
        )

    except ValueError:
        await update.message.reply_text("❌ Limite deve ser um número válido!")
    except Exception as e:
        logger.error(f"Erro ao criar caixinha: {e}")
        await update.message.reply_text("❌ Erro ao criar caixinha. Tente novamente.")


async def listar_caixinhas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /caixinhas"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    caixinhas = db.listar_caixinhas(user_id)

    if not caixinhas:
        await update.message.reply_text(
            "📦 Você ainda não tem caixinhas!\n\n"
            "Crie uma com: /criar <nome> <limite>\n"
            "Exemplo: /criar Alimentação 1000"
        )
        return

    mensagem = "📦 **Suas caixinhas:**\n\n"

    for c in caixinhas:
        percentual = c.percentual_usado
        emoji_status = "🟢" if percentual < 50 else "🟡" if percentual < 80 else "🔴"

        mensagem += (
            f"{emoji_status} **{c.nome}**\n"
            f"💰 R$ {c.gasto_atual:.2f} / R$ {c.limite:.2f}\n"
            f"📊 {percentual:.1f}% usado\n"
            f"💵 Restante: R$ {c.saldo_restante:.2f}\n\n"
        )

    await update.message.reply_text(mensagem)


async def historico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /historico"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    transacoes = db.listar_transacoes(user_id, limit=10)

    if not transacoes:
        await update.message.reply_text("📝 Nenhuma transação registrada ainda.")
        return

    mensagem = "📝 **Últimas 10 transações:**\n\n"

    for t in transacoes:
        data_formatada = t.data_transacao.strftime("%d/%m/%Y")
        mensagem += (
            f"🏪 {t.estabelecimento}\n"
            f"💰 R$ {t.valor:.2f} - {t.categoria}\n"
            f"📅 {data_formatada}\n\n"
        )

    await update.message.reply_text(mensagem)


async def processar_imagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa imagem do comprovante enviada pelo usuário"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    # Verifica se usuário tem caixinhas
    caixinhas = db.listar_caixinhas(user_id)
    if not caixinhas:
        await update.message.reply_text(
            "❌ Você precisa criar pelo menos uma caixinha primeiro!\n\n"
            "Use: /criar <nome> <limite>\n"
            "Exemplo: /criar Alimentação 1000"
        )
        return

    await update.message.reply_text("🔍 Analisando comprovante...")

    try:
        # Download da imagem
        logger.info(f"Baixando imagem do usuário {user_id}")
        photo = await update.message.photo[-1].get_file()
        image_path = f"temp_{user_id}.jpg"
        await photo.download_to_drive(image_path)
        logger.info(f"Imagem salva em: {image_path}")

        # Processa com Gemini
        logger.info("Processando comprovante com Gemini...")
        dados = processor.processar_comprovante(image_path)
        logger.info(f"Dados extraídos: {dados}")

        # Remove arquivo temporário (com retry para Windows)
        try:
            if os.path.exists(image_path):
                import time
                time.sleep(0.1)  # Pequeno delay para Windows liberar o arquivo
                os.remove(image_path)
        except Exception as e:
            logger.warning(f"Não foi possível remover arquivo temporário: {e}")

        if not dados or not dados['valor']:
            await update.message.reply_text(
                "❌ Não consegui extrair as informações do comprovante.\n"
                "Tente tirar uma foto mais clara ou enviar outro comprovante."
            )
            logger.warning(f"Falha ao extrair dados do comprovante: {dados}")
            return

        # Tenta encontrar caixinha pela categoria sugerida
        categoria = dados['categoria_sugerida']
        caixinha = db.buscar_caixinha_por_categoria(user_id, categoria)

        # Se não encontrou, tenta usar IA para categorizar
        if not caixinha:
            nomes_caixinhas = [c.nome for c in caixinhas]
            categoria_encontrada = processor.categorizar_estabelecimento(
                dados['estabelecimento'],
                nomes_caixinhas
            )

            if categoria_encontrada:
                caixinha = db.buscar_caixinha_por_categoria(user_id, categoria_encontrada)

        # Se ainda não encontrou, usa a primeira caixinha
        if not caixinha:
            caixinha = caixinhas[0]

        # Registra a transação
        transacao = db.adicionar_transacao(
            user_id=user_id,
            caixinha_id=caixinha.id,
            valor=dados['valor'],
            estabelecimento=dados['estabelecimento'] or "Não identificado",
            categoria=caixinha.nome,
            data_transacao=dados['data']
        )

        # Atualiza a caixinha
        db.session.refresh(caixinha)

        # Monta mensagem de resposta
        percentual = caixinha.percentual_usado
        emoji_alerta = "✅" if percentual < 50 else "⚠️" if percentual < 80 else "🚨"

        mensagem = f"""
{emoji_alerta} **Compra registrada!**

🏪 **Estabelecimento:** {dados['estabelecimento']}
💰 **Valor:** R$ {dados['valor']:.2f}
📅 **Data:** {dados['data'].strftime('%d/%m/%Y')}

📦 **Caixinha:** {caixinha.nome}
📊 **Gasto:** R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}
💵 **Restante:** R$ {caixinha.saldo_restante:.2f}
📈 **{percentual:.1f}% usado**
"""

        if percentual >= 100:
            mensagem += "\n🚨 **ATENÇÃO: Limite ultrapassado!**"
        elif percentual >= 80:
            mensagem += "\n⚠️ **Atenção: Você já usou mais de 80% do limite!**"
        elif percentual >= 50:
            mensagem += "\n⚠️ Você já usou metade do limite."

        await update.message.reply_text(mensagem)

    except Exception as e:
        logger.error(f"Erro ao processar imagem: {e}")
        await update.message.reply_text(
            "❌ Ocorreu um erro ao processar o comprovante. Tente novamente."
        )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ajuda"""
    await start(update, context)


def main():
    """Inicia o bot"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not token:
        logger.error("Token do Telegram não encontrado! Configure o arquivo .env")
        return

    # Cria a aplicação
    application = Application.builder().token(token).build()

    # Registra handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ajuda", ajuda))
    application.add_handler(CommandHandler("criar", criar_caixinha))
    application.add_handler(CommandHandler("caixinhas", listar_caixinhas))
    application.add_handler(CommandHandler("historico", historico))
    application.add_handler(MessageHandler(filters.PHOTO, processar_imagem))

    # Inicia o bot
    logger.info("Bot iniciado!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
