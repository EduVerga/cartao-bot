"""
Script para restaurar backup do banco de dados
ATENÇÃO: Este script IRÁ SUBSTITUIR todos os dados atuais!
"""
import os
import sys
import json
from datetime import datetime
from database import Database, Caixinha, Transacao, GastoRecorrente, PagamentoRecorrente, EstabelecimentoConhecido, ConfiguracaoUsuario

def restaurar_backup(arquivo_backup):
    """Restaura dados de um arquivo de backup JSON"""

    if not os.path.exists(arquivo_backup):
        print(f"❌ Arquivo não encontrado: {arquivo_backup}")
        return False

    print(f"⚠️  ATENÇÃO: Este processo irá SUBSTITUIR todos os dados atuais!")
    print(f"📁 Arquivo de backup: {arquivo_backup}")

    # Confirmação de segurança
    confirmacao = input("\nDigite 'CONFIRMAR' para continuar: ")
    if confirmacao != 'CONFIRMAR':
        print("❌ Operação cancelada.")
        return False

    db = Database()

    try:
        # Carrega backup
        with open(arquivo_backup, 'r', encoding='utf-8') as f:
            backup = json.load(f)

        print(f"\n🔄 Iniciando restauração...")
        print(f"📅 Data do backup: {backup.get('data_backup', 'Desconhecida')}")

        # LIMPA TABELAS (CUIDADO!)
        print("\n🗑️  Limpando dados existentes...")
        db.session.query(PagamentoRecorrente).delete()
        db.session.query(Transacao).delete()
        db.session.query(EstabelecimentoConhecido).delete()
        db.session.query(GastoRecorrente).delete()
        db.session.query(Caixinha).delete()
        db.session.query(ConfiguracaoUsuario).delete()
        db.session.commit()

        # Restaura Caixinhas
        print(f"📦 Restaurando {len(backup['caixinhas'])} caixinhas...")
        for c in backup['caixinhas']:
            caixinha = Caixinha(
                id=c['id'],
                user_id=c['user_id'],
                nome=c['nome'],
                limite=c['limite'],
                gasto_atual=c['gasto_atual'],
                criado_em=datetime.fromisoformat(c['criado_em']) if c['criado_em'] else None
            )
            db.session.add(caixinha)

        # Restaura Transações
        print(f"💳 Restaurando {len(backup['transacoes'])} transações...")
        for t in backup['transacoes']:
            transacao = Transacao(
                id=t['id'],
                user_id=t['user_id'],
                caixinha_id=t['caixinha_id'],
                valor=t['valor'],
                estabelecimento=t['estabelecimento'],
                categoria=t.get('categoria'),
                data_transacao=datetime.fromisoformat(t['data_transacao']) if t['data_transacao'] else None,
                criado_em=datetime.fromisoformat(t['criado_em']) if t['criado_em'] else None
            )
            db.session.add(transacao)

        # Restaura Gastos Recorrentes
        print(f"🔄 Restaurando {len(backup['gastos_recorrentes'])} gastos recorrentes...")
        for g in backup['gastos_recorrentes']:
            gasto = GastoRecorrente(
                id=g['id'],
                user_id=g['user_id'],
                descricao=g['descricao'],
                valor_padrao=g['valor_padrao'],
                dia_vencimento=g['dia_vencimento'],
                caixinha_id=g.get('caixinha_id'),
                ativo=g['ativo'],
                criado_em=datetime.fromisoformat(g['criado_em']) if g['criado_em'] else None
            )
            db.session.add(gasto)

        # Restaura Pagamentos Recorrentes
        print(f"💰 Restaurando {len(backup['pagamentos_recorrentes'])} pagamentos...")
        for p in backup['pagamentos_recorrentes']:
            pagamento = PagamentoRecorrente(
                id=p['id'],
                gasto_recorrente_id=p['gasto_recorrente_id'],
                user_id=p['user_id'],
                mes=p['mes'],
                ano=p['ano'],
                valor=p['valor'],
                pago=p['pago'],
                data_pagamento=datetime.fromisoformat(p['data_pagamento']) if p['data_pagamento'] else None,
                ultimo_lembrete=datetime.fromisoformat(p['ultimo_lembrete']) if p['ultimo_lembrete'] else None
            )
            db.session.add(pagamento)

        # Restaura Estabelecimentos
        print(f"🏪 Restaurando {len(backup['estabelecimentos'])} estabelecimentos...")
        for e in backup['estabelecimentos']:
            estab = EstabelecimentoConhecido(
                id=e['id'],
                user_id=e['user_id'],
                nome_estabelecimento=e['nome_estabelecimento'],
                caixinha_id=e['caixinha_id']
            )
            db.session.add(estab)

        # Restaura Configurações
        print(f"⚙️  Restaurando {len(backup['configuracoes'])} configurações...")
        for cfg in backup['configuracoes']:
            config = ConfiguracaoUsuario(
                user_id=cfg['user_id'],
                dia_fechamento=cfg['dia_fechamento']
            )
            db.session.add(config)

        # Commit final
        db.session.commit()

        print("\n✅ Restauração concluída com sucesso!")
        return True

    except Exception as e:
        print(f"\n❌ Erro durante restauração: {e}")
        db.session.rollback()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("❌ Uso: python restore_backup.py <arquivo_backup.json>")
        print("\nExemplo: python restore_backup.py backup_railway_20241205_143022.json")
        sys.exit(1)

    arquivo = sys.argv[1]
    restaurar_backup(arquivo)
