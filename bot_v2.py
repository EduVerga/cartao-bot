"""
Bot do Telegram para controle de gastos do cartão de crédito - VERSÃO 2
Com confirmação de categorias, memória de estabelecimentos e relatórios automáticos
"""
import os
import logging
import time
from datetime import datetime, time as dtime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

from database import Database, Caixinha
from gemini_processor import ComprovanteProcessor
from audio_processor import AudioProcessor
from scheduler_tasks import reset_mensal_automatico, enviar_relatorio_mensal
from scheduler_v3 import BotScheduler

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicializa banco de dados e processadores
db = Database()
processor = ComprovanteProcessor(api_key=os.getenv('GEMINI_API_KEY'))
audio_processor = AudioProcessor(api_key=os.getenv('GEMINI_API_KEY'))

# ID do usuário autorizado (deixe vazio para permitir todos)
ALLOWED_USER_ID = os.getenv('ALLOWED_USER_ID')

# Dicionário temporário para armazenar dados pendentes de confirmação
pending_transactions = {}


def is_authorized(user_id: int) -> bool:
    """Verifica se o usuário está autorizado"""
    if not ALLOWED_USER_ID:
        return True
    # Suporta múltiplos IDs separados por vírgula
    allowed_ids = [id.strip() for id in ALLOWED_USER_ID.split(',')]
    return str(user_id) in allowed_ids


def get_alerta_gasto(percentual: float) -> str:
    """Retorna mensagem de alerta baseada no percentual gasto"""
    if percentual >= 100:
        return "\n\n🚨 **ATENÇÃO: LIMITE ULTRAPASSADO!**\n💡 Considere reduzir gastos nesta categoria."
    elif percentual >= 90:
        return "\n\n🔴 **ALERTA CRÍTICO: 90% do limite usado!**\n💡 Pega leve! Só restam 10% do orçamento."
    elif percentual >= 80:
        return "\n\n⚠️ **ATENÇÃO: 80% do limite usado!**\n💡 Hora de controlar os gastos nesta categoria!"
    elif percentual >= 70:
        return "\n\n🟡 **Cuidado: 70% do limite usado**\n💡 Fique atento aos próximos gastos."
    elif percentual >= 50:
        return "\n\n🟢 **Metade do limite usado**\n💡 Você está no caminho certo!"
    else:
        return "\n\n✅ **Tudo sob controle!**\n💡 Continue assim! 💪"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    user = update.effective_user

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
Envie uma foto do comprovante do cartão de crédito e eu vou:
• Extrair automaticamente o valor, estabelecimento e data
• Categorizar o gasto (com confirmação na primeira vez)
• Memorizar o estabelecimento para próximas compras
• Atualizar sua caixinha correspondente
• Te avisar quanto sobrou do limite

💰 **Comandos disponíveis:**

/caixinhas - Ver todas as suas caixinhas
/criar <nome> <limite> - Criar nova caixinha
  Exemplo: /criar Alimentação 1000

/fechamento <dia> - Definir dia de fechamento do cartão
  Exemplo: /fechamento 20
  Use /fechamento sem número para ver o dia configurado

/recentes - Ver últimas 10 transações
/historico <meses> - Histórico consolidado
  Exemplo: /historico 12 (últimos 12 meses)
  Opções: 6, 12, 18 ou 24 meses
/relatorio - Relatório do mês atual
/ajuda - Ver esta mensagem novamente

🔄 **Automações:**
• Dia de fechamento às 22h: Relatório automático
• Dia seguinte ao fechamento às 00:10: Reset dos gastos

🚀 **Comece criando sua primeira caixinha e definindo o fechamento!**
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


async def definir_fechamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /fechamento <dia> para definir dia de fechamento do cartão"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    # Se não passou argumento, mostra o dia configurado
    if len(context.args) == 0:
        dia_atual = db.obter_dia_fechamento(user_id)
        if dia_atual:
            await update.message.reply_text(
                f"📅 **Dia de fechamento configurado:** {dia_atual}\n\n"
                f"💳 Seu cartão fecha todo dia **{dia_atual}** do mês.\n"
                f"🔄 Os gastos são resetados automaticamente no dia **{dia_atual + 1 if dia_atual < 28 else 1}**.\n\n"
                f"Para alterar, use: /fechamento <dia>"
            )
        else:
            await update.message.reply_text(
                "❌ Você ainda não configurou o dia de fechamento.\n\n"
                "Use: /fechamento <dia>\n"
                "Exemplo: /fechamento 20"
            )
        return

    # Valida e define o dia
    try:
        dia = int(context.args[0])

        if dia < 1 or dia > 28:
            await update.message.reply_text(
                "❌ O dia deve estar entre 1 e 28.\n\n"
                "Exemplo: /fechamento 20"
            )
            return

        db.definir_dia_fechamento(user_id, dia)

        await update.message.reply_text(
            f"✅ **Dia de fechamento definido!**\n\n"
            f"📅 Seu cartão fecha todo dia **{dia}** do mês.\n"
            f"🔄 Os gastos serão resetados automaticamente no dia **{dia + 1 if dia < 28 else 1}**.\n\n"
            f"💡 A partir de agora, o bot vai gerenciar seus ciclos de fatura automaticamente!"
        )

    except ValueError:
        await update.message.reply_text(
            "❌ Dia inválido! Use um número entre 1 e 28.\n\n"
            "Exemplo: /fechamento 20"
        )
    except Exception as e:
        logger.error(f"Erro ao definir fechamento: {e}")
        await update.message.reply_text("❌ Erro ao configurar fechamento. Tente novamente.")


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


