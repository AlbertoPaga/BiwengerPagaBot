```python
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
)


# ============================================================
# LOGS INTERNOS
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_TELEGRAM = 4000


# ============================================================
# UTILIDAD PARA MENSAJES LARGOS
# ============================================================

async def enviar_largo(update, texto):

    if not texto:
        texto = "Sin datos"

    partes = [
        texto[i:i + MAX_TELEGRAM]
        for i in range(0, len(texto), MAX_TELEGRAM)
    ]

    for parte in partes:
        await update.message.reply_text(parte)


# ============================================================
# SELECTOR DE LIGA
# ============================================================

async def mostrar_selector_liga(update):

    ligas = obtener_ligas()
    botones = []

    for liga in ligas:

        if not isinstance(liga, dict):
            continue

        liga_id = liga.get("id")
        nombre = liga.get(
            "name",
            f"Liga {liga_id}",
        )

        if liga_id is None:
            continue

        botones.append([
            InlineKeyboardButton(
                str(nombre),
                callback_data=f"liga:{liga_id}",
            )
        ])

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


# ============================================================
# MENÚ DE LIGA
# ============================================================

async def mostrar_menu_liga(update, context):

    nombre = context.user_data.get(
        "liga_nombre",
        "Liga seleccionada",
    )

    await update.message.reply_text(
        f"🏆 {nombre}\n\n"
        f"Comandos disponibles:\n\n"
        f"/informe\n"
        f"/mercado\n"
        f"/mercado24\n"
        f"/liga\n"
        f"/ayuda"
    )


# ============================================================
# START
# ============================================================

async def start(update, context):

    liga_id = context.user_data.get("liga")

    if liga_id:

        await mostrar_menu_liga(
            update,
            context,
        )

    else:

        await update.message.reply_text(
            "🤖 ConsultasBiwenger\n\n"
            "Primero selecciona una liga."
        )

        await mostrar_selector_liga(
            update
        )


# ============================================================
# CAMBIAR DE LIGA
# ============================================================

async def liga(update, context):

    try:

        await mostrar_selector_liga(
            update
        )

    except Exception as e:

        logger.exception(
            "ERROR LIGA"
        )

        await update.message.reply_text(
            f"Error obteniendo ligas:\n{e}"
        )


# ============================================================
# ELEGIR LIGA
# ============================================================

async def elegir_liga(update, context):

    query = update.callback_query

    await query.answer()

    try:

        if not query.data.startswith("liga:"):

            raise ValueError(
                "Callback de liga inválido"
            )

        liga_id = int(
            query.data.split(
                ":",
                1,
            )[1]
        )

        # ----------------------------------------------------
        # Buscamos el nombre de la liga.
        # ----------------------------------------------------

        ligas = obtener_ligas()

        liga_encontrada = next(
            (
                liga
                for liga in ligas
                if (
                    isinstance(
                        liga,
                        dict,
                    )
                    and
                    str(liga.get("id"))
                    == str(liga_id)
                )
            ),
            None,
        )

        if liga_encontrada is None:

            raise ValueError(
                "La liga seleccionada "
                "ya no está disponible."
            )

        liga_nombre = liga_encontrada.get(
            "name",
            f"Liga {liga_id}",
        )

    except Exception as e:

        logger.exception(
            "ERROR ELEGIR LIGA"
        )

        await query.edit_message_text(
            "❌ No se pudo seleccionar la liga."
        )

        return

    # --------------------------------------------------------
    # Guardamos la liga para ESTE usuario de Telegram.
    #
    # El ID se guarda internamente, pero nunca se muestra.
    # --------------------------------------------------------

    context.user_data["liga"] = liga_id
    context.user_data["liga_nombre"] = liga_nombre

    # --------------------------------------------------------
    # Confirmación limpia.
    # --------------------------------------------------------

    await query.edit_message_text(
        f"✅ Liga seleccionada\n\n"
        f"🏆 {liga_nombre}"
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


# ============================================================
# COMPROBAR LIGA ACTIVA
# ============================================================

async def comprobar_liga(update, context):

    liga_id = context.user_data.get(
        "liga"
    )

    if not liga_id:

        await update.message.reply_text(
            "Primero selecciona una liga "
            "con /liga"
        )

        return None

    return int(liga_id)


# ============================================================
# FORMATEAR DINERO
# ============================================================

def formatear_dinero(valor):

    try:
        return f"{int(valor):,}€"

    except Exception:
        return "0€"


# ============================================================
# INFORME
# ============================================================

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
            "📊 INFORME DE MANAGERS\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        # ----------------------------------------------------
        # Si no hay miembros.
        # ----------------------------------------------------

        if not report:

            texto += (
                "No se han encontrado "
                "miembros en esta liga."
            )

            await enviar_largo(
                update,
                texto,
            )

            return

        # ----------------------------------------------------
        # Ordenamos por saldo.
        # ----------------------------------------------------

        managers = sorted(
            report.items(),
            key=lambda item: item[1].get(
                "saldo_actual",
                0,
            ),
            reverse=True,
        )

        # ----------------------------------------------------
        # Construimos cada manager.
        # ----------------------------------------------------

        for manager, datos in managers:

            numero_jugadores = datos.get(
                "numero_jugadores",
                0,
            )

            compras = datos.get(
                "total_compras",
                0,
            )

            ventas = datos.get(
                "total_ventas",
                0,
            )

            saldo = datos.get(
                "saldo_actual",
                0,
            )

            puja_maxima = datos.get(
                "puja_maxima",
                0,
            )

            texto += (
                f"👤 {manager}\n"
                f"⚽ Jugadores: "
                f"{numero_jugadores}\n"
                f"🟢 Compras: "
                f"{formatear_dinero(compras)}\n"
                f"🔴 Ventas: "
                f"{formatear_dinero(ventas)}\n"
                f"💰 Saldo: "
                f"{formatear_dinero(saldo)}\n"
                f"💵 Puja máxima: "
                f"{formatear_dinero(puja_maxima)}\n\n"
            )

        await enviar_largo(
            update,
            texto,
        )

    except Exception as e:

        logger.exception(
            "ERROR INFORME"
        )

        await update.message.reply_text(
            f"Error calculando informe:\n{e}"
        )


# ============================================================
# MERCADO COMPLETO
# ============================================================

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

        logger.exception(
            "ERROR MERCADO"
        )

        await update.message.reply_text(
            f"Error obteniendo mercado:\n{e}"
        )


# ============================================================
# ALIAS MOVIMIENTOS
# ============================================================

async def movimientos(update, context):

    await mercado(
        update,
        context,
    )


# ============================================================
# MERCADO 24 HORAS
# ============================================================

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

        logger.exception(
            "ERROR MERCADO 24H"
        )

        await update.message.reply_text(
            f"Error obteniendo mercado:\n{e}"
        )


# ============================================================
# AYUDA
# ============================================================

async def ayuda(update, context):

    liga_id = context.user_data.get(
        "liga"
    )

    if liga_id:

        texto = (
            "📚 Comandos disponibles:\n\n"
            "/informe\n"
            "Informe de managers, "
            "jugadores, compras, ventas, "
            "saldo y puja máxima.\n\n"
            "/mercado\n"
            "Mercado completo agrupado "
            "por fechas.\n\n"
            "/mercado24\n"
            "Movimientos de las últimas "
            "24 horas.\n\n"
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

    await update.message.reply_text(
        texto
    )


# ============================================================
# MANEJADOR GLOBAL DE ERRORES
# ============================================================

async def error_handler(
    update,
    context,
):

    logger.error(
        "ERROR GLOBAL: %s",
        context.error,
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    app = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
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

    print("Bot iniciado...")

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
```
