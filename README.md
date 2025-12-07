# Bot de Controle de Gastos do Cartão de Crédito

Bot do Telegram para controlar gastos do cartão usando sistema de "caixinhas" (categorias com limites).

**Deploy de Teste #2** - Verificando persistência de dados no volume

## Funcionalidades

- 📸 **Processamento de imagens**: Envia foto de nota fiscal/comprovante
- 🎤 **Processamento de áudio**: Grava áudio descrevendo o gasto
- ✍️ **Processamento de texto**: Digite o gasto (ex: "Gastei 50 reais no restaurante")
- 📦 **Sistema de Caixinhas**: Categorias com limites individuais
- 🧠 **Memória de estabelecimentos**: Auto-categorização após primeiro registro
- 📊 **Relatórios automáticos**: No dia de fechamento (22h)
- 🔄 **Reset automático**: No dia após fechamento (00:10)
- 👥 **Multi-usuário**: Suporta múltiplos usuários com dados isolados

## Tecnologias

- Python 3.13
- python-telegram-bot 21.0
- Google Gemini AI (OCR, transcrição de áudio, NLP)
- SQLAlchemy (banco de dados)
- APScheduler (tarefas agendadas)

## Comandos

- `/start` - Inicia o bot
- `/criar <nome> <limite>` - Cria nova caixinha
- `/caixinhas` - Lista todas as caixinhas
- `/historico` - Mostra últimas transações
- `/relatorio` - Relatório mensal completo
- `/fechamento <dia>` - Define dia de fechamento do cartão
- `/resetar_tudo CONFIRMO` - Apaga todos os dados do usuário
- `/ajuda` - Ajuda completa

## Deploy em Render.com (Gratuito)

### 1. Preparação

1. Crie uma conta no [GitHub](https://github.com) (se não tiver)
2. Faça upload deste código para um repositório GitHub
3. Crie conta em [render.com](https://render.com)

### 2. Configuração no Render

1. No Render, clique em **"New +"** → **"Background Worker"**
2. Conecte seu repositório GitHub
3. Configure:
   - **Name**: `cartao-bot` (ou qualquer nome)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot_v2.py`

### 3. Variáveis de Ambiente

Adicione estas variáveis em **"Environment Variables"**:

```
TELEGRAM_BOT_TOKEN=seu_token_aqui
GEMINI_API_KEY=sua_key_aqui
ALLOWED_USER_ID=seu_id_telegram
```

**Como obter:**
- **TELEGRAM_BOT_TOKEN**: Fale com [@BotFather](https://t.me/BotFather) no Telegram
- **GEMINI_API_KEY**: Crie em [aistudio.google.com](https://aistudio.google.com/app/apikey)
- **ALLOWED_USER_ID**: Envie `/start` para [@userinfobot](https://t.me/userinfobot)

### 4. Deploy

Clique em **"Create Background Worker"** e pronto! Seu bot estará online 24/7.

## Multi-usuário

Para adicionar mais usuários, edite a variável `ALLOWED_USER_ID` separando IDs por vírgula:

```
ALLOWED_USER_ID=123456789,987654321,111222333
```

Cada usuário terá seus próprios dados isolados.

## Estrutura do Projeto

```
cartao-bot/
├── bot_v2.py              # Bot principal
├── database.py            # Modelos e operações do banco
├── gemini_processor.py    # Processamento de imagens (OCR)
├── audio_processor.py     # Processamento de áudio e texto
├── scheduler_v3.py        # Tarefas agendadas
├── requirements.txt       # Dependências
├── Procfile              # Configuração para deploy
└── .env                  # Variáveis de ambiente (não versionar!)
```

## Licença

Projeto pessoal - Use livremente!
