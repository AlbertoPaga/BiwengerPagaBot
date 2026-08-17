from datetime import datetime, timezone

from lineup_image import (
    alineacion_confirmada,
    obtener_alineacion_mostrable,
)


def jugador(player_id, name, position, points=None):
    return {
        "id": player_id,
        "name": name,
        "position": position,
        "points": points,
    }


def test_antes_del_partido_muestra_reports_sin_puntos():
    game = {
        "date": datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc).timestamp(),
        "home": {
            "name": "Local",
            "reports": [
                {"player": jugador(1, "Portero", 1, 7)},
            ],
        },
    }

    players, confirmed = obtener_alineacion_mostrable(
        game,
        "home",
        now=datetime(2026, 8, 20, 17, 0, tzinfo=timezone.utc),
    )

    assert confirmed is False
    assert players[0]["name"] == "Portero"
    assert players[0]["points"] == 7


def test_al_llegar_la_hora_busca_initial_lineup():
    game = {
        "date": datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc).timestamp(),
        "initialLineups": {
            "home": [
                jugador(99, "Titular real", 1, 0),
            ],
        },
        "home": {
            "name": "Local",
            "reports": [
                {"player": jugador(1, "Posible", 1, 0)},
            ],
        },
    }

    players, confirmed = obtener_alineacion_mostrable(
        game,
        "home",
        now=datetime(2026, 8, 20, 18, 1, tzinfo=timezone.utc),
    )

    assert confirmed is True
    assert players[0]["name"] == "Titular real"


def test_initial_lineups_true_confirma_aunque_no_haya_fecha():
    game = {
        "initialLineups": True,
        "home": {
            "reports": [
                {"player": jugador(1, "Jugador", 1, 5)},
            ],
        },
    }

    assert alineacion_confirmada(game) is True
