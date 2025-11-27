"""
Módulo para alertas inteligentes e previsões de gastos
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from database import Caixinha, Transacao, Database
from sqlalchemy import func


class AlertaInteligente:
    """Sistema de alertas inteligentes com previsões"""

    def __init__(self, db: Database):
        self.db = db

    def calcular_gasto_diario_medio(self, caixinha: Caixinha, dias: int = 7) -> float:
        """
        Calcula o gasto diário médio de uma caixinha nos últimos N dias
        """
        data_inicio = datetime.now() - timedelta(days=dias)

        transacoes = self.db.session.query(Transacao).filter(
            Transacao.caixinha_id == caixinha.id,
            Transacao.criado_em >= data_inicio
        ).all()

        if not transacoes:
            return 0.0

        total_gasto = sum(t.valor for t in transacoes)
        dias_decorridos = (datetime.now() - transacoes[0].criado_em).days + 1

        return total_gasto / max(dias_decorridos, 1)

    def prever_data_estouro(self, caixinha: Caixinha) -> Optional[datetime]:
        """
        Prevê quando a caixinha vai estourar o limite baseado no ritmo atual
        """
        saldo_restante = caixinha.saldo_restante

        if saldo_restante <= 0:
            return None  # Já estourou

        gasto_diario = self.calcular_gasto_diario_medio(caixinha, dias=7)

        if gasto_diario <= 0:
            return None  # Sem gastos recentes

        dias_ate_estouro = saldo_restante / gasto_diario
        data_estouro = datetime.now() + timedelta(days=dias_ate_estouro)

        return data_estouro

    def calcular_nivel_alerta(self, caixinha: Caixinha) -> Tuple[str, str]:
        """
        Calcula o nível de alerta de uma caixinha
        Retorna: (nivel, emoji)
        - 'ok': Situação tranquila (< 50%)
        - 'atencao': Atenção necessária (50-79%)
        - 'alerta': Alerta vermelho (80-99%)
        - 'estourado': Limite ultrapassado (>= 100%)
        """
        percentual = caixinha.percentual_usado

        if percentual >= 100:
            return ('estourado', '🔴')
        elif percentual >= 80:
            return ('alerta', '🟠')
        elif percentual >= 50:
            return ('atencao', '🟡')
        else:
            return ('ok', '🟢')

    def gerar_mensagem_alerta(self, caixinha: Caixinha) -> Optional[str]:
        """
        Gera mensagem de alerta inteligente para uma caixinha
        Retorna None se não há necessidade de alerta
        """
        nivel, emoji = self.calcular_nivel_alerta(caixinha)

        # Não gera alerta para caixinhas OK
        if nivel == 'ok':
            return None

        percentual = caixinha.percentual_usado
        saldo = caixinha.saldo_restante
        gasto_diario = self.calcular_gasto_diario_medio(caixinha, dias=7)
        data_estouro = self.prever_data_estouro(caixinha)

        # Monta a mensagem baseada no nível
        if nivel == 'estourado':
            excedente = abs(saldo)
            msg = (
                f"{emoji} **LIMITE ESTOURADO - {caixinha.nome}**\n\n"
                f"💰 Gasto atual: R$ {caixinha.gasto_atual:.2f}\n"
                f"🎯 Limite: R$ {caixinha.limite:.2f}\n"
                f"📊 Percentual: {percentual:.1f}%\n"
                f"⚠️ Excedente: R$ {excedente:.2f}\n\n"
                f"Você ultrapassou o limite desta caixinha!"
            )

        elif nivel == 'alerta':
            msg = (
                f"{emoji} **ALERTA - {caixinha.nome}**\n\n"
                f"💰 Gasto atual: R$ {caixinha.gasto_atual:.2f}\n"
                f"🎯 Limite: R$ {caixinha.limite:.2f}\n"
                f"📊 Percentual usado: {percentual:.1f}%\n"
                f"💵 Saldo restante: R$ {saldo:.2f}\n\n"
            )

            if data_estouro and gasto_diario > 0:
                dias_restantes = (data_estouro - datetime.now()).days
                msg += (
                    f"📈 Ritmo atual: R$ {gasto_diario:.2f}/dia\n"
                    f"⏰ Previsão de estouro: {data_estouro.strftime('%d/%m/%Y')}"
                )
                if dias_restantes <= 3:
                    msg += f" ({dias_restantes} dias!)"
            else:
                msg += "⚠️ Atenção: você está muito próximo do limite!"

        elif nivel == 'atencao':
            msg = (
                f"{emoji} **Atenção - {caixinha.nome}**\n\n"
                f"💰 Gasto: R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}\n"
                f"📊 {percentual:.1f}% usado\n"
                f"💵 Saldo: R$ {saldo:.2f}\n\n"
            )

            if data_estouro and gasto_diario > 0:
                msg += (
                    f"📈 Ritmo: R$ {gasto_diario:.2f}/dia\n"
                    f"⏰ Previsão de estouro: {data_estouro.strftime('%d/%m/%Y')}"
                )

        return msg

    def verificar_alertas_usuario(self, user_id: int) -> List[str]:
        """
        Verifica todas as caixinhas do usuário e retorna alertas necessários
        """
        caixinhas = self.db.listar_caixinhas(user_id)
        alertas = []

        for caixinha in caixinhas:
            msg = self.gerar_mensagem_alerta(caixinha)
            if msg:
                alertas.append(msg)

        return alertas

    def deve_enviar_alerta_apos_gasto(self, caixinha: Caixinha, percentual_anterior: float) -> bool:
        """
        Verifica se deve enviar alerta após um novo gasto
        Envia alertas ao cruzar limites importantes: 50%, 75%, 90%, 100%
        """
        percentual_atual = caixinha.percentual_usado

        limites = [50, 75, 90, 100]

        for limite in limites:
            # Se cruzou um limite importante
            if percentual_anterior < limite <= percentual_atual:
                return True

        return False

    def gerar_relatorio_previsoes(self, user_id: int) -> str:
        """
        Gera relatório com previsões de todas as caixinhas
        """
        caixinhas = self.db.listar_caixinhas(user_id)

        if not caixinhas:
            return "📊 Você ainda não tem caixinhas cadastradas."

        msg = "📊 **Relatório de Previsões**\n\n"

        for caixinha in caixinhas:
            nivel, emoji = self.calcular_nivel_alerta(caixinha)
            percentual = caixinha.percentual_usado
            gasto_diario = self.calcular_gasto_diario_medio(caixinha, dias=7)

            msg += f"{emoji} **{caixinha.nome}**\n"
            msg += f"   Usado: {percentual:.1f}% (R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f})\n"

            if gasto_diario > 0:
                msg += f"   Ritmo: R$ {gasto_diario:.2f}/dia\n"

                data_estouro = self.prever_data_estouro(caixinha)
                if data_estouro:
                    dias_restantes = (data_estouro - datetime.now()).days
                    msg += f"   Previsão: {data_estouro.strftime('%d/%m/%Y')} ({dias_restantes} dias)\n"
            else:
                msg += f"   Sem gastos recentes\n"

            msg += "\n"

        return msg

    def gerar_dicas_economia(self, caixinha: Caixinha) -> Optional[str]:
        """
        Gera dicas personalizadas de economia baseadas no comportamento
        """
        nivel, _ = self.calcular_nivel_alerta(caixinha)

        if nivel == 'ok':
            return None

        gasto_diario = self.calcular_gasto_diario_medio(caixinha, dias=7)
        data_estouro = self.prever_data_estouro(caixinha)

        dicas = []

        if nivel == 'estourado':
            dicas.append("🎯 Considere revisar e aumentar o limite desta caixinha")
            dicas.append("💡 Analise se há gastos que podem ser adiados ou reduzidos")
            dicas.append("🔄 Revise suas transações recentes para identificar excessos")

        elif nivel == 'alerta':
            if data_estouro and gasto_diario > 0:
                dias = (data_estouro - datetime.now()).days
                if dias <= 5:
                    reducao_necessaria = gasto_diario * 0.3
                    dicas.append(f"⚠️ Tente reduzir cerca de R$ {reducao_necessaria:.2f}/dia para não estourar")
            dicas.append("🛑 Evite gastos não essenciais nesta categoria")
            dicas.append("📱 Considere alternativas mais econômicas")

        elif nivel == 'atencao':
            dicas.append("👀 Monitore seus gastos nesta categoria com mais atenção")
            dicas.append("📊 Você ainda tem margem, mas o ritmo está acelerado")

        if not dicas:
            return None

        msg = "💡 **Dicas de Economia:**\n\n"
        for i, dica in enumerate(dicas, 1):
            msg += f"{i}. {dica}\n"

        return msg
