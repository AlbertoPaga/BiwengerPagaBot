from io import BytesIO

from lineup_image import generar_imagen_alineacion, normalizar_alineacion


def _team():
    names = [
        ("Sivera", 1),
        ("Jonny", 2),
        ("Koski", 2),
        ("Tenaglia", 2),
        ("Yusi Enríquez", 2),
        ("Blanco", 3),
        ("Aleñá", 3),
        ("Ibáñez", 3),
        ("Mañas", 4),
        ("Martínez", 4),
        ("Ángel Pérez", 4),
    ]
    return {
        "id": 91,
        "name": "Alavés",
        "reports": [
            {
                "player": {
                    "id": index + 1,
                    "name": name,
                    "position": position,
                },
                "points": 6 if position != 4 else 8,
            }
            for index, (name, position) in enumerate(names)
        ],
    }


def test_normalizar_alineacion():
    players = normalizar_alineacion(_team())
    assert len(players) == 11
    assert players[0]["position_label"] == "POR"
    assert players[-1]["position_label"] == "DEL"


def test_generar_imagen_posible_sin_puntos():
    image = generar_imagen_alineacion(
        _team(),
        {"name": "Getafe"},
        confirmed=False,
    )
    assert isinstance(image, BytesIO)
    assert image.name == "alineacion.png"
    assert image.getvalue()[:8] == b"\x89PNG\r\n\x1a\n"


def test_generar_imagen_confirmada():
    image = generar_imagen_alineacion(
        _team(),
        {"name": "Getafe"},
        confirmed=True,
    )
    assert image.getvalue()[:8] == b"\x89PNG\r\n\x1a\n"
