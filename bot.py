import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
    diagnostico_liga,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_TELEGRAM = 4000


async def enviar_largo(update, texto):
    if not texto:
        texto = "Sin datos"

    partes = [
        texto[i:i + MAX_TELEGRAM]
        for i in range(0, len(texto), MAX_TELEGRAM)
    ]

    for parte in partes:
        await update.message.reply_text(parte)


async def mostrar_selector_liga(update):
    ligas = obtener_ligas()
    botones = []

    for liga in ligas:
        if not isinstance(liga, dict):
            continue

        liga_id = liga.get("id")
        nombre = liga.get("name", f"Liga {liga_id}")

        if liga_id is None:
            continue

        # SOLO enviamos el ID. El nombre ya no viaja en callback_data.
        botones.append([
            InlineKeyboardButton(
                str(nombre),
                callback_data=f"liga:{liga_id}",
            )
        ])

    if not botones:
        await update.message.reply_text("No se encontraron ligas.")
        return

    await update.message.reply_text(
        "🏆 Selecciona una liga:",
        reply_markup=InlineKeyboardMarkup(botones),
    )


async def mostrar_menu_liga(update, context):
    nombre = context.user_data.get("liga_nombre", "Liga seleccionada")
    liga_id = context.user_data.get("liga")

    await update.message.reply_text(
        f"✅ Liga activa\n\n"
        f"🏆 {nombre}\n"
        f"🆔 Liga: {liga_id}\n\n"
        f"Comandos disponibles:\n\n"
        f"/informe\n"
        f"/mercado\n"
        f"/mercado24\n"
        f"/liga\n"
        f"/ayuda"
    )


async def start(update, context):
    liga_id = context.user_data.get("liga")

    if liga_id:
        await mostrar_menu_liga(update, context)
    else:
        await update.message.reply_text(
            "🤖 ConsultasBiwenger\n\n"
            "Primero selecciona una liga."
        )
        await mostrar_selector_liga(update)


async def liga(update, context):
    try:
        await mostrar_selector_liga(update)
    except Exception as e:
        logger.exception("ERROR LIGA")
        await update.message.reply_text(
            f"Error obteniendo ligas:\n{e}"
        )


async def elegir_liga(update, context):
    query = update.callback_query
    await query.answer()

    try:
        if not query.data.startswith("liga:"):
            raise ValueError("Callback de liga inválido")

        liga_id = int(query.data.split(":", 1)[1])

        # Buscamos el nombre directamente en /account.
        ligas = obtener_ligas()
        liga_encontrada = next(
            (
                liga for liga in ligas
                if isinstance(liga, dict)
                and str(liga.get("id")) == str(liga_id)
            ),
            None,
        )

        if liga_encontrada is None:
            raise ValueError(
                f"La liga {liga_id} no aparece en /account"
            )

        liga_nombre = liga_encontrada.get(
            "name", f"Liga {liga_id}"
        )

    except Exception as e:
        logger.exception("ERROR ELEGIR LIGA")
        await query.edit_message_text(
            f"❌ Liga inválida.\n{e}"
        )
        return

    # Guardamos únicamente la liga elegida para ESTE usuario de Telegram.
    context.user_data["liga"] = liga_id
    context.user_data["liga_nombre"] = liga_nombre

    await query.edit_message_text(
        f"✅ Liga seleccionada\n\n"
        f"🏆 {liga_nombre}\n"
        f"🆔 Liga: {liga_id}"
    )

    # Diagnóstico real contra Biwenger.
    try:
        diag = diagnostico_liga(liga_id)

        await query.message.reply_text(
            f"🔎 DIAGNÓSTICO\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Liga: {liga_nombre}\n"
            f"League ID: {diag['league_id']}\n"
            f"User ID: {diag['user_id']}\n"
            f"Eventos board: {diag['eventos_board']}\n\n"
            f"Si cambias de liga, estos IDs deben cambiar."
        )
    except Exception as e:
        logger.exception("ERROR DIAGNÓSTICO LIGA")
        await query.message.reply_text(
            f"⚠️ Liga guardada, pero el diagnóstico falló:\n{e}"
        )

    await query.message.reply_text(
        f"🏆 {liga_nombre}\n\n"
        f"Comandos disponibles:\n\n"
        f"/informe\n"
        f"/mercado\n"
        f"/mercado24\n"
        f"/liga\n"
        f"/ayuda"
    )


