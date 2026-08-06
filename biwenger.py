from biwenger_client import BiwengerClient



def obtener_ligas():

    client=BiwengerClient()

    client.login()

    return client.leagues()



def cargar_liga(
    liga_id
):


    client=BiwengerClient()

    client.login()


    liga=client.league(
        liga_id
    )


    print("===================")
    print("RESPUESTA LIGA")
    print(liga)
    print("===================")



    data=liga.get(
        "data",
        {}
    )


    usuarios=[]


    if "users" in data:

        usuarios=data["users"]


    elif "members" in data:

        usuarios=data["members"]


    elif "managers" in data:

        usuarios=data["managers"]



    movimientos=cargar_movimientos(
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

        board=client.board(
            liga_id
        )


        print("===================")
        print("RESPUESTA BOARD")
        print(board)
        print("===================")



        data=board.get(
            "data",
            []
        )


        if isinstance(data,dict):

            for key in [
                "items",
                "movements",
                "transactions",
                "board"
            ]:

                if key in data:

                    return data[key]


        return data



    except Exception as e:


        print(
            "ERROR MOVIMIENTOS:",
            e
        )


        return []



def patrimonio(
    usuario
):


    dinero=usuario.get(
        "balance",
        0
    )


    valor=usuario.get(
        "teamValue",
        0
    )


    return (
        dinero,
        valor,
        dinero+valor
    )