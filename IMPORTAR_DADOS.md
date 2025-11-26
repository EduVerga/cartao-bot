# Como Importar Dados para o Railway

## ✅ Importação Automática (Configurado!)

O bot agora importa os dados **automaticamente** no primeiro boot!

## Como funciona:

1. **Você faz:** Commit e push do `backup_dados.json` para o GitHub
2. **Railway faz:** Deploy automático
3. **Bot faz:** Detecta o arquivo e importa tudo sozinho!
4. **Bot faz:** Renomeia para `backup_dados.json.imported` (não importa 2x)

## Passo a Passo:

### 1. Adicione o backup ao repositório:

```bash
git add backup_dados.json import_data.py
git commit -m "Add backup data for auto-import"
git push
```

### 2. Railway faz o deploy automático

O bot vai:
- Detectar o arquivo `backup_dados.json`
- Importar automaticamente:
  - 7 caixinhas
  - 18 transações
  - 16 estabelecimentos
  - 1 configuração
- Renomear para `.imported` (não importa de novo)

### 3. Verificação

Confira nos logs do Railway:
```
Backup encontrado! Importando dados...
OK 7 caixinhas processadas
OK 18 transacoes importadas
OK 16 estabelecimentos processados
OK 1 configuracoes importadas
Importacao concluida com sucesso!
```

Teste no Telegram:
- `/caixinhas` - Deve mostrar suas 7 caixinhas
- `/historico` - Deve mostrar as 18 transações

## Importante

- ✅ Importa automaticamente UMA VEZ
- ✅ Não duplica (arquivo é renomeado)
- ✅ Tem proteção contra duplicatas
- ✅ Totalmente automático, zero configuração!
