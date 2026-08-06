import json
import logging

from pathlib import Path

from biwenger_client import BiwengerClient



PLAYERS_FILE = Path(
    "/app/players.json"
)



def cargar_jugadores():


    logging.info(
        "Descargando jugadores desde Biwenger..."
    )


    try:

        client = BiwengerClient()


        datos = client.players()



        jugadores = {}



        data = datos.get(
            "data",
            {}
        )



        players = data.get(
            "players",
            {}
        )



        if isinstance(players, dict):


            for player_id, jugador in players.items():


                if not isinstance(
                    jugador,
                    dict
                ):
                    continue



                jugadores[str(player_id)] = {

                    "name":
                        jugador.get(
                            "name",
                            f"Jugador {player_id}"
                        ),


                    "team":
                        jugador.get(
                            "team",
                            {}
                        )
                }



        elif isinstance(players, list):


            for jugador in players:


                if not isinstance(
                    jugador,
                    dict
                ):
                    continue



                player_id = jugador.get(
                    "id"
                )


                if player_id:


                    jugadores[str(player_id)] = {

                        "name":
                            jugador.get(
                                "name",
                                f"Jugador {player_id}"
                            ),


                        "team":
                            jugador.get(
                                "team",
                                {}
                            )
                    }



        with open(
            PLAYERS_FILE,
            "w",
            encoding="utf-8"
        ) as archivo:


            json.dump(
                {
                    "players": jugadores
                },
                archivo,
                ensure_ascii=False,
                indent=2
            )



        logging.info(
            f"Jugadores guardados: {len(jugadores)}"
        )


        return jugadores



    except Exception:


        logging.exception(
            "Error cargando jugadores"
        )


        return {}




def cargar_cache():


    if not PLAYERS_FILE.exists():

        return cargar_jugadores()



    try:

        with open(
            PLAYERS_FILE,
            encoding="utf-8"
        ) as archivo:

            datos = json.load(
                archivo
            )


        return datos.get(
            "players",
            {}
        )


    except Exception:


        return cargar_jugadores()




def actualizar_cache():


    return cargar_jugadores()




def get_player_name(
    player_id
):


    jugadores = cargar_cache()


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