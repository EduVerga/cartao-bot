#!/usr/bin/env python3
"""
Script para testar persistência de dados entre deploys
"""
import os
import json
from datetime import datetime

PERSISTENCE_FILE = '/app/data/persistence_test.json'

def test_persistence():
    """Testa se dados persistem entre deploys"""

    print("\n" + "="*60)
    print("TESTE DE PERSISTÊNCIA DE DADOS")
    print("="*60 + "\n")

    # Informações sobre este deploy
    deploy_info = {
        'timestamp': datetime.now().isoformat(),
        'deploy_count': 1
    }

    # Verifica se arquivo de teste existe
    if os.path.exists(PERSISTENCE_FILE):
        print("✅ Arquivo de persistência EXISTE!")
        print("   Isso significa que dados SOBREVIVERAM ao deploy!\n")

        try:
            with open(PERSISTENCE_FILE, 'r') as f:
                data = json.load(f)

            print(f"📅 Último deploy: {data.get('timestamp')}")
            print(f"🔢 Número de deploys: {data.get('deploy_count')}")

            # Incrementa contador
            deploy_info['deploy_count'] = data.get('deploy_count', 0) + 1

        except Exception as e:
            print(f"⚠️  Erro ao ler arquivo: {e}")
    else:
        print("❌ Arquivo de persistência NÃO existe")
        print("   Este é o PRIMEIRO deploy com volume")
        print("   OU o volume foi RECRIADO\n")

    # Salva informações deste deploy
    try:
        with open(PERSISTENCE_FILE, 'w') as f:
            json.dump(deploy_info, f, indent=2)
        print(f"✅ Arquivo de teste salvo: {PERSISTENCE_FILE}")
        print(f"   Deploy #{deploy_info['deploy_count']}\n")
    except Exception as e:
        print(f"❌ ERRO ao salvar arquivo: {e}")
        print("   Volume pode não ter permissão de escrita!\n")

    # Lista todos os arquivos no volume
    print("📂 Arquivos em /app/data:")
    try:
        files = os.listdir('/app/data')
        for f in files:
            path = os.path.join('/app/data', f)
            size = os.path.getsize(path)
            print(f"   - {f} ({size} bytes)")
    except Exception as e:
        print(f"   Erro: {e}")

    print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    test_persistence()
