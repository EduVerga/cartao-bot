# Como Importar Dados para o Railway

## Passo 1: Exportar Dados Locais (JÁ FEITO!)

✅ Você já tem o arquivo `backup_dados.json` com todos os dados exportados:
- 7 caixinhas
- 18 transações
- 16 estabelecimentos
- 1 configuração

## Passo 2: Enviar backup_dados.json para o Railway

### Opção A: Via GitHub (Recomendado)

1. Adicione o backup ao repositório:
```bash
git add backup_dados.json import_data.py
git commit -m "Add backup data for import"
git push
```

2. No Railway, o deploy será automático

### Opção B: Upload Manual via Railway CLI

```bash
railway up backup_dados.json
railway run python import_data.py
```

## Passo 3: Importar no Railway

1. Acesse o **Dashboard do Railway**
2. Vá em **Deployments** do seu bot
3. Clique nos **3 pontinhos** → **View Logs**
4. Abra o **Shell** (ícone de terminal)
5. Execute:

```bash
python import_data.py
```

Pronto! Todos os dados serão importados.

## Verificação

Após importar, teste no Telegram:
- `/caixinhas` - Deve mostrar suas 7 caixinhas
- `/historico` - Deve mostrar as 18 transações

## Importante

- ⚠️ Execute `import_data.py` APENAS UMA VEZ
- ⚠️ Executar novamente pode duplicar dados (ele tem proteção, mas evite)
- ✅ O script ignora caixinhas/estabelecimentos duplicados automaticamente

## Alternativa: Via Variável de Ambiente

Se o Railway não permitir upload de arquivos, você pode:

1. Copiar o conteúdo de `backup_dados.json`
2. Criar uma variável de ambiente `BACKUP_DATA` no Railway
3. Colar o JSON lá
4. Modificar `import_data.py` para ler da variável

Mas a opção A (GitHub) é mais fácil!
