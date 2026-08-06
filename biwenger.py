from pprint import pprint

from biwenger_client import BiwengerClient
from player_cache import get_player_name



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

    print(
        "\n================ LIGA ================="
    )

    pprint(liga)

    print(
        "=======================================\n"
    )


    data = liga.get(
        "data",
        {}
    )


    print(
        "CLAVES DE DATA:",
        list(data.keys())
    )


    for key in data.keys():

        valor = data[key]

        if isinstance(valor, list):

            print(
                f"{key}: lista con {len(valor)} elementos"
            )

        elif isinstance(valor, dict):

            print(
                f"{key}: diccionario con {len(valor)} claves"
            )

        else:

            print(
                f"{key}: {type(valor)}"
            )


    usuarios = []


    if "users" in data:

        usuarios = data["users"]

    elif "members" in data:

        usuarios = data["members"]

    elif "managers" in data:

        usuarios = data["managers"]


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


        print(
            "\n================ BOARD ================="
        )

        pprint(board)

        print(
            "========================================\n"
        )


        data = board.get(
            "data",
            []
        )


        if isinstance(data, dict):

            print(
                "CLAVES BOARD:",
                list(data.keys())
            )


            for key in [
                "items",
                "movements",
                "transactions",
                "board"
            ]:

                if key in data:

                    data = data[key]

                    break


        return formatear_movimientos(
            data
        )


    except Exception as e:

        print(
            "ERROR MOVIMIENTOS:",
            e
        )

        return []



def formatear_movimientos(
    movimientos
):

    resultado = []


    if not isinstance(
        movimientos,
        list
    ):

        return resultado



    print(
        f"TOTAL MOVIMIENTOS: {len(movimientos)}"
    )


    for i, m in enumerate(
        movimientos[:3]
    ):

        print(
            f"\n------ MOVIMIENTO {i+1} ------"
        )

        pprint(m)



    for m in movimientos:


        tipo = m.get(
            "type",
            ""
        )


        contenido = m.get(
            "content",
            []
        )


        if tipo in [
            "market",
            "transfer"
        ]:


            for item in contenido:


                player_id = item.get(
                    "player",
                    "?"
                )


                jugador = get_player_name(
                    player_id
                )


                print(
                    "CACHE JUGADOR:",
                    player_id,
                    "->",
                    jugador
                )


                cantidad = item.get(
                    "amount",
                    0
                )


                comprador = ""

                vendedor = ""


                if item.get("to"):

                    comprador = item["to"].get(
                        "name",
                        ""
                    )


                if item.get("from"):

                    vendedor = item["from"].get(
                        "name",
                        ""
                    )


                if comprador:

                    resultado.append(
                        f"🟢 {comprador} ficha a {jugador} por {cantidad:,}€"
                    )


                elif vendedor:

                    resultado.append(
                        f"🔴 {vendedor} vende a {jugador} por {cantidad:,}€"
                    )


                else:

                    resultado.append(
                        f"⚽ Movimiento de {jugador} ({cantidad:,}€)"
                    )



        elif tipo == "playerMovements":


            for item in contenido:


                player_id = item.get(
                    "player",
                    "?"
                )


                jugador = get_player_name(
                    player_id
                )


                print(
                    "CACHE JUGADOR:",
                    player_id,
                    "->",
                    jugador
                )


                resultado.append(
                    f"🔄 Cambio de {jugador}"
                )



    return resultado[:30]



def patrimonio(
    usuario
):

    dinero = usuario.get(
        "balance",
        0
    )


    valor = usuario.get(
        "teamValue",
        0
    )


    return (
        dinero,
        valor,
        dinero + valor
    )