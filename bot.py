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


async def mostrar_selector_liga(
    update,
):

    ligas = obtener_ligas()

    botones = []

    for liga in ligas:

        liga_id = liga.get(
            "id"
        )

        liga_nombre = liga.get(
            "name",
            f"Liga {liga_id}",
        )

        if liga_id is None:
            continue

        botones.append(
            [
                InlineKeyboardButton(
                    liga_nombre,
                    callback_data=(
                        f"liga:{liga_id}"
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
        "🏆 Selecciona una liga:",
        reply_markup=InlineKeyboardMarkup(
            botones
        ),
    )


async def mostrar_menu_liga(
    update,
    context,
):

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

async def start(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )

    if liga_id is not None:

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

async def liga(
    update,
    context,
):

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

async def elegir_liga(
    update,
    context,
):

    query = update.callback_query

    await query.answer()

    try:

        datos = query.data

        if not datos.startswith(
            "liga:"
        ):

            raise ValueError(
                "Callback inválido."
            )

        liga_id = datos.split(
            ":",
            1
        )[1]

        # Lo guardamos como string.
        # biwenger.py compara IDs de forma robusta
        # independientemente de que la API use int/string.

        liga_id = str(
            liga_id
        )

    except Exception:

        await query.edit_message_text(
            "❌ Liga inválida."
        )

        return

    # ==========================================================
    # RESOLVER EL NOMBRE REAL DE LA LIGA
    # ==========================================================

    try:

        ligas = obtener_ligas()

        liga_encontrada = None

        for liga_data in ligas:

            if str(
                liga_data.get("id")
            ) == liga_id:

                liga_encontrada = (
                    liga_data
                )

                break

        if liga_encontrada is None:

            await query.edit_message_text(
                "❌ No se encontró esa liga."
            )

            return

        liga_nombre = liga_encontrada.get(
            "name",
            f"Liga {liga_id}",
        )

    except Exception as e:

        logging.exception(
            "ERROR RESOLVIENDO LIGA"
        )

        await query.edit_message_text(
            f"❌ Error obteniendo la liga:\n{e}"
        )

        return

    # ==========================================================
    # GUARDAR LIGA DEL USUARIO
    # ==========================================================

    context.user_data["liga"] = liga_id

    context.user_data["liga_nombre"] = (
        liga_nombre
    )

    # ==========================================================
    # LIMPIAR CUALQUIER DATO ANTIGUO
    # ==============================================================

    # No guardamos user_id aquí.
    # biwenger.py lo resolverá siempre a partir del league_id.
    context.user_data.pop(
        "user_id",
        None,
    )

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

async def comprobar_liga(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )

    if liga_id is None:

        await update.message.reply_text(
            "Primero selecciona una liga con /liga"
        )

        return None

    return liga_id


# ==============================================================
# INFORME
# ==============================================================

async def informe(
    update,
    context,
):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if liga_id is None:
        return

    try:

        await update.message.reply_text(
            "📊 Calculando informe..."
        )

        report = obtener_informe(
            liga_id
        )

        if report is None:
            report = {}

        texto = (
            "📊 INFORME DE MANAGERS\n"
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

async def mercado(
    update,
    context,
):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if liga_id is None:
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


# ==============================================================
# ALIAS COMPATIBILIDAD
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
# MERCADO 24 HORAS
# ==============================================================

async def mercado24(
    update,
    context,
):

    liga_id = await comprobar_liga(
        update,
        context,
    )

    if liga_id is None:
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

async def ayuda(
    update,
    context,
):

    liga_id = context.user_data.get(
        "liga"
    )

    if liga_id is not None:

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
            pattern=r"^liga:",
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