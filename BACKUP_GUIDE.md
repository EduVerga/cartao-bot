# 🛡️ Guia de Backup e Proteção de Dados

## ⚠️ PROBLEMA ATUAL

Você está perdendo dados a cada deploy porque o Railway **NÃO tem volume persistente configurado**.

Sem volume persistente:
- ✅ Deploy acontece normalmente
- ❌ Banco de dados é criado do zero
- ❌ Todos os dados anteriores são PERDIDOS

## 🎯 SOLUÇÕES

### 1. URGENTE - Fazer Backup AGORA (Antes do próximo deploy)

**No Railway CLI ou via SSH:**

```bash
# 1. Conectar ao Railway
railway login
railway link

# 2. Executar script de backup
railway run python backup_railway.py

# 3. Baixar o arquivo de backup
railway run cat backup_railway_*.json > backup_local.json
```

**Ou adicione um comando de backup ao bot:**

Você pode criar um comando `/backup` no bot que gera e envia o JSON via Telegram.

---

### 2. Configurar Volume Persistente no Railway

**Método 1 - Via Dashboard (Recomendado):**

1. Acesse seu projeto no Railway: https://railway.app/dashboard
2. Clique no seu serviço (bot)
3. Vá em **Settings** → **Volumes**
4. Clique em **+ New Volume**
5. Configure:
   - **Mount Path:** `/app/data`
   - **Size:** 1 GB (suficiente para SQLite)
6. Salve

**Método 2 - Via railway.json:**

Crie arquivo `railway.json` na raiz:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  },
  "volumes": [
    {
      "mountPath": "/app/data"
    }
  ]
}
```

---

### 3. Atualizar o Código para Usar o Volume

**Editar `database.py`:**

```python
# Antes:
DB_PATH = 'cartao.db'

# Depois:
import os
DB_PATH = os.getenv('DB_PATH', '/app/data/cartao.db')
```

**Editar `.env` (localmente):**

```
DB_PATH=cartao_bot.db
```

**No Railway (Environment Variables):**

```
DB_PATH=/app/data/cartao.db
```

---

### 4. Workflow de Deploy Seguro

**ANTES de cada deploy:**

```bash
# 1. Fazer backup dos dados do Railway
railway run python backup_railway.py

# 2. Baixar o backup
railway run cat backup_railway_*.json > backup_$(date +%Y%m%d).json

# 3. Fazer as alterações no código
# (suas mudanças aqui)

# 4. Commit e push
git add .
git commit -m "Descrição das mudanças"
git push

# 5. Se algo der errado, restaurar backup
railway run python restore_backup.py backup_20241205.json
```

---

### 5. Backup Automático Diário

Adicione ao `scheduler_tasks.py`:

```python
async def backup_automatico_diario():
    """Faz backup automático do banco todos os dias"""
    from backup_railway import fazer_backup
    fazer_backup()
    logger.info("Backup automático concluído")
```

E no `bot_v2.py`:

```python
# Agendar backup diário às 4h da manhã
scheduler.add_job(
    backup_automatico_diario,
    trigger='cron',
    hour=4,
    minute=0
)
```

---

## 📋 Checklist de Segurança

### Antes de QUALQUER deploy:

- [ ] Fazer backup manual: `railway run python backup_railway.py`
- [ ] Baixar backup localmente
- [ ] Verificar que `*.db` está no `.gitignore`
- [ ] Confirmar que volume persistente está configurado

### Após deploy:

- [ ] Testar se dados ainda estão lá
- [ ] Se perdeu dados, restaurar backup: `railway run python restore_backup.py backup.json`

---

## 🆘 Recuperação de Emergência

Se você perdeu dados e NÃO fez backup:

1. **PARE TUDO** - Não faça mais nenhum deploy
2. Verifique se Railway tem snapshots automáticos (Settings → Deployments)
3. Faça rollback para deploy anterior se possível
4. Entre em contato com suporte do Railway

---

## 📞 Comandos Úteis

### Fazer backup manual:
```bash
railway run python backup_railway.py
```

### Listar backups:
```bash
railway run ls -lh backup_*.json
```

### Restaurar backup:
```bash
railway run python restore_backup.py backup_20241205.json
```

### Verificar tamanho do banco:
```bash
railway run ls -lh /app/data/cartao.db
```

---

## 🔐 Boas Práticas

1. **Nunca** commite arquivos `.db` no Git
2. **Sempre** faça backup antes de deploy
3. **Configure** volume persistente no Railway
4. **Teste** backup/restore periodicamente
5. **Mantenha** backups locais em lugar seguro

---

## 📝 Notas

- Backups são salvos em formato JSON (human-readable)
- Você pode abrir e editar backups manualmente se necessário
- Backups incluem TODOS os dados: caixinhas, transações, recorrentes, etc.
- Formato do backup é compatível entre versões do bot