async def recentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /recentes - Últimas 10 transações"""
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


async def historico_consolidado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /historico <meses> - Histórico consolidado de 6, 12, 18 ou 24 meses"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    # Valida parâmetro
    if len(context.args) == 0:
        await update.message.reply_text(
            "📊 **Histórico Consolidado**\n\n"
            "Use: /historico <meses>\n\n"
            "Opções disponíveis:\n"
            "• /historico 6 - Últimos 6 meses\n"
            "• /historico 12 - Último ano\n"
            "• /historico 18 - Últimos 18 meses\n"
            "• /historico 24 - Últimos 2 anos"
        )
        return

    try:
        num_meses = int(context.args[0])

        if num_meses not in [6, 12, 18, 24]:
            await update.message.reply_text(
                "❌ Período inválido!\n\n"
                "Escolha: 6, 12, 18 ou 24 meses"
            )
            return

        # Busca histórico consolidado
        historico = db.get_historico_consolidado(user_id, num_meses)

        if not historico:
            await update.message.reply_text(
                f"📝 Nenhuma transação encontrada nos últimos {num_meses} meses."
            )
            return

        # Monta mensagem
        mensagem = f"📊 **Histórico Consolidado - {num_meses} meses**\n\n"

        total_geral = 0.0
        total_transacoes = 0

        for mes_ano, categorias in historico.items():
            total_mes = sum(cat['total'] for cat in categorias.values())
            total_geral += total_mes

            mensagem += f"📅 **{mes_ano}** - Total: R$ {total_mes:.2f}\n"

            # Ordena categorias por valor (maior primeiro)
            categorias_ordenadas = sorted(categorias.items(), key=lambda x: x[1]['total'], reverse=True)

            for categoria, dados in categorias_ordenadas:
                total_transacoes += dados['count']
                mensagem += f"  📦 {categoria}: R$ {dados['total']:.2f} ({dados['count']} transações)\n"

            mensagem += "\n"

        # Resumo final
        mensagem += f"💰 **Total Geral:** R$ {total_geral:.2f}\n"
        mensagem += f"📝 **Total de Transações:** {total_transacoes}\n"
        mensagem += f"📊 **Média Mensal:** R$ {total_geral / len(historico):.2f}"

        await update.message.reply_text(mensagem)

    except ValueError:
        await update.message.reply_text(
            "❌ Valor inválido!\n\n"
            "Use: /historico <meses>\n"
            "Exemplo: /historico 12"
        )
    except Exception as e:
        logger.error(f"Erro ao gerar histórico consolidado: {e}")
        await update.message.reply_text("❌ Erro ao gerar histórico. Tente novamente.")


async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /relatorio - Relatório do mês atual"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    rel = db.get_relatorio_mensal(user_id)
    hoje = datetime.now()
    mes_nome = hoje.strftime("%B/%Y")

    mensagem = f"""
📊 **Relatório Mensal - {mes_nome}**

{'='*40}

📦 **Resumo das Caixinhas:**

"""

    for c in rel['caixinhas']:
        percentual = c.percentual_usado
        emoji_status = "🟢" if percentual < 50 else "🟡" if percentual < 80 else "🔴"

        mensagem += f"""
{emoji_status} **{c.nome}**
   💰 Gasto: R$ {c.gasto_atual:.2f}
   🎯 Limite: R$ {c.limite:.2f}
   💵 Restante: R$ {c.saldo_restante:.2f}
   📊 {percentual:.1f}% usado

"""

    mensagem += f"""
{'='*40}

💵 **Totais do Mês:**
• Total gasto: R$ {rel['total_gasto']:.2f}
• Total de limites: R$ {rel['total_limite']:.2f}
• Total disponível: R$ {rel['total_disponivel']:.2f}
• Número de transações: {rel['num_transacoes']}
"""

    await update.message.reply_text(mensagem)


async def processar_imagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa imagem do comprovante com sistema de confirmação"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

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
        logger.info(f"Baixando imagem do usuário {user_id}")
        photo = await update.message.photo[-1].get_file()
        image_path = f"temp_{user_id}.jpg"
        await photo.download_to_drive(image_path)

        logger.info("Processando comprovante com Gemini...")
        dados = processor.processar_comprovante(image_path)

        try:
            if os.path.exists(image_path):
                time.sleep(0.1)
                os.remove(image_path)
        except Exception as e:
            logger.warning(f"Não foi possível remover arquivo temporário: {e}")

        if not dados or not dados['valor']:
            await update.message.reply_text(
                "❌ Não consegui extrair as informações do comprovante.\n"
                "Tente tirar uma foto mais clara."
            )
            return

        estabelecimento = dados['estabelecimento'] or "Não identificado"

        # Verifica se o estabelecimento já é conhecido
        # MAS: estabelecimentos genéricos sempre pedem confirmação
        estabelecimento_conhecido = None
        estabelecimentos_genericos = ["NÃO IDENTIFICADO", "NÃO ESPECIFICADO"]
        if estabelecimento.upper() not in estabelecimentos_genericos:
            estabelecimento_conhecido = db.buscar_estabelecimento_conhecido(user_id, estabelecimento)

        if estabelecimento_conhecido:
            # Adiciona direto
            caixinha = estabelecimento_conhecido.caixinha
            db.adicionar_transacao(
                user_id=user_id,
                caixinha_id=caixinha.id,
                valor=dados['valor'],
                estabelecimento=estabelecimento,
                categoria=caixinha.nome,
                data_transacao=dados['data']
            )

            db.session.refresh(caixinha)
            percentual = caixinha.percentual_usado
            emoji = "✅" if percentual < 50 else "🟡" if percentual < 70 else "⚠️" if percentual < 90 else "🚨"

            msg = f"""
{emoji} **Compra registrada!**

