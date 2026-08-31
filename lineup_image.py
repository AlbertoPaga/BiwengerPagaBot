"""Generador de imágenes de alineaciones para Telegram."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


POSITION_LABELS = {
    1: "POR",
    2: "DEF",
    3: "MED",
    4: "DEL",
}

# Campo vertical:
# POR abajo -> DEF -> MED -> DEL arriba
_ROW_Y = {
    1: 0.88,
    2: 0.68,
    3: 0.45,
    4: 0.20,
}


class LineupImageError(ValueError):
    """Error de datos al construir una imagen de alineación."""


# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------


def _font(size: int, bold: bool = False):
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )

    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)

    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Normalización de jugadores
# ---------------------------------------------------------------------------


def _normalizar_jugador(
    jugador: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(jugador, dict):
        return None

    # Algunos payloads vienen como:
    #
    # {
    #     "player": {
    #         "id": ...,
    #         "name": ...,
    #         "position": ...
    #     },
    #     "points": ...
    # }
    #
    # y otros directamente como jugador.
    player = jugador.get("player")

    if isinstance(player, dict):
        datos = dict(player)
        datos.update(
            {
                key: value
                for key, value in jugador.items()
                if key != "player"
            }
        )
    else:
        datos = jugador

    try:
        position = int(datos.get("position"))
    except (TypeError, ValueError):
        return None

    if position not in POSITION_LABELS:
        return None

    return {
        "id": datos.get("id"),
        "name": str(
            datos.get("name")
            or datos.get("nombre")
            or "Jugador"
        ),
        "position": position,
        "position_label": POSITION_LABELS[position],
        "alt_positions": datos.get("altPositions") or [],
        "points": datos.get("points"),
        "photo": (
            datos.get("photo")
            or datos.get("image")
            or datos.get("imageUrl")
        ),
    }


def _aplanar_jugadores(valor: Any) -> list[dict[str, Any]]:
    """Convierte las diferentes estructuras de lineup en una lista."""

    if isinstance(valor, list):
        return [
            item
            for item in valor
            if isinstance(item, dict)
        ]

    if not isinstance(valor, dict):
        return []

    for key in (
        "players",
        "starters",
        "lineup",
        "initialLineup",
        "initialLineups",
        "startingXI",
        "data",
    ):
        nested = valor.get(key)

        if isinstance(nested, list):
            return [
                item
                for item in nested
                if isinstance(item, dict)
            ]

        if isinstance(nested, dict):
            result = _aplanar_jugadores(nested)

            if result:
                return result

    # Algunos payloads pueden ser:
    #
    # {
    #     "1234": {...jugador...},
    #     "5678": {...jugador...}
    # }
    valores = list(valor.values())

    if valores and all(
        isinstance(item, dict)
        for item in valores
    ):
        return valores

    return []


def _normalizar_lista_jugadores(
    jugadores: list[Any],
) -> list[dict[str, Any]]:
    resultado: list[dict[str, Any]] = []
    vistos: set[Any] = set()

    for jugador in jugadores:
        normalizado = _normalizar_jugador(jugador)

        if normalizado is None:
            continue

        player_id = normalizado.get("id")

        if (
            player_id is not None
            and player_id in vistos
        ):
            continue

        if player_id is not None:
            vistos.add(player_id)

        resultado.append(normalizado)

        # Un once son 11 jugadores.
        if len(resultado) == 11:
            break

    return resultado


# ---------------------------------------------------------------------------
# Alineación de un equipo / partido
# ---------------------------------------------------------------------------



def normalizar_alineacion(
    team: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Obtiene la alineación posible de un equipo para un partido.

    Para partidos en PREVIEW, Biwenger proporciona el posible XI
    directamente en:

        team["reports"]

    Cada elemento tiene:

        {
            "player": {
                "id": ...,
                "name": ...,
                "position": ...
            },
            "points": None
        }

    IMPORTANTE:
    reports se utiliza aquí SOLO para partidos que todavía no han
    comenzado. No debe confundirse con la alineación de un manager.
    """

    if not isinstance(team, dict):
        return []

    reports = team.get("reports")

    if not isinstance(reports, list):
        return []

    resultado = []

    for report in reports:
        if not isinstance(report, dict):
            continue

        player = report.get("player")

        if not isinstance(player, dict):
            continue

        jugador = _normalizar_jugador(
            {
                "player": player,
                "points": report.get("points"),
            }
        )

        if jugador is None:
            continue

        resultado.append(jugador)

        # Un posible XI son 11 jugadores.
        if len(resultado) == 11:
            break

    return resultado





