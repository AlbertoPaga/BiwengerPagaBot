from biwenger_client import BiwengerClient



def cargar_liga():

    client = BiwengerClient()

    client.login()


    liga = client.get_league_by_name(
        "Los más sucios"
    )


    liga_id = liga["id"]

    usuario_id = liga["user"]["id"]


    client.league_id = liga_id

    client.user_id = usuario_id



    datos_liga = client.league(
        liga_id
    )


    usuarios = {}


    for u in datos_liga["data"]["users"]:

        usuarios[u["id"]] = {

            "nombre":
                u["name"],

            "compras":
                0,

            "ventas":
                0,

            "comprados":
                [],

            "vendidos":
                [],
        }



    catalogo = {}



    try:

        jugadores = client.league_players(
            liga_id
        )


        for jugador in jugadores["data"]:

            catalogo[
                jugador["id"]
            ] = jugador


    except Exception as e:

        print(
            "ERROR PLAYERS:",
            e
        )



    eventos = descargar_tablon(
        client,
        liga_id
    )


    procesar_movimientos(
        eventos,
        usuarios,
        catalogo
    )



    plantillas = cargar_plantillas(
        client,
        liga_id,
        usuarios
    )



    return usuarios, plantillas





def descargar_tablon(
    client,
    liga_id
):

    try:

        data = client.board(
            liga_id
        )


        return data.get(
            "data",
            []
        )


    except Exception as e:

        print(
            "ERROR BOARD:",
            e
        )

        return []





def procesar_movimientos(
    eventos,
    usuarios,
    catalogo
):

    for evento in eventos:


        for mov in evento.get(
            "content",
            []
        ):


            pass





def cargar_plantillas(
    client,
    liga_id,
    usuarios
):

    resultado = {}


    for uid in usuarios:


        resultado[uid] = []


        try:


            data = client.league_user_players(
                liga_id,
                uid
            )


            resultado[uid] = data["data"]


        except Exception as e:

            print(
                "ERROR PLANTILLA",
                uid,
                e
            )


    return resultado





def patrimonio(
    usuario,
    plantilla
):

    valor = 0


    for jugador in plantilla:


        if isinstance(
            jugador,
            dict
        ):

            valor += jugador.get(
                "price",
                0
            )


    dinero = (
        20000000
        +
        usuario["ventas"]
        -
        usuario["compras"]
    )


    return (
        dinero,
        valor,
        dinero + valor
    )