🏪 {estabelecimento}
💰 R$ {dados['valor']:.2f}
📅 {dados['data'].strftime('%d/%m/%Y')}

📦 {caixinha.nome}
📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}
💵 Restante: R$ {caixinha.saldo_restante:.2f}
📈 {percentual:.1f}% usado
"""
            msg += get_alerta_gasto(percentual)

            await update.message.reply_text(msg)

        else:
            # Estabelecimento novo - pede confirmação
            categoria_sugerida = dados['categoria_sugerida']
            caixinha_sugerida = db.buscar_caixinha_por_categoria(user_id, categoria_sugerida)

            if not caixinha_sugerida:
                nomes = [c.nome for c in caixinhas]
                cat = processor.categorizar_estabelecimento(estabelecimento, nomes)
                if cat:
                    caixinha_sugerida = db.buscar_caixinha_por_categoria(user_id, cat)

            if not caixinha_sugerida:
                caixinha_sugerida = caixinhas[0]

            # Armazena temporariamente
            import uuid
            trans_id = str(uuid.uuid4())[:8]
            pending_transactions[trans_id] = {
                'user_id': user_id,
                'valor': dados['valor'],
                'estabelecimento': estabelecimento,
                'data': dados['data'],
                'tipo': 'imagem'  # Marca como imagem
            }

            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirmar", callback_data=f"confirm_{trans_id}_{caixinha_sugerida.id}"),
                    InlineKeyboardButton("❌ Mudar categoria", callback_data=f"change_{trans_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"🆕 **Novo estabelecimento!**\n\n"
                f"🏪 {estabelecimento}\n"
                f"💰 R$ {dados['valor']:.2f}\n"
                f"📅 {dados['data'].strftime('%d/%m/%Y')}\n\n"
                f"📦 Categoria sugerida: **{caixinha_sugerida.nome}**\n\n"
                f"A categoria está correta?",
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Erro: {e}")
        await update.message.reply_text("❌ Erro ao processar. Tente novamente.")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para botões"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data.startswith("confirm_"):
        # Formato: confirm_{trans_id}_{caixinha_id}
        parts = data.replace("confirm_", "").split("_")
        trans_id = parts[0]
        caixinha_id = int(parts[1])

        if trans_id not in pending_transactions:
            await query.edit_message_text("❌ Transação expirada.")
            return

        td = pending_transactions[trans_id]
        caixinha = db.session.query(Caixinha).get(caixinha_id)

        db.adicionar_transacao(
            user_id=td['user_id'],
            caixinha_id=caixinha.id,
            valor=td['valor'],
            estabelecimento=td['estabelecimento'],
            categoria=caixinha.nome,
            data_transacao=td['data']
        )

        db.salvar_estabelecimento_conhecido(user_id, td['estabelecimento'], caixinha.id)
        del pending_transactions[trans_id]

        db.session.refresh(caixinha)
        perc = caixinha.percentual_usado
        emoji = "✅" if perc < 50 else "🟡" if perc < 70 else "⚠️" if perc < 90 else "🚨"

        # Monta mensagem diferente para áudio/texto vs imagem
        tipo = td.get('tipo', 'imagem')
        if tipo in ['audio', 'texto']:
            metodo = td.get('metodo_pagamento')
            metodo_texto = f" ({metodo.upper()})" if metodo else ""
            descricao = td.get('descricao', '')
            icone = "🎤" if tipo == 'audio' else "✍️"
            tipo_nome = "áudio" if tipo == 'audio' else "texto"

            msg = (
                f"{emoji} **Gasto registrado via {tipo_nome}!{metodo_texto}**\n\n"
                f"{icone} \"{descricao}\"\n\n"
                f"🏪 {td['estabelecimento']}\n"
                f"💰 R$ {td['valor']:.2f}\n\n"
                f"📦 {caixinha.nome}\n"
                f"📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}\n"
                f"💵 Restante: R$ {caixinha.saldo_restante:.2f}\n"
                f"📈 {perc:.1f}% usado\n\n"
                f"💾 Da próxima vez será automático!"
            )
        else:
            msg = (
                f"{emoji} **Registrado e memorizado!**\n\n"
                f"🏪 {td['estabelecimento']}\n"
                f"💰 R$ {td['valor']:.2f}\n\n"
                f"📦 {caixinha.nome}\n"
                f"📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}\n"
                f"💵 Restante: R$ {caixinha.saldo_restante:.2f}\n"
                f"📈 {perc:.1f}% usado\n\n"
                f"💾 Da próxima vez será automático!"
            )
        msg += get_alerta_gasto(perc)

        await query.edit_message_text(msg)

    elif data.startswith("change_"):
        trans_id = data.replace("change_", "")
        if trans_id not in pending_transactions:
            await query.edit_message_text("❌ Transação expirada.")
            return

        caixinhas = db.listar_caixinhas(user_id)
        keyboard = [[InlineKeyboardButton(f"📦 {c.nome}", callback_data=f"sel_{trans_id}_{c.id}")] for c in caixinhas]
        # Adiciona botão para criar nova caixinha
        keyboard.append([InlineKeyboardButton("➕ Adicionar nova caixinha", callback_data=f"new_{trans_id}")])
        await query.edit_message_text("Escolha a categoria:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("sel_"):
        parts = data.replace("sel_", "").rsplit("_", 1)
        trans_id = parts[0]
        caixinha_id = int(parts[1])

        if trans_id not in pending_transactions:
            await query.edit_message_text("❌ Transação expirada.")
            return

        td = pending_transactions[trans_id]
        caixinha = db.session.query(Caixinha).get(caixinha_id)

        db.adicionar_transacao(
            user_id=td['user_id'],
            caixinha_id=caixinha.id,
            valor=td['valor'],
            estabelecimento=td['estabelecimento'],
            categoria=caixinha.nome,
            data_transacao=td['data']
        )

        db.salvar_estabelecimento_conhecido(user_id, td['estabelecimento'], caixinha.id)
        del pending_transactions[trans_id]

        db.session.refresh(caixinha)
        perc = caixinha.percentual_usado
        emoji = "✅" if perc < 50 else "🟡" if perc < 70 else "⚠️" if perc < 90 else "🚨"

        # Monta mensagem diferente para áudio/texto vs imagem
        tipo = td.get('tipo', 'imagem')
        if tipo in ['audio', 'texto']:
            metodo = td.get('metodo_pagamento')
            metodo_texto = f" ({metodo.upper()})" if metodo else ""
            descricao = td.get('descricao', '')
            icone = "🎤" if tipo == 'audio' else "✍️"
            tipo_nome = "áudio" if tipo == 'audio' else "texto"

            msg = (
                f"{emoji} **Gasto registrado via {tipo_nome}!{metodo_texto}**\n\n"
                f"{icone} \"{descricao}\"\n\n"
                f"🏪 {td['estabelecimento']}\n"
                f"💰 R$ {td['valor']:.2f}\n\n"
                f"📦 {caixinha.nome}\n"
                f"📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}\n"
                f"💵 Restante: R$ {caixinha.saldo_restante:.2f}\n"
                f"📈 {perc:.1f}% usado\n\n"
                f"💾 Da próxima vez será automático!"
            )
        else:
            msg = (
                f"{emoji} **Registrado e memorizado!**\n\n"
                f"🏪 {td['estabelecimento']}\n"
                f"💰 R$ {td['valor']:.2f}\n\n"
                f"📦 {caixinha.nome}\n"
                f"📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}\n"
                f"💵 Restante: R$ {caixinha.saldo_restante:.2f}\n"
                f"📈 {perc:.1f}% usado\n\n"
                f"💾 Da próxima vez será automático!"
            )
        msg += get_alerta_gasto(perc)

        await query.edit_message_text(msg)

    elif data.startswith("new_"):
        # Usuário quer criar nova caixinha durante o registro
        trans_id = data.replace("new_", "")
        if trans_id not in pending_transactions:
            await query.edit_message_text("❌ Transação expirada.")
            return

        # Marca que o usuário está esperando criar uma caixinha para esta transação
        pending_transactions[trans_id]['awaiting_new_caixinha'] = True

        await query.edit_message_text(
            "➕ **Criar nova caixinha**\n\n"
            "Envie no formato:\n"
            "`nome limite`\n\n"
            "Exemplo:\n"
            "`Educação 500`\n\n"
            "Depois disso, seu gasto será registrado automaticamente nesta nova caixinha!"
        )


async def processar_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa áudio de voz para registrar gasto manual"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    caixinhas = db.listar_caixinhas(user_id)
    if not caixinhas:
        await update.message.reply_text(
            "❌ Você precisa criar pelo menos uma caixinha primeiro!\n\n"
            "Use: /criar <nome> <limite>"
        )
        return

    await update.message.reply_text("🎤 Ouvindo seu áudio...")

    try:
        # Download do áudio
        logger.info(f"Baixando áudio do usuário {user_id}")
        voice = update.message.voice
        audio_file = await voice.get_file()
        audio_path = f"temp_audio_{user_id}.ogg"
        await audio_file.download_to_drive(audio_path)

        # Processa com Gemini
        logger.info("Processando áudio com Gemini...")
        dados = audio_processor.processar_audio(audio_path)
        logger.info(f"Dados extraídos do áudio: {dados}")

        # Remove arquivo temporário
        try:
            if os.path.exists(audio_path):
                time.sleep(0.1)
                os.remove(audio_path)
        except Exception as e:
            logger.warning(f"Não foi possível remover arquivo de áudio: {e}")

        if not dados or not dados['valor']:
            await update.message.reply_text(
                "❌ Não consegui entender o valor do gasto.\n\n"
                "Tente dizer algo como:\n"
                "• 'Gastei 100 reais no supermercado'\n"
                "• 'Paguei 50 de Uber'\n"
                "• 'Almocei no restaurante, 45 reais'"
            )
            return

        estabelecimento = dados['estabelecimento'].upper()

        # Verifica se estabelecimento já é conhecido
        # MAS: "Não especificado" sempre pede confirmação (não é um estabelecimento real)
        estab_conhecido = None
        if estabelecimento != "NÃO ESPECIFICADO":
            estab_conhecido = db.buscar_estabelecimento_conhecido(user_id, estabelecimento)

        if estab_conhecido:
            # Estabelecimento conhecido - registra direto
            caixinha = db.session.get(Caixinha, estab_conhecido.caixinha_id)

            db.adicionar_transacao(
                user_id=user_id,
                caixinha_id=caixinha.id,
                valor=dados['valor'],
                estabelecimento=estabelecimento,
                categoria=caixinha.nome,
                data_transacao=datetime.now()
            )

            db.session.refresh(caixinha)
            percentual = caixinha.percentual_usado
            emoji = "✅" if percentual < 50 else "🟡" if percentual < 70 else "⚠️" if percentual < 90 else "🚨"

            metodo = dados.get('metodo_pagamento')
            metodo_texto = f" ({metodo.upper()})" if metodo else ""

            msg = f"""
{emoji} **Gasto registrado via áudio!{metodo_texto}**

