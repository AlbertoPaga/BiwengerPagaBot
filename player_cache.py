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

        _players = data.get(
            "players",
            {}
        )

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



if __name__ == "__main__":

    jugadores = get_players()

    print(
        "TOTAL JUGADORES:",
        len(jugadores)
    )


    pruebas = [
        10182,
        31267,
        18382,
        41072
    ]


    for pid in pruebas:

        print(
            pid,
            "->",
            get_player_name(pid)
        )