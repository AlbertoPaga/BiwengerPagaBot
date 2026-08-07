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
    cargar_liga,
    obtener_informe,
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


def euros(
    cantidad,
):

    try:
        return f"{int(cantidad):,}€"
    except Exception:
        return "0€"


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
/informe - informe del mercado
/movimientos - ver movimientos
/ayuda - ayuda
"""
    )


# ==============================================================
# SELECCIONAR LIGA
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

        context.user_data["liga"] = liga_id

        await query.edit_message_text(
            f"✅ Liga seleccionada\n\n"
            f"ID: {liga_id}\n\n"
            f"Ya puedes usar /informe "
            f"o /movimientos."
        )

    except Exception as e:

        logging.exception(
            "ERROR SELECCIONANDO LIGA"
        )

        await query.edit_message_text(
            f"Error seleccionando liga:\n{e}"
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

        informe_data = obtener_informe(
            liga_id
        )

        if not informe_data:

            await update.message.reply_text(
                "No se pudo obtener el informe."
            )

            return

        managers = informe_data.get(
            "managers",
            {}
        )

        if not managers:

            await update.message.reply_text(
                "No hay movimientos suficientes "
                "para generar el informe."
            )

            return

        texto = (
            "📊 INFORME DEL MERCADO\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        # ----------------------------------------------------------
        # RESUMEN GENERAL
        # ----------------------------------------------------------

        texto += (
            "🌐 RESUMEN GENERAL\n\n"
            f"💰 Compras: "
            f"{euros(informe_data.get('total_compras', 0))}\n"
            f"💵 Ventas: "
            f"{euros(informe_data.get('total_ventas', 0))}\n"
            f"⚖️ Balance: "
            f"{euros(informe_data.get('balance_total', 0))}\n\n"
        )

        # ----------------------------------------------------------
        # MAYOR GASTO
        # ----------------------------------------------------------

        mayor_gasto = informe_data.get(
            "mayor_gasto"
        )

        if mayor_gasto:

            texto += (
                "💸 MAYOR GASTO\n"
                f"• {mayor_gasto['manager']}: "
                f"{euros(mayor_gasto['amount'])}\n\n"
            )

        # ----------------------------------------------------------
        # MAYOR INGRESO
        # ----------------------------------------------------------

        mayor_ingreso = informe_data.get(
            "mayor_ingreso"
        )

        if mayor_ingreso:

            texto += (
                "💰 MAYOR INGRESO\n"
                f"• {mayor_ingreso['manager']}: "
                f"{euros(mayor_ingreso['amount'])}\n\n"
            )

        # ----------------------------------------------------------
        # MEJOR BALANCE
        # ----------------------------------------------------------

        mejor_balance = informe_data.get(
            "mejor_balance"
        )

        if mejor_balance:

            texto += (
                "📈 MEJOR BALANCE\n"
                f"• {mejor_balance['manager']}: "
                f"{euros(mejor_balance['amount'])}\n\n"
            )

        # ----------------------------------------------------------
        # PEOR BALANCE
        # ----------------------------------------------------------

        peor_balance = informe_data.get(
            "peor_balance"
        )

        if peor_balance:

            texto += (
                "📉 PEOR BALANCE\n"
                f"• {peor_balance['manager']}: "
                f"{euros(peor_balance['amount'])}\n\n"
            )

        # ----------------------------------------------------------
        # DETALLE POR MANAGER
        # ----------------------------------------------------------

        texto += (
            "👥 DETALLE POR MANAGER\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        managers_ordenados = sorted(
            managers.items(),
            key=lambda item:
                item[1].get(
                    "total_compras",
                    0,
                ),
            reverse=True,
        )

        for nombre, datos in managers_ordenados:

            compras = datos.get(
                "total_compras",
                0,
            )

            ventas = datos.get(
                "total_ventas",
                0,
            )

            balance = datos.get(
                "balance",
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

            if balance > 0:
                icono_balance = "🟢"
            elif balance < 0:
                icono_balance = "🔴"
            else:
                icono_balance = "⚪"

            texto += (
                f"👤 {nombre}\n"
                f"   🟢 Compras: "
                f"{numero_compras} "
                f"({euros(compras)})\n"
                f"   🔴 Ventas: "
                f"{numero_ventas} "
                f"({euros(ventas)})\n"
                f"   {icono_balance} Balance: "
                f"{euros(balance)}\n\n"
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
# MOVIMIENTOS
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
            "🔄 Cargando movimientos..."
        )

        usuarios, movs = cargar_liga(
            liga_id
        )

        texto = (
            "🔄 MOVIMIENTOS\n\n"
        )

        if not movs:

            texto += "Sin movimientos"

        else:

            for movimiento in movs:

                texto += (
                    f"• {movimiento}\n"
                )

        await enviar_largo(
            update,
            texto,
        )

    except Exception as e:

        logging.exception(
            "ERROR MOVIMIENTOS"
        )

        await update.message.reply_text(
            f"Error:\n{e}"
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
Seleccionar liga Biwenger.

/informe
Calcula el informe completo del mercado:
• compras
• ventas
• gasto total
• ingresos totales
• balance
• número de operaciones
• mayor gasto
• mayor ingreso
• mejor balance
• peor balance

/movimientos
Muestra los movimientos individuales
extraídos del historial de Biwenger.

/start
Iniciar bot.
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
            "movimientos",
            movimientos,
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