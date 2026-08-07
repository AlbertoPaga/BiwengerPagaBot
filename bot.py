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
# UTILIDADES
# ==============================================================

async def enviar_largo(update, texto):

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
        await update.message.reply_text(parte)



async def mostrar_selector_liga(update):

    ligas = obtener_ligas()

    botones = []

    for liga in ligas:
        botones.append(
            [
                InlineKeyboardButton(
                    liga["name"],
                    callback_data=f'{liga["id"]}|{liga["name"]}',
                )
            ]
        )

    if not botones:
        await update.message.reply_text(
            "No se encontraron ligas."
        )
        return

    await update.message.reply_text(
        "🏆 Selecciona una liga:",
        reply_markup=InlineKeyboardMarkup(
            botones
        ),
    )



async def mostrar_menu_liga(update, context):

    nombre = context.user_data.get(
        "liga_nombre",
        "Liga seleccionada",
    )

    await update.message.reply_text(
        f"""
✅ Liga activa

🏆 {nombre}

Comandos disponibles:

/informe
/mercado
/mercado24
/liga
/ayuda
"""
    )



# ==============================================================
# START
# ==============================================================

async def start(update, context):

    liga_id = context.user_data.get(
        "liga"
    )

    if liga_id:

        await mostrar_menu_liga(
            update,
            context,
        )

    else:

        await update.message.reply_text(
            """
🤖 ConsultasBiwenger

Primero selecciona una liga.
"""
        )

        await mostrar_selector_liga(
            update
        )



# ==============================================================
# CAMBIAR LIGA
# ==============================================================

async def liga(update, context):

    try:

        await mostrar_selector_liga(
            update
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

async def elegir_liga(update, context):

    query = update.callback_query

    await query.answer()

    try:

        datos = query.data.split("|")

        liga_id = int(datos[0])

        liga_nombre = datos[1]

    except Exception:

        await query.edit_message_text(
            "❌ Liga inválida."
        )

        return


    context.user_data["liga"] = liga_id

    context.user_data["liga_nombre"] = liga_nombre


    await query.edit_message_text(
        "✅ Liga seleccionada"
    )


    await query.message.reply_text(
        f"""
🏆 {liga_nombre}

Comandos disponibles:

/informe
/mercado
/mercado24
/liga
/ayuda
"""
    )



# ==============================================================
# COMPROBAR LIGA
# ==============================================================

async def comprobar_liga(update, context):

    liga_id = context.user_data.get(
        "liga"
    )

    if not liga_id:

        await update.message.reply_text(
            "Primero selecciona una liga con /liga"
        )

        return None

    return liga_id

# ==============================================================
# INFORME
# ==============================================================

async def informe(update, context):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if not liga_id:
        return

    try:

        await update.message.reply_text(
            "📊 Calculando informe..."
        )

        report = obtener_informe(
            liga_id
        )


        texto = (
            "📊 INFORME DEL MERCADO\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "👥 MANAGERS\n"
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


            emoji = (
                "💰"
                if saldo >= 0
                else "🔴"
            )


            texto += (
                f"👤 {manager}\n"
                f"🟢 Compras: "
                f"{numero_compras} "
                f"({compras:,}€)\n"
                f"🔴 Ventas: "
                f"{numero_ventas} "
                f"({ventas:,}€)\n"
                f"{emoji} Saldo: "
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

async def mercado(update, context):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if not liga_id:
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
            "ERROR MERCADO"
        )

        await update.message.reply_text(
            f"Error obteniendo mercado:\n{e}"
        )



# Alias para compatibilidad con versiones anteriores

async def movimientos(update, context):

    await mercado(
        update,
        context,
    )



# ==============================================================
# MERCADO 24 HORAS
# ==============================================================

async def mercado24(update, context):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if not liga_id:
        return


    try:

        await update.message.reply_text(
            "⏱️ Cargando últimas 24 horas..."
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
            f"Error obteniendo mercado 24h:\n{e}"
        )



# ==============================================================
# AYUDA
# ==============================================================

async def ayuda(update, context):

    liga_id = context.user_data.get(
        "liga"
    )


    if liga_id:

        texto = """
📚 Comandos disponibles:

/informe
Informe de saldos de managers.

/mercado
Mercado completo agrupado por fechas.

/mercado24
Movimientos últimas 24 horas.

/liga
Cambiar de liga.

/ayuda
Mostrar ayuda.
"""

    else:

        texto = """
📚 Comandos:

/start
Iniciar bot y seleccionar liga.

/liga
Seleccionar liga.
"""


    await update.message.reply_text(
        texto
    )



# ==============================================================
# ERROR GLOBAL
# ==============================================================

async def error_handler(update, context):

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
        CallbackQueryHandler(
            elegir_liga,
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