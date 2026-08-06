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



async def liga(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

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
            reply_markup=InlineKeyboardMarkup(
                botones
            )
        )


    except Exception as e:

        print(
            "ERROR LIGA:",
            e
        )


        await update.message.reply_text(
            "❌ No se pudieron cargar las ligas."
        )



async def elegir_liga(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):


    try:

        query = update.callback_query


        await query.answer()


        liga_id=int(
            query.data
        )


        context.user_data[
            "liga"
        ] = liga_id


        await query.edit_message_text(
            "✅ Liga seleccionada correctamente"
        )


    except Exception as e:

        print(
            "ERROR SELECCION LIGA:",
            e
        )



async def informe(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):


    try:

        liga_id=context.user_data.get(
            "liga"
        )


        if not liga_id:

            await update.message.reply_text(
                "Primero usa /liga"
            )

            return



        usuarios,movimientos=cargar_liga(
            liga_id
        )


        texto="🏆 PATRIMONIO\n\n"


        if not usuarios:

            texto+="No hay usuarios disponibles."


        else:

            for u in usuarios:

                texto+=(
                    f"• {u.get('name','Sin nombre')}\n"
                )



        await update.message.reply_text(
            texto
        )



    except Exception as e:


        print(
            "ERROR INFORME:",
            e
        )


        await update.message.reply_text(
            "❌ Error obteniendo informe."
        )



async def movimientos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):


    try:

        liga_id=context.user_data.get(
            "liga"
        )


        if not liga_id:

            await update.message.reply_text(
                "Primero usa /liga"
            )

            return



        usuarios,movs=cargar_liga(
            liga_id
        )


        texto="🔄 MOVIMIENTOS\n\n"


        if not movs:

            texto+="No hay movimientos."

        else:

            for m in movs[:15]:

                texto+=(
                    f"• {m.get('type','Movimiento')}\n"
                )



        await update.message.reply_text(
            texto
        )



    except Exception as e:


        print(
            "ERROR MOVIMIENTOS:",
            e
        )


        await update.message.reply_text(
            "❌ Error obteniendo movimientos."
        )



async def ayuda(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):


    await update.message.reply_text(
        """
⚽ Bot Biwenger

/liga
Seleccionar liga

/informe
Ranking usuarios

/movimientos
Compras y ventas

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


    try:

        if update and update.message:

            await update.message.reply_text(
                "❌ Error interno del bot."
            )

    except:

        pass



def main():


    app = (
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