import sys
import time
import logging


from telegram import Update

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


from config import TELEGRAM_TOKEN

from biwenger import (
    cargar_liga,
    patrimonio,
)



logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)



print(
    "Python:",
    sys.version
)



CACHE = {

    "time": 0,

    "usuarios": None,

    "plantillas": None,

    "movimientos": None,

}




def obtener_datos():


    ahora = time.time()


    if (
        CACHE["usuarios"] is None
        or ahora - CACHE["time"] > 300
    ):


        usuarios, plantillas, movimientos = cargar_liga()



        CACHE["usuarios"] = usuarios

        CACHE["plantillas"] = plantillas

        CACHE["movimientos"] = movimientos

        CACHE["time"] = ahora



    return (

        CACHE["usuarios"],

        CACHE["plantillas"],

        CACHE["movimientos"],

    )






# --------------------------------------------------
# INFORME
# --------------------------------------------------


async def informe(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):


    usuarios, plantillas, _ = obtener_datos()



    ranking = []



    for usuario in usuarios:


        uid = usuario["id"]



        dinero, valor, total = patrimonio(

            usuario,

            plantillas.get(uid, [])

        )



        ranking.append(

            (

                total,

                usuario["name"],

                dinero,

                valor,

            )

        )



    ranking.sort(
        reverse=True
    )



    texto = (

        "🏆 <b>RANKING PATRIMONIO</b>\n\n"

    )



    for posicion, dato in enumerate(

        ranking,

        1

    ):


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






# --------------------------------------------------
# EQUIPO
# --------------------------------------------------


async def equipo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):


    if not context.args:


        await update.message.reply_text(

            "Uso:\n/equipo Nombre"

        )

        return




    nombre = (

        " ".join(context.args)

        .lower()

    )



    usuarios, plantillas, _ = obtener_datos()



    for usuario in usuarios:


        if nombre in usuario["name"].lower():


            uid = usuario["id"]



            dinero, valor, total = patrimonio(

                usuario,

                plantillas.get(uid, [])

            )



            texto = (

                f"<b>{usuario['name']}</b>\n\n"

                f"💰 Dinero: {dinero:,.0f} €\n"

                f"👥 Plantilla: {valor:,.0f} €\n"

                f"📊 Patrimonio: {total:,.0f} €\n\n"

            )



            jugadores = plantillas.get(

                uid,

                []

            )



            if not jugadores:


                texto += (

                    "No disponible la plantilla "
                    "por API actualmente."

                )


            else:


                for jugador in jugadores:


                    texto += (

                        f"• {jugador}\n"

                    )




            await update.message.reply_text(

                texto,

                parse_mode="HTML"

            )



            return




    await update.message.reply_text(

        "Equipo no encontrado."

    )







# --------------------------------------------------
# MOVIMIENTOS
# --------------------------------------------------


async def movimientos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):


    _, _, movimientos = obtener_datos()



    texto = (

        "📢 <b>ÚLTIMOS MOVIMIENTOS</b>\n\n"

    )



    contador = 0



    for movimiento in movimientos:


        if contador >= 10:

            break



        tipo = movimiento.get(

            "type",

            ""

        )



        if tipo in [

            "market",

            "transfer"

        ]:


            texto += (

                f"🔹 <b>{tipo}</b>\n"

            )


            contenido = movimiento.get(

                "content",

                []

            )



            texto += (

                f"{contenido}\n\n"

            )


            contador += 1




    if contador == 0:


        texto += (

            "No hay movimientos."

        )



    await update.message.reply_text(

        texto,

        parse_mode="HTML"

    )







# --------------------------------------------------
# REFRESH
# --------------------------------------------------


async def refresh(

    update: Update,

    context: ContextTypes.DEFAULT_TYPE

):


    CACHE["usuarios"] = None

    CACHE["plantillas"] = None

    CACHE["movimientos"] = None



    obtener_datos()



    await update.message.reply_text(

        "✅ Datos actualizados."

    )







# --------------------------------------------------
# AYUDA
# --------------------------------------------------


async def ayuda(

    update: Update,

    context: ContextTypes.DEFAULT_TYPE

):


    await update.message.reply_text(

"""
🤖 Comandos

/informe
Ranking patrimonio

/equipo nombre
Ver equipo

/movimientos
Últimos movimientos

/refresh
Actualizar datos

"""

    )







# --------------------------------------------------
# ERROR
# --------------------------------------------------


async def error_handler(

    update,

    context

):


    logging.error(

        "Error:",

        exc_info=context.error

    )







# --------------------------------------------------
# MAIN
# --------------------------------------------------


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