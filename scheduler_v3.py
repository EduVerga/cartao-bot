"""
Scheduler para tarefas automáticas do bot V3
Usa APScheduler para gerenciar reset automático baseado no dia de fechamento
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from database import Database

logger = logging.getLogger(__name__)


class BotScheduler:
    """Gerenciador de tarefas agendadas do bot"""

    def __init__(self, db: Database, telegram_app):
        self.db = db
        self.telegram_app = telegram_app
        self.scheduler = BackgroundScheduler()

        # Importa sistema de lembretes
        from lembretes_recorrentes import LembretesRecorrentes
        self.lembretes = LembretesRecorrentes(db)

    def verificar_reset_automatico(self):
        """Verifica se algum usuário precisa de reset hoje"""
        try:
            from database import ConfiguracaoUsuario

            # Busca todas as configurações
            configs = self.db.session.query(ConfiguracaoUsuario).all()
            dia_hoje = datetime.now().day

            for config in configs:
                if config.dia_fechamento is None:
                    continue

                # Calcula o dia de reset (dia seguinte ao fechamento)
                dia_reset = config.dia_fechamento + 1 if config.dia_fechamento < 28 else 1

                if dia_hoje == dia_reset:
                    logger.info(f"Executando reset automático para usuário {config.user_id}")

                    # Reseta os gastos
                    num_caixinhas = self.db.resetar_gastos_mensais(config.user_id)

                    # Envia notificação
                    try:
                        import asyncio
                        asyncio.create_task(
                            self.telegram_app.bot.send_message(
                                chat_id=config.user_id,
                                text=(
                                    f"🔄 **Reset Automático Realizado!**\n\n"
                                    f"📅 Novo ciclo iniciado!\n"
                                    f"✅ {num_caixinhas} caixinha(s) resetada(s)\n\n"
                                    f"💰 Todos os gastos foram zerados para o novo período.\n"
                                    f"📊 Use /caixinhas para ver o status."
                                )
                            )
                        )
                    except Exception as e:
                        logger.error(f"Erro ao enviar notificação de reset: {e}")

        except Exception as e:
            logger.error(f"Erro ao verificar reset automático: {e}")

    def enviar_relatorio_fechamento(self):
        """Envia relatório automático no dia de fechamento às 22h"""
        try:
            from database import ConfiguracaoUsuario

            # Busca todas as configurações
            configs = self.db.session.query(ConfiguracaoUsuario).all()
            dia_hoje = datetime.now().day

            for config in configs:
                if config.dia_fechamento is None:
                    continue

                # Verifica se hoje é o dia de fechamento
                if dia_hoje == config.dia_fechamento:
                    logger.info(f"Enviando relatório de fechamento para usuário {config.user_id}")

                    # Gera o relatório
                    rel = self.db.get_relatorio_mensal(config.user_id)
                    hoje = datetime.now()
                    mes_nome = hoje.strftime("%B/%Y")

                    if not rel['caixinhas']:
                        continue

                    # Monta mensagem do relatório
                    mensagem = f"📊 **Relatório de Fechamento - {mes_nome}**\n\n"
                    mensagem += f"🔔 Seu cartão fecha hoje (dia {config.dia_fechamento})!\n\n"
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
                    dia_reset = config.dia_fechamento + 1 if config.dia_fechamento < 28 else 1
                    mensagem += f"🔄 Amanhã (dia {dia_reset}) os gastos serão resetados automaticamente!"

                    # Envia o relatório
                    try:
                        import asyncio
                        asyncio.create_task(
                            self.telegram_app.bot.send_message(
                                chat_id=config.user_id,
                                text=mensagem
                            )
                        )
                    except Exception as e:
                        logger.error(f"Erro ao enviar relatório de fechamento: {e}")

        except Exception as e:
            logger.error(f"Erro ao verificar relatório de fechamento: {e}")

    def verificar_lembretes_sync(self):
        """Verifica lembretes de forma síncrona (para o scheduler)"""
        try:
            import asyncio
            # Cria um novo event loop se necessário
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Executa a verificação assíncrona
            loop.run_until_complete(self.lembretes.verificar_e_enviar_lembretes(self.telegram_app))
        except Exception as e:
            logger.error(f"Erro ao verificar lembretes: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def iniciar(self):
        """Inicia o scheduler"""
        # Verifica diariamente às 00:10 se precisa fazer reset
        self.scheduler.add_job(
            self.verificar_reset_automatico,
            'cron',
            hour=0,
            minute=10,
            id='verificar_reset_diario'
        )

        # Envia relatório diariamente às 22:00 (verifica se é dia de fechamento)
        self.scheduler.add_job(
            self.enviar_relatorio_fechamento,
            'cron',
            hour=22,
            minute=0,
            id='relatorio_fechamento'
        )

        # Verifica lembretes de gastos recorrentes diariamente às 09:00
        self.scheduler.add_job(
            self.verificar_lembretes_sync,
            'cron',
            hour=9,
            minute=0,
            id='lembretes_recorrentes'
        )

        self.scheduler.start()
        logger.info("Scheduler V3 iniciado - Reset às 00:10, Relatório às 22:00, Lembretes às 09:00")

    def parar(self):
        """Para o scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler V3 parado")
