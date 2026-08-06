import logging


from telegram import (
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



async def liga(
    update,
    context
):


    try:

        ligas=obtener_ligas()


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
            reply_markup=InlineKeyboardMarkup(
                botones
            )
        )


    except Exception as e:

        print(
            "ERROR LIGA:",
            e
        )



async def elegir_liga(
    update,
    context
):


    query=update.callback_query


    await query.answer()


    liga_id=int(
        query.data
    )


    context.user_data["liga"]=liga_id


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



    usuarios,movs=cargar_liga(
        liga_id
    )


    texto="🏆 PATRIMONIO\n\n"


    if not usuarios:

        texto+="No se encontraron usuarios"


    else:

        for u in usuarios:

            texto+=(
                f"• {u.get('name','Sin nombre')}\n"
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



    usuarios,movs=cargar_liga(
        liga_id
    )


    texto="🔄 MOVIMIENTOS\n\n"


    if not movs:

        texto+="Sin movimientos"


    else:

        for m in movs[:15]:

            texto+=(
                f"• {m}\n"
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

/movimientos - movimientos
"""
    )



async def error_handler(
    update,
    context
):

    print(
        "ERROR GLOBAL:",
        context.error
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


    app.add_error_handler(
        error_handler
    )


    print(
        "Bot iniciado..."
    )


    app.run_polling(
        drop_pending_updates=True
    )



if __name__=="__main__":

    main()