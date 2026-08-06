import json
import logging

from pathlib import Path

from biwenger_client import BiwengerClient


CACHE_FILE = Path(__file__).parent / "players.json"


_players = None



def cargar_jugadores():

    global _players


    if _players is not None:

        return _players



    # 1. Intentar cargar cache existente

    if CACHE_FILE.exists():

        try:

            with open(
                CACHE_FILE,
                encoding="utf-8"
            ) as f:

                data = json.load(f)


            _players = data.get(
                "players",
                {}
            )


            logging.info(
                f"Jugadores cargados desde cache: {len(_players)}"
            )


            return _players


        except Exception:

            logging.exception(
                "Error leyendo players.json"
            )



    # 2. Crear cache nueva

    try:

        logging.info(
            "Descargando jugadores desde Biwenger..."
        )


        client = BiwengerClient()


        datos = client.players()


        jugadores = datos.get(
            "players",
            {}
        )


        if not jugadores:

            raise Exception(
                "Respuesta sin jugadores"
            )



        with open(
            CACHE_FILE,
            "w",
            encoding="utf-8"
        ) as f:


            json.dump(
                {
                    "players": jugadores
                },
                f,
                ensure_ascii=False,
                indent=2
            )


        logging.info(
            f"Cache creada con {len(jugadores)} jugadores"
        )


        _players = jugadores


        return jugadores



    except Exception:

        logging.exception(
            "Error cargando jugadores"
        )


        _players = {}


        return {}





def get_players():

    return cargar_jugadores()





def get_player_name(
    player_id
):


    jugadores = get_players()


    jugador = jugadores.get(
        str(player_id)
    )


    if jugador:


        return jugador.get(
            "name",
            f"Jugador {player_id}"
        )



    return f"Jugador {player_id}"