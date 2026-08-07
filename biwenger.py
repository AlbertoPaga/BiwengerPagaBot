```python
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

    """
    Descarga TODO el historial del tablón de la liga.

    Se solicitan únicamente movimientos de:

        - market
        - transfer

    Se descargan en páginas de 100 elementos.

    La paginación se realiza utilizando la fecha
    más antigua recibida en cada página:

        página 1
        ↓
        fecha más antigua
        ↓
        página 2 con date = fecha - 1
        ↓
        fecha más antigua
        ↓
        ...

    El proceso termina cuando Biwenger no devuelve
    más movimientos.
    """

    movimientos = []

    cursor = None

    pagina = 0

    print(
        "\n======================================================"
    )

    print(
        "          DESCARGANDO HISTORIAL DEL MERCADO"
    )

    print(
        "======================================================"
    )

    while True:

        pagina += 1

        params = {
            "type": "transfer,market",
            "limit": 100
        }

        if cursor is not None:

            params["date"] = cursor

        print(
            f"\n---------- PÁGINA {pagina} ----------"
        )

        print(
            "PARAMETROS:",
            params
        )

        try:

            respuesta = client.get(
                f"/league/{liga_id}/board",
                params=params
            )

        except Exception as e:

            print(
                "\nERROR DESCARGANDO PÁGINA:",
                pagina
            )

            print(
                "ERROR:",
                e
            )

            break

        data = respuesta.get(
            "data",
            []
        )

        if not isinstance(
            data,
            list
        ):

            print(
                "ERROR: data no es una lista."
            )

            print(
                "TIPO:",
                type(data)
            )

            break

        print(
            "MOVIMIENTOS RECIBIDOS:",
            len(data)
        )

        if not data:

            print(
                "\nNo hay más movimientos."
            )

            break

        movimientos.extend(
            data
        )

        fechas = []

        for movimiento in data:

            fecha = movimiento.get(
                "date"
            )

            if fecha is not None:

                fechas.append(
                    fecha
                )

        if not fechas:

            print(
                "\nLos movimientos recibidos "
                "no contienen campo 'date'."
            )

            print(
                "No se puede continuar la paginación."
            )

            break

        fecha_mas_antigua = min(
            fechas
        )

        fecha_mas_reciente = max(
            fechas
        )

        print(
            "FECHA MÁS RECIENTE:",
            fecha_mas_reciente
        )

        print(
            "FECHA MÁS ANTIGUA:",
            fecha_mas_antigua
        )

        nuevo_cursor = (
            fecha_mas_antigua - 1
        )

        if cursor is not None:

            if nuevo_cursor >= cursor:

                print(
                    "\nAVISO: el cursor no está avanzando "
                    "hacia atrás."
                )

                print(
                    "Cursor actual:",
                    cursor
                )

                print(
                    "Nuevo cursor:",
                    nuevo_cursor
                )

                print(
                    "Se detiene la paginación para evitar "
                    "un bucle infinito."
                )

                break

        cursor = nuevo_cursor

    print(
        "\n======================================================"
    )

    print(
        "              DESCARGA FINALIZADA"
    )

    print(
        "======================================================"
    )

    print(
        "PÁGINAS DESCARGADAS:",
        pagina
    )

    print(
        "TOTAL MOVIMIENTOS:",
        len(movimientos)
    )

    print(
        "======================================================\n"
    )

    return movimientos


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
                        f"🟢 {comprador} ficha a "
                        f"{jugador} por "
                        f"{cantidad:,}€"
                    )

                elif vendedor:

                    resultado.append(
                        f"🔴 {vendedor} vende a "
                        f"{jugador} por "
                        f"{cantidad:,}€"
                    )

                else:

                    resultado.append(
                        f"⚽ Movimiento de "
                        f"{jugador} "
                        f"({cantidad:,}€)"
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
```
