import json
from pathlib import Path


_players = None


def get_players():

    global _players

    if _players is None:

        ruta = Path(__file__).parent / "players.json"

        with open(
            ruta,
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        _players = data["players"]

    return _players


def get_player_name(player_id):

    jugador = get_players().get(str(player_id))

    if jugador:

        return jugador["name"]

    return f"Jugador {player_id}"