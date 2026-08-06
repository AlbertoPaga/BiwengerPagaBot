import json
import requests

from pathlib import Path


_players = None


PLAYERS_URL = (
    "https://cf.biwenger.com/api/v2/competitions/"
    "la-liga/data?lang=es&score=2"
)


def get_players():

    global _players


    if _players is not None:

        return _players


    ruta = Path(__file__).parent / "players.json"


    if ruta.exists():

        try:

            with open(
                ruta,
                encoding="utf-8"
            ) as f:

                data = json.load(f)


            _players = data.get(
                "players",
                {}
            )


            if _players:

                return _players


        except Exception:

            pass


    print(
        "Descargando jugadores Biwenger..."
    )


    _players = descargar_players()


    guardar_players(
        _players,
        ruta
    )


    return _players



def descargar_players():

    respuesta = requests.get(
        PLAYERS_URL,
        timeout=20
    )


    respuesta.raise_for_status()


    data = respuesta.json()


    jugadores = data.get(
        "players",
        {}
    )


    if not jugadores:

        raise RuntimeError(
            "No se han encontrado jugadores en Biwenger"
        )


    return jugadores



def guardar_players(
    players,
    ruta
):

    datos = {
        "players": players
    }


    with open(
        ruta,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            datos,
            f,
            ensure_ascii=False,
            indent=2
        )


    print(
        f"Cache jugadores actualizado: {len(players)} jugadores"
    )



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