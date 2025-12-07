#!/usr/bin/env python3
"""
Script para verificar configuração de volume ao iniciar o bot
"""
import os
import sys

def check_volume_setup():
    """Verifica se volume persistente está configurado corretamente"""

    print("=" * 60)
    print("VERIFICAÇÃO DE VOLUME PERSISTENTE")
    print("=" * 60)

    # 1. Verifica variável de ambiente
    db_path = os.getenv('DB_PATH', 'NÃO CONFIGURADO')
    print(f"\n📁 DB_PATH: {db_path}")

    # 2. Verifica se /app/data existe
    if os.path.exists('/app/data'):
        print("✅ Diretório /app/data EXISTE")

        # Verifica permissões
        if os.access('/app/data', os.W_OK):
            print("✅ Diretório /app/data tem permissão de ESCRITA")
        else:
            print("❌ Diretório /app/data NÃO tem permissão de escrita!")

        # Lista conteúdo
        try:
            arquivos = os.listdir('/app/data')
            print(f"📂 Arquivos em /app/data: {arquivos if arquivos else '(vazio)'}")
        except Exception as e:
            print(f"❌ Erro ao listar /app/data: {e}")
    else:
        print("❌ Diretório /app/data NÃO EXISTE!")
        print("⚠️  Volume persistente NÃO foi montado!")

    # 3. Verifica diretório atual
    cwd = os.getcwd()
    print(f"\n📂 Diretório atual: {cwd}")

    # 4. Verifica se banco já existe
    if db_path != 'NÃO CONFIGURADO':
        if os.path.exists(db_path):
            tamanho = os.path.getsize(db_path)
            print(f"✅ Banco {db_path} EXISTE ({tamanho} bytes)")
        else:
            print(f"⚠️  Banco {db_path} ainda NÃO existe (será criado)")

    # 5. Verifica se existe banco no local errado
    banco_errado = 'cartao_bot.db'
    if os.path.exists(banco_errado):
        tamanho = os.path.getsize(banco_errado)
        print(f"⚠️  ATENÇÃO: Banco em local ERRADO: {banco_errado} ({tamanho} bytes)")
        print(f"    Este banco será PERDIDO em cada deploy!")

    # 6. Diagnóstico final
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO:")
    print("=" * 60)

    if db_path == 'NÃO CONFIGURADO':
        print("❌ ERRO: Variável DB_PATH não configurada!")
        print("   Configure no Railway: DB_PATH=/app/data/cartao.db")
        return False

    if not os.path.exists('/app/data'):
        print("❌ ERRO CRÍTICO: Volume /app/data não foi montado!")
        print("   Verifique railway.toml e configuração de volumes")
        print("   Dados SERÃO PERDIDOS a cada deploy!")
        return False

    if not db_path.startswith('/app/data'):
        print(f"⚠️  AVISO: DB_PATH não aponta para volume persistente!")
        print(f"   DB_PATH atual: {db_path}")
        print(f"   Deveria ser: /app/data/cartao.db")
        print("   Dados podem ser perdidos!")
        return False

    print("✅ Configuração CORRETA!")
    print(f"   Banco será salvo em: {db_path}")
    print("   Volume persistente está montado")
    print("   Dados sobreviverão a deploys")
    return True

if __name__ == '__main__':
    sucesso = check_volume_setup()
    print("=" * 60)

    if not sucesso:
        print("\n⚠️  AVISO: Problemas detectados na configuração!")
        print("O bot continuará rodando, mas dados podem ser perdidos.\n")
    else:
        print("\n✅ Tudo OK! O bot está configurado corretamente.\n")
