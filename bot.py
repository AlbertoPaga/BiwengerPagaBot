import logging


from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
)


from config import TELEGRAM_TOKEN


from biwenger import (
    obtener_ligas,
    obtener_nombre_liga,
    obtener_informe,
    obtener_mercado_completo,
    obtener_mercado_24h,
)


logging.basicConfig(
    level=logging.INFO
)


MAX_TELEGRAM = 4000



# ==============================================================
# ENVIAR MENSAJES LARGOS
# ==============================================================


async def enviar_largo(
    update,
    texto,
):

    if not texto:

        texto = "Sin datos"


    partes = [
        texto[i:i + MAX_TELEGRAM]
        for i in range(
            0,
            len(texto),
            MAX_TELEGRAM,
        )
    ]


    for parte in partes:

        if update.message:

            await update.message.reply_text(
                parte
            )

        elif update.callback_query:

            await update.callback_query.message.reply_text(
                parte
            )



# ==============================================================
# MENÚ DE LIGA
# ==============================================================


async def mostrar_menu_liga(
    update,
    context,
):

    nombre = context.user_data.get(
        "liga_nombre",
        "Liga seleccionada",
    )


    texto = (
        "✅ Liga seleccionada\n\n"
        f"🏆 {nombre}\n\n"
        "Comandos disponibles:\n\n"
        "/informe\n"
        "/mercado\n"
        "/mercado24\n"
        "/liga\n"
        "/ayuda"
    )


    botones = [

        [
            InlineKeyboardButton(
                "📊 Informe",
                callback_data="accion_informe",
            )
        ],

        [
            InlineKeyboardButton(
                "🔄 Mercado",
                callback_data="accion_mercado",
            )
        ],

        [
            InlineKeyboardButton(
                "⏱ Mercado 24h",
                callback_data="accion_mercado24",
            )
        ],

        [
            InlineKeyboardButton(
                "🔀 Cambiar liga",
                callback_data="accion_liga",
            )
        ],

        [
            InlineKeyboardButton(
                "❓ Ayuda",
                callback_data="accion_ayuda",
            )
        ],

    ]


    mensaje = (
        update.message
        if update.message
        else update.callback_query.message
    )


    await mensaje.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            botones
        ),
    )



# ==============================================================
# SELECTOR DE LIGA
# ==============================================================


async def mostrar_selector_ligas(
    update,
):

    try:

        ligas = obtener_ligas()


        botones = []


        for liga in ligas:

            botones.append(
                [
                    InlineKeyboardButton(
                        liga["name"],
                        callback_data=f"liga:{liga['id']}",
                    )
                ]
            )


        if not botones:

            mensaje = (
                update.message
                if update.message
                else update.callback_query.message
            )

            await mensaje.reply_text(
                "No se encontraron ligas."
            )

            return


        mensaje = (
            update.message
            if update.message
            else update.callback_query.message
        )


        await mensaje.reply_text(
            "🏆 Selecciona una liga:",
            reply_markup=InlineKeyboardMarkup(
                botones
            ),
        )


    except Exception as e:

        logging.exception(
            "ERROR MOSTRANDO LIGAS"
        )


        mensaje = (
            update.message
            if update.message
            else update.callback_query.message
        )


        await mensaje.reply_text(
            f"Error obteniendo ligas:\n{e}"
        )

# ==============================================================
# START
# ==============================================================


async def start(
    update,
    context,
):

    if context.user_data.get(
        "liga"
    ):

        await mostrar_menu_liga(
            update,
            context,
        )

    else:

        await mostrar_selector_ligas(
            update
        )



# ==============================================================
# CAMBIAR LIGA
# ==============================================================


async def liga(
    update,
    context,
):

    await mostrar_selector_ligas(
        update
    )



# ==============================================================
# CALLBACKS BOTONES
# ==============================================================


async def botones_callback(
    update,
    context,
):

    query = update.callback_query


    await query.answer()


    data = query.data


    # ----------------------------------------------------------
    # CAMBIAR LIGA
    # ----------------------------------------------------------

    if data == "accion_liga":

        await mostrar_selector_ligas(
            update
        )

        return



    # ----------------------------------------------------------
    # ACCIONES
    # ----------------------------------------------------------

    if data == "accion_informe":

        await informe(
            update,
            context,
        )

        return



    if data == "accion_mercado":

        await mercado(
            update,
            context,
        )

        return



    if data == "accion_mercado24":

        await mercado24(
            update,
            context,
        )

        return



    if data == "accion_ayuda":

        await ayuda(
            update,
            context,
        )

        return



    # ----------------------------------------------------------
    # SELECCIÓN DE LIGA
    # ----------------------------------------------------------

    if data.startswith(
        "liga:"
    ):

        try:

            liga_id = int(
                data.split(":")[1]
            )


        except Exception:

            await query.edit_message_text(
                "❌ Liga inválida."
            )

            return



        context.user_data["liga"] = liga_id


        context.user_data["liga_nombre"] = (
            obtener_nombre_liga(
                liga_id
            )
        )


        await query.edit_message_text(
            "✅ Liga cambiada correctamente."
        )


        await mostrar_menu_liga(
            update,
            context,
        )



# ==============================================================
# INFORME
# ==============================================================