🎤 "{dados['descricao']}"

🏪 {estabelecimento}
💰 R$ {dados['valor']:.2f}
📅 {datetime.now().strftime('%d/%m/%Y')}

📦 {caixinha.nome}
📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}
💵 Restante: R$ {caixinha.saldo_restante:.2f}
📈 {percentual:.1f}% usado
"""
            msg += get_alerta_gasto(percentual)
            await update.message.reply_text(msg)

        else:
            # Estabelecimento novo - pede confirmação
            categoria_sugerida = dados['categoria_sugerida']
            caixinha_sugerida = db.buscar_caixinha_por_categoria(user_id, categoria_sugerida)

            if not caixinha_sugerida:
                nomes = [c.nome for c in caixinhas]
                cat = processor.categorizar_estabelecimento(estabelecimento, nomes)
                if cat:
                    caixinha_sugerida = db.buscar_caixinha_por_categoria(user_id, cat)

            if not caixinha_sugerida:
                caixinha_sugerida = caixinhas[0]

            # Gera ID único para esta transação pendente
            import uuid
            trans_id = str(uuid.uuid4())[:8]

            # Armazena dados temporariamente
            metodo = dados.get('metodo_pagamento')
            pending_transactions[trans_id] = {
                'user_id': user_id,
                'valor': dados['valor'],
                'estabelecimento': estabelecimento,
                'data': datetime.now(),
                'descricao': dados['descricao'],
                'metodo_pagamento': metodo,
                'tipo': 'audio'  # Marca como áudio
            }

            # Monta mensagem com botões
            metodo_texto = f"\n💳 Forma: {metodo.upper()}" if metodo else ""

            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirmar", callback_data=f"confirm_{trans_id}_{caixinha_sugerida.id}"),
                    InlineKeyboardButton("❌ Mudar categoria", callback_data=f"change_{trans_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            msg = f"""
