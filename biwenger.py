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

        if isinstance(
            valor,
            list
        ):

            print(
                f"{key}: lista con {len(valor)} elementos"
            )

        elif isinstance(
            valor,
            dict
        ):

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

    print(
        "\n======================================================"
    )

    print(
        "        INSPECCIONANDO HISTORIAL DEL MERCADO"
    )

    print(
        "======================================================"
    )

    try:

        resultado = client.board_history(
            liga_id
        )

        print(
            "\n================ RESPUESTA RAW ================="
        )

        pprint(
            resultado
        )

        print(
            "================================================="
        )

        print(
            "\nTIPO DE RESPUESTA:"
        )

        print(
            type(resultado)
        )

        print(
            "\n¿ES LISTA?:"
        )

        print(
            isinstance(
                resultado,
                list
            )
        )

        print(
            "\n¿ES DICCIONARIO?:"
        )

        print(
            isinstance(
                resultado,
                dict
            )
        )

        if isinstance(
            resultado,
            dict
        ):

            print(
                "\nCLAVES DEL DICCIONARIO:"
            )

            print(
                list(
                    resultado.keys()
                )
            )

            for key, valor in resultado.items():

                print(
                    "\n----------------------------------------"
                )

                print(
                    "CLAVE:",
                    key
                )

                print(
                    "TIPO:",
                    type(valor)
                )

                if isinstance(
                    valor,
                    list
                ):

                    print(
                        "LISTA CON:",
                        len(valor),
                        "ELEMENTOS"
                    )

                    if valor:

                        print(
                            "\nPRIMER ELEMENTO:"
                        )

                        pprint(
                            valor[0]
                        )

                        print(
                            "\nTIPO PRIMER ELEMENTO:"
                        )

                        print(
                            type(
                                valor[0]
                            )
                        )

                elif isinstance(
                    valor,
                    dict
                ):

                    print(
                        "DICCIONARIO CON:",
                        len(valor),
                        "CLAVES"
                    )

                    print(
                        "\nCLAVES:"
                    )

                    print(
                        list(
                            valor.keys()
                        )
                    )

                else:

                    print(
                        "VALOR:",
                        valor
                    )

        elif isinstance(
            resultado,
            list
        ):

            print(
                "\nLISTA CON:",
                len(resultado),
                "ELEMENTOS"
            )

            if resultado:

                print(
                    "\nPRIMER ELEMENTO:"
                )

                pprint(
                    resultado[0]
                )

                print(
                    "\nTIPO PRIMER ELEMENTO:"
                )

                print(
                    type(
                        resultado[0]
                    )
                )

        print(
            "\n======================================================"
        )

        print(
            "        FIN INSPECCION"
        )

        print(
            "======================================================"
        )

        # De momento no intentamos interpretar
        # los movimientos.
        #
        # Queremos primero conocer exactamente
        # la estructura que devuelve la API.

        return []

    except Exception as e:

        print(
            "\n======================================================"
        )

        print(
            "ERROR OBTENIENDO HISTORIAL"
        )

        print(
            "======================================================"
        )

        print(
            "TIPO DE ERROR:",
            type(e)
        )

        print(
            "ERROR:",
            e
        )

        print(
            "======================================================"
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

                cantidad = item.get(
                    "amount",
                    0
                )

                comprador = ""

                vendedor = ""

                if item.get(
                    "to"
                ):

                    comprador = item["to"].get(
                        "name",
                        ""
                    )

                if item.get(
                    "from"
                ):

                    vendedor = item["from"].get(
                        "name",
                        ""
                    )

                if comprador:

                    resultado.append(
                        f"🟢 {comprador} ficha a "
                        f"{jugador} por {cantidad:,}€"
                    )

                elif vendedor:

                    resultado.append(
                        f"🔴 {vendedor} vende a "
                        f"{jugador} por {cantidad:,}€"
                    )

                else:

                    resultado.append(
                        f"⚽ Movimiento de "
                        f"{jugador} ({cantidad:,}€)"
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
