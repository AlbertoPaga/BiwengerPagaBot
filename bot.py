import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)


from config import TELEGRAM_TOKEN

from biwenger import (
    obtener_ligas,
    cargar_liga
)



logging.basicConfig(
    level=logging.INFO
)



CACHE={}



async def liga(
    update,
    context
):

    ligas = obtener_ligas()


    botones=[]


    for l in ligas:

        botones.append(
            [
                InlineKeyboardButton(
                    l["name"],
                    callback_data=str(
                        l["id"]
                    )
                )
            ]
        )


    await update.message.reply_text(
        "Selecciona liga:",
        reply_markup=
        InlineKeyboardMarkup(
            botones
        )
    )



async def elegir_liga(
    update,
    context
):

    query = update.callback_query

    await query.answer()


    liga_id=int(
        query.data
    )


    context.user_data[
        "liga"
    ] = liga_id


    await query.edit_message_text(
        "✅ Liga seleccionada"
    )



async def informe(
    update,
    context
):


    liga_id=context.user_data.get(
        "liga"
    )


    if not liga_id:

        await update.message.reply_text(
            "Usa primero /liga"
        )

        return



    usuarios,movimientos = cargar_liga(
        liga_id
    )


    texto="🏆 PATRIMONIO\n\n"


    for u in usuarios:

        texto += (
            f"• {u['name']}\n"
        )


    await update.message.reply_text(
        texto
    )



async def movimientos(
    update,
    context
):

    liga_id=context.user_data.get(
        "liga"
    )


    if not liga_id:

        await update.message.reply_text(
            "Usa primero /liga"
        )

        return



    usuarios,movs = cargar_liga(
        liga_id
    )


    texto="🔄 MOVIMIENTOS\n\n"


    for m in movs[:15]:

        texto += (
            f"{m.get('type')}\n"
        )


    await update.message.reply_text(
        texto
    )



async def ayuda(
    update,
    context
):

    await update.message.reply_text(
        """
/liga - elegir liga

/informe - ranking

/movimientos - compras y ventas
"""
    )



def main():


    app=(
        Application
        .builder()
        .token(
            TELEGRAM_TOKEN
        )
        .build()
    )


    app.add_handler(
        CommandHandler(
            "liga",
            liga
        )
    )


    app.add_handler(
        CallbackQueryHandler(
            elegir_liga
        )
    )


    app.add_handler(
        CommandHandler(
            "informe",
            informe
        )
    )


    app.add_handler(
        CommandHandler(
            "movimientos",
            movimientos
        )
    )


    app.add_handler(
        CommandHandler(
            "ayuda",
            ayuda
        )
    )


    print(
        "Bot iniciado..."
    )


    app.run_polling(
        drop_pending_updates=True
    )



if __name__=="__main__":

    main()