🆕 **Novo gasto via áudio!**

🎤 "{dados['descricao']}"

🏪 {estabelecimento}
💰 R$ {dados['valor']:.2f}{metodo_texto}
📦 Categoria sugerida: **{caixinha_sugerida.nome}**

A categoria está correta?
"""
            await update.message.reply_text(msg, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Erro ao processar áudio: {e}")
        await update.message.reply_text(
            "❌ Erro ao processar o áudio. Tente novamente.\n\n"
            "Dica: Fale de forma clara mencionando o valor e onde gastou."
        )


async def processar_criar_caixinha_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, trans_id: str, texto: str):
    """Processa criação de caixinha inline durante registro de gasto"""
    user_id = update.effective_user.id

    # Parse do texto: "nome limite"
    partes = texto.rsplit(None, 1)  # Separa pelo último espaço

    if len(partes) != 2:
        await update.message.reply_text(
            "❌ Formato incorreto!\n\n"
            "Use: `nome limite`\n"
            "Exemplo: `Educação 500`"
        )
        return

    nome, limite_str = partes

    try:
        limite = float(limite_str.replace(',', '.'))

        # Cria a caixinha
        caixinha = db.criar_caixinha(user_id, nome, limite)

        # Pega dados da transação pendente
        td = pending_transactions[trans_id]

        # Registra a transação na nova caixinha
        db.adicionar_transacao(
            user_id=td['user_id'],
            caixinha_id=caixinha.id,
            valor=td['valor'],
            estabelecimento=td['estabelecimento'],
            categoria=caixinha.nome,
            data_transacao=td['data']
        )

        # Salva o estabelecimento como conhecido
        db.salvar_estabelecimento_conhecido(user_id, td['estabelecimento'], caixinha.id)

        # Remove da pendência
        del pending_transactions[trans_id]

        # Atualiza dados da caixinha
        db.session.refresh(caixinha)
        perc = caixinha.percentual_usado
        emoji = "✅" if perc < 50 else "🟡" if perc < 70 else "⚠️" if perc < 90 else "🚨"

        # Monta mensagem diferente para áudio vs imagem vs texto
        tipo = td.get('tipo', 'imagem')
        if tipo in ['audio', 'texto']:
            metodo = td.get('metodo_pagamento')
            metodo_texto = f" ({metodo.upper()})" if metodo else ""
            descricao = td.get('descricao', '')
            icone = "🎤" if tipo == 'audio' else "✍️"

            msg = (
                f"{emoji} **Nova caixinha criada e gasto registrado!**\n\n"
                f"📦 Caixinha: **{caixinha.nome}**\n"
                f"🎯 Limite: R$ {caixinha.limite:.2f}\n\n"
                f"{icone} \"{descricao}\"\n\n"
                f"🏪 {td['estabelecimento']}\n"
                f"💰 R$ {td['valor']:.2f}{metodo_texto}\n\n"
                f"📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}\n"
                f"💵 Restante: R$ {caixinha.saldo_restante:.2f}\n"
                f"📈 {perc:.1f}% usado\n\n"
                f"💾 Da próxima vez será automático!"
            )
        else:
            msg = (
                f"{emoji} **Nova caixinha criada e gasto registrado!**\n\n"
                f"📦 Caixinha: **{caixinha.nome}**\n"
                f"🎯 Limite: R$ {caixinha.limite:.2f}\n\n"
                f"🏪 {td['estabelecimento']}\n"
                f"💰 R$ {td['valor']:.2f}\n\n"
                f"📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}\n"
                f"💵 Restante: R$ {caixinha.saldo_restante:.2f}\n"
                f"📈 {perc:.1f}% usado\n\n"
                f"💾 Da próxima vez será automático!"
            )

        msg += get_alerta_gasto(perc)
        await update.message.reply_text(msg)

    except ValueError:
        await update.message.reply_text(
            "❌ Limite inválido!\n\n"
            "Use: `nome limite`\n"
            "Exemplo: `Educação 500`"
        )
    except Exception as e:
        logger.error(f"Erro ao criar caixinha inline: {e}")
        await update.message.reply_text("❌ Erro ao criar caixinha. Tente novamente.")


async def processar_gasto_texto(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str):
    """Processa gasto descrito em texto livre"""
    user_id = update.effective_user.id

    caixinhas = db.listar_caixinhas(user_id)
    if not caixinhas:
        await update.message.reply_text(
            "❌ Você precisa criar pelo menos uma caixinha primeiro!\n\n"
            "Use: /criar <nome> <limite>"
        )
        return

    await update.message.reply_text("✍️ Processando seu gasto...")

    try:
        # Processa com Gemini
        logger.info(f"Processando texto com Gemini: {texto}")
        dados = audio_processor.processar_texto(texto)
        logger.info(f"Dados extraídos do texto: {dados}")

        if not dados or not dados['valor']:
            await update.message.reply_text(
                "❌ Não consegui entender o valor do gasto.\n\n"
                "Tente novamente mencionando o valor.\n"
                "Exemplos:\n"
                "• 'Gastei 100 reais no supermercado'\n"
                "• 'Paguei 50 de Uber'\n"
                "• 'Almocei no restaurante, 45 reais'"
            )
            return

        estabelecimento = dados['estabelecimento'].upper()

        # Verifica se estabelecimento já é conhecido (mas não genéricos)
        estab_conhecido = None
        estabelecimentos_genericos = ["NÃO IDENTIFICADO", "NÃO ESPECIFICADO"]
        if estabelecimento not in estabelecimentos_genericos:
            estab_conhecido = db.buscar_estabelecimento_conhecido(user_id, estabelecimento)

        if estab_conhecido:
            # Estabelecimento conhecido - registra direto
            caixinha = db.session.get(Caixinha, estab_conhecido.caixinha_id)

            db.adicionar_transacao(
                user_id=user_id,
                caixinha_id=caixinha.id,
                valor=dados['valor'],
                estabelecimento=estabelecimento,
                categoria=caixinha.nome,
                data_transacao=datetime.now()
            )

            db.session.refresh(caixinha)
            percentual = caixinha.percentual_usado
            emoji = "✅" if percentual < 50 else "🟡" if percentual < 70 else "⚠️" if percentual < 90 else "🚨"

            metodo = dados.get('metodo_pagamento')
            metodo_texto = f" ({metodo.upper()})" if metodo else ""

            msg = f"""
{emoji} **Gasto registrado via texto!{metodo_texto}**

