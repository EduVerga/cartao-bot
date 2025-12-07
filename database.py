"""
Módulo de banco de dados para gerenciar caixinhas e transações
"""
import os
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


class GastoRecorrente(Base):
    """Modelo para gastos recorrentes"""
    __tablename__ = 'gastos_recorrentes'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    caixinha_id = Column(Integer, ForeignKey('caixinhas.id'), nullable=True)  # Opcional - não usado para recorrentes
    descricao = Column(String(200), nullable=False)
    valor_padrao = Column(Float, nullable=True)  # Valor padrão (None se for variável)
    dia_vencimento = Column(Integer, nullable=False)  # Dia do mês (1-28)
    ativo = Column(Integer, default=1)  # 1 = ativo, 0 = inativo
    criado_em = Column(DateTime, default=datetime.now)

    caixinha = relationship("Caixinha")
    pagamentos = relationship("PagamentoRecorrente", back_populates="gasto_recorrente")

    @property
    def valor_variavel(self):
        """Retorna True se o valor é variável (não tem valor padrão)"""
        return self.valor_padrao is None

    def __repr__(self):
        if self.valor_variavel:
            return f"<GastoRecorrente {self.descricao}: VARIÁVEL dia {self.dia_vencimento}>"
        return f"<GastoRecorrente {self.descricao}: R$ {self.valor_padrao:.2f} dia {self.dia_vencimento}>"


class PagamentoRecorrente(Base):
    """Modelo para controlar pagamentos mensais de gastos recorrentes"""
    __tablename__ = 'pagamentos_recorrentes'

    id = Column(Integer, primary_key=True)
    gasto_recorrente_id = Column(Integer, ForeignKey('gastos_recorrentes.id'))
    user_id = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)  # Mês (1-12)
    ano = Column(Integer, nullable=False)  # Ano
    valor = Column(Float, nullable=True)  # Valor definido para este mês
    pago = Column(Integer, default=0)  # 0 = não pago, 1 = pago
    data_pagamento = Column(DateTime, nullable=True)  # Quando foi marcado como pago
    ultimo_lembrete = Column(DateTime, nullable=True)  # Último lembrete enviado
    criado_em = Column(DateTime, default=datetime.now)

    gasto_recorrente = relationship("GastoRecorrente", back_populates="pagamentos")

    def __repr__(self):
        status = "PAGO" if self.pago else "PENDENTE"
        return f"<Pagamento {self.mes}/{self.ano}: {status}>"


