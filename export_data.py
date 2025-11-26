"""
Script para exportar todos os dados do banco SQLite para JSON
"""
import json
from database import Database, Caixinha, Transacao, EstabelecimentoConhecido, ConfiguracaoUsuario
from datetime import datetime

def export_data():
    """Exporta todos os dados para JSON"""
    db = Database()

    export = {
        'caixinhas': [],
        'transacoes': [],
        'estabelecimentos': [],
        'configuracoes': []
    }

    # Exporta caixinhas
    caixinhas = db.session.query(Caixinha).all()
    for c in caixinhas:
        export['caixinhas'].append({
            'id': c.id,
            'user_id': c.user_id,
            'nome': c.nome,
            'limite': float(c.limite),
            'gasto_atual': float(c.gasto_atual),
            'criado_em': c.criado_em.isoformat() if c.criado_em else None
        })

    # Exporta transações
    transacoes = db.session.query(Transacao).all()
    for t in transacoes:
        export['transacoes'].append({
            'id': t.id,
            'user_id': t.user_id,
            'caixinha_id': t.caixinha_id,
            'valor': float(t.valor),
            'estabelecimento': t.estabelecimento,
            'categoria': t.categoria,
            'data_transacao': t.data_transacao.isoformat() if t.data_transacao else None,
            'criado_em': t.criado_em.isoformat() if t.criado_em else None
        })

    # Exporta estabelecimentos conhecidos
    estabelecimentos = db.session.query(EstabelecimentoConhecido).all()
    for e in estabelecimentos:
        export['estabelecimentos'].append({
            'id': e.id,
            'user_id': e.user_id,
            'nome_estabelecimento': e.nome_estabelecimento,
            'caixinha_id': e.caixinha_id
        })

    # Exporta configurações
    configs = db.session.query(ConfiguracaoUsuario).all()
    for cfg in configs:
        export['configuracoes'].append({
            'user_id': cfg.user_id,
            'dia_fechamento': cfg.dia_fechamento
        })

    # Salva em arquivo JSON
    with open('backup_dados.json', 'w', encoding='utf-8') as f:
        json.dump(export, f, indent=2, ensure_ascii=False)

    print(f"OK Exportacao concluida!")
    print(f"Caixinhas: {len(export['caixinhas'])}")
    print(f"Transacoes: {len(export['transacoes'])}")
    print(f"Estabelecimentos: {len(export['estabelecimentos'])}")
    print(f"Configuracoes: {len(export['configuracoes'])}")
    print(f"\nArquivo salvo: backup_dados.json")

if __name__ == '__main__':
    export_data()
