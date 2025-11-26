"""
Script para importar dados do JSON para o banco SQLite
ATENÇÃO: Execute este script NO SERVIDOR (Railway)
"""
import json
from database import Database, Caixinha, Transacao, EstabelecimentoConhecido, ConfiguracaoUsuario
from datetime import datetime

def import_data():
    """Importa dados do JSON para o banco"""
    db = Database()

    # Lê o arquivo JSON
    with open('backup_dados.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("Iniciando importacao...")

    # Mapeia IDs antigos para novos (caso haja conflito)
    caixinha_id_map = {}

    # Importa caixinhas
    for c in data['caixinhas']:
        # Verifica se caixinha já existe
        existe = db.session.query(Caixinha).filter_by(
            user_id=c['user_id'],
            nome=c['nome']
        ).first()

        if existe:
            print(f"Aviso: Caixinha '{c['nome']}' ja existe, pulando...")
            caixinha_id_map[c['id']] = existe.id
            continue

        caixinha = Caixinha(
            user_id=c['user_id'],
            nome=c['nome'],
            limite=c['limite'],
            gasto_atual=c['gasto_atual'],
            criado_em=datetime.fromisoformat(c['criado_em']) if c['criado_em'] else None
        )
        db.session.add(caixinha)
        db.session.flush()  # Pega o novo ID
        caixinha_id_map[c['id']] = caixinha.id

    db.session.commit()
    print(f"OK {len(data['caixinhas'])} caixinhas processadas")

    # Importa transações
    for t in data['transacoes']:
        # Usa o novo ID da caixinha
        novo_caixinha_id = caixinha_id_map.get(t['caixinha_id'])
        if not novo_caixinha_id:
            print(f"Aviso: Caixinha ID {t['caixinha_id']} nao encontrada, pulando transacao...")
            continue

        transacao = Transacao(
            user_id=t['user_id'],
            caixinha_id=novo_caixinha_id,
            valor=t['valor'],
            estabelecimento=t['estabelecimento'],
            categoria=t.get('categoria'),
            data_transacao=datetime.fromisoformat(t['data_transacao']) if t.get('data_transacao') else None,
            criado_em=datetime.fromisoformat(t['criado_em']) if t.get('criado_em') else None
        )
        db.session.add(transacao)

    db.session.commit()
    print(f"OK {len(data['transacoes'])} transacoes importadas")

    # Importa estabelecimentos conhecidos
    for e in data['estabelecimentos']:
        novo_caixinha_id = caixinha_id_map.get(e['caixinha_id'])
        if not novo_caixinha_id:
            print(f"Aviso: Caixinha ID {e['caixinha_id']} nao encontrada, pulando estabelecimento...")
            continue

        # Verifica se já existe
        existe = db.session.query(EstabelecimentoConhecido).filter_by(
            user_id=e['user_id'],
            nome_estabelecimento=e['nome_estabelecimento']
        ).first()

        if existe:
            continue

        estabelecimento = EstabelecimentoConhecido(
            user_id=e['user_id'],
            nome_estabelecimento=e['nome_estabelecimento'],
            caixinha_id=novo_caixinha_id
        )
        db.session.add(estabelecimento)

    db.session.commit()
    print(f"OK {len(data['estabelecimentos'])} estabelecimentos processados")

    # Importa configurações
    for cfg in data['configuracoes']:
        # Verifica se já existe
        existe = db.session.query(ConfiguracaoUsuario).filter_by(
            user_id=cfg['user_id']
        ).first()

        if existe:
            existe.dia_fechamento = cfg['dia_fechamento']
        else:
            config = ConfiguracaoUsuario(
                user_id=cfg['user_id'],
                dia_fechamento=cfg['dia_fechamento']
            )
            db.session.add(config)

    db.session.commit()
    print(f"OK {len(data['configuracoes'])} configuracoes importadas")

    print("\nImportacao concluida com sucesso!")

if __name__ == '__main__':
    import_data()