async def informe(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )


    if not liga_id:

        mensaje = (
            update.message
            if update.message
            else update.callback_query.message
        )

        await mensaje.reply_text(
            "Usa primero /liga"
        )

        return



    try:

        if update.message:

            await update.message.reply_text(
                "📊 Calculando informe del mercado..."
            )


        report = obtener_informe(
            liga_id
        )


        texto = (
            "📊 INFORME DEL MERCADO\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "👥 DETALLE POR MANAGER\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )


        if not report:

            texto += (
                "No hay movimientos registrados."
            )

            await enviar_largo(
                update,
                texto,
            )

            return



        managers = sorted(
            report.items(),
            key=lambda item:
                item[1].get(
                    "saldo_actual",
                    0,
                ),
            reverse=True,
        )


        for manager, datos in managers:


            compras = datos.get(
                "total_compras",
                0,
            )


            ventas = datos.get(
                "total_ventas",
                0,
            )


            numero_compras = datos.get(
                "numero_compras",
                0,
            )


            numero_ventas = datos.get(
                "numero_ventas",
                0,
            )


            saldo = datos.get(
                "saldo_actual",
                20_000_000,
            )


            emoji_saldo = (
                "💰"
                if saldo >= 0
                else "🔴"
            )


            texto += (

                f"👤 {manager}\n"

                f"   🟢 Compras: "
                f"{numero_compras} "
                f"({compras:,}€)\n"

                f"   🔴 Ventas: "
                f"{numero_ventas} "
                f"({ventas:,}€)\n"

                f"   {emoji_saldo} "
                f"Saldo actual: "
                f"{saldo:,}€\n\n"

            )


        await enviar_largo(
            update,
            texto,
        )


    except Exception as e:

        logging.exception(
            "ERROR INFORME"
        )


        mensaje = (
            update.message
            if update.message
            else update.callback_query.message
        )


        await mensaje.reply_text(
            f"Error calculando informe:\n{e}"
        )



# ==============================================================
# MERCADO COMPLETO
# ==============================================================


async def mercado(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )


    if not liga_id:

        mensaje = (
            update.message
            if update.message
            else update.callback_query.message
        )

        await mensaje.reply_text(
            "Usa primero /liga"
        )

        return



    try:

        if update.message:

            await update.message.reply_text(
                "🔄 Cargando mercado completo..."
            )


        texto = obtener_mercado_completo(
            liga_id
        )


        await enviar_largo(
            update,
            texto,
        )


    except Exception as e:

        logging.exception(
            "ERROR MERCADO"
        )


        mensaje = (
            update.message
            if update.message
            else update.callback_query.message
        )


        await mensaje.reply_text(
            f"Error obteniendo mercado:\n{e}"
        )

# ==============================================================
# COMPATIBILIDAD CON COMANDO ANTIGUO
# ==============================================================


async def movimientos(
    update,
    context,
):

    await mercado(
        update,
        context,
    )



# ==============================================================
# MERCADO ÚLTIMAS 24 HORAS
# ==============================================================


async def mercado24(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )


    if not liga_id:

        mensaje = (
            update.message
            if update.message
            else update.callback_query.message
        )


        await mensaje.reply_text(
            "Usa primero /liga"
        )

        return



    try:

        if update.message:

            await update.message.reply_text(
                "⏱️ Cargando mercado de las últimas 24 horas..."
            )


        texto = obtener_mercado_24h(
            liga_id
        )


        await enviar_largo(
            update,
            texto,
        )


    except Exception as e:


        logging.exception(
            "ERROR MERCADO 24H"
        )


        mensaje = (
            update.message
            if update.message
            else update.callback_query.message
        )


        await mensaje.reply_text(
            f"Error obteniendo mercado 24h:\n{e}"
        )



# ==============================================================
# AYUDA
# ==============================================================


async def ayuda(
    update,
    context,
):


    texto = """

📚 Comandos disponibles:


/liga

Cambiar de liga Biwenger.



/informe

Informe de compras, ventas y saldo actual.



/mercado

Historial completo del mercado agrupado por fecha.



/mercado24

Movimientos realizados durante las últimas 24 horas.



/start

Mostrar menú principal.

"""


    mensaje = (
        update.message
        if update.message
        else update.callback_query.message
    )


    await mensaje.reply_text(
        texto
    )



# ==============================================================
# ERROR GLOBAL
# ==============================================================


async def error_handler(
    update,
    context,
):

    logging.error(
        "ERROR GLOBAL: %s",
        context.error,
    )



# ==============================================================
# MAIN
# ==============================================================


def main():

    app = (
        Application
        .builder()
        .token(
            TELEGRAM_TOKEN
        )
        .build()
    )


    # ----------------------------------------------------------
    # COMANDOS
    # ----------------------------------------------------------


    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )


    app.add_handler(
        CommandHandler(
            "liga",
            liga,
        )
    )


    app.add_handler(
        CommandHandler(
            "informe",
            informe,
        )
    )


    app.add_handler(
        CommandHandler(
            "mercado",
            mercado,
        )
    )


    # Compatibilidad versión antigua

    app.add_handler(
        CommandHandler(
            "movimientos",
            movimientos,
        )
    )


    app.add_handler(
        CommandHandler(
            "mercado24",
            mercado24,
        )
    )


    app.add_handler(
        CommandHandler(
            "ayuda",
            ayuda,
        )
    )



    # ----------------------------------------------------------
    # BOTONES
    # ----------------------------------------------------------


    app.add_handler(
        CallbackQueryHandler(
            botones_callback
        )
    )



    # ----------------------------------------------------------
    # ERRORES
    # ----------------------------------------------------------


    app.add_error_handler(
        error_handler
    )



    print(
        "Bot iniciado..."
    )


    app.run_polling(
        drop_pending_updates=True
    )



# ==============================================================
# EJECUCIÓN
# ==============================================================


if __name__ == "__main__":

    main()