✍️ "{dados['descricao']}"

🏪 {estabelecimento}
💰 R$ {dados['valor']:.2f}
📅 {datetime.now().strftime('%d/%m/%Y')}

📦 {caixinha.nome}
📊 R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}
💵 Restante: R$ {caixinha.saldo_restante:.2f}
📈 {percentual:.1f}% usado
"""
            msg += get_alerta_gasto(percentual)
            await update.message.reply_text(msg)

        else:
            # Estabelecimento novo - pede confirmação
            categoria_sugerida = dados['categoria_sugerida']
            caixinha_sugerida = db.buscar_caixinha_por_categoria(user_id, categoria_sugerida)

            if not caixinha_sugerida:
                nomes = [c.nome for c in caixinhas]
                cat = processor.categorizar_estabelecimento(estabelecimento, nomes)
                if cat:
                    caixinha_sugerida = db.buscar_caixinha_por_categoria(user_id, cat)

            if not caixinha_sugerida:
                caixinha_sugerida = caixinhas[0]

            # Gera ID único para esta transação pendente
            import uuid
            trans_id = str(uuid.uuid4())[:8]

            # Armazena dados temporariamente
            metodo = dados.get('metodo_pagamento')
            pending_transactions[trans_id] = {
                'user_id': user_id,
                'valor': dados['valor'],
                'estabelecimento': estabelecimento,
                'data': datetime.now(),
                'descricao': dados['descricao'],
                'metodo_pagamento': metodo,
                'tipo': 'texto'  # Marca como texto
            }

            # Monta mensagem com botões
            metodo_texto = f"\n💳 Forma: {metodo.upper()}" if metodo else ""

            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirmar", callback_data=f"confirm_{trans_id}_{caixinha_sugerida.id}"),
                    InlineKeyboardButton("❌ Mudar categoria", callback_data=f"change_{trans_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            msg = f"""
