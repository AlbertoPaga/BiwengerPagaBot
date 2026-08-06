import json
import logging

from pathlib import Path

from biwenger_client import BiwengerClient


CACHE_FILE = Path(__file__).parent / "players.json"


_players = None



def cargar_jugadores():

    global _players


    try:

        logging.info(
            "Descargando jugadores desde Biwenger..."
        )


        client = BiwengerClient()


        datos = client.players()


        jugadores = {}


        data = datos.get(
            "data",
            {}
        )


        # Biwenger devuelve estructuras distintas
        # según endpoint/temporada

        lista = data.get(
            "players",
            []
        )


        for jugador in lista:

            jugadores[
                str(jugador["id"])
            ] = {

                "name":
                    jugador.get(
                        "name",
                        f"Jugador {jugador['id']}"
                    )
            }



        CACHE_FILE.write_text(
            json.dumps(
                {
                    "players": jugadores
                },
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )


        _players = jugadores


        logging.info(
            f"Jugadores guardados: {len(jugadores)}"
        )


        return jugadores



    except Exception:

        logging.exception(
            "Error cargando jugadores"
        )


        return {}



def get_players():

    global _players


    if _players is None:


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


            except Exception:

                _players = {}



        else:

            _players = cargar_jugadores()



    return _players



def get_player_name(
    player_id
):

    jugador = get_players().get(
        str(player_id)
    )


    if jugador:

        return jugador.get(
            "name",
            f"Jugador {player_id}"
        )


    return f"Jugador {player_id}"