def _lista_candidatos_alineacion(
    game: dict[str, Any],
    team_key: str,
) -> list[Any]:
    """
    Busca el once confirmado sin asumir una única estructura de Biwenger.
    """

    team = game.get(team_key) or {}

    candidatos: list[Any] = []

    if isinstance(team, dict):
        for key in (
            "initialLineup",
            "initialLineups",
            "lineup",
            "lineups",
            "starters",
            "startingXI",
        ):
            value = team.get(key)

            if value:
                candidatos.append(value)

    initial = game.get("initialLineups")

    if isinstance(initial, dict):
        value = initial.get(team_key)

        if value:
            candidatos.append(value)

    elif isinstance(initial, list):
        candidatos.append(initial)

    for key in (
        "lineups",
        "initialLineup",
        "starters",
        "startingXI",
    ):
        value = game.get(key)

        if isinstance(value, dict):
            value = value.get(team_key)

        if value:
            candidatos.append(value)

    return candidatos


def normalizar_alineacion_confirmada(
    game: dict[str, Any],
    team_key: str,
) -> list[dict[str, Any]]:
    """
    Obtiene exclusivamente el 11 inicial real del partido.

    NO hace fallback a ``reports``.
    """

    for candidato in _lista_candidatos_alineacion(
        game,
        team_key,
    ):
        jugadores = _aplanar_jugadores(candidato)

        resultado = _normalizar_lista_jugadores(
            jugadores
        )

        if resultado:
            return resultado

    return []


def alineacion_confirmada(
    game: dict[str, Any],
    now: datetime | None = None,
) -> bool:
    """
    Determina si el partido debe tratarse como confirmado.

    Antes del inicio:
        11 POSIBLE

    Después del inicio:
        11 INICIAL

    Si Biwenger marca ``initialLineups=True``, tiene prioridad.
    """

    if not isinstance(game, dict):
        return False

    if game.get("initialLineups") is True:
        return True

    timestamp = game.get("date")

    if timestamp is None:
        return False

    try:
        partido = datetime.fromtimestamp(
            float(timestamp),
            tz=timezone.utc,
        )

        actual = now or datetime.now(timezone.utc)

        return actual >= partido

    except (
        TypeError,
        ValueError,
        OSError,
        OverflowError,
    ):
        return False


def obtener_alineacion_mostrable(
    game: dict[str, Any],
    team_key: str,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], bool]:

    if not isinstance(game, dict):
        return [], False

    team = game.get(team_key) or {}

    if not isinstance(team, dict):
        return [], False

    status = str(
        game.get("status") or ""
    ).lower()

    # ---------------------------------------------------------
    # PREVIEW → posible XI desde reports
    # ---------------------------------------------------------

    if status == "preview":
        jugadores = normalizar_alineacion(team)

        return jugadores, False

    # ---------------------------------------------------------
    # LIVE / FINISHED → XI inicial real
    # ---------------------------------------------------------

    jugadores = normalizar_alineacion_confirmada(
        game,
        team_key,
    )

    if jugadores:
        return jugadores, True

    return [], True

# ---------------------------------------------------------------------------
# Once elegido por cada miembro de la liga
# ---------------------------------------------------------------------------


def normalizar_once_manager(
    players: list[Any],
) -> list[dict[str, Any]]:
    """
    Normaliza el once elegido por un manager.

    Esta función está pensada para datos procedentes de:

        standings[].lineup.players

    y NO de los ``reports`` de un partido.

    Esto es importante porque el "once de la jornada" de un miembro es
    independiente de los jugadores que posteriormente hayan participado
    en cada partido.
    """

    if not isinstance(players, list):
        return []

    resultado: list[dict[str, Any]] = []
    vistos: set[Any] = set()

    for jugador in players:
        normalizado = _normalizar_jugador(jugador)

        if normalizado is None:
            continue

        player_id = normalizado.get("id")

        if (
            player_id is not None
            and player_id in vistos
        ):
            continue

        if player_id is not None:
            vistos.add(player_id)

        resultado.append(normalizado)

        if len(resultado) == 11:
            break

    return resultado


