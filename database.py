"""
Módulo de banco de dados para gerenciar caixinhas e transações
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()


class Caixinha(Base):
    """Modelo de caixinha de gastos"""
    __tablename__ = 'caixinhas'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    nome = Column(String(100), nullable=False)
    limite = Column(Float, nullable=False)
    gasto_atual = Column(Float, default=0.0)
    criado_em = Column(DateTime, default=datetime.now)

    transacoes = relationship("Transacao", back_populates="caixinha")

    @property
    def saldo_restante(self):
        return self.limite - self.gasto_atual

    @property
    def percentual_usado(self):
        return (self.gasto_atual / self.limite * 100) if self.limite > 0 else 0

    def __repr__(self):
        return f"<Caixinha {self.nome}: R$ {self.gasto_atual:.2f} / R$ {self.limite:.2f}>"


class Transacao(Base):
    """Modelo de transação"""
    __tablename__ = 'transacoes'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    caixinha_id = Column(Integer, ForeignKey('caixinhas.id'))
    valor = Column(Float, nullable=False)
    estabelecimento = Column(String(200))
    categoria = Column(String(100))
    data_transacao = Column(DateTime)
    criado_em = Column(DateTime, default=datetime.now)

    caixinha = relationship("Caixinha", back_populates="transacoes")

    def __repr__(self):
        return f"<Transacao R$ {self.valor:.2f} - {self.estabelecimento}>"


class EstabelecimentoConhecido(Base):
    """Modelo para memorizar categorias de estabelecimentos"""
    __tablename__ = 'estabelecimentos_conhecidos'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    nome_estabelecimento = Column(String(200), nullable=False)
    caixinha_id = Column(Integer, ForeignKey('caixinhas.id'))
    criado_em = Column(DateTime, default=datetime.now)

    caixinha = relationship("Caixinha")

    def __repr__(self):
        return f"<Estabelecimento {self.nome_estabelecimento} -> Caixinha ID {self.caixinha_id}>"


class ConfiguracaoUsuario(Base):
    """Modelo para configurações do usuário"""
    __tablename__ = 'configuracoes_usuario'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)
    dia_fechamento = Column(Integer, default=None)  # Dia do mês (1-28)
    criado_em = Column(DateTime, default=datetime.now)
    atualizado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Config User {self.user_id}: Fechamento dia {self.dia_fechamento}>"


class Database:
    """Gerenciador do banco de dados"""

    def __init__(self, db_path='cartao_bot.db'):
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def criar_caixinha(self, user_id: int, nome: str, limite: float):
        """Cria uma nova caixinha"""
        caixinha = Caixinha(user_id=user_id, nome=nome, limite=limite)
        self.session.add(caixinha)
        self.session.commit()
        return caixinha

    def listar_caixinhas(self, user_id: int):
        """Lista todas as caixinhas de um usuário"""
        return self.session.query(Caixinha).filter_by(user_id=user_id).all()

    def buscar_caixinha_por_categoria(self, user_id: int, categoria: str):
        """Busca caixinha por nome/categoria"""
        return self.session.query(Caixinha).filter_by(
            user_id=user_id,
            nome=categoria
        ).first()

    def adicionar_transacao(self, user_id: int, caixinha_id: int, valor: float,
                           estabelecimento: str, categoria: str, data_transacao: datetime):
        """Adiciona uma nova transação e atualiza a caixinha"""
        transacao = Transacao(
            user_id=user_id,
            caixinha_id=caixinha_id,
            valor=valor,
            estabelecimento=estabelecimento,
            categoria=categoria,
            data_transacao=data_transacao
        )

        # Atualiza o gasto da caixinha
        caixinha = self.session.query(Caixinha).get(caixinha_id)
        if caixinha:
            caixinha.gasto_atual += valor

        self.session.add(transacao)
        self.session.commit()
        return transacao

    def listar_transacoes(self, user_id: int, limit=10):
        """Lista últimas transações de um usuário"""
        return self.session.query(Transacao).filter_by(
            user_id=user_id
        ).order_by(Transacao.criado_em.desc()).limit(limit).all()

    def deletar_caixinha(self, caixinha_id: int):
        """Deleta uma caixinha"""
        caixinha = self.session.query(Caixinha).get(caixinha_id)
        if caixinha:
            self.session.delete(caixinha)
            self.session.commit()
            return True
        return False

    def editar_limite_caixinha(self, caixinha_id: int, novo_limite: float):
        """Edita o limite de uma caixinha"""
        caixinha = self.session.query(Caixinha).get(caixinha_id)
        if caixinha:
            caixinha.limite = novo_limite
            self.session.commit()
            return caixinha
        return None

    def renomear_caixinha(self, caixinha_id: int, novo_nome: str):
        """Renomeia uma caixinha"""
        caixinha = self.session.query(Caixinha).get(caixinha_id)
        if caixinha:
            caixinha.nome = novo_nome
            self.session.commit()
            return caixinha
        return None

    def buscar_estabelecimento_conhecido(self, user_id: int, nome_estabelecimento: str):
        """Busca estabelecimento conhecido na memória"""
        return self.session.query(EstabelecimentoConhecido).filter_by(
            user_id=user_id,
            nome_estabelecimento=nome_estabelecimento.upper()
        ).first()

    def salvar_estabelecimento_conhecido(self, user_id: int, nome_estabelecimento: str, caixinha_id: int):
        """Salva um estabelecimento na memória"""
        estabelecimento = EstabelecimentoConhecido(
            user_id=user_id,
            nome_estabelecimento=nome_estabelecimento.upper(),
            caixinha_id=caixinha_id
        )
        self.session.add(estabelecimento)
        self.session.commit()
        return estabelecimento

    def definir_dia_fechamento(self, user_id: int, dia: int):
        """Define o dia de fechamento do cartão (1-28)"""
        config = self.session.query(ConfiguracaoUsuario).filter_by(user_id=user_id).first()

        if config:
            config.dia_fechamento = dia
            config.atualizado_em = datetime.now()
        else:
            config = ConfiguracaoUsuario(user_id=user_id, dia_fechamento=dia)
            self.session.add(config)

        self.session.commit()
        return config

    def obter_dia_fechamento(self, user_id: int):
        """Obtém o dia de fechamento configurado"""
        config = self.session.query(ConfiguracaoUsuario).filter_by(user_id=user_id).first()
        return config.dia_fechamento if config else None

    def resetar_gastos_mensais(self, user_id: int):
        """Reseta os gastos de todas as caixinhas mantendo os limites"""
        caixinhas = self.listar_caixinhas(user_id)
        for caixinha in caixinhas:
            caixinha.gasto_atual = 0.0
        self.session.commit()
        return len(caixinhas)

    def resetar_tudo_usuario(self, user_id: int):
        """
        Deleta TODOS os dados de um usuário específico:
        - Todas as transações
        - Todos os estabelecimentos conhecidos
        - Todas as caixinhas
        - Configurações (dia de fechamento)

        O usuário volta ao estado inicial, como se nunca tivesse usado o bot.
        """
        try:
            # 1. Deleta todas as transações do usuário
            self.session.query(Transacao).filter_by(user_id=user_id).delete()

            # 2. Deleta todos os estabelecimentos conhecidos
            self.session.query(EstabelecimentoConhecido).filter_by(user_id=user_id).delete()

            # 3. Deleta todas as caixinhas (CASCADE vai deletar transações relacionadas automaticamente)
            self.session.query(Caixinha).filter_by(user_id=user_id).delete()

            # 4. Deleta configurações do usuário
            self.session.query(ConfiguracaoUsuario).filter_by(user_id=user_id).delete()

            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            import logging
            logging.error(f"Erro ao resetar dados do usuário {user_id}: {e}")
            return False

    def get_relatorio_mensal(self, user_id: int):
        """Gera relatório mensal com todas as informações"""
        from datetime import date
        from sqlalchemy import func, extract

        hoje = date.today()

        # Busca todas as caixinhas
        caixinhas = self.listar_caixinhas(user_id)

        # Busca transações do mês atual
        transacoes_mes = self.session.query(Transacao).filter(
            Transacao.user_id == user_id,
            extract('year', Transacao.data_transacao) == hoje.year,
            extract('month', Transacao.data_transacao) == hoje.month
        ).all()

        # Calcula totais
        total_gasto = sum(c.gasto_atual for c in caixinhas)
        total_limite = sum(c.limite for c in caixinhas)

        return {
            'caixinhas': caixinhas,
            'transacoes_mes': transacoes_mes,
            'total_gasto': total_gasto,
            'total_limite': total_limite,
            'total_disponivel': total_limite - total_gasto,
            'num_transacoes': len(transacoes_mes)
        }

    def get_historico_consolidado(self, user_id: int, num_meses: int):
        """Retorna histórico consolidado dos últimos N meses agrupado por mês e caixinha"""
        from datetime import date, timedelta
        from sqlalchemy import func, extract
        from collections import defaultdict

        hoje = date.today()
        # Calcula data inicial (N meses atrás)
        data_inicio = hoje - timedelta(days=num_meses * 30)

        # Busca todas as transações do período
        transacoes = self.session.query(Transacao).filter(
            Transacao.user_id == user_id,
            Transacao.data_transacao >= data_inicio
        ).order_by(Transacao.data_transacao.desc()).all()

        if not transacoes:
            return None

        # Agrupa por mês e caixinha
        consolidado = defaultdict(lambda: defaultdict(lambda: {'total': 0.0, 'count': 0, 'transacoes': []}))

        for t in transacoes:
            mes_ano = t.data_transacao.strftime("%m/%Y")
            categoria = t.categoria or "Sem categoria"

            consolidado[mes_ano][categoria]['total'] += t.valor
            consolidado[mes_ano][categoria]['count'] += 1
            consolidado[mes_ano][categoria]['transacoes'].append(t)

        # Converte para dicionário normal e ordena por mês (mais recente primeiro)
        resultado = {}
        for mes_ano in sorted(consolidado.keys(), key=lambda x: (x.split('/')[1], x.split('/')[0]), reverse=True):
            resultado[mes_ano] = dict(consolidado[mes_ano])

        return resultado
