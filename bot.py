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

    return (
        CACHE["usuarios"],
        CACHE["plantillas"]
    )



async def informe(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    usuarios, plantillas = obtener_datos()

    datos = []


    for uid, usuario in usuarios.items():

        dinero, valor, total = patrimonio(
            usuario,
            plantillas.get(uid, [])
        )

        datos.append(
            (
                total,
                usuario["nombre"],
                dinero,
                valor
            )
        )


    datos.sort(
        reverse=True
    )


    texto = (
        "🏆 <b>RANKING PATRIMONIO</b>\n\n"
    )


    for posicion, dato in enumerate(datos, 1):

        texto += (
            f"{posicion}. "
            f"<b>{dato[1]}</b>\n"
            f"💰 Dinero: {dato[2]:,.0f} €\n"
            f"👥 Plantilla: {dato[3]:,.0f} €\n"
            f"📊 Total: {dato[0]:,.0f} €\n\n"
        )


    await update.message.reply_text(
        texto,
        parse_mode="HTML"
    )



async def equipo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "Uso:\n/equipo Nombre"
        )

        return


    nombre = " ".join(
        context.args
    ).lower()


    usuarios, plantillas = obtener_datos()


    for uid, usuario in usuarios.items():

        if nombre in usuario["nombre"].lower():


            dinero, valor, total = patrimonio(
                usuario,
                plantillas.get(uid, [])
            )


            texto = (
                f"<b>{usuario['nombre']}</b>\n\n"
                f"💰 Dinero: {dinero:,.0f} €\n"
                f"👥 Plantilla: {valor:,.0f} €\n"
                f"📊 Patrimonio: {total:,.0f} €\n\n"
            )


            jugadores = sorted(
                plantillas.get(uid, []),
                key=lambda x: x.get(
                    "price",
                    0
                ),
                reverse=True
            )


            for jugador in jugadores:

                texto += (
                    f"• {jugador.get('name','Desconocido')} "
                    f"({jugador.get('price',0):,.0f} €)\n"
                )


            await update.message.reply_text(
                texto,
                parse_mode="HTML"
            )

            return



    await update.message.reply_text(
        "Equipo no encontrado."
    )



async def movimientos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    usuarios, _ = obtener_datos()


    texto = (
        "<b>COMPRAS / VENTAS</b>\n\n"
    )


    for usuario in usuarios.values():

        texto += (
            f"<b>{usuario['nombre']}</b>\n"
            f"Compras: {usuario['compras']:,.0f} €\n"
            f"Ventas: {usuario['ventas']:,.0f} €\n\n"
        )


    await update.message.reply_text(
        texto,
        parse_mode="HTML"
    )



async def ayuda(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    texto = """
🤖 Comandos

/informe
Ranking patrimonio

/equipo Nombre
Ver plantilla

/movimientos
Compras y ventas

/refresh
Actualizar datos
"""


    await update.message.reply_text(
        texto
    )



async def refresh(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    CACHE["usuarios"] = None
    CACHE["plantillas"] = None

    obtener_datos()


    await update.message.reply_text(
        "Datos actualizados."
    )



app = (
    Application
    .builder()
    .token(TELEGRAM_TOKEN)
    .build()
)



app.add_handler(
    CommandHandler(
        "informe",
        informe
    )
)

app.add_handler(
    CommandHandler(
        "equipo",
        equipo
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
        "refresh",
        refresh
    )
)

app.add_handler(
    CommandHandler(
        "ayuda",
        ayuda
    )
)



print(
    "Bot iniciado..."
)


app.run_polling(
    drop_pending_updates=True
)