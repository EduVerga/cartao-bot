"""
Sistema de lembretes para gastos recorrentes
"""
from datetime import datetime, timedelta
from database import Database
import logging

logger = logging.getLogger(__name__)


class LembretesRecorrentes:
    """Gerencia lembretes de vencimento de gastos recorrentes"""

    def __init__(self, db: Database):
        self.db = db

    def calcular_dias_ate_vencimento(self, dia_vencimento: int) -> int:
        """Calcula quantos dias faltam até o vencimento"""
        hoje = datetime.now()
        dia_atual = hoje.day
        mes_atual = hoje.month
        ano_atual = hoje.year

        # Se o vencimento já passou este mês
        if dia_atual > dia_vencimento:
            # Calcula para o próximo mês
            if mes_atual == 12:
                mes_vencimento = 1
                ano_vencimento = ano_atual + 1
            else:
                mes_vencimento = mes_atual + 1
                ano_vencimento = ano_atual
        else:
            mes_vencimento = mes_atual
            ano_vencimento = ano_atual

        data_vencimento = datetime(ano_vencimento, mes_vencimento, dia_vencimento)
        dias_faltando = (data_vencimento - hoje).days

        return dias_faltando

    def deve_enviar_lembrete(self, pagamento, dias_ate_vencimento: int) -> bool:
        """
        Decide se deve enviar um lembrete baseado em:
        - Dias até o vencimento
        - Último lembrete enviado
        - Status de pagamento
        """
        # Já foi pago, não envia lembrete
        if pagamento.pago:
            return False

        # Hoje é o dia do vencimento - SEMPRE envia
        if dias_ate_vencimento == 0:
            return True

        # Entre 1 e 5 dias antes - envia 1 vez por dia
        if 1 <= dias_ate_vencimento <= 5:
            if not pagamento.ultimo_lembrete:
                return True

            # Verifica se já passou 1 dia desde o último lembrete
            dias_desde_ultimo = (datetime.now() - pagamento.ultimo_lembrete).days
            return dias_desde_ultimo >= 1

        return False

    def gerar_mensagem_lembrete(self, gasto, pagamento, dias_ate_vencimento: int) -> str:
        """Gera a mensagem de lembrete apropriada"""
        from datetime import datetime

        mes_atual = datetime.now().month
        data_vencimento = f"{gasto.dia_vencimento}/{mes_atual:02d}"

        # Mensagem crítica no dia do vencimento
        if dias_ate_vencimento == 0:
            msg = f"🚨 **VENCIMENTO HOJE - {gasto.descricao}**\n\n"
            msg += f"⏰ **Hoje é o último dia para o pagamento dessa conta!**\n"
            msg += f"📅 Vencimento: {data_vencimento}\n\n"

            if gasto.valor_variavel:
                if pagamento.valor:
                    msg += f"💰 Valor: R$ {pagamento.valor:.2f}\n"
                else:
                    msg += f"⚠️ **ATENÇÃO: Você ainda não definiu o valor deste mês!**\n"
                    msg += f"Use: /valor_recorrente {gasto.descricao} <valor>\n"
            else:
                msg += f"💰 Valor: R$ {gasto.valor_padrao:.2f}\n"

            msg += f"\n🔴 **Não deixe o boleto vencer!**\n"
            msg += f"Responda 'Pago' quando pagar."

        # Mensagem de alerta 1-5 dias antes
        else:
            if dias_ate_vencimento == 1:
                dias_texto = "**AMANHÃ**"
            else:
                dias_texto = f"em **{dias_ate_vencimento} dias**"

            msg = f"🔔 **Lembrete - {gasto.descricao}**\n\n"
            msg += f"📅 Vence {dias_texto} ({data_vencimento})\n\n"

            if gasto.valor_variavel:
                if pagamento.valor:
                    msg += f"💰 Valor: R$ {pagamento.valor:.2f}\n"
                else:
                    msg += f"⚠️ **Você ainda não definiu o valor para esse mês.**\n"
                    msg += f"Qual seria o valor desse boleto?\n\n"
                    msg += f"Use: /valor_recorrente {gasto.descricao} <valor>\n"
            else:
                msg += f"💰 Valor: R$ {gasto.valor_padrao:.2f}\n"

            msg += f"\nResponda 'Pago' quando pagar."

        return msg

    async def verificar_e_enviar_lembretes(self, application):
        """
        Verifica todos os usuários e envia lembretes necessários
        Deve ser chamado diariamente pelo scheduler
        """
        logger.info("Verificando lembretes de gastos recorrentes...")

        try:
            from database import GastoRecorrente

            # Busca todos os gastos recorrentes ativos
            gastos = self.db.session.query(GastoRecorrente).filter_by(ativo=1).all()

            usuarios_processados = set()

            for gasto in gastos:
                user_id = gasto.user_id

                # Evita processar o mesmo usuário múltiplas vezes
                if user_id in usuarios_processados:
                    continue

                # Busca todos os gastos do usuário
                gastos_usuario = self.db.listar_gastos_recorrentes(user_id, apenas_ativos=True)

                for g in gastos_usuario:
                    # Calcula dias até vencimento
                    dias_ate = self.calcular_dias_ate_vencimento(g.dia_vencimento)

                    # Pula se faltam mais de 5 dias ou já passou muito tempo
                    if dias_ate < 0 or dias_ate > 5:
                        continue

                    # Busca/cria pagamento do mês
                    pagamento = self.db.obter_ou_criar_pagamento_mes(g.id, user_id)

                    # Verifica se deve enviar lembrete
                    if self.deve_enviar_lembrete(pagamento, dias_ate):
                        # Gera mensagem
                        mensagem = self.gerar_mensagem_lembrete(g, pagamento, dias_ate)

                        # Envia lembrete
                        try:
                            await application.bot.send_message(chat_id=user_id, text=mensagem)
                            logger.info(f"Lembrete enviado para user {user_id}: {g.descricao} ({dias_ate} dias)")

                            # Atualiza último lembrete
                            self.db.atualizar_ultimo_lembrete(pagamento.id)

                        except Exception as e:
                            logger.error(f"Erro ao enviar lembrete para user {user_id}: {e}")

                usuarios_processados.add(user_id)

            logger.info(f"Verificação de lembretes concluída. {len(usuarios_processados)} usuários processados.")

        except Exception as e:
            logger.error(f"Erro ao verificar lembretes: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
