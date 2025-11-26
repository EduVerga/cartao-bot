"""
Melhorias para o bot - Sistema de confirmação e callbacks
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import logging

logger = logging.getLogger(__name__)

# Dicionário temporário para armazenar dados pendentes de confirmação
pending_transactions = {}


async def processar_imagem_com_confirmacao(update: Update, context: ContextTypes.DEFAULT_TYPE, db, processor):
    """Processa imagem do comprovante com sistema de confirmação"""
    import os
    user_id = update.effective_user.id

    # Verifica se usuário tem caixinhas
    caixinhas = db.listar_caixinhas(user_id)
    if not caixinhas:
        await update.message.reply_text(
            "❌ Você precisa criar pelo menos uma caixinha primeiro!\n\n"
            "Use: /criar <nome> <limite>\n"
            "Exemplo: /criar Alimentação 1000"
        )
        return

    await update.message.reply_text("🔍 Analisando comprovante...")

    try:
        # Download da imagem
        logger.info(f"Baixando imagem do usuário {user_id}")
        photo = await update.message.photo[-1].get_file()
        image_path = f"temp_{user_id}.jpg"
        await photo.download_to_drive(image_path)
        logger.info(f"Imagem salva em: {image_path}")

        # Processa com Gemini
        logger.info("Processando comprovante com Gemini...")
        dados = processor.processar_comprovante(image_path)
        logger.info(f"Dados extraídos: {dados}")

        # Remove arquivo temporário
        try:
            if os.path.exists(image_path):
                import time
                time.sleep(0.1)
                os.remove(image_path)
        except Exception as e:
            logger.warning(f"Não foi possível remover arquivo temporário: {e}")

        if not dados or not dados['valor']:
            await update.message.reply_text(
                "❌ Não consegui extrair as informações do comprovante.\n"
                "Tente tirar uma foto mais clara ou enviar outro comprovante."
            )
            logger.warning(f"Falha ao extrair dados do comprovante: {dados}")
            return

        estabelecimento = dados['estabelecimento'] or "Não identificado"

        # NOVIDADE: Verifica se o estabelecimento já é conhecido
        estabelecimento_conhecido = db.buscar_estabelecimento_conhecido(user_id, estabelecimento)

        if estabelecimento_conhecido:
            # Estabelecimento já conhecido - adiciona direto
            caixinha = estabelecimento_conhecido.caixinha

            transacao = db.adicionar_transacao(
                user_id=user_id,
                caixinha_id=caixinha.id,
                valor=dados['valor'],
                estabelecimento=estabelecimento,
                categoria=caixinha.nome,
                data_transacao=dados['data']
            )

            db.session.refresh(caixinha)
            percentual = caixinha.percentual_usado
            emoji_alerta = "✅" if percentual < 50 else "⚠️" if percentual < 80 else "🚨"

            mensagem = f"""
{emoji_alerta} **Compra registrada!**

🏪 **Estabelecimento:** {estabelecimento}
💰 **Valor:** R$ {dados['valor']:.2f}
📅 **Data:** {dados['data'].strftime('%d/%m/%Y')}

📦 **Caixinha:** {caixinha.nome}
📊 **Gasto:** R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}
💵 **Restante:** R$ {caixinha.saldo_restante:.2f}
📈 **{percentual:.1f}% usado**
"""

            if percentual >= 100:
                mensagem += "\n🚨 **ATENÇÃO: Limite ultrapassado!**"
            elif percentual >= 80:
                mensagem += "\n⚠️ **Atenção: Você já usou mais de 80% do limite!**"

            await update.message.reply_text(mensagem)

        else:
            # NOVIDADE: Estabelecimento desconhecido - pede confirmação
            categoria_sugerida = dados['categoria_sugerida']
            caixinha_sugerida = db.buscar_caixinha_por_categoria(user_id, categoria_sugerida)

            # Se não encontrou pela categoria, tenta com IA
            if not caixinha_sugerida:
                nomes_caixinhas = [c.nome for c in caixinhas]
                categoria_encontrada = processor.categorizar_estabelecimento(
                    estabelecimento,
                    nomes_caixinhas
                )
                if categoria_encontrada:
                    caixinha_sugerida = db.buscar_caixinha_por_categoria(user_id, categoria_encontrada)

            # Se ainda não encontrou, usa a primeira
            if not caixinha_sugerida:
                caixinha_sugerida = caixinhas[0]

            # Armazena dados temporariamente
            transaction_id = f"{user_id}_{int(time.time())}"
            pending_transactions[transaction_id] = {
                'user_id': user_id,
                'valor': dados['valor'],
                'estabelecimento': estabelecimento,
                'data': dados['data'],
                'caixinha_sugerida_id': caixinha_sugerida.id
            }

            # Cria botões de confirmação
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirmar", callback_data=f"confirm_{transaction_id}"),
                    InlineKeyboardButton("❌ Mudar categoria", callback_data=f"change_{transaction_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            mensagem_confirmacao = f"""
🆕 **Novo estabelecimento detectado!**

