"""
Tarefas agendadas do bot (reset mensal e relatórios)
"""
from datetime import datetime, time
from telegram import Bot
from database import Database
import os
import logging

logger = logging.getLogger(__name__)


async def reset_mensal_automatico(context):
    """Reseta os gastos de todas as caixinhas no dia 1 de cada mês"""
    db = Database()
    bot = context.bot

    try:
        # Busca todos os usuários únicos (se tiver múltiplos usuários)
        from sqlalchemy import distinct
        user_ids = db.session.query(distinct(db.session.query('caixinhas').c.user_id)).all()

        for (user_id,) in user_ids:
            num_caixinhas = db.resetar_gastos_mensais(user_id)

            mensagem = f"""
🔄 **Reset Mensal Automático**

Novo mês começou! Seus gastos foram zerados.

📦 {num_caixinhas} caixinha(s) resetada(s)
💰 Seus limites foram mantidos

Bom controle financeiro! 💪
"""

            await bot.send_message(chat_id=user_id, text=mensagem)
            logger.info(f"Reset mensal executado para usuário {user_id}")

    except Exception as e:
        logger.error(f"Erro no reset mensal: {e}")


async def enviar_relatorio_mensal(context):
    """Envia relatório mensal no último dia do mês às 22h"""
    db = Database()
    bot = context.bot

    try:
        from sqlalchemy import distinct
        user_ids = db.session.query(distinct(db.session.query('caixinhas').c.user_id)).all()

        for (user_id,) in user_ids:
            relatorio = db.get_relatorio_mensal(user_id)

            # Monta mensagem do relatório
            hoje = datetime.now()
            mes_nome = hoje.strftime("%B/%Y")

            mensagem = f"""
📊 **Relatório Mensal - {mes_nome}**

{'='*40}

📦 **Resumo das Caixinhas:**

"""

            for c in relatorio['caixinhas']:
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
• Total gasto: R$ {relatorio['total_gasto']:.2f}
• Total de limites: R$ {relatorio['total_limite']:.2f}
• Total disponível: R$ {relatorio['total_disponivel']:.2f}
• Número de transações: {relatorio['num_transacoes']}

{'='*40}

📈 **Análise:**
"""

            # Adiciona análise
            percentual_total = (relatorio['total_gasto'] / relatorio['total_limite'] * 100) if relatorio['total_limite'] > 0 else 0

            if percentual_total < 70:
                mensagem += "\n✅ Parabéns! Você manteve seus gastos sob controle este mês!"
            elif percentual_total < 90:
                mensagem += "\n⚠️ Atenção! Você usou a maior parte dos seus limites."
            else:
                mensagem += "\n🚨 Cuidado! Você ultrapassou ou chegou muito perto dos limites."

            mensagem += "\n\n🔄 Seus gastos serão zerados automaticamente no dia 1º!"

            await bot.send_message(chat_id=user_id, text=mensagem)
            logger.info(f"Relatório mensal enviado para usuário {user_id}")

    except Exception as e:
        logger.error(f"Erro ao enviar relatório mensal: {e}")