def obtener_once_manager(
    miembro: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """
    Extrae el once elegido por un miembro desde standings.

    Espera estructuras del estilo:

        {
            "name": "Alberto",
            "lineup": {
                "formation": "4-3-3",
                "players": [...]
            }
        }

    También soporta que ``lineup`` sea directamente una lista.
    """

    if not isinstance(miembro, dict):
        return [], ""

    lineup = miembro.get("lineup")

    formation = ""

    if isinstance(lineup, dict):
        formation = str(
            lineup.get("formation")
            or lineup.get("system")
            or lineup.get("style")
            or ""
        )

        players = lineup.get("players")

        if isinstance(players, list):
            return (
                normalizar_once_manager(players),
                formation,
            )

        players = _aplanar_jugadores(lineup)

        return (
            normalizar_once_manager(players),
            formation,
        )

    if isinstance(lineup, list):
        return (
            normalizar_once_manager(lineup),
            formation,
        )

    # Compatibilidad con posibles payloads donde lineup viene anidado.
    for key in (
        "selectedLineup",
        "startingXI",
        "startingLineup",
        "players",
    ):
        value = miembro.get(key)

        if isinstance(value, list):
            return (
                normalizar_once_manager(value),
                formation,
            )

    return [], formation


# ---------------------------------------------------------------------------
# Posicionamiento
# ---------------------------------------------------------------------------


def _agrupar_por_posicion(
    jugadores: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    grouped = {
        1: [],
        2: [],
        3: [],
        4: [],
    }

    for jugador in jugadores:
        try:
            position = int(
                jugador.get("position")
            )
        except (TypeError, ValueError):
            continue

        if position in grouped:
            grouped[position].append(jugador)

    return grouped


def _xs_repartidas(
    cantidad: int,
    minimo: int,
    maximo: int,
) -> list[int]:
    if cantidad <= 0:
        return []

    if cantidad == 1:
        return [
            (minimo + maximo) // 2
        ]

    step = (
        maximo - minimo
    ) / (cantidad - 1)

    return [
        round(
            minimo + step * index
        )
        for index in range(cantidad)
    ]


def _slots_por_posicion(
    jugadores: list[dict[str, Any]],
    width: int,
    *,
    left: int | None = None,
    right: int | None = None,
):
    """
    Campo vertical.

    POR  -> abajo
    DEF  -> arriba del POR
    MED  -> centro
    DEL  -> arriba

    El payload nunca decide dónde pintar al jugador:
    manda ``position``.
    """

    grouped = _agrupar_por_posicion(
        jugadores
    )

    if left is None:
        left = int(width * 0.09)

    if right is None:
        right = int(width * 0.91)

    slots = []

    for position in (
        1,
        2,
        3,
        4,
    ):
        row = grouped[position]

        if not row:
            continue

        xs = _xs_repartidas(
            len(row),
            left,
            right,
        )

        y = round(
            width * _ROW_Y[position]
        )

        for jugador, x in zip(
            row,
            xs,
        ):
            slots.append(
                (
                    jugador,
                    x,
                    y,
                )
            )

    return slots


def _slots_partido(
    jugadores: list[dict[str, Any]],
    *,
    field_left: int,
    field_right: int,
    field_top: int,
    field_bottom: int,
    lado: str,
):
    """
    Posiciona una alineación en un campo horizontal.

    HOME:
        POR -> izquierda
        DEL -> centro

    AWAY:
        POR -> derecha
        DEL -> centro

    De esta forma ambas alineaciones se enfrentan correctamente.
    """

    grouped = _agrupar_por_posicion(
        jugadores
    )

    field_width = field_right - field_left
    field_height = field_bottom - field_top

    # Separación de las líneas dentro de cada mitad.
    if lado == "home":
        x_positions = {
            1: field_left + field_width * 0.08,
            2: field_left + field_width * 0.22,
            3: field_left + field_width * 0.34,
            4: field_left + field_width * 0.45,
        }
    else:
        x_positions = {
            1: field_right - field_width * 0.08,
            2: field_right - field_width * 0.22,
            3: field_right - field_width * 0.34,
            4: field_right - field_width * 0.45,
        }

    slots = []

    for position in (
        1,
        2,
        3,
        4,
    ):
        row = grouped[position]

        if not row:
            continue

        center_y = (
            field_top
            + field_height
            * _ROW_Y[position]
        )

        # No importa si es home o away:
        # los jugadores se distribuyen verticalmente.
        ys = _xs_repartidas(
            len(row),
            int(field_top + field_height * 0.10),
            int(field_top + field_height * 0.90),
        )

        # Para evitar que una línea de 4 defensas/medios quede demasiado
        # pegada al borde superior/inferior, usamos el centro de la fila
        # como referencia y una separación controlada.
        if len(row) == 1:
            ys = [round(center_y)]

        elif len(row) == 2:
            separation = field_height * 0.20
            ys = [
                round(center_y - separation / 2),
                round(center_y + separation / 2),
            ]

        elif len(row) == 3:
            separation = field_height * 0.24
            ys = [
                round(center_y - separation),
                round(center_y),
                round(center_y + separation),
            ]

        else:
            separation = field_height * 0.18
            total = separation * (len(row) - 1)
            start = center_y - total / 2

            ys = [
                round(
                    start
                    + separation * index
                )
                for index in range(len(row))
            ]

        x = round(
            x_positions[position]
        )

        for jugador, y in zip(
            row,
            ys,
        ):
            slots.append(
                (
                    jugador,
                    x,
                    y,
                )
            )

    return slots


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------


def _truncate(
    text: str,
    max_length: int = 16,
) -> str:
    if len(text) <= max_length:
        return text

    return (
        text[: max_length - 1]
        .rstrip()
        + "…"
    )


def _texto_puntos(
    points: Any,
) -> str | None:
    if points is None:
        return None

    try:
        return str(
            int(float(points))
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def _rounded_label(
    draw,
    xy,
    name,
    position,
    points=None,
    confirmed=False,
):
    x1, y1, x2, y2 = xy

    draw.rounded_rectangle(
        xy,
        radius=10,
        fill=(8, 18, 30),
        outline=(86, 112, 132),
        width=1,
    )

    name_font = _font(
        19,
        True,
    )

    pos_font = _font(
        14,
        True,
    )

    name_text = _truncate(
        str(name)
    )

    box = draw.textbbox(
        (0, 0),
        name_text,
        font=name_font,
    )

    draw.text(
        (
            (
                x1
                + x2
                - box[2]
                + box[0]
            ) // 2,
            y1 + 7,
        ),
        name_text,
        font=name_font,
        fill=(245, 248, 250),
    )

    position_text = str(
        position
    )

    puntos = _texto_puntos(
        points
    )

    if confirmed and puntos is not None:
        position_text = (
            f"{position}  •  {puntos} pts"
        )

    box = draw.textbbox(
        (0, 0),
        position_text,
        font=pos_font,
    )

    draw.text(
        (
            (
                x1
                + x2
                - box[2]
                + box[0]
            ) // 2,
            y1 + 34,
        ),
        position_text,
        font=pos_font,
        fill=(139, 219, 177),
    )


# ---------------------------------------------------------------------------
# Campo
# ---------------------------------------------------------------------------


def _dibujar_campo_vertical(
    draw,
    field_left: int,
    field_right: int,
    field_top: int,
    field_bottom: int,
):
    width = field_right - field_left
    height = field_bottom - field_top

    draw.rounded_rectangle(
        (
            field_left,
            field_top,
            field_right,
            field_bottom,
        ),
        radius=24,
        fill=(34, 112, 63),
        outline=(117, 190, 130),
        width=3,
    )

    mid_y = (
        field_top
        + field_bottom
    ) // 2

    cx = (
        field_left
        + field_right
    ) // 2

    draw.line(
        (
            field_left,
            mid_y,
            field_right,
            mid_y,
        ),
        fill=(183, 224, 187),
        width=2,
    )

    radius = min(
        115,
        int(width * 0.12),
    )

    draw.ellipse(
        (
            cx - radius,
            mid_y - radius,
            cx + radius,
            mid_y + radius,
        ),
        outline=(183, 224, 187),
        width=2,
    )

    box_width = int(
        width * 0.34
    )

    box_height = int(
        height * 0.15
    )

    draw.rectangle(
        (
            cx - box_width // 2,
            field_top,
            cx + box_width // 2,
            field_top + box_height,
        ),
        outline=(183, 224, 187),
        width=2,
    )

    draw.rectangle(
        (
            cx - box_width // 2,
            field_bottom - box_height,
            cx + box_width // 2,
            field_bottom,
        ),
        outline=(183, 224, 187),
        width=2,
    )


def _dibujar_campo_partido(
    draw,
    field_left: int,
    field_right: int,
    field_top: int,
    field_bottom: int,
):
    """
    Campo horizontal para mostrar HOME + AWAY juntos.

    Esto sustituye al antiguo comportamiento de crear dos imágenes
    completas y poner una debajo de otra.
    """

    width = field_right - field_left
    height = field_bottom - field_top

    draw.rounded_rectangle(
        (
            field_left,
            field_top,
            field_right,
            field_bottom,
        ),
        radius=28,
        fill=(34, 112, 63),
        outline=(117, 190, 130),
        width=3,
    )

    cx = (
        field_left
        + field_right
    ) // 2

    cy = (
        field_top
        + field_bottom
    ) // 2

    # Línea de medio campo.
    draw.line(
        (
            cx,
            field_top,
            cx,
            field_bottom,
        ),
        fill=(183, 224, 187),
        width=3,
    )

    # Círculo central.
    radius = min(
        120,
        int(width * 0.10),
    )

    draw.ellipse(
        (
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
        ),
        outline=(183, 224, 187),
        width=3,
    )

    # Punto central.
    draw.ellipse(
        (
            cx - 5,
            cy - 5,
            cx + 5,
            cy + 5,
        ),
        fill=(183, 224, 187),
    )

    # Áreas grandes.
    area_depth = int(
        width * 0.14
    )

    area_height = int(
        height * 0.48
    )

    area_top = (
        cy
        - area_height // 2
    )

    area_bottom = (
        cy
        + area_height // 2
    )

    # Área izquierda.
    draw.rectangle(
        (
            field_left,
            area_top,
            field_left + area_depth,
            area_bottom,
        ),
        outline=(183, 224, 187),
        width=3,
    )

    # Área derecha.
    draw.rectangle(
        (
            field_right - area_depth,
            area_top,
            field_right,
            area_bottom,
        ),
        outline=(183, 224, 187),
        width=3,
    )

    # Áreas pequeñas / portero.
    small_depth = int(
        width * 0.055
    )

    small_height = int(
        height * 0.24
    )

    small_top = (
        cy
        - small_height // 2
    )

    small_bottom = (
        cy
        + small_height // 2
    )

    draw.rectangle(
        (
            field_left,
            small_top,
            field_left + small_depth,
            small_bottom,
        ),
        outline=(183, 224, 187),
        width=3,
    )

    draw.rectangle(
        (
            field_right - small_depth,
            small_top,
            field_right,
            small_bottom,
        ),
        outline=(183, 224, 187),
        width=3,
    )


# ---------------------------------------------------------------------------
# Imagen individual
# ---------------------------------------------------------------------------


def _jugadores_para_imagen(
    team: dict[str, Any],
    game: dict[str, Any] | None,
    team_key: str | None,
    confirmed: bool,
) -> list[dict[str, Any]]:
    if (
        confirmed
        and game is not None
        and team_key is not None
    ):
        jugadores = normalizar_alineacion_confirmada(
            game,
            team_key,
        )

        if jugadores:
            return jugadores

        return []

    return normalizar_alineacion(
        team
    )


def generar_imagen_alineacion(
    team: dict[str, Any],
    opponent=None,
    confirmed=False,
    width=1200,
    height=1500,
    game: dict[str, Any] | None = None,
    team_key: str | None = None,
) -> BytesIO:
    """
    Genera una imagen individual de un equipo.

    Mantiene compatibilidad con el código existente.
    """

    if not isinstance(team, dict):
        raise LineupImageError(
            "El equipo debe ser un diccionario"
        )

    players = _jugadores_para_imagen(
        team,
        game,
        team_key,
        confirmed,
    )

    if not players:
        raise LineupImageError(
            "No hay jugadores en la alineación"
        )

    team_name = str(
        team.get("name")
        or "Equipo"
    )

    opponent_name = str(
        (opponent or {}).get("name")
        or ""
    )

    title = (
        "11 INICIAL"
        if confirmed
        else "11 POSIBLE"
    )

    image = Image.new(
        "RGB",
        (width, height),
        (7, 14, 24),
    )

    draw = ImageDraw.Draw(
        image
    )

    draw.text(
        (55, 40),
        team_name,
        font=_font(38, True),
        fill=(245, 248, 250),
    )

    draw.text(
        (55, 90),
        title,
        font=_font(25, True),
        fill=(139, 219, 177),
    )

    if opponent_name:
        versus = (
            f"vs {opponent_name}"
        )

        box = draw.textbbox(
            (0, 0),
            versus,
            font=_font(22),
        )

        draw.text(
            (
                width
                - 55
                - (
                    box[2]
                    - box[0]
                ),
                48,
            ),
            versus,
            font=_font(22),
            fill=(170, 184, 195),
        )

    field_top = 155
    field_bottom = height - 70
    field_left = 45
    field_right = width - 45

    _dibujar_campo_vertical(
        draw,
        field_left,
        field_right,
        field_top,
        field_bottom,
    )

    slots = _slots_por_posicion(
        players,
        width,
        left=field_left + 90,
        right=field_right - 90,
    )

    label_w = 180
    label_h = 66

    for jugador, x, y in slots:
        x = max(
            field_left
            + label_w // 2,
            min(
                field_right
                - label_w // 2,
                x,
            ),
        )

        y = max(
            field_top
            + 35
            + label_h // 2,
            min(
                field_bottom
                - label_h
                - 35,
                y,
            ),
        )

        # Marcador visual.
        draw.ellipse(
            (
                x - 30,
                y - 30,
                x + 30,
                y + 30,
            ),
            fill=(238, 242, 244),
            outline=(8, 18, 30),
            width=3,
        )

        _rounded_label(
            draw,
            (
                x - label_w // 2,
                y + 35,
                x + label_w // 2,
                y + 35 + label_h,
            ),
            jugador["name"],
            jugador["position_label"],
            jugador.get("points"),
            confirmed,
        )

    footer = (
        "Alineación confirmada"
        if confirmed
        else "Alineación probable"
    )

    font = _font(19)

    box = draw.textbbox(
        (0, 0),
        footer,
        font=font,
    )

    draw.text(
        (
            (
                width
                - box[2]
                + box[0]
            ) // 2,
            height - 45,
        ),
        footer,
        font=font,
        fill=(170, 184, 195),
    )

    output = BytesIO()

    output.name = (
        "alineacion.png"
    )

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return output


# ---------------------------------------------------------------------------
# Imagen ÚNICA del partido
# ---------------------------------------------------------------------------


def generar_imagen_partido(
    game: dict[str, Any],
    now: datetime | None = None,
    width: int = 1600,
    height: int = 1050,
) -> tuple[BytesIO, bool]:
    """
    Genera UNA sola imagen con las dos alineaciones enfrentadas.

    HOME:
        POR -> extremo izquierdo
        DEL -> hacia el centro

    AWAY:
        POR -> extremo derecho
        DEL -> hacia el centro

    Es decir, visualmente:

        POR DEF MED DEL | DEL MED DEF POR
        HOME             | AWAY

    y nunca se mezclan los jugadores de un partido con los del otro.
    """

    if not isinstance(game, dict):
        raise LineupImageError(
            "El partido debe ser un diccionario"
        )

    confirmed = alineacion_confirmada(
        game,
        now=now,
    )

    home = game.get("home") or {}
    away = game.get("away") or {}

    if confirmed:
        home_players = normalizar_alineacion_confirmada(
            game,
            "home",
        )

        away_players = normalizar_alineacion_confirmada(
            game,
            "away",
        )
    else:
        home_players = normalizar_alineacion(
            home
        )

        away_players = normalizar_alineacion(
            away
        )

    if not home_players:
        raise LineupImageError(
            "No hay alineación disponible para el equipo local"
        )

    if not away_players:
        raise LineupImageError(
            "No hay alineación disponible para el equipo visitante"
        )

    home_name = str(
        home.get("name")
        or "Local"
    )

    away_name = str(
        away.get("name")
        or "Visitante"
    )

    home_score = home.get(
        "score"
    )

    away_score = away.get(
        "score"
    )

    image = Image.new(
        "RGB",
        (width, height),
        (7, 14, 24),
    )

    draw = ImageDraw.Draw(
        image
    )

    # ------------------------------------------------------------------
    # Cabecera
    # ------------------------------------------------------------------

    header_y = 30

    draw.text(
        (65, header_y),
        home_name,
        font=_font(42, True),
        fill=(245, 248, 250),
    )

    draw.text(
        (
            width - 65,
            header_y,
        ),
        away_name,
        font=_font(42, True),
        fill=(245, 248, 250),
        anchor="ra",
    )

    # Resultado / VS.
    if (
        home_score is not None
        and away_score is not None
    ):
        resultado = (
            f"{home_score}  :  {away_score}"
        )
    else:
        resultado = "VS"

    draw.text(
        (
            width // 2,
            header_y + 4,
        ),
        resultado,
        font=_font(38, True),
        fill=(245, 248, 250),
        anchor="ma",
    )

    estado = (
        "11 INICIAL"
        if confirmed
        else "11 POSIBLE"
    )

    draw.text(
        (
            width // 2,
            header_y + 55,
        ),
        estado,
        font=_font(21, True),
        fill=(139, 219, 177),
        anchor="ma",
    )

    # ------------------------------------------------------------------
    # Campo
    # ------------------------------------------------------------------

    field_left = 35
    field_right = width - 35
    field_top = 125
    field_bottom = height - 35

    _dibujar_campo_partido(
        draw,
        field_left,
        field_right,
        field_top,
        field_bottom,
    )

    # ------------------------------------------------------------------
    # Jugadores
    # ------------------------------------------------------------------

    home_slots = _slots_partido(
        home_players,
        field_left=field_left,
        field_right=field_right,
        field_top=field_top,
        field_bottom=field_bottom,
        lado="home",
    )

    away_slots = _slots_partido(
        away_players,
        field_left=field_left,
        field_right=field_right,
        field_top=field_top,
        field_bottom=field_bottom,
        lado="away",
    )

    label_w = 185
    label_h = 65

    for (
        jugador,
        x,
        y,
    ) in (
        home_slots
        + away_slots
    ):
        x = max(
            field_left + label_w // 2,
            min(
                field_right - label_w // 2,
                x,
            ),
        )

        y = max(
            field_top + 42,
            min(
                field_bottom - label_h - 10,
                y,
            ),
        )

        # Círculo del jugador.
        draw.ellipse(
            (
                x - 29,
                y - 29,
                x + 29,
                y + 29,
            ),
            fill=(238, 242, 244),
            outline=(8, 18, 30),
            width=3,
        )

        _rounded_label(
            draw,
            (
                x - label_w // 2,
                y + 34,
                x + label_w // 2,
                y + 34 + label_h,
            ),
            jugador["name"],
            jugador["position_label"],
            jugador.get("points"),
            confirmed,
        )

    # ------------------------------------------------------------------
    # Pie
    # ------------------------------------------------------------------

    footer = (
        "Alineaciones confirmadas"
        if confirmed
        else "Alineaciones probables"
    )

    draw.text(
        (
            width // 2,
            height - 15,
        ),
        footer,
        font=_font(18),
        fill=(170, 184, 195),
        anchor="ms",
    )

    output = BytesIO()

    output.name = (
        "alineaciones_partido.png"
    )

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return output, confirmed


# ---------------------------------------------------------------------------
# Compatibilidad con el código existente
# ---------------------------------------------------------------------------


def generar_imagen_partido_completa(
    game: dict[str, Any],
    now: datetime | None = None,
) -> tuple[BytesIO, bool]:
    """
    Alias compatible con partido_alineaciones.py.

    Antes esta función generaba dos campos completos y los apilaba.
    Ahora genera directamente un único campo horizontal con ambas
    alineaciones enfrentadas.
    """

    return generar_imagen_partido(
        game,
        now=now,
    )


# ---------------------------------------------------------------------------
# Imagen del once elegido por un manager
# ---------------------------------------------------------------------------


def generar_imagen_alineacion_manager(
    manager_name: str,
    formation: str,
    players: list[dict[str, Any]],
    width: int = 1200,
    height: int = 1500,
) -> BytesIO:
    """
    Genera la imagen del ONCE ELEGIDO por un manager.

    Los jugadores deben proceder del once de la jornada del miembro,
    normalmente:

        standings[].lineup.players

    NO se utiliza ningún ``reports`` de partidos.
    """

    jugadores = normalizar_once_manager(
        players
    )

    if not jugadores:
        raise LineupImageError(
            "No hay jugadores válidos en el once elegido"
        )

    image = Image.new(
        "RGB",
        (width, height),
        (7, 14, 24),
    )

    draw = ImageDraw.Draw(
        image
    )

    # ------------------------------------------------------------------
    # Cabecera
    # ------------------------------------------------------------------

    draw.text(
        (55, 35),
        str(manager_name),
        font=_font(40, True),
        fill=(245, 248, 250),
    )

    formation_text = (
        f"⚽ {formation}"
        if formation
        else "⚽ ONCE DE LA JORNADA"
    )

    draw.text(
        (55, 88),
        formation_text,
        font=_font(26, True),
        fill=(139, 219, 177),
    )

    draw.text(
        (
            width - 55,
            50,
        ),
        "ONCE ELEGIDO",
        font=_font(22, True),
        fill=(170, 184, 195),
        anchor="ra",
    )

    # ------------------------------------------------------------------
    # Campo
    # ------------------------------------------------------------------

    field_top = 155
    field_bottom = height - 70
    field_left = 45
    field_right = width - 45

    _dibujar_campo_vertical(
        draw,
        field_left,
        field_right,
        field_top,
        field_bottom,
    )

    slots = _slots_por_posicion(
        jugadores,
        width,
        left=field_left + 90,
        right=field_right - 90,
    )

    label_w = 180
    label_h = 66

    for (
        jugador,
        x,
        y,
    ) in slots:
        x = max(
            field_left + label_w // 2,
            min(
                field_right - label_w // 2,
                x,
            ),
        )

        y = max(
            field_top + 35,
            min(
                field_bottom - label_h - 35,
                y,
            ),
        )

        draw.ellipse(
            (
                x - 30,
                y - 30,
                x + 30,
                y + 30,
            ),
            fill=(238, 242, 244),
            outline=(8, 18, 30),
            width=3,
        )

        _rounded_label(
            draw,
            (
                x - label_w // 2,
                y + 35,
                x + label_w // 2,
                y + 35 + label_h,
            ),
            jugador["name"],
            jugador["position_label"],
            jugador.get("points"),
            False,
        )

    # ------------------------------------------------------------------
    # Pie
    # ------------------------------------------------------------------

    footer = (
        "Once elegido por el manager"
    )

    draw.text(
        (
            width // 2,
            height - 45,
        ),
        footer,
        font=_font(19),
        fill=(170, 184, 195),
        anchor="ms",
    )

    output = BytesIO()

    output.name = (
        "once_manager.png"
    )

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return output


# ---------------------------------------------------------------------------
# Helper específico para generar directamente el once de un miembro
# ---------------------------------------------------------------------------


def generar_imagen_once_miembro(
    miembro: dict[str, Any],
    width: int = 1200,
    height: int = 1500,
) -> BytesIO:
    """
    Atajo para standings[].lineup.players.

    Ejemplo:

        imagen = generar_imagen_once_miembro(miembro)
    """

    if not isinstance(miembro, dict):
        raise LineupImageError(
            "El miembro debe ser un diccionario"
        )

    manager_name = str(
        miembro.get("name")
        or miembro.get("username")
        or miembro.get("userName")
        or miembro.get("nickname")
        or "Manager"
    )

    players, formation = obtener_once_manager(
        miembro
    )

    return generar_imagen_alineacion_manager(
        manager_name=manager_name,
        formation=formation,
        players=players,
        width=width,
        height=height,
    )