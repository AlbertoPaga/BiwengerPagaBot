from importlib.metadata import version
import pydantic
import pybiwenger
import sys
import time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

from config import TELEGRAM_TOKEN
from biwenger import cargar_liga, patrimonio


print("Python:", sys.version)
print("Pybiwenger:", version("pybiwenger"))
print("Pydantic:", pydantic.__version__)


CACHE = {
    "time": 0,
    "usuarios": None,
    "plantillas": None
}


def obtener_datos():

    ahora = time.time()

    if (
        CACHE["usuarios"] is None
        or ahora - CACHE["time"] > 300
    ):

        usuarios, plantillas = cargar_liga()

        CACHE["usuarios"] = usuarios
        CACHE["plantillas"] = plantillas
        CACHE["time"] = ahora

    return CACHE["usuarios"], CACHE["plantillas"]


async def informe(update: Update, context: ContextTypes.DEFAULT_TYPE):

    usuarios, plantillas = obtener_datos()

    datos = []

    for uid, u in usuarios.items():

        dinero, valor, total = patrimonio(
            u,
            plantillas.get(uid, [])
        )

        datos.append(
            (
                total,
                u["nombre"],
                dinero,
                valor
            )
        )

    datos.sort(reverse=True)

    texto = "🏆 <b>RANKING PATRIMONIO</b>\n\n"

    for pos, d in enumerate(datos, 1):

        texto += (
            f"{pos}. <b>{d[1]}</b>\n"
            f"💰 Dinero: {d[2]:,.0f} €\n"
            f"👥 Plantilla: {d[3]:,.0f} €\n"
            f"📊 Total: {d[0]:,.0f} €\n\n"
        )

    await update.message.reply_text(
        texto,
        parse_mode="HTML"
    )


async def equipo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "Uso:\n/equipo Nombre"
        )
        return

    nombre = " ".join(context.args).lower()

    usuarios, plantillas = obtener_datos()

    for uid, u in usuarios.items():

        if nombre in u["nombre"].lower():

            dinero, valor, total = patrimonio(
                u,
                plantillas.get(uid, [])
            )

            texto = (
                f"<b>{u['nombre']}</b>\n\n"
                f"💰 Dinero: {dinero:,.0f} €\n"
                f"👥 Valor plantilla: {valor:,.0f} €\n"
                f"📊 Patrimonio: {total:,.0f} €\n\n"
            )

            jugadores = sorted(
                plantillas.get(uid, []),
                key=lambda x: getattr(x, "price", 0),
                reverse=True
            )

            for j in jugadores:

                texto += (
                    f"• {j.name} "
                    f"({j.price:,.0f} €)\n"
                )

            await update.message.reply_text(
                texto,
                parse_mode="HTML"
            )

            return

    await update.message.reply_text(
        "Equipo no encontrado."
    )


async def movimientos(update: Update, context: ContextTypes.DEFAULT_TYPE):

    usuarios, _ = obtener_datos()

    texto = "<b>COMPRAS / VENTAS</b>\n\n"

    for u in usuarios.values():

        texto += (
            f"<b>{u['nombre']}</b>\n"
            f"Compras: {u['compras']:,.0f} €\n"
            f"Ventas: {u['ventas']:,.0f} €\n\n"
        )

    await update.message.reply_text(
        texto,
        parse_mode="HTML"
    )


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        """
🤖 Comandos

/informe
Ranking patrimonio

/equipo nombre

/movimientos

/refresh
"""
    )


async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):

    CACHE["usuarios"] = None

    obtener_datos()

    await update.message.reply_text(
        "Datos actualizados."
    )


app = Application.builder().token(
    TELEGRAM_TOKEN
).build()

app.add_handler(CommandHandler("informe", informe))
app.add_handler(CommandHandler("equipo", equipo))
app.add_handler(CommandHandler("movimientos", movimientos))
app.add_handler(CommandHandler("refresh", refresh))
app.add_handler(CommandHandler("ayuda", ayuda))

print("Bot iniciado...")

app.run_polling()