async def comprobar_liga(update, context):
    liga_id = context.user_data.get("liga")

    if not liga_id:
        await update.message.reply_text(
            "Primero selecciona una liga con /liga"
        )
        return None

    return int(liga_id)


async def informe(update, context):
    liga_id = await comprobar_liga(update, context)
    if not liga_id:
        return

    try:
        await update.message.reply_text("📊 Calculando informe...")

        report = obtener_informe(liga_id)

        texto = (
            "📊 INFORME DE MANAGERS\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if not report:
            texto += "No hay movimientos registrados."
            await enviar_largo(update, texto)
            return

        managers = sorted(
            report.items(),
            key=lambda item: item[1].get("saldo_actual", 0),
            reverse=True,
        )

        for manager, datos in managers:
            compras = datos.get("total_compras", 0)
            ventas = datos.get("total_ventas", 0)
            numero_compras = datos.get("numero_compras", 0)
            numero_ventas = datos.get("numero_ventas", 0)
            saldo = datos.get("saldo_actual", 20_000_000)

            emoji = "💰" if saldo >= 0 else "🔴"

            texto += (
                f"👤 {manager}\n"
                f"🟢 Compras: {numero_compras} ({compras:,}€)\n"
                f"🔴 Ventas: {numero_ventas} ({ventas:,}€)\n"
                f"{emoji} Saldo: {saldo:,}€\n\n"
            )

        await enviar_largo(update, texto)

    except Exception as e:
        logger.exception("ERROR INFORME")
        await update.message.reply_text(
            f"Error calculando informe:\n{e}"
        )


async def mercado(update, context):
    liga_id = await comprobar_liga(update, context)
    if not liga_id:
        return

    try:
        await update.message.reply_text(
            "🔄 Cargando mercado completo..."
        )

        texto = obtener_mercado_completo(liga_id)
        await enviar_largo(update, texto)

    except Exception as e:
        logger.exception("ERROR MERCADO")
        await update.message.reply_text(
            f"Error obteniendo mercado:\n{e}"
        )


async def movimientos(update, context):
    await mercado(update, context)


async def mercado24(update, context):
    liga_id = await comprobar_liga(update, context)
    if not liga_id:
        return

    try:
        await update.message.reply_text(
            "⏱️ Cargando últimas 24 horas..."
        )

        texto = obtener_mercado_24h(liga_id)
        await enviar_largo(update, texto)

    except Exception as e:
        logger.exception("ERROR MERCADO 24H")
        await update.message.reply_text(
            f"Error obteniendo mercado 24h:\n{e}"
        )


async def ayuda(update, context):
    liga_id = context.user_data.get("liga")

    if liga_id:
        texto = (
            "📚 Comandos disponibles:\n\n"
            "/informe\n"
            "Informe de saldos de managers.\n\n"
            "/mercado\n"
            "Mercado completo agrupado por fechas.\n\n"
            "/mercado24\n"
            "Movimientos últimas 24 horas.\n\n"
            "/liga\n"
            "Cambiar de liga.\n\n"
            "/ayuda\n"
            "Mostrar ayuda."
        )
    else:
        texto = (
            "📚 Comandos:\n\n"
            "/start\n"
            "Iniciar bot y seleccionar liga.\n\n"
            "/liga\n"
            "Seleccionar liga."
        )

    await update.message.reply_text(texto)


async def error_handler(update, context):
    logger.error(
        "ERROR GLOBAL: %s",
        context.error,
        exc_info=context.error,
    )


def main():
    app = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("liga", liga))
    app.add_handler(
        CallbackQueryHandler(
            elegir_liga,
            pattern=r"^liga:",
        )
    )
    app.add_handler(CommandHandler("informe", informe))
    app.add_handler(CommandHandler("mercado", mercado))
    app.add_handler(CommandHandler("movimientos", movimientos))
    app.add_handler(CommandHandler("mercado24", mercado24))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_error_handler(error_handler)

    print("Bot iniciado...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
