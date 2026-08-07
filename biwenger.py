from pprint import pprint
from datetime import datetime

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
            "======================================================"
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
            "        DESCARGA FINALIZADA"
        )

        print(
            "======================================================"
        )

        print(
            "TIPO RESPUESTA:",
            type(movimientos)
        )

        if isinstance(movimientos, dict):

            print(
                "CLAVES RESPUESTA:",
                list(movimientos.keys())
            )

            data = movimientos.get(
                "data",
                []
            )

        else:

            data = movimientos

        if not isinstance(data, list):

            print(
                "ERROR: los movimientos no son una lista"
            )

            return []

        print(
            "TOTAL EVENTOS DESCARGADOS:",
            len(data)
        )

        print(
            "======================================================"
        )

        resultado = formatear_movimientos(
            data
        )

        print(
            "TOTAL OPERACIONES FORMATEADAS:",
            len(resultado)
        )

        print(
            "======================================================"
        )

        return resultado

    except Exception as e:

        print(
            "ERROR MOVIMIENTOS:",
            e
        )

        return []


def formatear_fecha(
    timestamp
):

    if not timestamp:

        return "Fecha desconocida"

    try:

        return datetime.fromtimestamp(
            timestamp
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception:

        return "Fecha desconocida"


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
        "======================================================"
    )

    print(
        "           DETALLE DE MOVIMIENTOS"
    )

    print(
        "======================================================"
    )

    total_operaciones = 0

    for indice, m in enumerate(
        movimientos,
        start=1
    ):

        tipo = m.get(
            "type",
            ""
        )

        contenido = m.get(
            "content",
            []
        )

        fecha = m.get(
            "date"
        )

        fecha_formateada = formatear_fecha(
            fecha
        )

        print(
            "------------------------------------------------------"
        )

        print(
            f"MOVIMIENTO #{indice}"
        )

        print(
            "------------------------------------------------------"
        )

        print(
            "FECHA:",
            fecha_formateada
        )

        print(
            "TIMESTAMP:",
            fecha
        )

        print(
            "TIPO:",
            tipo
        )

        print(
            "TÍTULO:",
            m.get(
                "title",
                ""
            )
        )

        print(
            "FIXED:",
            m.get(
                "fixed",
                False
            )
        )

        if not isinstance(
            contenido,
            list
        ):

            print(
                "CONTENT NO ES LISTA"
            )

            continue

        print(
            "OPERACIONES EN CONTENT:",
            len(contenido)
        )

        for indice_item, item in enumerate(
            contenido,
            start=1
        ):

            total_operaciones += 1

            print(
                f"  OPERACIÓN #{indice_item}"
            )

            print(
                "  -----------------------------"
            )

            if not isinstance(
                item,
                dict
            ):

                print(
                    "  OPERACIÓN NO ES DICCIONARIO"
                )

                continue

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
            comprador_id = None

            vendedor = ""
            vendedor_id = None

            if item.get(
                "to"
            ):

                comprador_id = item["to"].get(
                    "id"
                )

                comprador = item["to"].get(
                    "name",
                    ""
                )

            if item.get(
                "from"
            ):

                vendedor_id = item["from"].get(
                    "id"
                )

                vendedor = item["from"].get(
                    "name",
                    ""
                )

            print(
                "  PLAYER ID:",
                player_id
            )

            print(
                "  JUGADOR:",
                jugador
            )

            print(
                "  IMPORTE:",
                f"{cantidad:,} €"
            )

            print(
                "  VENDEDOR / ORIGEN:",
                vendedor if vendedor else "-"
            )

            if vendedor_id:

                print(
                    "      ID:",
                    vendedor_id
                )

            print(
                "  COMPRADOR / DESTINO:",
                comprador if comprador else "-"
            )

            if comprador_id:

                print(
                    "      ID:",
                    comprador_id
                )

            bids = item.get(
                "bids",
                []
            )

            if bids:

                print(
                    "  PUJAS:"
                )

                for bid in bids:

                    usuario_bid = bid.get(
                        "user",
                        {}
                    )

                    nombre_bid = usuario_bid.get(
                        "name",
                        "Usuario desconocido"
                    )

                    id_bid = usuario_bid.get(
                        "id"
                    )

                    cantidad_bid = bid.get(
                        "amount",
                        0
                    )

                    print(
                        f"      {nombre_bid} "
                        f"(ID {id_bid}) -> "
                        f"{cantidad_bid:,} €"
                    )

            else:

                print(
                    "  PUJAS: ninguna"
                )

            if comprador:

                resultado.append(
                    f"🟢 {fecha_formateada} | "
                    f"{comprador} ficha a "
                    f"{jugador} por "
                    f"{cantidad:,}€"
                )

            elif vendedor:

                resultado.append(
                    f"🔴 {fecha_formateada} | "
                    f"{vendedor} vende a "
                    f"{jugador} por "
                    f"{cantidad:,}€"
                )

            else:

                resultado.append(
                    f"⚽ {fecha_formateada} | "
                    f"Movimiento de "
                    f"{jugador} "
                    f"({cantidad:,}€)"
                )

    print(
        "======================================================"
    )

    print(
        "TOTAL OPERACIONES EN TODOS LOS EVENTOS:",
        total_operaciones
    )

    print(
        "TOTAL RESULTADOS GENERADOS:",
        len(resultado)
    )

    print(
        "======================================================"
    )

    # IMPORTANTE:
    # Antes se utilizaba:
    #
    # return resultado[:30]
    #
    # Eso limitaba artificialmente los movimientos
    # mostrados a únicamente 30 operaciones.
    #
    # Ahora devolvemos TODOS los resultados.

    return resultado


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
