from telegram import Update
from importlib.metadata import version
import pybiwenger
import pydantic
import sys

print("Python:", sys.version)
print("Pybiwenger:", version("pybiwenger"))
print("Pydantic:", pydantic.__version__)

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

from config import TELEGRAM_TOKEN

from biwenger import (
    cargar_liga,
    patrimonio
)



async def informe(
    update,
    context
):

    usuarios,plantillas=cargar_liga()


    texto="🏆 <b>RANKING PATRIMONIO</b>\n\n"


    datos=[]


    for uid,u in usuarios.items():

        dinero,valor,total=patrimonio(
            u,
            plantillas.get(uid,[])
        )

        datos.append(
            (
                total,
                u["nombre"],
                dinero,
                valor
            )
        )


    datos.sort(
        reverse=True
    )


    for i,d in enumerate(datos,1):

        texto+=(
            f"{i}. <b>{d[1]}</b>\n"
            f"💰 {d[2]:,.0f} €\n"
            f"👥 {d[3]:,.0f} €\n"
            f"📊 {d[0]:,.0f} €\n\n"
        )


    await update.message.reply_text(
        texto,
        parse_mode="HTML"
    )




async def equipo(
    update,
    context
):

    nombre=" ".join(
        context.args
    )


    usuarios,plantillas=cargar_liga()


    for uid,u in usuarios.items():

        if u["nombre"].lower()==nombre.lower():


            dinero,valor,total=patrimonio(
                u,
                plantillas.get(uid,[])
            )


            texto=(
                f"<b>{u['nombre']}</b>\n\n"
                f"💰 Dinero: {dinero:,.0f} €\n"
                f"👥 Plantilla: {valor:,.0f} €\n"
                f"📊 Patrimonio: {total:,.0f} €"
            )


            await update.message.reply_text(
                texto,
                parse_mode="HTML"
            )

            return


    await update.message.reply_text(
        "Equipo no encontrado"
    )




async def ayuda(update,context):

    await update.message.reply_text(
        """
🤖 Comandos:

/informe
Ranking patrimonio

/equipo NOMBRE
Detalle rival

/próximamente
mercado, compras y ventas
"""
    )




app=Application.builder().token(
    TELEGRAM_TOKEN
).build()



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
        "ayuda",
        ayuda
    )
)



print(
    "Bot iniciado..."
)


app.run_polling()