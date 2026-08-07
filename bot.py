import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import TELEGRAM_TOKEN

from biwenger import (
    obtener_ligas,
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

        await update.message.reply_text(
            parte
        )


# ==============================================================
# START
# ==============================================================

async def start(
    update,
    context,
):

    await update.message.reply_text(
        """
🤖 Bot Biwenger activo

Comandos:

/liga - seleccionar liga
/informe - informe de saldos
/movimientos - mercado completo
/mercado24 - mercado últimas 24 horas
/ayuda - ayuda
"""
    )


# ==============================================================
# LIGA
# ==============================================================

async def liga(
    update,
    context,
):

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
                        ),
                    )
                ]
            )

        if not botones:

            await update.message.reply_text(
                "No se encontraron ligas."
            )

            return

        await update.message.reply_text(
            "Selecciona liga:",
            reply_markup=InlineKeyboardMarkup(
                botones
            ),
        )

    except Exception as e:

        logging.exception(
            "ERROR LIGA"
        )

        await update.message.reply_text(
            f"Error obteniendo ligas:\n{e}"
        )


# ==============================================================
# ELEGIR LIGA
# ==============================================================

async def elegir_liga(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        liga_id = int(
            query.data
        )

    except Exception:

        await query.edit_message_text(
            "❌ ID de liga inválido."
        )

        return

    context.user_data[
        "liga"
    ] = liga_id

    await query.edit_message_text(
        "✅ Liga seleccionada\n\n"
        f"ID: {liga_id}\n\n"
        "Ya puedes usar /informe, "
        "/movimientos o /mercado24."
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

        await update.message.reply_text(
            "Usa primero /liga"
        )

        return

    try:

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
                "No hay movimientos "
                "registrados."
            )

            await enviar_largo(
                update,
                texto,
            )

            return

        # ------------------------------------------------------
        # Ordenar managers por saldo actual
        # De mayor a menor
        # ------------------------------------------------------

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

        await update.message.reply_text(
            f"Error calculando informe:\n{e}"
        )


# ==============================================================
# MERCADO COMPLETO
# ==============================================================

async def movimientos(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )

    if not liga_id:

        await update.message.reply_text(
            "Usa primero /liga"
        )

        return

    try:

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
            "ERROR MERCADO COMPLETO"
        )

        await update.message.reply_text(
            f"Error obteniendo el mercado:\n{e}"
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

        await update.message.reply_text(
            "Usa primero /liga"
        )

        return

    try:

        await update.message.reply_text(
            "⏱️ Cargando mercado de las "
            "últimas 24 horas..."
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

        await update.message.reply_text(
            "Error obteniendo el mercado "
            f"de las últimas 24 horas:\n{e}"
        )


# ==============================================================
# AYUDA
# ==============================================================

async def ayuda(
    update,
    context,
):

    await update.message.reply_text(
        """
📚 Comandos:

/liga
Seleccionar liga Biwenger

/informe
Informe del mercado y saldo actual
de cada manager.

/movimientos
Mercado completo, agrupado por fechas.

/mercado24
Movimientos realizados durante
las últimas 24 horas.

/start
Iniciar bot
"""
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
    # START
    # ----------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # ----------------------------------------------------------
    # LIGA
    # ----------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "liga",
            liga,
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            elegir_liga,
        )
    )

    # ----------------------------------------------------------
    # INFORME
    # ----------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "informe",
            informe,
        )
    )

    # ----------------------------------------------------------
    # MERCADO COMPLETO
    # ----------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "movimientos",
            movimientos,
        )
    )

    # ----------------------------------------------------------
    # MERCADO 24 HORAS
    # ----------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "mercado24",
            mercado24,
        )
    )

    # ----------------------------------------------------------
    # AYUDA
    # ----------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "ayuda",
            ayuda,
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