class Database:
    """Gerenciador do banco de dados"""

    def __init__(self, db_path=None):
        import logging
        logger = logging.getLogger(__name__)

        # Usa variável de ambiente DB_PATH se disponível, senão usa padrão
        if db_path is None:
            db_path = os.getenv('DB_PATH', 'cartao_bot.db')

        # Garante que o diretório existe (importante para Railway)
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Verifica se banco já existe
        db_exists = os.path.exists(db_path)

        print("\n" + "="*80)
        print("DATABASE INITIALIZATION DEBUG")
        print("="*80)
        print(f"DB_PATH: {db_path}")
        print(f"DB exists: {db_exists}")

        if db_exists:
            db_size = os.path.getsize(db_path)
            print(f"DB size: {db_size} bytes")
            logger.info(f"📂 Banco existente encontrado: {db_path} ({db_size} bytes)")
        else:
            print("DB will be created")
            logger.info(f"📂 Criando novo banco: {db_path}")

        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)

        # create_all NÃO apaga dados, apenas cria tabelas que não existem
        Base.metadata.create_all(self.engine)
        print("Tables created/verified")

        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Verifica quantos registros existem após conectar
        try:
            num_caixinhas = self.session.query(Caixinha).count()
            num_transacoes = self.session.query(Transacao).count()
            num_recorrentes = self.session.query(GastoRecorrente).count()

            print(f"Records found:")
            print(f"  - Caixinhas: {num_caixinhas}")
            print(f"  - Transações: {num_transacoes}")
            print(f"  - Recorrentes: {num_recorrentes}")
            print("="*80 + "\n")

            logger.info(f"✅ Banco conectado - {num_caixinhas} caixinha(s), {num_transacoes} transação(ões), {num_recorrentes} recorrente(s)")
        except Exception as e:
            print(f"ERROR counting records: {e}")
            print("="*80 + "\n")
            logger.warning(f"⚠️  Erro ao contar registros: {e}")

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

    def buscar_caixinha_por_id(self, caixinha_id: int):
        """Busca uma caixinha por ID"""
        return self.session.get(Caixinha, caixinha_id)

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

    def buscar_configuracao_usuario(self, user_id: int):
        """Busca a configuração do usuário"""
        return self.session.query(ConfiguracaoUsuario).filter_by(user_id=user_id).first()

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

    def criar_gasto_recorrente(self, user_id: int, descricao: str, dia_vencimento: int, valor_padrao: float = None, caixinha_id: int = None):
        """Cria um novo gasto recorrente (valor_padrao=None para valores variáveis)"""
        gasto = GastoRecorrente(
            user_id=user_id,
            caixinha_id=caixinha_id,  # Agora opcional
            descricao=descricao,
            valor_padrao=valor_padrao,
            dia_vencimento=dia_vencimento
        )
        self.session.add(gasto)
        self.session.commit()
        return gasto

    def listar_gastos_recorrentes(self, user_id: int, apenas_ativos: bool = True):
        """Lista todos os gastos recorrentes do usuário"""
        query = self.session.query(GastoRecorrente).filter_by(user_id=user_id)
        if apenas_ativos:
            query = query.filter_by(ativo=1)
        return query.order_by(GastoRecorrente.dia_vencimento).all()

    def buscar_gasto_recorrente_por_id(self, gasto_id: int):
        """Busca um gasto recorrente por ID"""
        return self.session.query(GastoRecorrente).get(gasto_id)

    def editar_gasto_recorrente(self, gasto_id: int, **kwargs):
        """Edita um gasto recorrente"""
        gasto = self.session.query(GastoRecorrente).get(gasto_id)
        if gasto:
            for key, value in kwargs.items():
                if hasattr(gasto, key):
                    setattr(gasto, key, value)
            self.session.commit()
            return gasto
        return None

    def desativar_gasto_recorrente(self, gasto_id: int):
        """Desativa um gasto recorrente"""
        gasto = self.session.query(GastoRecorrente).get(gasto_id)
        if gasto:
            gasto.ativo = 0
            self.session.commit()
            return gasto
        return None

    def deletar_gasto_recorrente(self, gasto_id: int):
        """Deleta um gasto recorrente"""
        gasto = self.session.query(GastoRecorrente).get(gasto_id)
        if gasto:
            self.session.delete(gasto)
            self.session.commit()
            return True
        return False

    def calcular_total_recorrentes_mes(self, user_id: int):
        """Calcula o total de gastos recorrentes do mês"""
        gastos = self.listar_gastos_recorrentes(user_id, apenas_ativos=True)
        return sum(g.valor_padrao for g in gastos if g.valor_padrao)

    def buscar_gasto_recorrente_por_descricao(self, user_id: int, descricao: str):
        """Busca um gasto recorrente pela descrição (case-insensitive)"""
        from sqlalchemy import func
        return self.session.query(GastoRecorrente).filter(
            GastoRecorrente.user_id == user_id,
            func.lower(GastoRecorrente.descricao) == func.lower(descricao),
            GastoRecorrente.ativo == 1
        ).first()

    def obter_ou_criar_pagamento_mes(self, gasto_recorrente_id: int, user_id: int, mes: int = None, ano: int = None):
        """Obtém ou cria um registro de pagamento para o mês atual"""
        from datetime import datetime
        if mes is None:
            mes = datetime.now().month
        if ano is None:
            ano = datetime.now().year

        pagamento = self.session.query(PagamentoRecorrente).filter_by(
            gasto_recorrente_id=gasto_recorrente_id,
            user_id=user_id,
            mes=mes,
            ano=ano
        ).first()

        if not pagamento:
            pagamento = PagamentoRecorrente(
                gasto_recorrente_id=gasto_recorrente_id,
                user_id=user_id,
                mes=mes,
                ano=ano
            )
            self.session.add(pagamento)
            self.session.commit()

        return pagamento

    def definir_valor_recorrente_mes(self, gasto_recorrente_id: int, user_id: int, valor: float, mes: int = None, ano: int = None):
        """Define o valor de um gasto recorrente para o mês atual"""
        pagamento = self.obter_ou_criar_pagamento_mes(gasto_recorrente_id, user_id, mes, ano)
        pagamento.valor = valor
        self.session.commit()
        return pagamento

    def marcar_recorrente_como_pago(self, gasto_recorrente_id: int, user_id: int, mes: int = None, ano: int = None):
        """Marca um gasto recorrente como pago"""
        from datetime import datetime
        pagamento = self.obter_ou_criar_pagamento_mes(gasto_recorrente_id, user_id, mes, ano)
        pagamento.pago = 1
        pagamento.data_pagamento = datetime.now()
        self.session.commit()
        return pagamento

    def obter_pagamentos_pendentes(self, user_id: int, mes: int = None, ano: int = None):
        """Lista todos os pagamentos pendentes do usuário para o mês"""
        from datetime import datetime
        if mes is None:
            mes = datetime.now().month
        if ano is None:
            ano = datetime.now().year

        # Busca todos os gastos recorrentes ativos
        gastos = self.listar_gastos_recorrentes(user_id, apenas_ativos=True)
        pendentes = []

        for gasto in gastos:
            pagamento = self.obter_ou_criar_pagamento_mes(gasto.id, user_id, mes, ano)
            if not pagamento.pago:
                pendentes.append((gasto, pagamento))

        return pendentes

    def atualizar_ultimo_lembrete(self, pagamento_id: int):
        """Atualiza a data do último lembrete enviado"""
        from datetime import datetime
        pagamento = self.session.query(PagamentoRecorrente).get(pagamento_id)
        if pagamento:
            pagamento.ultimo_lembrete = datetime.now()
            self.session.commit()
        return pagamento

    def resetar_tudo_usuario(self, user_id: int):
        """
        Deleta TODOS os dados de um usuário específico:
        - Todas as transações
        - Todos os estabelecimentos conhecidos
        - Todas as caixinhas
        - Gastos recorrentes
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

            # 4. Deleta pagamentos recorrentes
            self.session.query(PagamentoRecorrente).filter_by(user_id=user_id).delete()

            # 5. Deleta gastos recorrentes
            self.session.query(GastoRecorrente).filter_by(user_id=user_id).delete()

            # 6. Deleta configurações do usuário
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
