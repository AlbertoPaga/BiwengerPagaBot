from biwenger_client import BiwengerClient


def cargar_liga():

    client = BiwengerClient()
    client.login()

    liga = client.get_league_by_name("Los más sucios")

    liga_id = liga["id"]

    datos_liga = client.league(liga_id)

    usuarios = {}

    for u in datos_liga["data"]["users"]:

        usuarios[u["id"]] = {
            "nombre": u["name"],
            "compras": 0,
            "ventas": 0,
            "comprados": [],
            "vendidos": [],
        }

    eventos = descargar_tablon(
        client,
        liga_id,
    )

    try:
        jugadores = client.players()

        catalogo = {
            p["id"]: p
            for p in jugadores["data"]
        }

    except Exception:

        # Todavía no conocemos el endpoint definitivo.
        catalogo = {}

    procesar_movimientos(
        eventos,
        usuarios,
        catalogo,
    )

    plantillas = cargar_plantillas(
        client,
        liga_id,
        usuarios,
        catalogo,
    )

    return usuarios, plantillas


def descargar_tablon(
    client,
    liga_id,
):

    movimientos = []

    cursor = None

    while True:

        endpoint = (
            f"/league/{liga_id}/board"
            "?type=transfer,market"
            "&limit=100"
        )

        if cursor:

            endpoint += f"&date={cursor}"

        respuesta = client.get(endpoint)

        pagina = respuesta.get(
            "data",
            [],
        )

        if not pagina:
            break

        movimientos.extend(pagina)

        fecha = min(
            x["date"]
            for x in pagina
        )

        if fecha == cursor:
            break

        cursor = fecha - 1

    return movimientos


def procesar_movimientos(
    eventos,
    usuarios,
    catalogo,
):

    for evento in eventos:

        tipo = evento.get("type")

        for mov in evento.get(
            "content",
            [],
        ):

            jugador = catalogo.get(
                mov.get("player")
            )

            if jugador:

                nombre = jugador.get(
                    "name",
                    str(mov.get("player"))
                )

            else:

                nombre = str(
                    mov.get("player")
                )

            cantidad = mov.get(
                "amount",
                0,
            )

            if tipo == "transfer":

                vendedor = mov["from"]["id"]

                if vendedor in usuarios:

                    usuarios[vendedor]["ventas"] += cantidad

                    usuarios[vendedor]["vendidos"].append(
                        (
                            nombre,
                            cantidad,
                        )
                    )

            elif tipo == "market":

                comprador = (
                    mov.get("to", {})
                    .get("id")
                )

                if comprador in usuarios:

                    usuarios[comprador]["compras"] += cantidad

                    usuarios[comprador]["comprados"].append(
                        (
                            nombre,
                            cantidad,
                        )
                    )


def cargar_plantillas(
    client,
    liga_id,
    usuarios,
    catalogo,
):

    """
    TODO

    Este endpoint ha cambiado en la API v2.

    En cuanto localicemos el endpoint correcto
    devolveremos aquí las plantillas.
    """

    resultado = {}

    for uid in usuarios:

        resultado[uid] = []

    return resultado


def patrimonio(
    usuario,
    plantilla,
):

    valor = 0

    for jugador in plantilla:

        if isinstance(jugador, dict):

            valor += jugador.get(
                "price",
                0,
            )

        else:

            valor += getattr(
                jugador,
                "price",
                0,
            )

    dinero = (
        20000000
        + usuario["ventas"]
        - usuario["compras"]
    )

    return (
        dinero,
        valor,
        dinero + valor,
    )