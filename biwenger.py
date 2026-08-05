import pybiwenger

from pybiwenger import PlayersAPI, LeagueAPI

from config import (
    BIWENGER_USER,
    BIWENGER_PASSWORD
)


def cargar_liga():

    pybiwenger.authenticate(
        username=BIWENGER_USER,
        password=BIWENGER_PASSWORD
    )

    try:
        league = LeagueAPI()
        players = PlayersAPI()

    except Exception as e:
        print("ERROR CREANDO LEAGUE/PLAYERS:")
        print(type(e))
        print(repr(e))
        raise

    liga = league.account.leagues[1]

    players.league_id = liga.id

    usuarios = {}

    for u in players.get_league_users():

        usuarios[u.id] = {
            "nombre": u.name,
            "compras": 0,
            "ventas": 0,
            "comprados": [],
            "vendidos": []
        }


    eventos = descargar_tablon(
        league,
        liga.id
    )


    catalogo = {
        p.id:p
        for p in players.get_all_players()
    }


    procesar_movimientos(
        eventos,
        usuarios,
        catalogo
    )


    plantillas = cargar_plantillas(
        league,
        liga.id,
        usuarios,
        catalogo
    )


    return usuarios, plantillas




def descargar_tablon(
    league,
    liga_id
):

    movimientos=[]

    cursor=None


    while True:


        if cursor:

            url=(
                f"https://biwenger.as.com/api/v2/league/"
                f"{liga_id}/board"
                f"?type=transfer,market"
                f"&limit=100"
                f"&date={cursor}"
            )

        else:

            url=(
                f"https://biwenger.as.com/api/v2/league/"
                f"{liga_id}/board"
                f"?type=transfer,market"
                f"&limit=100"
            )


        respuesta=league.fetch(url)


        if not respuesta:
            break


        pagina=respuesta.get(
            "data",
            []
        )


        if not pagina:
            break


        movimientos.extend(
            pagina
        )


        fecha=min(
            x["date"]
            for x in pagina
        )


        if cursor == fecha:
            break


        cursor=fecha-1


    return movimientos




def procesar_movimientos(
    eventos,
    usuarios,
    catalogo
):


    for evento in eventos:

        tipo=evento.get(
            "type"
        )


        for mov in evento.get(
            "content",
            []
        ):


            jugador=catalogo.get(
                mov.get("player")
            )


            nombre=(
                jugador.name
                if jugador
                else str(mov.get("player"))
            )


            cantidad=mov.get(
                "amount",
                0
            )


            if tipo=="transfer":

                vendedor=mov["from"]["id"]

                if vendedor in usuarios:

                    usuarios[vendedor]["ventas"] += cantidad

                    usuarios[vendedor]["vendidos"].append(
                        (nombre,cantidad)
                    )


            elif tipo=="market":

                comprador=(
                    mov.get("to",{})
                    .get("id")
                )


                if comprador in usuarios:

                    usuarios[comprador]["compras"] += cantidad

                    usuarios[comprador]["comprados"].append(
                        (nombre,cantidad)
                    )




def cargar_plantillas(
    league,
    liga_id,
    usuarios,
    catalogo
):


    url=(
        f"https://biwenger.as.com/api/v2/league/"
        f"{liga_id}?fields=users(players)"
    )


    data=league.fetch(url)


    resultado={}


    ids=list(
        usuarios.keys()
    )


    for i,u in enumerate(
        data["data"]["users"]
    ):

        uid=ids[i]

        resultado[uid]=[]


        for p in u["players"]:

            jugador=catalogo.get(
                p["id"]
            )

            if jugador:
                resultado[uid].append(
                    jugador
                )


    return resultado




def patrimonio(usuario, plantilla):

    valor=sum(
        getattr(p,"price",0) or 0
        for p in plantilla
    )


    dinero=(
        20000000
        +
        usuario["ventas"]
        -
        usuario["compras"]
    )


    return dinero,valor,dinero+valor