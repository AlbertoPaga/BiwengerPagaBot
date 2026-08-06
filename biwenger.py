from biwenger_client import BiwengerClient



def obtener_ligas():

    client = BiwengerClient()

    client.login()

    return client.leagues()



def cargar_liga(
    liga_id
):

    client = BiwengerClient()

    client.login()


    liga = client.league(
        liga_id
    )


    usuarios = liga["data"]["users"]


    movimientos = cargar_movimientos(
        client,
        liga_id
    )


    return (
        usuarios,
        movimientos
    )



def cargar_movimientos(
    client,
    liga_id
):

    try:

        board = client.board(
            liga_id
        )

        return board["data"]


    except Exception as e:

        print(
            "ERROR MOVIMIENTOS",
            e
        )

        return []



def patrimonio(
    usuario
):

    dinero = usuario.get(
        "balance",
        0
    )

    valor = 0


    return (
        dinero,
        valor,
        dinero + valor
    )