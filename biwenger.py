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

        print(
            "\n======================================================"
        )

        print(
            "        DESCARGANDO HISTORIAL DEL MERCADO"
        )

        print(
            "======================================================"
        )

        movimientos = client.board_history(
            liga_id
        )

        print(
            "======================================================"
        )

        print(
            "        DESCARGA FINALIZADA"
        )

        print(
            "======================================================"
        )

        print(
            f"TOTAL MOVIMIENTOS DESCARGADOS: {len(movimientos)}"
        )

        print(
            "======================================================\n"
        )

        imprimir_movimientos_raw(
            movimientos
        )

        return formatear_movimientos(
            movimientos
        )

    except Exception as e:

        print(
            "ERROR MOVIMIENTOS:",
            e
        )

        return []


def imprimir_movimientos_raw(
    movimientos
):

    if not isinstance(
        movimientos,
        list
    ):

        print(
            "ERROR: los movimientos no son una lista"
        )

        return

    print(
        "\n======================================================"
    )

    print(
        "          MOVIMIENTOS RAW DESCARGADOS"
    )

    print(
        "======================================================"
    )

    for numero, movimiento in enumerate(
        movimientos,
        start=1
    ):

        print(
            f"\n---------------- MOVIMIENTO {numero} ----------------"
        )

        print(
            "TYPE:",
            movimiento.get(
                "type"
            )
        )

        print(
            "DATE:",
            movimiento.get(
                "date"
            )
        )

        contenido = movimiento.get(
            "content",
            []
        )

        print(
            "CONTENT:"
        )

        pprint(
            contenido
        )

    print(
        "\n======================================================"
    )

    print(
        "        FIN MOVIMIENTOS RAW"
    )

    print(
        "======================================================\n"
    )


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
