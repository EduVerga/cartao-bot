# Guia de Instalação e Configuração

## Passo 1: Criar o Bot no Telegram

1. Abra o Telegram e procure por `@BotFather`
2. Envie o comando `/newbot`
3. Escolha um nome para o bot (ex: "Meu Controle de Gastos")
4. Escolha um username (deve terminar com 'bot', ex: "meu_gastos_bot")
5. O BotFather vai te dar um **token** - guarde ele! Algo como:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567890
   ```

## Passo 2: Obter API Key do Google Gemini (GRATUITA)

1. Acesse: https://makersuite.google.com/app/apikey
2. Faça login com sua conta Google
3. Clique em "Create API Key"
4. Copie a chave gerada (algo como: `AIzaSy...`)

## Passo 3: Configurar o Projeto

1. Navegue até a pasta do projeto:
   ```bash
   cd c:\F\Scripts\Python\cartao-bot
   ```

2. Crie um ambiente virtual Python:
   ```bash
   python -m venv venv
   ```

3. Ative o ambiente virtual:
   - **Windows:**
     ```bash
     venv\Scripts\activate
     ```
   - **Linux/Mac:**
     ```bash
     source venv/bin/activate
     ```

4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

5. Copie o arquivo de exemplo e configure suas chaves:
   ```bash
   copy .env.example .env
   ```

6. Edite o arquivo `.env` e adicione suas chaves:
   ```
   TELEGRAM_BOT_TOKEN=seu_token_do_botfather_aqui
   GEMINI_API_KEY=sua_chave_do_gemini_aqui
   ```

## Passo 4: Executar o Bot

Com o ambiente virtual ativado, execute:

```bash
python bot.py
```

Você deve ver:
```
INFO - Bot iniciado!
```

## Passo 5: Testar no Telegram

1. Abra o Telegram
2. Procure pelo username do seu bot (ex: @meu_gastos_bot)
3. Envie `/start`
4. Crie uma caixinha: `/criar Alimentação 1000`
5. Tire uma foto de um comprovante do Samsung Pay
6. Envie a foto para o bot
7. Aguarde o processamento!

## Comandos Disponíveis

- `/start` - Inicia o bot e mostra instruções
- `/criar <nome> <limite>` - Cria nova caixinha
  - Exemplo: `/criar Transporte 500`
- `/caixinhas` - Lista todas as caixinhas com status
- `/historico` - Mostra últimas 10 transações
- `/ajuda` - Mostra mensagem de ajuda

## Categorias Sugeridas

O bot sugere automaticamente estas categorias:
- Alimentação fora de casa
- Supermercado
- Transporte
- Saúde
- Lazer
- Compras
- Contas
- Outros

**Dica:** Crie caixinhas com os mesmos nomes das categorias para categorização automática perfeita!

## Rodando 24/7

Para manter o bot rodando sempre:

### Opção 1: Servidor na nuvem (Recomendado)
- Railway.app (gratuito)
- Render.com (gratuito)
- DigitalOcean ($5/mês)

### Opção 2: Computador local
Use `screen` (Linux) ou deixe o terminal aberto

### Opção 3: Raspberry Pi
Perfeito para rodar em casa 24/7

## Troubleshooting

**Erro: "Token do Telegram não encontrado"**
- Verifique se o arquivo `.env` existe
- Confirme que o token está correto

**Erro: "Gemini API Key inválida"**
- Confirme que copiou a chave completa
- Verifique se a API está ativa no Google AI Studio

**Bot não responde:**
- Verifique se o script está rodando
- Veja os logs no terminal para erros
- Teste com `/start` primeiro

**Comprovante não é reconhecido:**
- Tire foto mais clara
- Certifique-se que o valor está visível
- Tente outro comprovante

## Estrutura do Projeto

```
cartao-bot/
├── bot.py                  # Bot principal
├── database.py            # Banco de dados SQLite
├── gemini_processor.py    # Processamento de imagens
├── requirements.txt       # Dependências Python
├── .env                   # Suas configurações (não commitar!)
├── .env.example          # Exemplo de configuração
├── README.md             # Documentação
└── SETUP.md              # Este arquivo
```

## Próximos Passos

Depois que testar e funcionar:
1. Adicione mais caixinhas para diferentes categorias
2. Envie vários comprovantes para testar a categorização
3. Use `/caixinhas` para acompanhar seus gastos
4. Configure para rodar 24/7 em um servidor

## Suporte

Se encontrar problemas:
1. Verifique os logs no terminal
2. Confirme que as APIs estão configuradas
3. Teste com comandos simples primeiro (`/start`, `/criar`)
