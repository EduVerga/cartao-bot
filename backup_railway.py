"""
Script para fazer backup do banco de dados do Railway
Execute este script ANTES de fazer deploy para salvar os dados atuais
"""
import os
import json
from datetime import datetime
from database import Database, Caixinha, Transacao, GastoRecorrente, PagamentoRecorrente, EstabelecimentoConhecido, ConfiguracaoUsuario

def fazer_backup():
    """Exporta todos os dados do banco para JSON com timestamp"""
    db = Database()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_railway_{timestamp}.json"

    backup = {
        'data_backup': datetime.now().isoformat(),
        'caixinhas': [],
        'transacoes': [],
        'gastos_recorrentes': [],
        'pagamentos_recorrentes': [],
        'estabelecimentos': [],
        'configuracoes': []
    }

    print(f"🔄 Iniciando backup do banco de dados...")

    # Exporta caixinhas
    caixinhas = db.session.query(Caixinha).all()
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
    transacoes = db.session.query(Transacao).all()
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
    gastos_rec = db.session.query(GastoRecorrente).all()
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
    pagamentos = db.session.query(PagamentoRecorrente).all()
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
    estabelecimentos = db.session.query(EstabelecimentoConhecido).all()
    for e in estabelecimentos:
        backup['estabelecimentos'].append({
            'id': e.id,
            'user_id': e.user_id,
            'nome_estabelecimento': e.nome_estabelecimento,
            'caixinha_id': e.caixinha_id
        })

    # Exporta configurações
    configs = db.session.query(ConfiguracaoUsuario).all()
    for cfg in configs:
        backup['configuracoes'].append({
            'user_id': cfg.user_id,
            'dia_fechamento': cfg.dia_fechamento
        })

    # Salva em arquivo JSON
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)

    print(f"✅ Backup concluído com sucesso!")
    print(f"📊 Estatísticas:")
    print(f"   - Caixinhas: {len(backup['caixinhas'])}")
    print(f"   - Transações: {len(backup['transacoes'])}")
    print(f"   - Gastos Recorrentes: {len(backup['gastos_recorrentes'])}")
    print(f"   - Pagamentos Recorrentes: {len(backup['pagamentos_recorrentes'])}")
    print(f"   - Estabelecimentos: {len(backup['estabelecimentos'])}")
    print(f"   - Configurações: {len(backup['configuracoes'])}")
    print(f"\n💾 Arquivo salvo: {filename}")
    print(f"\n⚠️  IMPORTANTE: Salve este arquivo em local seguro!")

if __name__ == '__main__':
    fazer_backup()
