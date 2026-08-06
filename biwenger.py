from biwenger_client import BiwengerClient



def obtener_ligas():

    client = BiwengerClient()

    client.login()

    return client.leagues()



def cargar_liga(liga_id):


    client = BiwengerClient()

    client.login()


    liga = client.league(
        liga_id
    )


    data = liga.get(
        "data",
        {}
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


        data = board.get(
            "data",
            []
        )


        if isinstance(data, dict):

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



    for m in movimientos:


        tipo = m.get(
            "type",
            ""
        )


        contenido = m.get(
            "content",
            []
        )


        fecha = m.get(
            "date",
            ""
        )


        if tipo in [
            "market",
            "transfer"
        ]:


            for item in contenido:


                jugador = item.get(
                    "player",
                    "?"
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
                        f"🟢 {comprador} ficha jugador {jugador} por {cantidad:,}€"
                    )


                elif vendedor:

                    resultado.append(
                        f"🔴 {vendedor} vende jugador {jugador} por {cantidad:,}€"
                    )


                else:

                    resultado.append(
                        f"⚽ Movimiento jugador {jugador} ({cantidad:,}€)"
                    )



        elif tipo == "playerMovements":


            for item in contenido:


                jugador = item.get(
                    "player",
                    "?"
                )


                resultado.append(
                    f"🔄 Cambio jugador {jugador}"
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