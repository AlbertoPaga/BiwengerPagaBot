from config import BIWENGER_LEAGUE

from biwenger_client import BiwengerClient



def cargar_liga():

    client = BiwengerClient()

    client.login()


    liga_id = int(
        BIWENGER_LEAGUE
    )


    client.set_context(
        league_id=liga_id
    )


    liga = client.league(
        liga_id
    )


    usuarios = liga["data"]["users"]


    plantillas = {}

    for usuario in usuarios:

        uid = usuario["id"]

        # De momento la API no da plantilla
        # con endpoints públicos v2

        plantillas[uid] = []



    movimientos = cargar_movimientos(
        client,
        liga_id
    )


    return (
        usuarios,
        plantillas,
        movimientos
    )




def cargar_movimientos(
    client,
    liga_id
):

    try:

        client.set_context(
            league_id=liga_id
        )


        respuesta = client.board(
            liga_id
        )


        return respuesta.get(
            "data",
            []
        )


    except Exception as e:

        print(
            "ERROR MOVIMIENTOS:",
            e
        )

        return []





def patrimonio(
    usuario,
    plantilla
):

    dinero = usuario.get(
        "balance",
        0
    )


    valor = 0


    total = dinero + valor


    return (
        dinero,
        valor,
        total
    )