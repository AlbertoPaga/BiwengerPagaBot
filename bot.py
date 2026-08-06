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


MAX_TELEGRAM = 4000


async def enviar_largo(update, texto):

    """
    Telegram permite unos 4096 caracteres.
    Divide mensajes largos automáticamente.
    """

    if not texto:
        texto = "Sin datos"

    partes = [
        texto[i:i + MAX_TELEGRAM]
        for i in range(0, len(texto), MAX_TELEGRAM)
    ]

    for parte in partes:

        await update.message.reply_text(
            parte
        )


async def start(update, context):

    await update.message.reply_text(
        """
🤖 Bot Biwenger activo

Comandos:

/liga - seleccionar liga
/informe - ver jugadores
/movimientos - ver movimientos
/ayuda - ayuda
"""
    )


async def liga(update, context):

    try:

        ligas = obtener_ligas()

        botones = []

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

        logging.exception(
            "ERROR LIGA"
        )

        await update.message.reply_text(
            f"Error obteniendo ligas:\n{e}"
        )


async def elegir_liga(update, context):

    query = update.callback_query

    await query.answer()


    liga_id = int(
        query.data
    )


    context.user_data["liga"] = liga_id


    await query.edit_message_text(
        "✅ Liga seleccionada"
    )


async def informe(update, context):


    liga_id = context.user_data.get(
        "liga"
    )


    if not liga_id:

        await update.message.reply_text(
            "Usa primero /liga"
        )

        return


    try:

        usuarios, movs = cargar_liga(
            liga_id
        )


        texto = "🏆 PATRIMONIO\n\n"


        if not usuarios:

            texto += "No hay usuarios"

        else:

            for u in usuarios:

                nombre = u.get(
                    "name",
                    "Sin nombre"
                )

                texto += (
                    f"• {nombre}\n"
                )


        await enviar_largo(
            update,
            texto
        )


    except Exception as e:

        logging.exception(
            "ERROR INFORME"
        )

        await update.message.reply_text(
            f"Error:\n{e}"
        )



async def movimientos(update, context):


    liga_id = context.user_data.get(
        "liga"
    )


    if not liga_id:

        await update.message.reply_text(
            "Usa primero /liga"
        )

        return


    try:

        usuarios, movs = cargar_liga(
            liga_id
        )


        texto = "🔄 MOVIMIENTOS\n\n"


        if not movs:

            texto += "Sin movimientos"


        else:

            for m in movs[:20]:

                texto += (
                    f"• {str(m)[:200]}\n"
                )


        await enviar_largo(
            update,
            texto
        )


    except Exception as e:

        logging.exception(
            "ERROR MOVIMIENTOS"
        )

        await update.message.reply_text(
            f"Error:\n{e}"
        )



async def ayuda(update, context):

    await update.message.reply_text(
        """
📚 Comandos:

/liga
Seleccionar liga Biwenger

/informe
Ver usuarios

/movimientos
Últimos movimientos

/start
Iniciar bot
"""
    )



async def error_handler(update, context):

    logging.error(
        "ERROR GLOBAL: %s",
        context.error
    )



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
            "start",
            start
        )
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



if __name__ == "__main__":

    main()