🆕 **Novo gasto via texto!**

✍️ "{dados['descricao']}"

🏪 {estabelecimento}
💰 R$ {dados['valor']:.2f}{metodo_texto}
📦 Categoria sugerida: **{caixinha_sugerida.nome}**

A categoria está correta?
"""
            await update.message.reply_text(msg, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Erro ao processar texto: {e}")
        await update.message.reply_text(
            "❌ Erro ao processar o texto. Tente novamente.\n\n"
            "Dica: Mencione o valor e onde gastou de forma clara."
        )


async def processar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de texto (para criar caixinha durante registro OU registrar gasto por texto)"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        return

    texto = update.message.text.strip()

    # Verifica se há alguma transação pendente esperando criar caixinha
    trans_id = None
    for tid, tdata in pending_transactions.items():
        if tdata.get('awaiting_new_caixinha') and tdata['user_id'] == user_id:
            trans_id = tid
            break

    # Se está esperando criar caixinha, processa criação
    if trans_id:
        await processar_criar_caixinha_inline(update, context, trans_id, texto)
        return

    # Caso contrário, tenta processar como gasto em texto livre
    await processar_gasto_texto(update, context, texto)


async def testar_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /testar_reset para simular reset automático"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    dia_fechamento = db.obter_dia_fechamento(user_id)

    if not dia_fechamento:
        await update.message.reply_text(
            "❌ Você precisa configurar o dia de fechamento primeiro!\n\n"
            "Use: /fechamento <dia>"
        )
        return

    # Mostra os gastos atuais antes do reset
    caixinhas = db.listar_caixinhas(user_id)

    if not caixinhas:
        await update.message.reply_text("❌ Você não tem caixinhas criadas!")
        return

    msg_antes = "📊 **Gastos ANTES do reset:**\n\n"
    for c in caixinhas:
        msg_antes += f"📦 {c.nome}: R$ {c.gasto_atual:.2f} / R$ {c.limite:.2f}\n"

    await update.message.reply_text(msg_antes)

    # Executa o reset
    num_caixinhas = db.resetar_gastos_mensais(user_id)

    # Atualiza as caixinhas
    caixinhas = db.listar_caixinhas(user_id)

    msg_depois = (
        f"🔄 **SIMULAÇÃO DE RESET EXECUTADA!**\n\n"
        f"✅ {num_caixinhas} caixinha(s) resetada(s)\n\n"
        f"📊 **Gastos DEPOIS do reset:**\n\n"
    )

    for c in caixinhas:
        msg_depois += f"📦 {c.nome}: R$ {c.gasto_atual:.2f} / R$ {c.limite:.2f}\n"

    msg_depois += (
        f"\n💡 **Isso é exatamente o que vai acontecer automaticamente "
        f"todo dia {dia_fechamento + 1 if dia_fechamento < 28 else 1} às 00:10!**"
    )

    await update.message.reply_text(msg_depois)


async def testar_relatorio_fechamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /testar_relatorio para simular relatório de fechamento"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    dia_fechamento = db.obter_dia_fechamento(user_id)

    if not dia_fechamento:
        await update.message.reply_text(
            "❌ Você precisa configurar o dia de fechamento primeiro!\n\n"
            "Use: /fechamento <dia>"
        )
        return

    # Gera o relatório
    rel = db.get_relatorio_mensal(user_id)
    hoje = datetime.now()
    mes_nome = hoje.strftime("%B/%Y")

    if not rel['caixinhas']:
        await update.message.reply_text("❌ Você não tem caixinhas criadas!")
        return

    # Monta mensagem do relatório
    mensagem = f"📊 **SIMULAÇÃO - Relatório de Fechamento - {mes_nome}**\n\n"
    mensagem += f"🔔 Seu cartão fecha todo dia {dia_fechamento}!\n\n"
    mensagem += "💰 **Resumo por Caixinha:**\n\n"

    for c in rel['caixinhas']:
        perc = c.percentual_usado
        emoji = "✅" if perc < 50 else "🟡" if perc < 80 else "⚠️" if perc < 90 else "🚨"

        mensagem += (
            f"{emoji} **{c.nome}**\n"
            f"   💰 R$ {c.gasto_atual:.2f} / R$ {c.limite:.2f}\n"
            f"   📊 {perc:.1f}% usado\n"
            f"   💵 Restante: R$ {c.saldo_restante:.2f}\n\n"
        )

    # Totais
    perc_total = (rel['total_gasto'] / rel['total_limite'] * 100) if rel['total_limite'] > 0 else 0

    mensagem += "📈 **Total Geral:**\n"
    mensagem += f"💰 Gasto: R$ {rel['total_gasto']:.2f}\n"
    mensagem += f"🎯 Limite: R$ {rel['total_limite']:.2f}\n"
    mensagem += f"💵 Disponível: R$ {rel['total_disponivel']:.2f}\n"
    mensagem += f"📊 {perc_total:.1f}% usado\n\n"

    mensagem += f"📝 Total de transações: {rel['num_transacoes']}\n\n"

    # Alerta sobre reset
    dia_reset = dia_fechamento + 1 if dia_fechamento < 28 else 1
    mensagem += (
        f"💡 **Esse relatório será enviado automaticamente todo dia {dia_fechamento} às 22h!**\n"
        f"🔄 E no dia {dia_reset} às 00:10 os gastos serão resetados."
    )

    await update.message.reply_text(mensagem)


async def resetar_tudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /resetar_tudo - Apaga TODOS os dados do usuário (com confirmação)"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    # Verifica se o usuário passou a confirmação
    if len(context.args) == 0 or context.args[0].upper() != "CONFIRMO":
        await update.message.reply_text(
            "⚠️ **ATENÇÃO: Este comando é IRREVERSÍVEL!**\n\n"
            "Este comando vai **DELETAR TUDO**:\n"
            "• ❌ Todas as suas caixinhas\n"
            "• ❌ Todas as transações\n"
            "• ❌ Todo o histórico\n"
            "• ❌ Estabelecimentos memorizados\n"
            "• ❌ Configuração de fechamento\n\n"
            "Você voltará ao **estado inicial**, como se nunca tivesse usado o bot.\n\n"
            "💡 Para confirmar, digite:\n"
            "`/resetar_tudo CONFIRMO`\n\n"
            "⚠️ **CUIDADO:** Não há como desfazer esta ação!"
        )
        return

    # Executa o reset
    await update.message.reply_text("🔄 Deletando todos os seus dados...")

    sucesso = db.resetar_tudo_usuario(user_id)

    if sucesso:
        await update.message.reply_text(
            "✅ **Tudo foi resetado com sucesso!**\n\n"
            "Você voltou ao início! 🎉\n\n"
            "Para começar novamente:\n"
            "1️⃣ `/criar <nome> <limite>` - Criar sua primeira caixinha\n"
            "2️⃣ `/fechamento <dia>` - Definir dia de fechamento do cartão\n"
            "3️⃣ Enviar fotos, áudios ou textos de gastos!\n\n"
            "Digite /ajuda para ver todos os comandos."
        )
    else:
        await update.message.reply_text(
            "❌ Erro ao resetar os dados.\n\n"
            "Tente novamente ou entre em contato com o suporte."
        )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ajuda"""
    await start(update, context)


