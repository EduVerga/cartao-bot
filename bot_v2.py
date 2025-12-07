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
from alertas import AlertaInteligente

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
alerta_sistema = AlertaInteligente(db)

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

🎯 **Menu Interativo:**
/menu - Abrir menu com botões (recomendado!)

📦 **Gerenciar Caixinhas:**
/criar <nome> <limite> - Criar nova caixinha
  Exemplo: /criar Alimentação 1000
/caixinhas - Ver todas as suas caixinhas
/editar_limite <nome> <novo_limite> - Ajustar limite
  Exemplo: /editar_limite Mercado 1500
/renomear <nome_atual> > <novo_nome> - Renomear caixinha
  Exemplo: /renomear Mercado > Supermercado
/deletar <nome> - Deletar caixinha (cuidado!)
  Exemplo: /deletar Mercado

⚙️ **Configurações:**
/fechamento <dia> - Definir dia de fechamento do cartão
  Exemplo: /fechamento 20
  Use /fechamento sem número para ver o dia configurado

📊 **Relatórios do Cartão:**
/recentes - Ver últimas 10 transações do cartão
/historico <meses> - Histórico consolidado do cartão
  Exemplo: /historico 12 (últimos 12 meses)
  Opções: 6, 12, 18 ou 24 meses
/relatorio - Relatório do cartão de crédito do mês
/grafico - Gráficos visuais dos gastos do cartão

🔔 **Alertas e Previsões:**
/alertas - Verificar alertas de todas as caixinhas
/previsoes - Ver previsões de gastos e quando vai estourar
/dicas <nome> - Dicas personalizadas de economia
  Exemplo: /dicas Mercado

🔄 **Gastos Recorrentes (Contas Fixas):**
/criar_recorrente <desc> | <dia> - Criar recorrente
  Valor fixo: /criar_recorrente Netflix | 45.90 | 15
  Valor variável: /criar_recorrente Condominio | 10
/valor_recorrente <nome> <valor> - Definir valor do mês
  Exemplo: /valor_recorrente Condominio 650
/pagar_recorrente <nome> - Marcar conta como paga
  Exemplo: /pagar_recorrente Luz
/recorrentes - Ver todos os gastos recorrentes e status
/relatorio_recorrente - Relatório mensal de contas fixas
/historico_recorrente <meses> - Histórico de contas fixas
  Exemplo: /historico_recorrente 12 (últimos 12 meses)
/remover_recorrente <ID> - Remover um gasto recorrente
💡 Também pode responder "Pago" para marcar como pago

🔧 **Outros:**
/resetar_tudo CONFIRMO - Apagar TODOS os seus dados
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


async def editar_limite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /editar_limite <nome_caixinha> <novo_limite>"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Uso correto: /editar_limite <nome> <novo_limite>\n\n"
            "Exemplo: /editar_limite Mercado 1500"
        )
        return

    try:
        nome = ' '.join(context.args[:-1])
        novo_limite = float(context.args[-1])

        if novo_limite <= 0:
            await update.message.reply_text("❌ O limite deve ser maior que zero!")
            return

        # Busca a caixinha
        caixinha = db.buscar_caixinha_por_categoria(user_id, nome)

        if not caixinha:
            await update.message.reply_text(
                f"❌ Caixinha '{nome}' não encontrada.\n\n"
                f"Use /caixinhas para ver suas caixinhas."
            )
            return

        limite_antigo = caixinha.limite
        caixinha = db.editar_limite_caixinha(caixinha.id, novo_limite)

        await update.message.reply_text(
            f"✅ Limite atualizado com sucesso!\n\n"
            f"📦 **{caixinha.nome}**\n"
            f"💰 Limite anterior: R$ {limite_antigo:.2f}\n"
            f"💰 Novo limite: R$ {caixinha.limite:.2f}\n\n"
            f"📊 Gasto atual: R$ {caixinha.gasto_atual:.2f}\n"
            f"💵 Saldo restante: R$ {caixinha.saldo_restante:.2f}"
        )

    except ValueError:
        await update.message.reply_text("❌ O novo limite deve ser um número válido!")
    except Exception as e:
        logger.error(f"Erro ao editar limite: {e}")
        await update.message.reply_text("❌ Erro ao editar limite. Tente novamente.")


async def renomear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /renomear <nome_atual> > <novo_nome>"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if len(context.args) < 3 or '>' not in context.args:
        await update.message.reply_text(
            "❌ Uso correto: /renomear <nome_atual> > <novo_nome>\n\n"
            "Exemplo: /renomear Mercado > Supermercado"
        )
        return

    try:
        # Encontra o separador >
        separador_idx = context.args.index('>')

        nome_atual = ' '.join(context.args[:separador_idx])
        novo_nome = ' '.join(context.args[separador_idx + 1:])

        if not nome_atual or not novo_nome:
            await update.message.reply_text(
                "❌ Uso correto: /renomear <nome_atual> > <novo_nome>\n\n"
                "Exemplo: /renomear Mercado > Supermercado"
            )
            return

        # Busca a caixinha
        caixinha = db.buscar_caixinha_por_categoria(user_id, nome_atual)

        if not caixinha:
            await update.message.reply_text(
                f"❌ Caixinha '{nome_atual}' não encontrada.\n\n"
                f"Use /caixinhas para ver suas caixinhas."
            )
            return

        caixinha = db.renomear_caixinha(caixinha.id, novo_nome)

        await update.message.reply_text(
            f"✅ Caixinha renomeada com sucesso!\n\n"
            f"📦 Nome anterior: **{nome_atual}**\n"
            f"📦 Novo nome: **{caixinha.nome}**\n\n"
            f"💰 Limite: R$ {caixinha.limite:.2f}\n"
            f"📊 Gasto atual: R$ {caixinha.gasto_atual:.2f}"
        )

    except ValueError:
        await update.message.reply_text(
            "❌ Formato incorreto. Use:\n"
            "/renomear <nome_atual> > <novo_nome>"
        )
    except Exception as e:
        logger.error(f"Erro ao renomear caixinha: {e}")
        await update.message.reply_text("❌ Erro ao renomear caixinha. Tente novamente.")


async def deletar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /deletar <nome_caixinha>"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if len(context.args) == 0:
        await update.message.reply_text(
            "❌ Uso correto: /deletar <nome>\n\n"
            "Exemplo: /deletar Mercado\n\n"
            "⚠️ ATENÇÃO: Isso vai deletar a caixinha e TODAS as transações relacionadas!"
        )
        return

    try:
        nome = ' '.join(context.args)

        # Busca a caixinha
        caixinha = db.buscar_caixinha_por_categoria(user_id, nome)

        if not caixinha:
            await update.message.reply_text(
                f"❌ Caixinha '{nome}' não encontrada.\n\n"
                f"Use /caixinhas para ver suas caixinhas."
            )
            return

        # Salva info antes de deletar
        nome_deletado = caixinha.nome
        gasto = caixinha.gasto_atual
        limite = caixinha.limite

        # Deleta
        sucesso = db.deletar_caixinha(caixinha.id)

        if sucesso:
            await update.message.reply_text(
                f"✅ Caixinha deletada com sucesso!\n\n"
                f"📦 **{nome_deletado}** foi removida.\n"
                f"💰 Tinha R$ {gasto:.2f} de R$ {limite:.2f}\n\n"
                f"⚠️ Todas as transações relacionadas também foram deletadas."
            )
        else:
            await update.message.reply_text("❌ Erro ao deletar caixinha. Tente novamente.")

    except Exception as e:
        logger.error(f"Erro ao deletar caixinha: {e}")
        await update.message.reply_text("❌ Erro ao deletar caixinha. Tente novamente.")


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
    """Comando /relatorio - Relatório do cartão de crédito do mês atual"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    rel = db.get_relatorio_mensal(user_id)
    hoje = datetime.now()
    mes_nome = hoje.strftime("%B/%Y")

    mensagem = f"""
💳 **Relatório do Cartão de Crédito - {mes_nome}**

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

💵 **Totais do Cartão:**
• Total gasto: R$ {rel['total_gasto']:.2f}
• Total de limites: R$ {rel['total_limite']:.2f}
• Total disponível: R$ {rel['total_disponivel']:.2f}
• Número de transações: {rel['num_transacoes']}

💡 Para ver gastos recorrentes (contas fixas):
   /relatorio_recorrente
