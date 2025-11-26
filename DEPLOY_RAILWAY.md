# Deploy no Railway - Guia Completo

## 📋 Checklist Pré-Deploy

✅ Backup criado: `backup_dados.json`
✅ Script de importação: `import_data.py`
✅ Auto-import configurado em `bot_v2.py`
✅ Arquivos de deploy: `Procfile`, `runtime.txt`, `requirements.txt`

## 🚀 Passo a Passo

### 1. Commit e Push para GitHub

```bash
cd c:\F\Scripts\Python\cartao-bot

# Adiciona todos os arquivos
git add .

# Commit
git commit -m "Add auto-import feature and backup data"

# Push para GitHub
git push
```

### 2. Deploy no Railway

1. Acesse [railway.app](https://railway.app)
2. Faça login com GitHub
3. Clique em **"New Project"**
4. Escolha **"Deploy from GitHub repo"**
5. Selecione o repositório `cartao-bot`
6. Aguarde o build

### 3. Configurar Variáveis de Ambiente

No Railway, vá em **Variables** e adicione:

```
TELEGRAM_BOT_TOKEN=seu_token_bot_father
GEMINI_API_KEY=sua_gemini_key
ALLOWED_USER_ID=2146228904,559513773
```

### 4. Verificar Deploy

Vá em **Deployments** → **View Logs**

Procure por estas linhas:
```
Backup encontrado! Importando dados...
OK 7 caixinhas processadas
OK 18 transacoes importadas
OK 16 estabelecimentos processados
OK 1 configuracoes importadas
Importacao concluida com sucesso!
Bot V3 iniciado com processamento de imagem, audio e reset automático!
```

### 5. Testar no Telegram

Envie para o bot:
- `/start` - Deve responder
- `/caixinhas` - Deve mostrar suas 7 caixinhas com os valores
- `/historico` - Deve mostrar as 18 transações

## 🎉 Pronto!

Seu bot está rodando 24/7 no Railway com todos os dados importados!

## 📊 Monitoramento

- **Logs**: Railway Dashboard → View Logs
- **Créditos**: Railway Dashboard → Usage
- **Redeploy**: Push novo commit no GitHub

## ⚠️ Problemas Comuns

### Bot não inicia
- Verifique as variáveis de ambiente
- Confira os logs de erro

### Dados não importaram
- Verifique se `backup_dados.json` está no repositório
- Confira os logs: deve aparecer "Backup encontrado!"

### Bot está offline
- Veja o status no Railway Dashboard
- Pode ter excedido o limite de créditos ($5/mês)

## 💡 Dicas

- Mantenha o `.gitignore` atualizado (não enviar .env, .db)
- Use `.env` local, mas variáveis de ambiente no Railway
- Monitore os créditos mensalmente