def main():
    """Inicia o bot"""
    # Auto-importa dados se existir backup
    import os.path
    if os.path.exists('backup_dados.json'):
        logger.info("Backup encontrado! Importando dados...")
        try:
            from import_data import import_data
            import_data()
            # Renomeia para não importar de novo
            os.rename('backup_dados.json', 'backup_dados.json.imported')
            logger.info("Dados importados com sucesso!")
        except Exception as e:
            logger.error(f"Erro ao importar dados: {e}")

    token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not token:
        logger.error("Token não encontrado!")
        return

    # Desabilita JobQueue temporariamente para evitar erro de weak reference
    application = Application.builder().token(token).job_queue(None).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ajuda", ajuda))
    application.add_handler(CommandHandler("criar", criar_caixinha))
    application.add_handler(CommandHandler("fechamento", definir_fechamento))
    application.add_handler(CommandHandler("testar_reset", testar_reset))
    application.add_handler(CommandHandler("testar_relatorio", testar_relatorio_fechamento))
    application.add_handler(CommandHandler("caixinhas", listar_caixinhas))
    application.add_handler(CommandHandler("recentes", recentes))
    application.add_handler(CommandHandler("historico", historico_consolidado))
    application.add_handler(CommandHandler("relatorio", relatorio))
    application.add_handler(CommandHandler("resetar_tudo", resetar_tudo))
    application.add_handler(MessageHandler(filters.PHOTO, processar_imagem))
    application.add_handler(MessageHandler(filters.VOICE, processar_audio))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_texto))
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Scheduler V3 - Reset automático baseado no dia de fechamento
    scheduler = BotScheduler(db, application)
    scheduler.iniciar()

    logger.info("Bot V3 iniciado com processamento de imagem, audio e reset automático!")

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        scheduler.parar()


if __name__ == '__main__':
    main()
