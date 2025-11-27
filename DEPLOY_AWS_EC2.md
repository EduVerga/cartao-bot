# Deploy no AWS EC2 Free Tier - Guia Completo

## 🎯 Por que AWS EC2?

- ✅ **12 meses gratuitos** (não apenas 30 dias como Railway)
- ✅ 750 horas/mês de t2.micro (suficiente para 24/7)
- ✅ Controle total do servidor
- ✅ Após 12 meses: ~$8-10/mês (mais barato que Railway)

## 📋 Pré-requisitos

- Conta AWS (cartão de crédito necessário, mas não será cobrado no Free Tier)
- Conhecimento básico de terminal Linux

## 🚀 Passo a Passo Completo

### 1. Criar Instância EC2

1. Acesse [AWS Console](https://console.aws.amazon.com)
2. Vá em **Services** → **EC2**
3. Clique em **Launch Instance**
4. Configure:

**Nome e Tags:**
- Name: `cartao-bot`

**Application and OS Images:**
- AMI: **Ubuntu Server 22.04 LTS** (Free tier eligible)

**Instance Type:**
- **t2.micro** (1 vCPU, 1GB RAM) - Free tier eligible

**Key pair (login):**
- Clique em **Create new key pair**
- Name: `cartao-bot-key`
- Key pair type: RSA
- Private key file format: `.pem`
- **BAIXE E GUARDE ESTE ARQUIVO!** Você não conseguirá baixar de novo

**Network settings:**
- Security group: **Create security group**
- Allow SSH traffic from: **My IP** (mais seguro)
  - Ou **Anywhere** (0.0.0.0/0) se você tem IP dinâmico

**Storage:**
- 8 GB (padrão) - Suficiente para o bot

5. Clique em **Launch Instance**

### 2. Conectar via SSH

#### No Windows:
```bash
# Ajuste permissões da chave (PowerShell)
icacls cartao-bot-key.pem /inheritance:r
icacls cartao-bot-key.pem /grant:r "%username%:R"

# Conecte via SSH
ssh -i cartao-bot-key.pem ubuntu@SEU_IP_PUBLICO
```

#### No Mac/Linux:
```bash
# Ajuste permissões
chmod 400 cartao-bot-key.pem

# Conecte
ssh -i cartao-bot-key.pem ubuntu@SEU_IP_PUBLICO
```

**Onde encontrar o IP público?**
- No console EC2, clique na instância
- Veja em **Public IPv4 address**

### 3. Instalar Dependências no Servidor

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.11, pip e git
sudo apt install python3.11 python3.11-venv python3-pip git -y

# Clonar repositório
git clone https://github.com/EduVerga/cartao-bot.git
cd cartao-bot

# Criar ambiente virtual
python3.11 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente

```bash
# Criar arquivo .env
nano .env
```

Cole (substitua pelos seus valores):
```
TELEGRAM_BOT_TOKEN=seu_token_bot_father
GEMINI_API_KEY=sua_gemini_key
ALLOWED_USER_ID=2146228904,559513773
```

**Salvar:** Ctrl+O, Enter, Ctrl+X

### 5. Testar o Bot

```bash
# Ativa o ambiente virtual
source venv/bin/activate

# Roda o bot
python bot_v2.py
```

Se funcionar, você verá:
```
Bot V3 iniciado com processamento de imagem, audio e reset automático!
```

Teste no Telegram com `/start`

**Pare o bot:** Ctrl+C

### 6. Configurar como Serviço (Rodar 24/7)

```bash
# Copiar arquivo de serviço
sudo cp cartao-bot.service /etc/systemd/system/

# Recarregar systemd
sudo systemctl daemon-reload

# Iniciar serviço
sudo systemctl start cartao-bot

# Verificar status
sudo systemctl status cartao-bot

# Habilitar para iniciar automaticamente no boot
sudo systemctl enable cartao-bot
```

### 7. Comandos Úteis

```bash
# Ver logs em tempo real
sudo journalctl -u cartao-bot -f

# Parar bot
sudo systemctl stop cartao-bot

# Reiniciar bot
sudo systemctl restart cartao-bot

# Ver status
sudo systemctl status cartao-bot
```

## 🔄 Atualizar o Bot

Quando você fizer mudanças no código:

```bash
# Conecte via SSH
ssh -i cartao-bot-key.pem ubuntu@SEU_IP_PUBLICO

# Entre no diretório
cd cartao-bot

# Puxar mudanças do GitHub
git pull

# Reiniciar serviço
sudo systemctl restart cartao-bot

# Verificar logs
sudo journalctl -u cartao-bot -f
```

## 📊 Monitoramento

### Ver uso de recursos:
```bash
# CPU e memória
htop

# Espaço em disco
df -h

# Processos Python
ps aux | grep python
```

### Ver logs do bot:
```bash
# Últimas 100 linhas
sudo journalctl -u cartao-bot -n 100

# Em tempo real
sudo journalctl -u cartao-bot -f
```

## 🔒 Segurança

### Recomendações:
1. **Nunca compartilhe sua chave .pem**
2. **Use IP específico no Security Group** (não 0.0.0.0/0)
3. **Mantenha sistema atualizado:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
4. **Configure firewall (opcional):**
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw enable
   ```

## 💰 Custos

### Free Tier (12 meses):
- ✅ 750 horas/mês de t2.micro = GRÁTIS
- ✅ 30 GB de storage EBS = GRÁTIS
- ✅ 15 GB de bandwidth = GRÁTIS

### Após Free Tier:
- t2.micro: ~$8-10/mês
- Storage: ~$1/mês (8GB)
- **Total: ~$9-11/mês**

Ainda mais barato que Railway após o trial!

## ⚠️ Importante

- **Monitore o AWS Billing Dashboard** mensalmente
- Configure **Billing Alerts** para ser avisado se ultrapassar limites
- A instância EC2 precisa estar **sempre ligada** (24/7)
- Não exceda 750 horas/mês (= 31 dias x 24h)

## 🆚 Comparação: Railway vs AWS EC2

| Feature | Railway | AWS EC2 |
|---------|---------|---------|
| Período Grátis | 30 dias trial | 12 meses |
| Configuração | Fácil (GUI) | Média (SSH) |
| Controle | Limitado | Total |
| Custo pós-trial | $10-20/mês | $9-11/mês |
| Manutenção | Zero | Você gerencia |
| Ideal para | Iniciantes | Quem quer aprender AWS |

## 🎓 Próximos Passos

Depois de dominar EC2, você pode:
- Configurar domínio personalizado
- Adicionar SSL/HTTPS
- Configurar backup automático
- Migrar para banco PostgreSQL (RDS Free Tier)
- Configurar monitoring (CloudWatch)

---

**Dúvidas?** Consulte a [documentação oficial da AWS](https://docs.aws.amazon.com/ec2/)
