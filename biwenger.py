from pprint import pprint
from datetime import datetime, timezone

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


def timestamp_a_fecha(
    timestamp
):

    if not timestamp:

        return "Sin fecha"


    try:

        fecha = datetime.fromtimestamp(
            int(timestamp),
            tz=timezone.utc
        )


        return fecha.strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )


    except Exception:

        return str(timestamp)


def cargar_movimientos(
    client,
    liga_id
):

    print(
        "\n======================================================"
    )

    print(
        "        DESCARGANDO HISTORIAL DEL MERCADO"
    )

    print(
        "======================================================"
    )


    try:

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
            f"TIPO RESPUESTA: {type(movimientos)}"
        )


        if isinstance(
            movimientos,
            dict
        ):

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


        if not isinstance(
            data,
            list
        ):

            print(
                "ERROR: los movimientos no son una lista"
            )


            print(
                "RESPUESTA COMPLETA:"
            )


            pprint(
                movimientos
            )


            return []


        print(
            f"TOTAL MOVIMIENTOS DESCARGADOS: {len(data)}"
        )


        print(
            "======================================================"
        )


        mostrar_movimientos_detallados(
            data
        )


        return formatear_movimientos(
            data
        )


    except Exception as e:

        print(
            "ERROR MOVIMIENTOS:",
            e
        )


        return []


def mostrar_movimientos_detallados(
    movimientos
):

    print(
        "\n======================================================"
    )

    print(
        "           DETALLE DE MOVIMIENTOS"
    )

    print(
        "======================================================"
    )


    for numero, movimiento in enumerate(
        movimientos,
        start=1
    ):

        tipo = movimiento.get(
            "type",
            "desconocido"
        )


        fecha_timestamp = movimiento.get(
            "date"
        )


        fecha = timestamp_a_fecha(
            fecha_timestamp
        )


        titulo = movimiento.get(
            "title",
            ""
        )


        fijo = movimiento.get(
            "fixed"
        )


        print(
            "\n------------------------------------------------------"
        )

        print(
            f"MOVIMIENTO #{numero}"
        )

        print(
            "------------------------------------------------------"
        )


        print(
            f"FECHA: {fecha}"
        )


        print(
            f"TIMESTAMP: {fecha_timestamp}"
        )


        print(
            f"TIPO: {tipo}"
        )


        print(
            f"TÍTULO: {titulo}"
        )


        print(
            f"FIXED: {fijo}"
        )


        contenido = movimiento.get(
            "content",
            []
        )


        if not isinstance(
            contenido,
            list
        ):

            print(
                "CONTENT NO ES LISTA:"
            )

            pprint(
                contenido
            )

            continue


        print(
            f"OPERACIONES EN CONTENT: {len(contenido)}"
        )


        for indice, item in enumerate(
            contenido,
            start=1
        ):

            mostrar_operacion(
                item,
                indice
            )


        autor = movimiento.get(
            "author"
        )


        if autor:

            print(
                "AUTOR:"
            )

            pprint(
                autor
            )

        else:

            print(
                "AUTOR: None"
            )


    print(
        "\n======================================================"
    )

    print(
        "        FIN DETALLE DE MOVIMIENTOS"
    )

    print(
        "======================================================"
    )


def mostrar_operacion(
    item,
    indice
):

    print(
        f"\n  OPERACIÓN #{indice}"
    )

    print(
        "  -----------------------------"
    )


    player_id = item.get(
        "player"
    )


    if player_id:

        jugador = get_player_name(
            player_id
        )

    else:

        jugador = "Jugador desconocido"


    print(
        f"  PLAYER ID: {player_id}"
    )


    print(
        f"  JUGADOR: {jugador}"
    )


    cantidad = item.get(
        "amount"
    )


    print(
        f"  IMPORTE: {cantidad:,} €"
        if isinstance(
            cantidad,
            (int, float)
        )
        else f"  IMPORTE: {cantidad}"
    )


    comprador = item.get(
        "to"
    )


    vendedor = item.get(
        "from"
    )


    if comprador:

        print(
            "  COMPRADOR / DESTINO:"
        )


        print(
            f"      ID: {comprador.get('id')}"
        )


        print(
            f"      NOMBRE: {comprador.get('name', 'Sin nombre')}"
        )


    else:

        print(
            "  COMPRADOR / DESTINO: -"
        )


    if vendedor:

        print(
            "  VENDEDOR / ORIGEN:"
        )


        print(
            f"      ID: {vendedor.get('id')}"
        )


        print(
            f"      NOMBRE: {vendedor.get('name', 'Sin nombre')}"
        )


    else:

        print(
            "  VENDEDOR / ORIGEN: -"
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

            if not isinstance(
                bid,
                dict
            ):

                pprint(
                    bid
                )

                continue


            bid_amount = bid.get(
                "amount"
            )


            user = bid.get(
                "user",
                {}
            )


            if isinstance(
                user,
                dict
            ):

                user_id = user.get(
                    "id"
                )

                user_name = user.get(
                    "name",
                    "Sin nombre"
                )

            else:

                user_id = None

                user_name = "Sin nombre"


            if isinstance(
                bid_amount,
                (int, float)
            ):

                cantidad_bid = (
                    f"{bid_amount:,} €"
                )

            else:

                cantidad_bid = str(
                    bid_amount
                )


            print(
                f"      {user_name} "
                f"(ID {user_id}) -> "
                f"{cantidad_bid}"
            )


    else:

        print(
            "  PUJAS: ninguna"
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


    for movimiento in movimientos:

        tipo = movimiento.get(
            "type",
            ""
        )


        fecha = timestamp_a_fecha(
            movimiento.get(
                "date"
            )
        )


        contenido = movimiento.get(
            "content",
            []
        )


        if not isinstance(
            contenido,
            list
        ):

            continue


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


            comprador = item.get(
                "to"
            )


            vendedor = item.get(
                "from"
            )


            if comprador:

                nombre_comprador = comprador.get(
                    "name",
                    "Sin nombre"
                )


                resultado.append(
                    f"🟢 {fecha} | "
                    f"{nombre_comprador} ficha a "
                    f"{jugador} por "
                    f"{cantidad:,}€"
                )


            elif vendedor:

                nombre_vendedor = vendedor.get(
                    "name",
                    "Sin nombre"
                )


                resultado.append(
                    f"🔴 {fecha} | "
                    f"{nombre_vendedor} vende a "
                    f"{jugador} por "
                    f"{cantidad:,}€"
                )


            else:

                resultado.append(
                    f"⚽ {fecha} | "
                    f"{tipo} | "
                    f"{jugador} | "
                    f"{cantidad:,}€"
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
