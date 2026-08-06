import logging
import requests


_players = None


BIWENGER_PLAYERS_URL = (
    "https://cf.biwenger.com/api/v2/"
    "competitions/la-liga/data"
    "?lang=es&score=2"
)



def cargar_jugadores():

    global _players


    if _players is not None:

        return _players


    try:

        logging.info(
            "Cargando jugadores desde Biwenger..."
        )


        respuesta = requests.get(
            BIWENGER_PLAYERS_URL,
            timeout=15
        )


        respuesta.raise_for_status()


        datos = respuesta.json()


        _players = datos.get(
            "players",
            {}
        )


        logging.info(
            "Jugadores cargados: %s",
            len(_players)
        )


        return _players


    except Exception as e:

        logging.exception(
            "Error cargando jugadores"
        )


        _players = {}


        return _players



def get_player_name(
    player_id
):

    jugadores = cargar_jugadores()


    jugador = jugadores.get(
        str(player_id)
    )


    if jugador:

        return jugador.get(
            "name",
            f"Jugador {player_id}"
        )


    return (
        f"Jugador {player_id}"
    )