🏪 **Estabelecimento:** {estabelecimento}
💰 **Valor:** R$ {dados['valor']:.2f}
📅 **Data:** {dados['data'].strftime('%d/%m/%Y')}

📦 **Categoria sugerida:** {caixinha_sugerida.nome}

A categoria está correta?
"""

            await update.message.reply_text(mensagem_confirmacao, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Erro ao processar imagem: {e}")
        await update.message.reply_text(
            "❌ Ocorreu um erro ao processar o comprovante. Tente novamente."
        )


async def callback_confirmacao(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handler para os botões de confirmação"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data.startswith("confirm_"):
        transaction_id = data.replace("confirm_", "")

        if transaction_id not in pending_transactions:
            await query.edit_message_text("❌ Esta transação expirou. Envie o comprovante novamente.")
            return

        trans_data = pending_transactions[transaction_id]

        # Adiciona a transação
        caixinha = db.session.query(db.session.query('caixinhas')).get(trans_data['caixinha_sugerida_id'])

        transacao = db.adicionar_transacao(
            user_id=trans_data['user_id'],
            caixinha_id=caixinha.id,
            valor=trans_data['valor'],
            estabelecimento=trans_data['estabelecimento'],
            categoria=caixinha.nome,
            data_transacao=trans_data['data']
        )

        # Salva o estabelecimento na memória
        db.salvar_estabelecimento_conhecido(
            user_id=user_id,
            nome_estabelecimento=trans_data['estabelecimento'],
            caixinha_id=caixinha.id
        )

        # Remove dos pendentes
        del pending_transactions[transaction_id]

        db.session.refresh(caixinha)
        percentual = caixinha.percentual_usado
        emoji_alerta = "✅" if percentual < 50 else "⚠️" if percentual < 80 else "🚨"

        mensagem = f"""
{emoji_alerta} **Compra registrada e memorizada!**

🏪 **Estabelecimento:** {trans_data['estabelecimento']}
💰 **Valor:** R$ {trans_data['valor']:.2f}

📦 **Caixinha:** {caixinha.nome}
📊 **Gasto:** R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}
💵 **Restante:** R$ {caixinha.saldo_restante:.2f}
📈 **{percentual:.1f}% usado**

💾 **Da próxima vez, {trans_data['estabelecimento']} será categorizado automaticamente!**
"""

        await query.edit_message_text(mensagem)

    elif data.startswith("change_"):
        transaction_id = data.replace("change_", "")

        if transaction_id not in pending_transactions:
            await query.edit_message_text("❌ Esta transação expirou. Envie o comprovante novamente.")
            return

        trans_data = pending_transactions[transaction_id]
        caixinhas = db.listar_caixinhas(user_id)

        # Cria botões com todas as caixinhas
        keyboard = []
        for caixinha in caixinhas:
            keyboard.append([
                InlineKeyboardButton(
                    f"📦 {caixinha.nome}",
                    callback_data=f"select_{transaction_id}_{caixinha.id}"
                )
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Escolha a categoria correta para **{trans_data['estabelecimento']}**:",
            reply_markup=reply_markup
        )

    elif data.startswith("select_"):
        parts = data.replace("select_", "").split("_")
        transaction_id = "_".join(parts[:-1])
        caixinha_id = int(parts[-1])

        if transaction_id not in pending_transactions:
            await query.edit_message_text("❌ Esta transação expirou. Envie o comprovante novamente.")
            return

        trans_data = pending_transactions[transaction_id]

        # Atualiza a caixinha selecionada
        trans_data['caixinha_sugerida_id'] = caixinha_id

        # Adiciona a transação
        from database import Caixinha
        caixinha = db.session.query(Caixinha).get(caixinha_id)

        transacao = db.adicionar_transacao(
            user_id=trans_data['user_id'],
            caixinha_id=caixinha.id,
            valor=trans_data['valor'],
            estabelecimento=trans_data['estabelecimento'],
            categoria=caixinha.nome,
            data_transacao=trans_data['data']
        )

        # Salva o estabelecimento na memória
        db.salvar_estabelecimento_conhecido(
            user_id=user_id,
            nome_estabelecimento=trans_data['estabelecimento'],
            caixinha_id=caixinha.id
        )

        # Remove dos pendentes
        del pending_transactions[transaction_id]

        db.session.refresh(caixinha)
        percentual = caixinha.percentual_usado
        emoji_alerta = "✅" if percentual < 50 else "⚠️" if percentual < 80 else "🚨"

        mensagem = f"""
{emoji_alerta} **Compra registrada e memorizada!**

🏪 **Estabelecimento:** {trans_data['estabelecimento']}
💰 **Valor:** R$ {trans_data['valor']:.2f}

📦 **Caixinha:** {caixinha.nome}
📊 **Gasto:** R$ {caixinha.gasto_atual:.2f} / R$ {caixinha.limite:.2f}
💵 **Restante:** R$ {caixinha.saldo_restante:.2f}
📈 **{percentual:.1f}% usado**

💾 **Da próxima vez, {trans_data['estabelecimento']} será categorizado automaticamente!**
"""

        await query.edit_message_text(mensagem)