"""

    await update.message.reply_text(mensagem)


async def relatorio_recorrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /relatorio_recorrente - Relatório de gastos recorrentes do mês"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    from datetime import datetime
    hoje = datetime.now()
    mes_atual = hoje.month
    ano_atual = hoje.year
    mes_nome = hoje.strftime("%B/%Y")

    gastos = db.listar_gastos_recorrentes(user_id, apenas_ativos=True)

    if not gastos:
        await update.message.reply_text(
            "🔄 Você não tem gastos recorrentes cadastrados.\n\n"
            "Use /criar_recorrente para cadastrar contas fixas."
        )
        return

    mensagem = f"🔄 **Relatório de Gastos Recorrentes - {mes_nome}**\n\n"
    mensagem += f"{'='*40}\n\n"

    total_pago = 0
    total_pendente = 0
    total_sem_valor = 0
    num_pagos = 0
    num_pendentes = 0

    mensagem += "📋 **Status dos Pagamentos:**\n\n"

    for g in gastos:
        pagamento = db.obter_ou_criar_pagamento_mes(g.id, user_id, mes_atual, ano_atual)

        # Define valor e status
        if g.valor_variavel:
            if pagamento.valor:
                valor = pagamento.valor
                valor_texto = f"R$ {valor:.2f}"
            else:
                valor = 0
                valor_texto = "⚠️ Não definido"
                total_sem_valor += 1
        else:
            valor = g.valor_padrao
            valor_texto = f"R$ {valor:.2f}"

        # Status de pagamento
        if pagamento.pago:
            status_emoji = "✅"
            status_texto = "PAGO"
            total_pago += valor
            num_pagos += 1
        else:
            status_emoji = "⏳"
            status_texto = "Pendente"
            if valor > 0:
                total_pendente += valor
            num_pendentes += 1

        # Calcula dias até vencimento
        from lembretes_recorrentes import LembretesRecorrentes
        lembretes = LembretesRecorrentes(db)
        dias_ate = lembretes.calcular_dias_ate_vencimento(g.dia_vencimento)

        if dias_ate == 0:
            dias_texto = "🔴 VENCE HOJE"
        elif dias_ate < 0:
            dias_texto = f"🔴 Venceu há {abs(dias_ate)} dias"
        elif dias_ate <= 3:
            dias_texto = f"⚠️ {dias_ate} dias"
        else:
            dias_texto = f"{dias_ate} dias"

        mensagem += (
            f"{status_emoji} **{g.descricao}**\n"
            f"   💰 {valor_texto}\n"
            f"   📅 Dia {g.dia_vencimento}/{mes_atual:02d} ({dias_texto})\n"
            f"   {status_texto}\n\n"
        )

    mensagem += f"{'='*40}\n\n"
    mensagem += "💵 **Totais do Mês:**\n"
    mensagem += f"✅ Já pago: R$ {total_pago:.2f} ({num_pagos} conta(s))\n"
    mensagem += f"⏳ Pendente: R$ {total_pendente:.2f} ({num_pendentes} conta(s))\n"
    mensagem += f"📊 Total: R$ {total_pago + total_pendente:.2f}\n"

    if total_sem_valor > 0:
        mensagem += f"\n⚠️ {total_sem_valor} conta(s) sem valor definido\n"
        mensagem += "Use /valor_recorrente <nome> <valor>"

    await update.message.reply_text(mensagem)


async def historico_recorrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /historico_recorrente <meses> - Histórico de gastos recorrentes"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    # Define número de meses (padrão 6)
    if context.args and context.args[0].isdigit():
        num_meses = int(context.args[0])
        if num_meses not in [3, 6, 12, 24]:
            await update.message.reply_text(
                "❌ Use 3, 6, 12 ou 24 meses.\n\n"
                "Exemplo: /historico_recorrente 12"
            )
            return
    else:
        num_meses = 6

    gastos = db.listar_gastos_recorrentes(user_id, apenas_ativos=True)

    if not gastos:
        await update.message.reply_text(
            "🔄 Você não tem gastos recorrentes cadastrados.\n\n"
            "Use /criar_recorrente para cadastrar contas fixas."
        )
        return

    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    hoje = datetime.now()
    mensagem = f"📊 **Histórico de Gastos Recorrentes ({num_meses} meses)**\n\n"

    # Para cada gasto recorrente
    for gasto in gastos:
        mensagem += f"📌 **{gasto.descricao}**\n"

        total_gasto = 0
        meses_com_valor = 0

        # Percorre os últimos N meses
        for i in range(num_meses):
            data_mes = hoje - relativedelta(months=i)
            mes = data_mes.month
            ano = data_mes.year
            mes_nome = data_mes.strftime("%b/%y")

            # Busca pagamento do mês
            pagamento = db.obter_ou_criar_pagamento_mes(gasto.id, user_id, mes, ano)

            # Define valor
            if gasto.valor_variavel:
                valor = pagamento.valor if pagamento.valor else 0
            else:
                valor = gasto.valor_padrao

            # Status
            if pagamento.pago:
                status = "✅"
            elif valor > 0:
                status = "⏳"
            else:
                status = "⚠️"

            if valor > 0:
                total_gasto += valor
                meses_com_valor += 1
                mensagem += f"   {mes_nome}: R$ {valor:.2f} {status}\n"
            else:
                mensagem += f"   {mes_nome}: - {status}\n"

        # Média
        if meses_com_valor > 0:
            media = total_gasto / meses_com_valor
            mensagem += f"   💰 Total: R$ {total_gasto:.2f} | Média: R$ {media:.2f}\n"
        else:
            mensagem += f"   💰 Sem valores registrados\n"

        mensagem += "\n"

    # Total geral
    mensagem += f"{'='*40}\n\n"
    mensagem += "💡 **Legenda:**\n"
    mensagem += "✅ = Pago | ⏳ = Pendente | ⚠️ = Sem valor definido"

    await update.message.reply_text(mensagem)


async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /grafico - Gera gráficos visuais dos gastos"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    caixinhas = db.listar_caixinhas(user_id)

    if not caixinhas:
        await update.message.reply_text(
            "📊 Você ainda não tem caixinhas para gerar gráficos!\n\n"
            "Crie uma com: /criar <nome> <limite>"
        )
        return

    # Verifica se tem gastos registrados
    if all(c.gasto_atual == 0 for c in caixinhas):
        await update.message.reply_text(
            "📊 Você ainda não tem gastos registrados!\n\n"
            "Envie uma foto de comprovante, áudio ou texto para registrar gastos."
        )
        return

    await update.message.reply_text("📊 Gerando gráficos... aguarde um momento!")

    try:
        from graficos import gerar_grafico_percentual, gerar_grafico_barras, gerar_grafico_pizza
        from telegram import InputMediaPhoto

        # Gera os 3 gráficos
        graph_percentual = gerar_grafico_percentual(caixinhas)
        graph_barras = gerar_grafico_barras(caixinhas)
        graph_pizza = gerar_grafico_pizza(caixinhas)

        # Envia os gráficos em um álbum (mídia agrupada)
        await update.message.reply_media_group([
            InputMediaPhoto(graph_percentual, caption="📊 Percentual de Uso por Caixinha"),
            InputMediaPhoto(graph_barras, caption="📊 Gastos vs Limites"),
            InputMediaPhoto(graph_pizza, caption="📊 Distribuição de Gastos")
        ])

        # Mensagem de resumo
        total_gasto = sum(c.gasto_atual for c in caixinhas)
        total_limite = sum(c.limite for c in caixinhas)
        percentual_geral = (total_gasto / total_limite * 100) if total_limite > 0 else 0

        await update.message.reply_text(
            f"✅ Gráficos gerados com sucesso!\n\n"
            f"💰 **Resumo Geral:**\n"
            f"• Total gasto: R$ {total_gasto:.2f}\n"
            f"• Total limites: R$ {total_limite:.2f}\n"
            f"• Percentual usado: {percentual_geral:.1f}%\n"
            f"• Saldo disponível: R$ {total_limite - total_gasto:.2f}"
        )

    except Exception as e:
        logger.error(f"Erro ao gerar gráficos: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(
            "❌ Erro ao gerar gráficos. Tente novamente."
        )


async def alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /alertas - Verifica alertas de todas as caixinhas"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    caixinhas = db.listar_caixinhas(user_id)

    if not caixinhas:
        await update.message.reply_text(
            "📊 Você ainda não tem caixinhas para monitorar!\n\n"
            "Crie uma com: /criar <nome> <limite>"
        )
        return

    alertas_encontrados = alerta_sistema.verificar_alertas_usuario(user_id)

    if not alertas_encontrados:
        await update.message.reply_text(
            "✅ **Tudo sob controle!**\n\n"
            "Nenhuma caixinha requer atenção especial no momento.\n"
            "Continue assim! 💪"
        )
        return

    # Envia cada alerta individualmente
    await update.message.reply_text(f"🔔 **Encontrei {len(alertas_encontrados)} alerta(s):**\n")

    for alerta in alertas_encontrados:
        await update.message.reply_text(alerta)


async def previsoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /previsoes - Mostra previsões de todas as caixinhas"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    relatorio = alerta_sistema.gerar_relatorio_previsoes(user_id)
    await update.message.reply_text(relatorio)


async def dicas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /dicas <nome_caixinha> - Gera dicas de economia para uma caixinha"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Uso correto: /dicas <nome_caixinha>\n\n"
            "Exemplo: /dicas Mercado\n\n"
            "Ou use /alertas para ver dicas de todas as caixinhas que precisam de atenção."
        )
        return

    nome = ' '.join(context.args)
    caixinha = db.buscar_caixinha_por_categoria(user_id, nome)

    if not caixinha:
        await update.message.reply_text(
            f"❌ Caixinha '{nome}' não encontrada.\n\n"
            f"Use /caixinhas para ver suas caixinhas."
        )
        return

    # Gera alerta e dicas
    msg_alerta = alerta_sistema.gerar_mensagem_alerta(caixinha)
    msg_dicas = alerta_sistema.gerar_dicas_economia(caixinha)

    if msg_alerta:
        await update.message.reply_text(msg_alerta)

    if msg_dicas:
        await update.message.reply_text(msg_dicas)
    else:
        await update.message.reply_text(
            f"✅ **{caixinha.nome}** está em boa situação!\n\n"
            f"Continue controlando seus gastos. Você está no caminho certo! 💪"
        )


async def criar_recorrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /criar_recorrente <descricao> | <dia>
    OU /criar_recorrente <descricao> | <valor fixo> | <dia>"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Uso correto:\n\n"
            "**Valor fixo:**\n"
            "/criar_recorrente <desc> | <valor> | <dia>\n"
            "Exemplo: /criar_recorrente Netflix | 45.90 | 15\n\n"
            "**Valor variável:**\n"
            "/criar_recorrente <desc> | <dia>\n"
            "Exemplo: /criar_recorrente Condominio | 10\n"
            "(Use /valor_recorrente para definir o valor de cada mês)"
        )
        return

    try:
        # Junta todos os args e separa por pipe
        texto_completo = ' '.join(context.args)
        partes = [p.strip() for p in texto_completo.split('|')]

        if len(partes) not in [2, 3]:
            await update.message.reply_text(
                "❌ Use | para separar os campos!\n\n"
                "2 campos = valor variável\n"
                "3 campos = valor fixo"
            )
            return

        descricao = partes[0]

        # Se tem 3 partes, o valor é fixo
        if len(partes) == 3:
            valor_padrao = float(partes[1])
            dia = int(partes[2])

            if valor_padrao <= 0:
                await update.message.reply_text("❌ O valor deve ser maior que zero!")
                return
        else:
            # Se tem 2 partes, o valor é variável
            valor_padrao = None
            dia = int(partes[1])

        if dia < 1 or dia > 28:
            await update.message.reply_text("❌ O dia deve ser entre 1 e 28!")
            return

        # Cria gasto recorrente (SEM caixinha)
        gasto = db.criar_gasto_recorrente(
            user_id=user_id,
            descricao=descricao,
            dia_vencimento=dia,
            valor_padrao=valor_padrao
        )

        if gasto.valor_variavel:
            await update.message.reply_text(
                f"✅ **Gasto recorrente criado!**\n\n"
                f"🔄 {gasto.descricao}\n"
                f"💰 Valor VARIÁVEL (defina a cada mês)\n"
                f"📅 Vencimento: Todo dia {gasto.dia_vencimento}\n\n"
                f"Use /valor_recorrente {gasto.descricao} <valor> para definir o valor do mês."
            )
        else:
            await update.message.reply_text(
                f"✅ **Gasto recorrente criado!**\n\n"
                f"🔄 {gasto.descricao}\n"
                f"💰 R$ {gasto.valor_padrao:.2f}\n"
                f"📅 Vencimento: Todo dia {gasto.dia_vencimento}\n\n"
                f"Use /recorrentes para ver todos os seus gastos recorrentes."
            )

    except ValueError:
        await update.message.reply_text("❌ Valor ou dia inválidos! Use números válidos.")
    except Exception as e:
        logger.error(f"Erro ao criar gasto recorrente: {e}")
        await update.message.reply_text("❌ Erro ao criar gasto recorrente. Tente novamente.")


async def valor_recorrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /valor_recorrente <descricao> <valor>"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Uso correto: /valor_recorrente <descricao> <valor>\n\n"
            "Exemplo: /valor_recorrente Condominio 650"
        )
        return

    try:
        # Último arg é o valor, o resto é a descrição
        valor = float(context.args[-1])
        descricao = ' '.join(context.args[:-1])

        if valor <= 0:
            await update.message.reply_text("❌ O valor deve ser maior que zero!")
            return

        # Busca gasto recorrente
        gasto = db.buscar_gasto_recorrente_por_descricao(user_id, descricao)
        if not gasto:
            await update.message.reply_text(
                f"❌ Gasto recorrente '{descricao}' não encontrado.\n\n"
                f"Use /recorrentes para ver seus gastos recorrentes."
            )
            return

        # Define valor para o mês atual
        from datetime import datetime
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year

        pagamento = db.definir_valor_recorrente_mes(gasto.id, user_id, valor)

        await update.message.reply_text(
            f"✅ **Valor definido para {descricao}!**\n\n"
            f"💰 R$ {valor:.2f}\n"
            f"📅 Vencimento: Dia {gasto.dia_vencimento}/{mes_atual:02d}\n\n"
            f"Quando pagar, responda com: Pago"
        )

    except ValueError:
        await update.message.reply_text("❌ Valor inválido! Use um número válido.")
    except Exception as e:
        logger.error(f"Erro ao definir valor recorrente: {e}")
        await update.message.reply_text("❌ Erro ao definir valor. Tente novamente.")


async def pagar_recorrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /pagar_recorrente <descricao>"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Uso correto: /pagar_recorrente <descricao>\n\n"
            "Exemplo: /pagar_recorrente Luz\n"
            "Ou: /pagar_recorrente Condominio"
        )
        return

    try:
        descricao = ' '.join(context.args)

        # Busca gasto recorrente
        gasto = db.buscar_gasto_recorrente_por_descricao(user_id, descricao)
        if not gasto:
            await update.message.reply_text(
                f"❌ Gasto recorrente '{descricao}' não encontrado.\n\n"
                f"Use /recorrentes para ver seus gastos recorrentes."
            )
            return

        from datetime import datetime
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year

        # Busca/cria pagamento do mês
        pagamento = db.obter_ou_criar_pagamento_mes(gasto.id, user_id, mes_atual, ano_atual)

        # Verifica se já está pago
        if pagamento.pago:
            await update.message.reply_text(
                f"✅ **{gasto.descricao}** já está marcado como pago este mês!\n\n"
                f"📅 Pago em: {pagamento.data_pagamento.strftime('%d/%m/%Y')}"
            )
            return

        # Verifica se tem valor definido (para variáveis)
        if gasto.valor_variavel and not pagamento.valor:
            await update.message.reply_text(
                f"⚠️ **{gasto.descricao}** ainda não tem valor definido para este mês.\n\n"
                f"Defina o valor primeiro:\n"
                f"/valor_recorrente {gasto.descricao} <valor>\n\n"
                f"Ou responda com o valor agora:"
            )
            return

        # Marca como pago
        db.marcar_recorrente_como_pago(gasto.id, user_id, mes_atual, ano_atual)

        # Define valor para exibição
        if gasto.valor_variavel:
            valor_texto = f"R$ {pagamento.valor:.2f}"
        else:
            valor_texto = f"R$ {gasto.valor_padrao:.2f}"

        await update.message.reply_text(
            f"✅ **{gasto.descricao}** marcado como pago!\n\n"
            f"💰 {valor_texto}\n"
            f"📅 Mês: {mes_atual:02d}/{ano_atual}"
        )

    except Exception as e:
        logger.error(f"Erro ao marcar recorrente como pago: {e}")
        await update.message.reply_text("❌ Erro ao marcar como pago. Tente novamente.")


async def listar_recorrentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /recorrentes - Lista todos os gastos recorrentes"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    gastos = db.listar_gastos_recorrentes(user_id)

    if not gastos:
        await update.message.reply_text(
            "🔄 **Você não tem gastos recorrentes cadastrados.**\n\n"
            "Crie um com:\n"
            "/criar_recorrente <descricao> | <valor> | <dia>\n\n"
            "Exemplo:\n"
            "/criar_recorrente Netflix | 45.90 | 15"
        )
        return

    from datetime import datetime
    mes_atual = datetime.now().month
    ano_atual = datetime.now().year

    total_mensal = db.calcular_total_recorrentes_mes(user_id)

    msg = f"🔄 **Seus Gastos Recorrentes** (Total fixo: R$ {total_mensal:.2f}/mês)\n\n"

    for g in gastos:
        # Busca pagamento do mês atual
        pagamento = db.obter_ou_criar_pagamento_mes(g.id, user_id)

        # Define o valor a exibir
        if g.valor_variavel:
            if pagamento.valor:
                valor_texto = f"R$ {pagamento.valor:.2f} (definido)"
            else:
                valor_texto = "VARIÁVEL (não definido)"
        else:
            valor_texto = f"R$ {g.valor_padrao:.2f}"

        # Status de pagamento
        status = "✅ PAGO" if pagamento.pago else "⏳ Pendente"

        msg += (
            f"📌 **{g.descricao}**\n"
            f"   💰 {valor_texto}\n"
            f"   📅 Dia {g.dia_vencimento}/{mes_atual:02d}\n"
            f"   {status}\n"
            f"   ID: {g.id}\n\n"
        )

    msg += (
        f"💡 **Comandos:**\n"
        f"/valor_recorrente <nome> <valor> - Definir valor variável\n"
        f"/remover_recorrente <ID> - Remover recorrente\n"
        f"Responda 'Pago' quando pagar uma conta"
    )

    await update.message.reply_text(msg)


async def remover_recorrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /remover_recorrente <ID>"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Uso correto: /remover_recorrente <ID>\n\n"
            "Use /recorrentes para ver os IDs dos seus gastos recorrentes."
        )
        return

    try:
        gasto_id = int(context.args[0])
        gasto = db.buscar_gasto_recorrente_por_id(gasto_id)

        if not gasto or gasto.user_id != user_id:
            await update.message.reply_text(
                f"❌ Gasto recorrente não encontrado.\n\n"
                f"Use /recorrentes para ver seus gastos."
            )
            return

        descricao = gasto.descricao

        if db.deletar_gasto_recorrente(gasto_id):
            if gasto.valor_variavel:
                valor_texto = "Valor variável"
            else:
                valor_texto = f"R$ {gasto.valor_padrao:.2f}"

            await update.message.reply_text(
                f"✅ **Gasto recorrente removido!**\n\n"
                f"🔄 {descricao}\n"
                f"💰 {valor_texto}"
            )
        else:
            await update.message.reply_text("❌ Erro ao remover gasto recorrente.")

    except ValueError:
        await update.message.reply_text("❌ ID inválido! Use um número.")
    except Exception as e:
        logger.error(f"Erro ao remover gasto recorrente: {e}")
        await update.message.reply_text("❌ Erro ao remover gasto recorrente.")


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

        # Salva percentual anterior para verificar se deve enviar alerta
        percentual_anterior = caixinha.percentual_usado

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

        # Verifica se deve enviar alerta inteligente
        if alerta_sistema.deve_enviar_alerta_apos_gasto(caixinha, percentual_anterior):
            msg_alerta = alerta_sistema.gerar_mensagem_alerta(caixinha)
            if msg_alerta:
                await context.bot.send_message(chat_id=user_id, text=msg_alerta)

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

        # Salva percentual anterior para verificar se deve enviar alerta
        percentual_anterior = caixinha.percentual_usado

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

        # Verifica se deve enviar alerta inteligente
        if alerta_sistema.deve_enviar_alerta_apos_gasto(caixinha, percentual_anterior):
            msg_alerta = alerta_sistema.gerar_mensagem_alerta(caixinha)
            if msg_alerta:
                await context.bot.send_message(chat_id=user_id, text=msg_alerta)

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

    # ===== ESTADOS DE CONVERSA DO MENU INTERATIVO =====

    # Estado: Aguardando nome da caixinha
    if context.user_data.get('estado') == 'aguardando_nome_caixinha':
        context.user_data['nome_caixinha'] = texto
        context.user_data['estado'] = 'aguardando_limite_caixinha'
        await update.message.reply_text(
            f"✅ Nome: **{texto}**\n\n"
            f"Agora digite o limite mensal (em reais):\n\n"
            f"Exemplo: 1000"
        )
        return

    # Estado: Aguardando limite da caixinha
    if context.user_data.get('estado') == 'aguardando_limite_caixinha':
        try:
            limite = float(texto.replace(',', '.'))
            if limite <= 0:
                await update.message.reply_text("❌ O limite deve ser maior que zero. Tente novamente:")
                return

            nome = context.user_data.get('nome_caixinha')

            # Cria a caixinha
            nova = db.criar_caixinha(user_id, nome, limite)

            await update.message.reply_text(
                f"✅ **Caixinha criada com sucesso!**\n\n"
                f"📦 {nova.nome}\n"
                f"💰 Limite: R$ {nova.limite:.2f}\n\n"
                f"Use /menu para voltar ao menu principal."
            )

            # Limpa o estado
            context.user_data.clear()
            return

        except ValueError:
            await update.message.reply_text("❌ Valor inválido. Digite apenas números (ex: 1000):")
            return

    # Estado: Aguardando novo limite de caixinha
    if context.user_data.get('estado') == 'aguardando_novo_limite':
        try:
            novo_limite = float(texto.replace(',', '.'))
            if novo_limite <= 0:
                await update.message.reply_text("❌ O limite deve ser maior que zero. Tente novamente:")
                return

            caixinha_id = context.user_data.get('caixinha_id')
            caixinha = db.buscar_caixinha_por_id(caixinha_id)

            if not caixinha:
                await update.message.reply_text("❌ Caixinha não encontrada.")
                context.user_data.clear()
                return

            limite_antigo = caixinha.limite

            # Edita o limite
            db.editar_limite_caixinha(caixinha_id, novo_limite)

            await update.message.reply_text(
                f"✅ **Limite atualizado!**\n\n"
                f"📦 {caixinha.nome}\n"
                f"💰 Limite anterior: R$ {limite_antigo:.2f}\n"
                f"💰 Novo limite: R$ {novo_limite:.2f}\n\n"
                f"Use /menu para voltar ao menu principal."
            )

            # Limpa o estado
            context.user_data.clear()
            return

        except ValueError:
            await update.message.reply_text("❌ Valor inválido. Digite apenas números (ex: 1500):")
            return

    # Estado: Aguardando novo nome de caixinha
    if context.user_data.get('estado') == 'aguardando_novo_nome':
        caixinha_id = context.user_data.get('caixinha_id')
        caixinha = db.buscar_caixinha_por_id(caixinha_id)

        if not caixinha:
            await update.message.reply_text("❌ Caixinha não encontrada.")
            context.user_data.clear()
            return

        nome_antigo = caixinha.nome

        # Renomeia a caixinha
        db.renomear_caixinha(caixinha_id, texto)

        await update.message.reply_text(
            f"✅ **Caixinha renomeada!**\n\n"
            f"📦 Nome anterior: **{nome_antigo}**\n"
            f"📦 Novo nome: **{texto}**\n\n"
            f"Use /menu para voltar ao menu principal."
        )

        # Limpa o estado
        context.user_data.clear()
        return

    # Estado: Aguardando nome do gasto recorrente
    if context.user_data.get('estado') == 'aguardando_nome_recorrente':
        context.user_data['nome_recorrente'] = texto
        context.user_data['estado'] = 'aguardando_dia_recorrente'
        await update.message.reply_text(
            f"✅ Conta: **{texto}**\n\n"
            f"Qual o dia de vencimento? (1-28)\n\n"
            f"Exemplo: 10"
        )
        return

    # Estado: Aguardando dia de vencimento
    if context.user_data.get('estado') == 'aguardando_dia_recorrente':
        try:
            dia = int(texto)
            if dia < 1 or dia > 28:
                await update.message.reply_text("❌ O dia deve estar entre 1 e 28. Tente novamente:")
                return

            context.user_data['dia_recorrente'] = dia
            context.user_data['estado'] = 'aguardando_valor_fixo_recorrente'

            # Pergunta se tem valor fixo ou variável
            keyboard = [
                [InlineKeyboardButton("💰 Valor Fixo", callback_data="rec_tipo_fixo")],
                [InlineKeyboardButton("📊 Valor Variável", callback_data="rec_tipo_variavel")]
            ]
            await update.message.reply_text(
                f"✅ Vencimento: Dia **{dia}** de cada mês\n\n"
                f"Esta conta tem valor fixo ou variável?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        except ValueError:
            await update.message.reply_text("❌ Digite apenas o número do dia (1-28):")
            return

    # Estado: Aguardando valor fixo do recorrente
    if context.user_data.get('estado') == 'aguardando_valor_fixo_digitado':
        try:
            valor = float(texto.replace(',', '.'))
            if valor <= 0:
                await update.message.reply_text("❌ O valor deve ser maior que zero. Tente novamente:")
                return

            # Cria o gasto recorrente com valor fixo
            nome = context.user_data.get('nome_recorrente')
            dia = context.user_data.get('dia_recorrente')

            gasto = db.criar_gasto_recorrente(
                user_id=user_id,
                descricao=nome,
                dia_vencimento=dia,
                valor_padrao=valor
            )

            await update.message.reply_text(
                f"✅ **Gasto recorrente criado!**\n\n"
                f"🔄 {gasto.descricao}\n"
                f"💰 R$ {gasto.valor_padrao:.2f}\n"
                f"📅 Vencimento: Todo dia {gasto.dia_vencimento}\n\n"
                f"Use /menu para voltar ao menu principal."
            )

            # Limpa o estado
            context.user_data.clear()
            return

        except ValueError:
            await update.message.reply_text("❌ Valor inválido. Digite apenas números (ex: 45.90):")
            return

    # Estado: Aguardando dia de fechamento
    if context.user_data.get('estado') == 'aguardando_dia_fechamento':
        try:
            dia = int(texto)
            if dia < 1 or dia > 28:
                await update.message.reply_text("❌ O dia deve estar entre 1 e 28. Tente novamente:")
                return

            # Define o fechamento
            db.definir_fechamento(user_id, dia)

            await update.message.reply_text(
                f"✅ **Dia de fechamento definido!**\n\n"
                f"📅 Seu fechamento será todo dia **{dia}** de cada mês.\n\n"
                f"🔄 O relatório automático será enviado neste dia às 22h.\n"
                f"🔄 Os gastos serão resetados no dia seguinte às 00:10.\n\n"
                f"Use /menu para voltar ao menu principal."
            )

            # Limpa o estado
            context.user_data.clear()
            return

        except ValueError:
            await update.message.reply_text("❌ Digite apenas o número do dia (1-28):")
            return

    # Estado: Aguardando valor para gasto variável
    if context.user_data.get('estado') == 'aguardando_valor_recorrente':
        try:
            valor = float(texto.replace(',', '.'))
            if valor <= 0:
                await update.message.reply_text("❌ O valor deve ser maior que zero. Tente novamente:")
                return

            gasto_id = context.user_data.get('gasto_id')

            # Define o valor
            db.definir_valor_recorrente_mes(gasto_id, user_id, valor)

            gasto = db.buscar_gasto_recorrente_por_id(gasto_id)

            await update.message.reply_text(
                f"✅ **Valor definido!**\n\n"
                f"🔄 {gasto.descricao}\n"
                f"💰 R$ {valor:.2f}\n\n"
                f"Use /menu para voltar ao menu principal."
            )

            # Limpa o estado
            context.user_data.clear()
            return

        except ValueError:
            await update.message.reply_text("❌ Valor inválido. Digite apenas números (ex: 650.50):")
            return

    # ===== FIM DOS ESTADOS =====

    # Verifica se é a palavra "Pago" (marca gastos recorrentes como pagos)
    if texto.lower() in ['pago', 'paga']:
        pendentes = db.obter_pagamentos_pendentes(user_id)
        if not pendentes:
            await update.message.reply_text(
                "✅ Você não tem gastos recorrentes pendentes no momento!\n\n"
                "Use /recorrentes para ver todos os seus gastos."
            )
            return

        # Mostra lista de pendentes para escolher
        msg = "📋 **Qual conta você pagou?**\n\n"
        for i, (gasto, pagamento) in enumerate(pendentes, 1):
            if gasto.valor_variavel:
                valor_texto = f"R$ {pagamento.valor:.2f}" if pagamento.valor else "Valor não definido"
            else:
                valor_texto = f"R$ {gasto.valor_padrao:.2f}"
            msg += f"{i}. {gasto.descricao} - {valor_texto}\n"

        msg += "\n💡 Responda com o número da conta"

        # Armazena no pending_transactions para processar depois
        trans_id = f"pago_{user_id}_{int(update.message.date.timestamp())}"
        pending_transactions[trans_id] = {
            'user_id': user_id,
            'tipo': 'pago_recorrente',
            'pendentes': pendentes
        }

        await update.message.reply_text(msg)
        return

    # Verifica se é um número (resposta para marcar como pago)
    if texto.isdigit():
        # Busca se há transação pendente do tipo pago_recorrente
        trans_id = None
        for tid, tdata in pending_transactions.items():
            if tdata.get('tipo') == 'pago_recorrente' and tdata['user_id'] == user_id:
                trans_id = tid
                break

        if trans_id:
            try:
                numero = int(texto)
                pendentes = pending_transactions[trans_id]['pendentes']

                if numero < 1 or numero > len(pendentes):
                    await update.message.reply_text("❌ Número inválido. Tente novamente.")
                    return

                gasto, pagamento = pendentes[numero - 1]

                # Marca como pago
                db.marcar_recorrente_como_pago(gasto.id, user_id)

                if gasto.valor_variavel:
                    valor_texto = f"R$ {pagamento.valor:.2f}" if pagamento.valor else "Valor não definido"
                else:
                    valor_texto = f"R$ {gasto.valor_padrao:.2f}"

                await update.message.reply_text(
                    f"✅ **{gasto.descricao}** marcado como pago!\n\n"
                    f"💰 {valor_texto}"
                )

                del pending_transactions[trans_id]
                return

            except (ValueError, IndexError):
                pass

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


async def resetar_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reseta os gastos do mês manualmente"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
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
    num_resetadas = db.resetar_gastos_mensais(user_id)

    msg_depois = f"\n✅ **Reset concluído!**\n\n"
    msg_depois += f"🔄 {num_resetadas} caixinha(s) resetada(s).\n\n"
    msg_depois += "📊 **Gastos DEPOIS do reset:**\n\n"

    caixinhas = db.listar_caixinhas(user_id)
    for c in caixinhas:
        msg_depois += f"📦 {c.nome}: R$ {c.gasto_atual:.2f} / R$ {c.limite:.2f}\n"

    msg_depois += "\n💡 Os limites foram mantidos, apenas os gastos foram zerados."

    await update.message.reply_text(msg_depois)


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


async def testar_lembretes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /testar_lembretes para simular verificação de lembretes"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    await update.message.reply_text("🔄 Verificando lembretes de gastos recorrentes...")

    try:
        from lembretes_recorrentes import LembretesRecorrentes
        from datetime import datetime

        lembretes_sistema = LembretesRecorrentes(db)

        # Busca gastos recorrentes do usuário
        gastos = db.listar_gastos_recorrentes(user_id, apenas_ativos=True)

        if not gastos:
            await update.message.reply_text(
                "📋 Você não tem gastos recorrentes cadastrados.\n\n"
                "Use /criar_recorrente para adicionar contas fixas."
            )
            return

        lembretes_enviados = 0
        info_gastos = []

        for gasto in gastos:
            # Calcula dias até vencimento
            dias_ate = lembretes_sistema.calcular_dias_ate_vencimento(gasto.dia_vencimento)

            # Busca/cria pagamento do mês
            mes_atual = datetime.now().month
            ano_atual = datetime.now().year
            pagamento = db.obter_ou_criar_pagamento_mes(gasto.id, user_id, mes_atual, ano_atual)

            # Info para debug
            status_pago = "PAGO" if pagamento.pago else "PENDENTE"
            info_gastos.append(f"• {gasto.descricao}: {dias_ate} dias, {status_pago}")

            # Verifica se deve enviar lembrete
            if lembretes_sistema.deve_enviar_lembrete(pagamento, dias_ate):
                mensagem = lembretes_sistema.gerar_mensagem_lembrete(gasto, pagamento, dias_ate)
                await update.message.reply_text(mensagem)

                # Atualiza último lembrete
                db.atualizar_ultimo_lembrete(pagamento.id)
                lembretes_enviados += 1

        # Envia resumo
        resumo = f"📊 **Resumo da Verificação:**\n\n"
        resumo += f"✅ Lembretes enviados: {lembretes_enviados}\n"
        resumo += f"📋 Total de gastos recorrentes: {len(gastos)}\n\n"
        resumo += "**Detalhes:**\n" + "\n".join(info_gastos)

        if lembretes_enviados == 0:
            resumo += "\n\n💡 Nenhum lembrete precisa ser enviado agora."
            resumo += "\n\n**Lembretes são enviados quando:**"
            resumo += "\n• Faltam entre 1-5 dias para o vencimento"
            resumo += "\n• No dia do vencimento"
            resumo += "\n• Conta ainda não foi paga"

        await update.message.reply_text(resumo)

    except Exception as e:
        logger.error(f"Erro ao testar lembretes: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(
            "❌ Erro ao verificar lembretes. Veja os logs para mais detalhes."
        )


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


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /menu - Menu interativo principal"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    keyboard = [
        [InlineKeyboardButton("💳 Caixinhas (Cartão de Crédito)", callback_data="menu_caixinhas")],
        [InlineKeyboardButton("🔄 Gastos Recorrentes", callback_data="menu_recorrentes")],
        [InlineKeyboardButton("📊 Relatórios e Análises", callback_data="menu_relatorios")],
        [InlineKeyboardButton("⚙️ Configurações", callback_data="menu_config")],
        [InlineKeyboardButton("❓ Ajuda", callback_data="menu_ajuda")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎯 **Menu Principal**\n\n"
        "Escolha uma opção abaixo:",
        reply_markup=reply_markup
    )


async def debug_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /debug_db - Mostra informações sobre o banco de dados"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    try:
        import os

        # Verifica variável de ambiente
        db_path_env = os.getenv('DB_PATH', 'NÃO CONFIGURADO')

        # Pega o caminho real do banco
        db_path_real = db.engine.url.database

        # Verifica se o arquivo existe e tamanho
        if os.path.exists(db_path_real):
            tamanho = os.path.getsize(db_path_real)
            tamanho_kb = tamanho / 1024
            existe = f"✅ Existe ({tamanho_kb:.2f} KB)"
        else:
            existe = "❌ Não existe"

        # Verifica se diretório /app/data existe
        if os.path.exists('/app/data'):
            volume_existe = "✅ Sim"
            # Lista arquivos no volume
            try:
                arquivos = os.listdir('/app/data')
                arquivos_texto = "\n".join(arquivos) if arquivos else "Vazio"
            except:
                arquivos_texto = "Erro ao listar"
        else:
            volume_existe = "❌ Não"
            arquivos_texto = "N/A"

        # Conta registros
        from database import Caixinha, Transacao, GastoRecorrente
        num_caixinhas = db.session.query(Caixinha).filter_by(user_id=user_id).count()
        num_transacoes = db.session.query(Transacao).filter_by(user_id=user_id).count()
        num_recorrentes = db.session.query(GastoRecorrente).filter_by(user_id=user_id).count()

        msg = "🔍 **Debug - Banco de Dados**\n\n"
        msg += f"📁 **Variável DB_PATH:**\n`{db_path_env}`\n\n"
        msg += f"📂 **Caminho real do banco:**\n`{db_path_real}`\n\n"
        msg += f"📄 **Arquivo do banco:** {existe}\n\n"
        msg += f"💾 **Volume /app/data:** {volume_existe}\n\n"
        msg += f"📋 **Arquivos no volume:**\n{arquivos_texto}\n\n"
        msg += f"📊 **Dados do usuário:**\n"
        msg += f"• Caixinhas: {num_caixinhas}\n"
        msg += f"• Transações: {num_transacoes}\n"
        msg += f"• Recorrentes: {num_recorrentes}\n\n"
        msg += f"⚠️ **Diagnóstico:**\n"

        if db_path_env == 'NÃO CONFIGURADO':
            msg += "❌ Variável DB_PATH não configurada no Railway!\n"
            msg += "Configure: DB_PATH=/app/data/cartao.db"
        elif volume_existe == "❌ Não":
            msg += "❌ Volume /app/data não foi criado!\n"
            msg += "Verifique railway.toml"
        elif db_path_real != '/app/data/cartao.db':
            msg += f"⚠️ Banco deveria estar em /app/data/cartao.db\n"
            msg += f"Mas está em {db_path_real}"
        else:
            msg += "✅ Tudo configurado corretamente!"

        await update.message.reply_text(msg)

    except Exception as e:
        logger.error(f"Erro ao gerar debug: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ Erro: {e}")


async def backup_dados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /backup - Gera e envia arquivo de backup via Telegram"""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("🚫 Acesso não autorizado.")
        return

    await update.message.reply_text("🔄 Gerando backup... Aguarde.")

    try:
        import json
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.json"

        backup = {
            'data_backup': datetime.now().isoformat(),
            'caixinhas': [],
            'transacoes': [],
            'gastos_recorrentes': [],
            'pagamentos_recorrentes': [],
            'estabelecimentos': [],
            'configuracoes': []
        }

        # Exporta caixinhas
        from database import Caixinha, Transacao, GastoRecorrente, PagamentoRecorrente, EstabelecimentoConhecido, ConfiguracaoUsuario

        caixinhas = db.session.query(Caixinha).filter_by(user_id=user_id).all()
        for c in caixinhas:
            backup['caixinhas'].append({
                'id': c.id,
                'user_id': c.user_id,
                'nome': c.nome,
                'limite': float(c.limite),
                'gasto_atual': float(c.gasto_atual),
                'criado_em': c.criado_em.isoformat() if c.criado_em else None
            })

        # Exporta transações
        transacoes = db.session.query(Transacao).filter_by(user_id=user_id).all()
        for t in transacoes:
            backup['transacoes'].append({
                'id': t.id,
                'user_id': t.user_id,
                'caixinha_id': t.caixinha_id,
                'valor': float(t.valor),
                'estabelecimento': t.estabelecimento,
                'categoria': t.categoria,
                'data_transacao': t.data_transacao.isoformat() if t.data_transacao else None,
                'criado_em': t.criado_em.isoformat() if t.criado_em else None
            })

        # Exporta gastos recorrentes
        gastos_rec = db.session.query(GastoRecorrente).filter_by(user_id=user_id).all()
        for g in gastos_rec:
            backup['gastos_recorrentes'].append({
                'id': g.id,
                'user_id': g.user_id,
                'descricao': g.descricao,
                'valor_padrao': float(g.valor_padrao) if g.valor_padrao else None,
                'dia_vencimento': g.dia_vencimento,
                'caixinha_id': g.caixinha_id,
                'ativo': g.ativo,
                'criado_em': g.criado_em.isoformat() if g.criado_em else None
            })

        # Exporta pagamentos recorrentes
        pagamentos = db.session.query(PagamentoRecorrente).filter_by(user_id=user_id).all()
        for p in pagamentos:
            backup['pagamentos_recorrentes'].append({
                'id': p.id,
                'gasto_recorrente_id': p.gasto_recorrente_id,
                'user_id': p.user_id,
                'mes': p.mes,
                'ano': p.ano,
                'valor': float(p.valor) if p.valor else None,
                'pago': p.pago,
                'data_pagamento': p.data_pagamento.isoformat() if p.data_pagamento else None,
                'ultimo_lembrete': p.ultimo_lembrete.isoformat() if p.ultimo_lembrete else None
            })

        # Exporta estabelecimentos conhecidos
        estabelecimentos = db.session.query(EstabelecimentoConhecido).filter_by(user_id=user_id).all()
        for e in estabelecimentos:
            backup['estabelecimentos'].append({
                'id': e.id,
                'user_id': e.user_id,
                'nome_estabelecimento': e.nome_estabelecimento,
                'caixinha_id': e.caixinha_id
            })

        # Exporta configurações
        config = db.session.query(ConfiguracaoUsuario).filter_by(user_id=user_id).first()
        if config:
            backup['configuracoes'].append({
                'user_id': config.user_id,
                'dia_fechamento': config.dia_fechamento
            })

        # Salva em arquivo JSON
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(backup, f, indent=2, ensure_ascii=False)

        # Monta mensagem de resumo
        msg = "✅ **Backup gerado com sucesso!**\n\n"
        msg += f"📊 **Estatísticas:**\n"
        msg += f"   📦 Caixinhas: {len(backup['caixinhas'])}\n"
        msg += f"   💳 Transações: {len(backup['transacoes'])}\n"
        msg += f"   🔄 Gastos Recorrentes: {len(backup['gastos_recorrentes'])}\n"
        msg += f"   💰 Pagamentos: {len(backup['pagamentos_recorrentes'])}\n"
        msg += f"   🏪 Estabelecimentos: {len(backup['estabelecimentos'])}\n\n"
        msg += f"⚠️ **IMPORTANTE:** Salve este arquivo em local seguro!"

        # Envia o arquivo
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=msg
            )

        # Remove o arquivo temporário
        import os
        os.remove(filename)

    except Exception as e:
        logger.error(f"Erro ao gerar backup: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await update.message.reply_text("❌ Erro ao gerar backup. Tente novamente.")


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para callbacks do menu"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await query.edit_message_text("🚫 Acesso não autorizado.")
        return

    data = query.data

    # Menu Caixinhas
    if data == "menu_caixinhas":
        keyboard = [
            [InlineKeyboardButton("➕ Criar Nova Caixinha", callback_data="action_criar_caixinha")],
            [InlineKeyboardButton("📋 Ver Todas as Caixinhas", callback_data="action_listar_caixinhas")],
            [InlineKeyboardButton("✏️ Editar Limite", callback_data="action_editar_limite")],
            [InlineKeyboardButton("🏷️ Renomear Caixinha", callback_data="action_renomear_caixinha")],
            [InlineKeyboardButton("🗑️ Deletar Caixinha", callback_data="action_deletar_caixinha")],
            [InlineKeyboardButton("📊 Gráficos", callback_data="action_graficos")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_principal")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "💳 **Menu de Caixinhas (Cartão de Crédito)**\n\n"
            "Gerencie suas categorias de gastos do cartão:",
            reply_markup=reply_markup
        )

    # Menu Recorrentes
    elif data == "menu_recorrentes":
        keyboard = [
            [InlineKeyboardButton("➕ Criar Gasto Recorrente", callback_data="action_criar_recorrente")],
            [InlineKeyboardButton("📋 Ver Gastos Recorrentes", callback_data="action_listar_recorrentes")],
            [InlineKeyboardButton("💰 Definir Valor do Mês", callback_data="action_definir_valor")],
            [InlineKeyboardButton("✅ Marcar Como Pago", callback_data="action_pagar_recorrente")],
            [InlineKeyboardButton("🗑️ Remover Recorrente", callback_data="action_remover_recorrente")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_principal")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🔄 **Menu de Gastos Recorrentes**\n\n"
            "Gerencie suas contas fixas mensais:",
            reply_markup=reply_markup
        )

    # Menu Relatórios
    elif data == "menu_relatorios":
        keyboard = [
            [InlineKeyboardButton("📊 Relatório do Cartão", callback_data="action_relatorio_cartao")],
            [InlineKeyboardButton("🔄 Relatório de Recorrentes", callback_data="action_relatorio_recorrentes")],
            [InlineKeyboardButton("📈 Histórico de Recorrentes", callback_data="action_historico")],
            [InlineKeyboardButton("🔮 Previsões de Gastos", callback_data="action_previsoes")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_principal")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📊 **Menu de Relatórios e Análises**\n\n"
            "Visualize e analise seus gastos:",
            reply_markup=reply_markup
        )

    # Menu Configurações
    elif data == "menu_config":
        keyboard = [
            [InlineKeyboardButton("📅 Definir Dia de Fechamento", callback_data="action_definir_fechamento")],
            [InlineKeyboardButton("🔄 Resetar Gastos Agora", callback_data="action_resetar_mes")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_principal")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚙️ **Menu de Configurações**\n\n"
            "Ajuste as configurações do bot:",
            reply_markup=reply_markup
        )

    # Menu Ajuda
    elif data == "menu_ajuda":
        keyboard = [
            [InlineKeyboardButton("🔙 Voltar", callback_data="menu_principal")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❓ **Ajuda**\n\n"
            "📖 **Como usar o bot:**\n\n"
            "**Caixinhas (Cartão de Crédito):**\n"
            "• Envie foto de comprovante para registrar gasto\n"
            "• Ou envie mensagem de texto/áudio\n"
            "• Use /caixinhas para ver todas\n\n"
            "**Gastos Recorrentes:**\n"
            "• Crie contas fixas com dia de vencimento\n"
            "• Receba lembretes automáticos\n"
            "• Valores podem ser fixos ou variáveis\n\n"
            "**Comandos Úteis:**\n"
            "/menu - Este menu\n"
            "/ajuda - Ajuda completa\n"
            "/caixinhas - Ver caixinhas\n"
            "/recorrentes - Ver recorrentes\n"
            "/relatorio - Relatório do cartão\n"
            "/relatorio_recorrente - Relatório de contas",
            reply_markup=reply_markup
        )

    # Voltar ao menu principal
    elif data == "menu_principal":
        keyboard = [
            [InlineKeyboardButton("💳 Caixinhas (Cartão de Crédito)", callback_data="menu_caixinhas")],
            [InlineKeyboardButton("🔄 Gastos Recorrentes", callback_data="menu_recorrentes")],
            [InlineKeyboardButton("📊 Relatórios e Análises", callback_data="menu_relatorios")],
            [InlineKeyboardButton("⚙️ Configurações", callback_data="menu_config")],
            [InlineKeyboardButton("❓ Ajuda", callback_data="menu_ajuda")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎯 **Menu Principal**\n\n"
            "Escolha uma opção abaixo:",
            reply_markup=reply_markup
        )

    # Ações - Caixinhas
    elif data == "action_criar_caixinha":
        # Inicia o fluxo de criação de caixinha
        context.user_data['estado'] = 'aguardando_nome_caixinha'
        await query.edit_message_text(
            "➕ **Criar Nova Caixinha**\n\n"
            "Digite o nome da nova caixinha:\n\n"
            "Exemplo: Mercado, Alimentação, Transporte..."
        )

    elif data == "action_listar_caixinhas":
        # Chama diretamente a lógica de listar caixinhas
        caixinhas_list = db.listar_caixinhas(user_id)

        if not caixinhas_list:
            await query.edit_message_text(
                "📦 Você ainda não tem caixinhas cadastradas!\n\n"
                "Crie uma com: /criar <nome> <limite>\n"
                "Exemplo: /criar Alimentação 1000"
            )
            return

        msg = "📦 **Suas Caixinhas:**\n\n"

        for c in caixinhas_list:
            percentual = c.percentual_usado
            saldo = c.saldo_restante

            if percentual >= 100:
                emoji = "🔴"
            elif percentual >= 80:
                emoji = "🟠"
            elif percentual >= 50:
                emoji = "🟡"
            else:
                emoji = "🟢"

            msg += (
                f"{emoji} **{c.nome}**\n"
                f"   💰 Gasto: R$ {c.gasto_atual:.2f} / R$ {c.limite:.2f}\n"
                f"   📊 {percentual:.1f}% usado\n"
                f"   💵 Saldo: R$ {saldo:.2f}\n\n"
            )

        msg += (
            "💡 **Comandos:**\n"
            "/editar_limite <nome> <novo_limite>\n"
            "/renomear <nome> > <novo_nome>\n"
            "/deletar <nome>"
        )

        await query.edit_message_text(msg)

    elif data == "action_graficos":
        caixinhas_list = db.listar_caixinhas(user_id)

        if not caixinhas_list:
            await query.edit_message_text(
                "📊 Você ainda não tem caixinhas para gerar gráficos!\n\n"
                "Crie uma com: /criar <nome> <limite>"
            )
            return

        # Verifica se tem gastos registrados
        if all(c.gasto_atual == 0 for c in caixinhas_list):
            await query.edit_message_text(
                "📊 Você ainda não tem gastos registrados!\n\n"
                "Envie uma foto de comprovante, áudio ou texto para registrar gastos."
            )
            return

        await query.edit_message_text("📊 Gerando gráficos... aguarde um momento!")

        try:
            from graficos import gerar_grafico_percentual, gerar_grafico_barras, gerar_grafico_pizza
            from telegram import InputMediaPhoto

            # Gera os 3 gráficos
            graph_percentual = gerar_grafico_percentual(caixinhas_list)
            graph_barras = gerar_grafico_barras(caixinhas_list)
            graph_pizza = gerar_grafico_pizza(caixinhas_list)

            # Envia os gráficos em um álbum (mídia agrupada)
            await context.bot.send_media_group(
                chat_id=user_id,
                media=[
                    InputMediaPhoto(graph_percentual, caption="📊 Percentual de Uso por Caixinha"),
                    InputMediaPhoto(graph_barras, caption="📊 Gastos vs Limites"),
                    InputMediaPhoto(graph_pizza, caption="📊 Distribuição de Gastos")
                ]
            )

            # Mensagem de resumo
            total_gasto = sum(c.gasto_atual for c in caixinhas_list)
            total_limite = sum(c.limite for c in caixinhas_list)
            percentual_geral = (total_gasto / total_limite * 100) if total_limite > 0 else 0

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ Gráficos gerados com sucesso!\n\n"
                    f"💰 **Resumo Geral:**\n"
                    f"• Total gasto: R$ {total_gasto:.2f}\n"
                    f"• Total limites: R$ {total_limite:.2f}\n"
                    f"• Percentual usado: {percentual_geral:.1f}%\n"
                )
            )

            # Deleta a mensagem de "aguarde"
            await query.message.delete()

        except Exception as e:
            logger.error(f"Erro ao gerar gráficos: {e}")
            await query.edit_message_text(
                "❌ Erro ao gerar gráficos. Tente novamente mais tarde."
            )

    elif data == "action_editar_limite":
        # Lista caixinhas para escolher qual editar
        caixinhas_list = db.listar_caixinhas(user_id)

        if not caixinhas_list:
            await query.edit_message_text(
                "📦 Você ainda não tem caixinhas cadastradas!\n\n"
                "Crie uma primeiro."
            )
            return

        msg = "✏️ **Editar Limite**\n\n"
        msg += "Escolha qual caixinha você quer editar:\n\n"

        keyboard = []
        for c in caixinhas_list:
            keyboard.append([InlineKeyboardButton(
                f"{c.nome} (R$ {c.limite:.2f})",
                callback_data=f"editlim_{c.id}"
            )])

        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_caixinhas")])

        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("editlim_"):
        # Usuário selecionou uma caixinha para editar limite
        caixinha_id = int(data.split("_")[1])
        caixinha = db.buscar_caixinha_por_id(caixinha_id)

        if not caixinha:
            await query.edit_message_text("❌ Caixinha não encontrada.")
            return

        context.user_data['estado'] = 'aguardando_novo_limite'
        context.user_data['caixinha_id'] = caixinha_id

        await query.edit_message_text(
            f"✏️ **{caixinha.nome}**\n\n"
            f"Limite atual: R$ {caixinha.limite:.2f}\n\n"
            f"Digite o novo limite:\n\n"
            f"Exemplo: 1500"
        )

    elif data == "action_renomear_caixinha":
        # Lista caixinhas para escolher qual renomear
        caixinhas_list = db.listar_caixinhas(user_id)

        if not caixinhas_list:
            await query.edit_message_text(
                "📦 Você ainda não tem caixinhas cadastradas!\n\n"
                "Crie uma primeiro."
            )
            return

        msg = "🏷️ **Renomear Caixinha**\n\n"
        msg += "Escolha qual caixinha você quer renomear:\n\n"

        keyboard = []
        for c in caixinhas_list:
            keyboard.append([InlineKeyboardButton(
                f"{c.nome}",
                callback_data=f"rename_{c.id}"
            )])

        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_caixinhas")])

        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("rename_"):
        # Usuário selecionou uma caixinha para renomear
        caixinha_id = int(data.split("_")[1])
        caixinha = db.buscar_caixinha_por_id(caixinha_id)

        if not caixinha:
            await query.edit_message_text("❌ Caixinha não encontrada.")
            return

        context.user_data['estado'] = 'aguardando_novo_nome'
        context.user_data['caixinha_id'] = caixinha_id

        await query.edit_message_text(
            f"🏷️ **Renomear: {caixinha.nome}**\n\n"
            f"Digite o novo nome:\n\n"
            f"Exemplo: Supermercado, Delivery, etc."
        )

    elif data == "action_deletar_caixinha":
        # Lista caixinhas para escolher qual deletar
        caixinhas_list = db.listar_caixinhas(user_id)

        if not caixinhas_list:
            await query.edit_message_text(
                "📦 Você ainda não tem caixinhas cadastradas!\n\n"
                "Não há nada para deletar."
            )
            return

        msg = "🗑️ **Deletar Caixinha**\n\n"
        msg += "⚠️ **ATENÇÃO:** Esta ação não pode ser desfeita!\n\n"
        msg += "Escolha qual caixinha você quer deletar:\n\n"

        keyboard = []
        for c in caixinhas_list:
            keyboard.append([InlineKeyboardButton(
                f"🗑️ {c.nome} (R$ {c.gasto_atual:.2f} gastos)",
                callback_data=f"delcaixa_{c.id}"
            )])

        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_caixinhas")])

        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("delcaixa_"):
        # Usuário selecionou uma caixinha para deletar - pede confirmação
        try:
            caixinha_id = int(data.split("_")[1])
            logger.info(f"User {user_id} tentando deletar caixinha ID: {caixinha_id}")

            caixinha = db.buscar_caixinha_por_id(caixinha_id)

            if not caixinha:
                logger.error(f"Caixinha {caixinha_id} não encontrada")
                await query.edit_message_text("❌ Caixinha não encontrada.")
                return

            # Verifica se a caixinha pertence ao usuário
            if caixinha.user_id != user_id:
                logger.error(f"Caixinha {caixinha_id} não pertence ao user {user_id}")
                await query.edit_message_text("❌ Esta caixinha não pertence a você.")
                return

        except Exception as e:
            logger.error(f"Erro ao processar delcaixa: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await query.edit_message_text(f"❌ Erro: {str(e)}")
            return

        keyboard = [
            [InlineKeyboardButton("✅ Sim, deletar", callback_data=f"confirmdel_{caixinha_id}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_caixinhas")]
        ]

        await query.edit_message_text(
            f"🗑️ **Confirmar Exclusão**\n\n"
            f"Tem certeza que deseja deletar a caixinha?\n\n"
            f"📦 **{caixinha.nome}**\n"
            f"💰 Gasto atual: R$ {caixinha.gasto_atual:.2f}\n"
            f"🎯 Limite: R$ {caixinha.limite:.2f}\n\n"
            f"⚠️ Todos os gastos associados também serão removidos!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("confirmdel_"):
        # Confirmação de exclusão
        caixinha_id = int(data.split("_")[1])
        caixinha = db.buscar_caixinha_por_id(caixinha_id)

        if not caixinha:
            await query.edit_message_text("❌ Caixinha não encontrada.")
            return

        nome = caixinha.nome

        # Deleta a caixinha
        db.deletar_caixinha(caixinha_id)

        await query.edit_message_text(
            f"✅ **Caixinha Deletada!**\n\n"
            f"📦 **{nome}** foi removida com sucesso.\n\n"
            f"Use /menu para voltar ao menu principal."
        )

    # Ações - Recorrentes
    elif data == "action_criar_recorrente":
        # Inicia o fluxo de criação de gasto recorrente
        context.user_data['estado'] = 'aguardando_nome_recorrente'
        await query.edit_message_text(
            "➕ **Criar Gasto Recorrente**\n\n"
            "Digite o nome/descrição da conta:\n\n"
            "Exemplo: Netflix, Condomínio, Luz, Internet..."
        )

    elif data == "action_listar_recorrentes":
        # Chama diretamente a lógica de listar recorrentes
        gastos = db.listar_gastos_recorrentes(user_id)

        if not gastos:
            await query.edit_message_text(
                "🔄 **Você não tem gastos recorrentes cadastrados.**\n\n"
                "Crie um com:\n"
                "/criar_recorrente <descricao> | <valor> | <dia>\n\n"
                "Exemplo:\n"
                "/criar_recorrente Netflix | 45.90 | 15"
            )
            return

        from datetime import datetime
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year

        total_mensal = db.calcular_total_recorrentes_mes(user_id)

        msg = f"🔄 **Seus Gastos Recorrentes** (Total fixo: R$ {total_mensal:.2f}/mês)\n\n"

        for g in gastos:
            # Busca pagamento do mês atual
            pagamento = db.obter_ou_criar_pagamento_mes(g.id, user_id)

            # Define o valor a exibir
            if g.valor_variavel:
                if pagamento.valor:
                    valor_texto = f"R$ {pagamento.valor:.2f} (definido)"
                else:
                    valor_texto = "VARIÁVEL (não definido)"
            else:
                valor_texto = f"R$ {g.valor_padrao:.2f}"

            # Status de pagamento
            status = "✅ PAGO" if pagamento.pago else "⏳ Pendente"

            msg += (
                f"📌 **{g.descricao}**\n"
                f"   💰 {valor_texto}\n"
                f"   📅 Dia {g.dia_vencimento}/{mes_atual:02d}\n"
                f"   {status}\n"
                f"   ID: {g.id}\n\n"
            )

        msg += (
            f"💡 **Comandos:**\n"
            f"/valor_recorrente <nome> <valor> - Definir valor variável\n"
            f"/remover_recorrente <ID> - Remover recorrente\n"
            f"Responda 'Pago' quando pagar uma conta"
        )

        await query.edit_message_text(msg)

    elif data == "action_definir_valor":
        # Lista gastos variáveis pendentes
        gastos = db.listar_gastos_recorrentes(user_id)
        gastos_variaveis = [g for g in gastos if g.valor_variavel]

        if not gastos_variaveis:
            await query.edit_message_text(
                "💰 **Definir Valor do Mês**\n\n"
                "Você não tem gastos recorrentes com valor variável cadastrados."
            )
            return

        msg = "💰 **Definir Valor do Mês**\n\n"
        msg += "Escolha qual gasto você quer definir o valor:\n\n"

        keyboard = []
        for g in gastos_variaveis:
            keyboard.append([InlineKeyboardButton(
                f"{g.descricao}",
                callback_data=f"defvalor_{g.id}"
            )])

        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_recorrentes")])

        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("defvalor_"):
        # Usuário selecionou um gasto para definir valor
        gasto_id = int(data.split("_")[1])
        gasto = db.buscar_gasto_recorrente_por_id(gasto_id)

        if not gasto:
            await query.edit_message_text("❌ Gasto não encontrado.")
            return

        context.user_data['estado'] = 'aguardando_valor_recorrente'
        context.user_data['gasto_id'] = gasto_id

        await query.edit_message_text(
            f"💰 **{gasto.descricao}**\n\n"
            f"Digite o valor para este mês:\n\n"
            f"Exemplo: 650.50"
        )

    elif data == "action_pagar_recorrente":
        # Lista gastos pendentes
        from datetime import datetime
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year

        gastos = db.listar_gastos_recorrentes(user_id)
        gastos_pendentes = []

        for g in gastos:
            pagamento = db.obter_ou_criar_pagamento_mes(g.id, user_id, mes_atual, ano_atual)
            if not pagamento.pago:
                gastos_pendentes.append((g, pagamento))

        if not gastos_pendentes:
            await query.edit_message_text(
                "✅ **Marcar Como Pago**\n\n"
                "Todas as suas contas do mês já foram pagas! 🎉"
            )
            return

        msg = "✅ **Marcar Como Pago**\n\n"
        msg += "Escolha qual conta você pagou:\n\n"

        keyboard = []
        for g, p in gastos_pendentes:
            if g.valor_variavel and p.valor:
                valor_texto = f"R$ {p.valor:.2f}"
            elif g.valor_variavel:
                valor_texto = "⚠️ Sem valor"
            else:
                valor_texto = f"R$ {g.valor_padrao:.2f}"

            keyboard.append([InlineKeyboardButton(
                f"{g.descricao} - {valor_texto}",
                callback_data=f"pagar_{g.id}"
            )])

        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_recorrentes")])

        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("pagar_"):
        # Usuário marcou um gasto como pago
        gasto_id = int(data.split("_")[1])
        gasto = db.buscar_gasto_recorrente_por_id(gasto_id)

        if not gasto:
            await query.edit_message_text("❌ Gasto não encontrado.")
            return

        from datetime import datetime
        mes_atual = datetime.now().month
        ano_atual = datetime.now().year

        sucesso = db.marcar_recorrente_como_pago(gasto_id, user_id, mes_atual, ano_atual)

        if sucesso:
            await query.edit_message_text(
                f"✅ **Pagamento Registrado!**\n\n"
                f"**{gasto.descricao}** foi marcado como pago! 🎉"
            )
        else:
            await query.edit_message_text("❌ Erro ao marcar como pago.")

    elif data == "action_remover_recorrente":
        # Lista gastos recorrentes para escolher qual remover
        gastos = db.listar_gastos_recorrentes(user_id)

        if not gastos:
            await query.edit_message_text(
                "🔄 Você não tem gastos recorrentes cadastrados!\n\n"
                "Não há nada para remover."
            )
            return

        msg = "🗑️ **Remover Gasto Recorrente**\n\n"
        msg += "Escolha qual gasto você quer remover:\n\n"

        keyboard = []
        for g in gastos:
            valor_texto = f"R$ {g.valor_padrao:.2f}" if not g.valor_variavel else "Variável"
            keyboard.append([InlineKeyboardButton(
                f"🗑️ {g.descricao} ({valor_texto})",
                callback_data=f"delrec_{g.id}"
            )])

        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_recorrentes")])

        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("delrec_"):
        # Usuário selecionou um gasto recorrente para remover - pede confirmação
        gasto_id = int(data.split("_")[1])
        gasto = db.buscar_gasto_recorrente_por_id(gasto_id)

        if not gasto:
            await query.edit_message_text("❌ Gasto não encontrado.")
            return

        keyboard = [
            [InlineKeyboardButton("✅ Sim, remover", callback_data=f"confirmdelrec_{gasto_id}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_recorrentes")]
        ]

        valor_texto = f"R$ {gasto.valor_padrao:.2f}" if not gasto.valor_variavel else "Valor variável"

        await query.edit_message_text(
            f"🗑️ **Confirmar Remoção**\n\n"
            f"Tem certeza que deseja remover este gasto recorrente?\n\n"
            f"🔄 **{gasto.descricao}**\n"
            f"💰 {valor_texto}\n"
            f"📅 Vence dia {gasto.dia_vencimento}\n\n"
            f"⚠️ Histórico de pagamentos também será removido!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("confirmdelrec_"):
        # Confirmação de remoção
        gasto_id = int(data.split("_")[1])
        gasto = db.buscar_gasto_recorrente_por_id(gasto_id)

        if not gasto:
            await query.edit_message_text("❌ Gasto não encontrado.")
            return

        descricao = gasto.descricao

        # Desativa o gasto recorrente
        db.desativar_gasto_recorrente(gasto_id)

        await query.edit_message_text(
            f"✅ **Gasto Recorrente Removido!**\n\n"
            f"🔄 **{descricao}** foi removido com sucesso.\n\n"
            f"Use /menu para voltar ao menu principal."
        )

    # Callbacks para criação de recorrente - escolha de tipo
    elif data == "rec_tipo_fixo":
        context.user_data['estado'] = 'aguardando_valor_fixo_digitado'
        await query.edit_message_text(
            "💰 **Valor Fixo**\n\n"
            "Digite o valor mensal fixo:\n\n"
            "Exemplo: 45.90"
        )

    elif data == "rec_tipo_variavel":
        # Cria o gasto recorrente com valor variável
        nome = context.user_data.get('nome_recorrente')
        dia = context.user_data.get('dia_recorrente')

        gasto = db.criar_gasto_recorrente(
            user_id=user_id,
            descricao=nome,
            dia_vencimento=dia,
            valor_padrao=None  # Valor variável
        )

        await query.edit_message_text(
            f"✅ **Gasto recorrente criado!**\n\n"
            f"🔄 {gasto.descricao}\n"
            f"📊 Valor VARIÁVEL (defina a cada mês)\n"
            f"📅 Vencimento: Todo dia {gasto.dia_vencimento}\n\n"
            f"Use /menu para voltar ao menu principal ou\n"
            f"/valor_recorrente para definir o valor deste mês."
        )

        # Limpa o estado
        context.user_data.clear()

    # Ações - Relatórios
    elif data == "action_relatorio_cartao":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text="📊 Gerando relatório do cartão... aguarde!"
        )

        # Cria um objeto Update mínimo para chamar a função
        class FakeMessage:
            def __init__(self, chat_id):
                self.chat_id = chat_id
                self.message_id = 0

            async def reply_text(self, text, **kwargs):
                return await context.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

        class FakeUpdate:
            def __init__(self, user_id):
                self.effective_user = type('obj', (object,), {'id': user_id})()
                self.message = FakeMessage(user_id)

        fake_update = FakeUpdate(user_id)
        await relatorio(fake_update, context)

    elif data == "action_relatorio_recorrentes":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text="📊 Gerando relatório de recorrentes... aguarde!"
        )

        # Cria um objeto Update mínimo para chamar a função
        class FakeMessage:
            def __init__(self, chat_id):
                self.chat_id = chat_id
                self.message_id = 0

            async def reply_text(self, text, **kwargs):
                return await context.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

        class FakeUpdate:
            def __init__(self, user_id):
                self.effective_user = type('obj', (object,), {'id': user_id})()
                self.message = FakeMessage(user_id)

        fake_update = FakeUpdate(user_id)
        await relatorio_recorrente(fake_update, context)

    elif data == "action_historico":
        await query.edit_message_text(
            "📈 **Histórico de Recorrentes**\n\n"
            "Use o comando:\n"
            "/historico_recorrente <meses>\n\n"
            "Exemplo:\n"
            "/historico_recorrente 12\n"
            "(mostra últimos 12 meses)"
        )

    elif data == "action_previsoes":
        await query.message.delete()

        # Cria um objeto Update mínimo para chamar a função
        class FakeMessage:
            def __init__(self, chat_id):
                self.chat_id = chat_id
                self.message_id = 0

            async def reply_text(self, text, **kwargs):
                return await context.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

        class FakeUpdate:
            def __init__(self, user_id):
                self.effective_user = type('obj', (object,), {'id': user_id})()
                self.message = FakeMessage(user_id)

        fake_update = FakeUpdate(user_id)
        await previsoes(fake_update, context)

    # Ações - Configurações
    elif data == "action_definir_fechamento":
        # Inicia fluxo de definir fechamento
        context.user_data['estado'] = 'aguardando_dia_fechamento'

        # Busca fechamento atual
        config = db.buscar_configuracao_usuario(user_id)
        fechamento_atual = config.dia_fechamento if config else None

        msg = "📅 **Definir Dia de Fechamento**\n\n"
        if fechamento_atual:
            msg += f"Fechamento atual: Dia **{fechamento_atual}** de cada mês\n\n"

        msg += "Digite o novo dia de fechamento (1-28):\n\n"
        msg += "Exemplo: 10"

        await query.edit_message_text(msg)

    elif data == "action_resetar_mes":
        await query.message.delete()

        # Cria um objeto Update mínimo para chamar a função
        class FakeMessage:
            def __init__(self, chat_id):
                self.chat_id = chat_id
                self.message_id = 0

            async def reply_text(self, text, **kwargs):
                return await context.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

        class FakeUpdate:
            def __init__(self, user_id):
                self.effective_user = type('obj', (object,), {'id': user_id})()
                self.message = FakeMessage(user_id)

        fake_update = FakeUpdate(user_id)
        await resetar_mes(fake_update, context)


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
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("criar", criar_caixinha))
    application.add_handler(CommandHandler("fechamento", definir_fechamento))
    application.add_handler(CommandHandler("testar_reset", testar_reset))
    application.add_handler(CommandHandler("resetar_mes", resetar_mes))
    application.add_handler(CommandHandler("testar_relatorio", testar_relatorio_fechamento))
    application.add_handler(CommandHandler("testar_lembretes", testar_lembretes))
    application.add_handler(CommandHandler("caixinhas", listar_caixinhas))
    application.add_handler(CommandHandler("editar_limite", editar_limite))
    application.add_handler(CommandHandler("renomear", renomear))
    application.add_handler(CommandHandler("deletar", deletar))
    application.add_handler(CommandHandler("recentes", recentes))
    application.add_handler(CommandHandler("historico", historico_consolidado))
    application.add_handler(CommandHandler("relatorio", relatorio))
    application.add_handler(CommandHandler("relatorio_recorrente", relatorio_recorrente))
    application.add_handler(CommandHandler("grafico", grafico))
    application.add_handler(CommandHandler("alertas", alertas))
    application.add_handler(CommandHandler("previsoes", previsoes))
    application.add_handler(CommandHandler("dicas", dicas))
    application.add_handler(CommandHandler("criar_recorrente", criar_recorrente))
    application.add_handler(CommandHandler("valor_recorrente", valor_recorrente))
    application.add_handler(CommandHandler("pagar_recorrente", pagar_recorrente))
    application.add_handler(CommandHandler("recorrentes", listar_recorrentes))
    application.add_handler(CommandHandler("historico_recorrente", historico_recorrente))
    application.add_handler(CommandHandler("remover_recorrente", remover_recorrente))
    application.add_handler(CommandHandler("resetar_tudo", resetar_tudo))
    application.add_handler(CommandHandler("backup", backup_dados))
    application.add_handler(CommandHandler("debug_db", debug_db))
    application.add_handler(MessageHandler(filters.PHOTO, processar_imagem))
    application.add_handler(MessageHandler(filters.VOICE, processar_audio))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_texto))

    # Callback handlers - ordem importa! Específicos antes dos genéricos
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^(menu_|action_|defvalor_|pagar_|rec_tipo_|editlim_|rename_|delcaixa_|confirmdel_|delrec_|confirmdelrec_)"))
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
