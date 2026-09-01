"""Generador de imágenes de alineaciones para Telegram."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from biwenger import (
    obtener_titulares_partido,
    obtener_cambios_partido,
)

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

    Primero intenta encontrar una alineación inicial explícita
    en el payload.

    Si Biwenger no la proporciona, utiliza los reports:

        type 5 = entra al campo

    Por tanto, un jugador sin type 5 dentro de reports
    comenzó el partido.
    """

    # ---------------------------------------------------------
    # 1. Intentar primero una alineación inicial explícita.
    # ---------------------------------------------------------

    for candidato in _lista_candidatos_alineacion(
        game,
        team_key,
    ):
        jugadores = _aplanar_jugadores(
            candidato
        )

        resultado = _normalizar_lista_jugadores(
            jugadores
        )

        if len(resultado) == 11:
            return resultado

    # ---------------------------------------------------------
    # 2. Fallback: reconstruir el XI desde reports.
    # ---------------------------------------------------------

    team = game.get(
        team_key
    ) or {}

    if not isinstance(team, dict):
        return []

    titulares = obtener_titulares_partido(
        team
    )

    if not titulares:
        return []

    resultado = []

    for jugador in titulares:

        normalizado = _normalizar_jugador(
            jugador
        )

        if normalizado is None:
            continue

        resultado.append(
            normalizado
        )

        if len(resultado) == 11:
            break

    return resultado


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

# El campo es HORIZONTAL.
#
# X = profundidad del campo
# Y = anchura del campo
#
# LOCAL:
#   POR -> izquierda
#   DEF -> izquierda
#   MED -> centro
#   DEL -> derecha
#
# VISITANTE:
#   exactamente reflejado horizontalmente.
#
# Para cada línea, los jugadores se reparten verticalmente
# en el centro de cada división.
#
# Ejemplo con 4 DEF:
#
#   DF
#
#   DF
#
#   DF
#
#   DF
#
# Y = 1/8, 3/8, 5/8, 7/8
#
# El portero siempre está exactamente centrado verticalmente.


_POSITION_DEPTH = {
    1: 0.08,   # POR
    2: 0.22,   # DEF
    3: 0.50,   # MED
    4: 0.78,   # DEL
}


def _agrupar_por_posicion(
    jugadores: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    """Agrupa los jugadores por posición."""

    grouped: dict[int, list[dict[str, Any]]] = {
        1: [],
        2: [],
        3: [],
        4: [],
    }

    for jugador in jugadores:
        position = jugador.get("position")

        if position in grouped:
            grouped[position].append(jugador)

    return grouped


def _ys_repartidas(
    cantidad: int,
    field_top: int,
    field_bottom: int,
) -> list[int]:
    """
    Divide verticalmente el campo en `cantidad` partes
    y devuelve el centro de cada división.

    1 -> 1/2
    2 -> 1/4, 3/4
    3 -> 1/6, 3/6, 5/6
    4 -> 1/8, 3/8, 5/8, 7/8
    """

    if cantidad <= 0:
        return []

    height = field_bottom - field_top

    return [
        round(
            field_top
            + (index + 0.5)
            * height
            / cantidad
        )
        for index in range(cantidad)
    ]


def _slots_por_posicion(
    jugadores: list[dict[str, Any]],
    *,
    field_left: int,
    field_right: int,
    field_top: int,
    field_bottom: int,
    home: bool,
) -> list[tuple[dict[str, Any], int, int]]:
    """
    Posiciona un equipo dentro de SU MEDIO CAMPO.

    LOCAL:
        ocupa desde field_left hasta el centro.

    VISITANTE:
        ocupa desde el centro hasta field_right.

    X = profundidad dentro del medio campo.
    Y = anchura del campo.

    El portero siempre queda centrado verticalmente.

    El resto de jugadores se reparte verticalmente
    dividiendo TODO el ancho vertical del campo entre
    el número de jugadores de su posición.
    """

    grouped = _agrupar_por_posicion(jugadores)

    center_x = (
        field_left + field_right
    ) / 2

    half_width = (
        field_right - field_left
    ) / 2

    slots = []

    # ---------------------------------------------------------
    # PROFUNDIDAD DENTRO DEL MEDIO CAMPO
    # ---------------------------------------------------------
    #
    # Los valores representan posiciones relativas dentro
    # del medio campo de cada equipo.
    #
    # 0.08 -> muy cerca de la portería
    # 0.30 -> defensa
    # 0.68 -> mediocampo
    # 0.90 -> ataque
    #
    # Esto evita que el delantero de un equipo invada
    # el campo del rival.
    #

    local_depth = {
        1: 0.08,   # POR
        2: 0.28,   # DEF
        3: 0.62,   # MED
        4: 0.90,   # DEL
    }

    for position in (
        1,
        2,
        3,
        4,
    ):

        row = grouped.get(
            position,
            [],
        )

        if not row:
            continue

        depth = local_depth[position]

        # -----------------------------------------------------
        # LOCAL
        # -----------------------------------------------------

        if home:

            x = (
                field_left
                + half_width * depth
            )

        # -----------------------------------------------------
        # VISITANTE
        # -----------------------------------------------------

        else:

            x = (
                field_right
                - half_width * depth
            )

        x = round(x)

        # -----------------------------------------------------
        # PORTERO
        # -----------------------------------------------------

        if position == 1:

            y = round(
                (
                    field_top
                    + field_bottom
                ) / 2
            )

            # Normalmente solo hay un portero.
            if len(row) == 1:

                slots.append(
                    (
                        row[0],
                        x,
                        y,
                    )
                )

                continue

        # -----------------------------------------------------
        # RESTO DE POSICIONES
        # -----------------------------------------------------
        #
        # Se divide TODO el medio campo verticalmente.
        #
        # 4 jugadores:
        #
        # 1/8
        # 3/8
        # 5/8
        # 7/8
        #

        ys = _ys_repartidas(
            len(row),
            field_top,
            field_bottom,
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


def _slots_partido(
    jugadores,
    *,
    field_left,
    field_right,
    field_top,
    field_bottom,
    lado,
):
    """
    Distribuye los jugadores de un equipo dentro de SU MEDIO CAMPO.

    Los dos equipos nunca comparten la zona de profundidad.

    LOCAL:
        field_left -> centro

    VISITANTE:
        centro -> field_right
    """

    return _slots_por_posicion(
        jugadores,
        field_left=field_left,
        field_right=field_right,
        field_top=field_top,
        field_bottom=field_bottom,
        home=(lado == "home"),
    )



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
    field_left,
    field_right,
    field_top,
    field_bottom,
):
    """
    Dibuja el campo horizontal de la alineación.
    Diseño compacto, con franjas y líneas limpias.
    """
    width = field_right - field_left
    height = field_bottom - field_top

    radius = 28

    grass = (35, 116, 65)
    grass_alt = (31, 106, 59)
    line = (220, 238, 222)

    # Fondo del campo.
    draw.rounded_rectangle(
        (
            field_left,
            field_top,
            field_right,
            field_bottom,
        ),
        radius=radius,
        fill=grass,
    )

    # Franjas verticales.
    stripe_width = max(80, width // 12)

    for i, x in enumerate(
        range(field_left, field_right, stripe_width)
    ):
        if i % 2:
            draw.rectangle(
                (
                    x,
                    field_top,
                    min(x + stripe_width, field_right),
                    field_bottom,
                ),
                fill=grass_alt,
            )

    # Borde exterior.
    draw.rounded_rectangle(
        (
            field_left,
            field_top,
            field_right,
            field_bottom,
        ),
        radius=radius,
        outline=line,
        width=3,
    )

    center_x = (field_left + field_right) // 2
    center_y = (field_top + field_bottom) // 2

    # Línea central.
    draw.line(
        (
            center_x,
            field_top,
            center_x,
            field_bottom,
        ),
        fill=line,
        width=3,
    )

    # Círculo central.
    center_radius = min(105, int(width * 0.085))

    draw.ellipse(
        (
            center_x - center_radius,
            center_y - center_radius,
            center_x + center_radius,
            center_y + center_radius,
        ),
        outline=line,
        width=3,
    )

    # Punto central.
    draw.ellipse(
        (
            center_x - 5,
            center_y - 5,
            center_x + 5,
            center_y + 5,
        ),
        fill=line,
    )

    # Áreas grandes.
    area_depth = int(width * 0.12)
    area_height = int(height * 0.46)

    area_top = center_y - area_height // 2
    area_bottom = center_y + area_height // 2

    draw.rectangle(
        (
            field_left,
            area_top,
            field_left + area_depth,
            area_bottom,
        ),
        outline=line,
        width=3,
    )

    draw.rectangle(
        (
            field_right - area_depth,
            area_top,
            field_right,
            area_bottom,
        ),
        outline=line,
        width=3,
    )

    # Áreas pequeñas.
    small_depth = int(width * 0.052)
    small_height = int(height * 0.22)

    small_top = center_y - small_height // 2
    small_bottom = center_y + small_height // 2

    draw.rectangle(
        (
            field_left,
            small_top,
            field_left + small_depth,
            small_bottom,
        ),
        outline=line,
        width=3,
    )

    draw.rectangle(
        (
            field_right - small_depth,
            small_top,
            field_right,
            small_bottom,
        ),
        outline=line,
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

    _dibujar_campo_partido(
        draw,
        field_left,
        field_right,
        field_top,
        field_bottom,
    )

    slots = _slots_por_posicion(
        players,
        field_left=field_left + 90,
        field_right=field_right - 90,
        field_top=field_top,
        field_bottom=field_bottom,
        home=True,
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
def _extraer_titulares_y_suplentes(
    team: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Reconstruye los titulares y suplentes reales a partir
    de los reports del partido.

    Reglas:

        type 5 = entra_al_campo

    Por tanto:

        - jugador SIN type 5 -> titular
        - jugador CON type 5 -> suplente que entró

    El suplente conserva el minuto de entrada.

    Soporta tanto reports normalizados directamente como
    reports con la estructura:

        {
            "player": {...},
            "events": [...]
        }
    """

    if not isinstance(team, dict):
        return [], []

    reports = team.get(
        "reports"
    )

    if not isinstance(
        reports,
        list,
    ):
        return [], []

    titulares = []
    suplentes = []

    for report in reports:

        if not isinstance(
            report,
            dict,
        ):
            continue

        # ---------------------------------------------------------
        # PLAYER
        # ---------------------------------------------------------

        player = report.get(
            "player"
        )

        if isinstance(
            player,
            dict,
        ):
            jugador = dict(
                player
            )

            # Datos del report que puedan ser útiles.
            for key in (
                "points",
                "breakdown",
                "star",
                "mvp",
            ):
                if key in report:
                    jugador[key] = (
                        report.get(key)
                    )

        else:
            jugador = dict(
                report
            )

        # ---------------------------------------------------------
        # NORMALIZAR JUGADOR
        # ---------------------------------------------------------

        normalizado = _normalizar_jugador(
            jugador
        )

        if normalizado is None:
            continue

        # ---------------------------------------------------------
        # EVENTOS
        # ---------------------------------------------------------

        eventos = report.get(
            "events"
        )

        if not isinstance(
            eventos,
            list,
        ):
            eventos = jugador.get(
                "events"
            )

        if not isinstance(
            eventos,
            list,
        ):
            eventos = []

        entra = False
        minuto_entrada = None

        for evento in eventos:

            if not isinstance(
                evento,
                dict,
            ):
                continue

            try:
                event_type = int(
                    evento.get("type")
                )
            except (
                TypeError,
                ValueError,
            ):
                event_type = None

            if event_type == 5:
                entra = True

                minuto = (
                    evento.get(
                        "minute"
                    )
                )

                if minuto is None:
                    minuto = evento.get(
                        "metadata"
                    )

                try:
                    minuto_entrada = int(
                        minuto
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    minuto_entrada = None

                break

        # ---------------------------------------------------------
        # SUPLENTE
        # ---------------------------------------------------------

        if entra:

            normalizado[
                "substitute"
            ] = True

            normalizado[
                "entry_minute"
            ] = minuto_entrada

            suplentes.append(
                normalizado
            )

        # ---------------------------------------------------------
        # TITULAR
        # ---------------------------------------------------------

        else:

            normalizado[
                "substitute"
            ] = False

            normalizado[
                "entry_minute"
            ] = None

            titulares.append(
                normalizado
            )

    # -------------------------------------------------------------
    # ORDENAR SUPLENTES POR MINUTO DE ENTRADA
    # -------------------------------------------------------------

    suplentes.sort(
        key=lambda jugador: (
            jugador.get(
                "entry_minute"
            )
            if jugador.get(
                "entry_minute"
            ) is not None
            else 999
        )
    )

    # -------------------------------------------------------------
    # SEGURIDAD
    # -------------------------------------------------------------

    if len(titulares) > 11:
        titulares = titulares[:11]

    return (
        titulares,
        suplentes,
    )


def _timestamp_partido(game):
    """Devuelve la fecha/hora del partido en formato legible."""
    timestamp = (
        game.get("timestamp")
        or game.get("date")
        or game.get("startTimestamp")
    )

    if not timestamp:
        return ""

    try:
        if isinstance(timestamp, str):
            timestamp = float(timestamp)

        # Si viene en milisegundos
        if timestamp > 10_000_000_000:
            timestamp /= 1000

        dt = datetime.fromtimestamp(timestamp)

        return dt.strftime("%d/%m/%Y · %H:%M")

    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _texto_suplente(
    jugador: dict[str, Any],
) -> str:
    nombre = str(
        jugador.get(
            "name"
        )
        or "Jugador"
    )

    minuto = jugador.get(
        "entry_minute"
    )

    if minuto is not None:
        return (
            f"{nombre} · "
            f"{minuto}'"
        )

    return nombre

def generar_imagen_partido(
    game: dict[str, Any],
    now: datetime | None = None,
    width: int = 1600,
    height: int = 1250,
) -> tuple[BytesIO, bool]:
    """
    Genera UNA única imagen del partido.

    Incluye:

        LOCAL
            11 titulares
            suplentes que entraron

        VISITANTE
            11 titulares
            suplentes que entraron

    Los titulares reales se determinan por los reports:

        type 5 = entra_al_campo

    Es decir:

        sin type 5 -> titular
        con type 5 -> suplente

    Los dos equipos aparecen enfrentados en el mismo campo.
    """

    if not isinstance(
        game,
        dict,
    ):
        raise LineupImageError(
            "El partido debe ser un diccionario"
        )

    # ---------------------------------------------------------
    # CONFIRMADO
    # ---------------------------------------------------------

    confirmed = alineacion_confirmada(
        game,
        now=now,
    )

    home = (
        game.get("home")
        or {}
    )

    away = (
        game.get("away")
        or {}
    )

    if not isinstance(
        home,
        dict,
    ):
        home = {}

    if not isinstance(
        away,
        dict,
    ):
        away = {}

    # ---------------------------------------------------------
    # JUGADORES
    # ---------------------------------------------------------

    if confirmed:

        home_players, home_subs = (
            _extraer_titulares_y_suplentes(
                home
            )
        )

        away_players, away_subs = (
            _extraer_titulares_y_suplentes(
                away
            )
        )

    else:

        home_players = (
            normalizar_alineacion(
                home
            )
        )

        away_players = (
            normalizar_alineacion(
                away
            )
        )

        home_subs = []
        away_subs = []

    # ---------------------------------------------------------
    # SEGURIDAD
    # ---------------------------------------------------------

    if not home_players:
        raise LineupImageError(
            "No hay alineación disponible "
            "para el equipo local"
        )

    if not away_players:
        raise LineupImageError(
            "No hay alineación disponible "
            "para el equipo visitante"
        )

    # ---------------------------------------------------------
    # NOMBRES
    # ---------------------------------------------------------

    home_name = str(
        home.get("name")
        or "Local"
    )

    away_name = str(
        away.get("name")
        or "Visitante"
    )

    # ---------------------------------------------------------
    # RESULTADO
    # ---------------------------------------------------------

    home_score = home.get(
        "score"
    )

    away_score = away.get(
        "score"
    )

    # ---------------------------------------------------------
    # IMAGEN
    # ---------------------------------------------------------

    image = Image.new(
        "RGB",
        (
            width,
            height,
        ),
        (7, 14, 24),
    )

    draw = ImageDraw.Draw(
        image
    )

    # ---------------------------------------------------------
    # CABECERA
    # ---------------------------------------------------------

    header_center = width // 2

    # Escudos / placeholders.
    _draw_logo_placeholder(
        draw,
        (145, 75),
        78,
        home,
    )

    _draw_logo_placeholder(
        draw,
        (width - 145, 75),
        78,
        away,
    )

    # Nombres de los equipos.
    draw.text(
        (220, 57),
        home_name,
        font=_font(42, True),
        fill=(245, 248, 250),
        anchor="lm",
    )

    draw.text(
        (width - 220, 57),
        away_name,
        font=_font(42, True),
        fill=(245, 248, 250),
        anchor="rm",
    )

    # Resultado.
    if (
        home.get("score") is not None
        or away.get("score") is not None
    ):
        resultado = (
            f"{_score_text(home.get('score'))}"
            f"  :  "
            f"{_score_text(away.get('score'))}"
        )
    else:
        resultado = "VS"

    draw.text(
        (header_center, 48),
        resultado,
        font=_font(50, True),
        fill=(245, 248, 250),
        anchor="ma",
    )

    # Fecha / hora.
    date_text = _timestamp_partido(game)

    if date_text:
        draw.text(
            (header_center, 105),
            date_text,
            font=_font(21, True),
            fill=(170, 184, 195),
            anchor="ma",
        )


    # ---------------------------------------------------------
    # CAMPO
    # ---------------------------------------------------------

    field_left = 55
    field_right = width - 55

    field_top = 175
    field_bottom = 875

    _dibujar_campo_partido(
        draw,
        field_left,
        field_right,
        field_top,
        field_bottom,
    )

    # ---------------------------------------------------------
    # SLOTS
    # ---------------------------------------------------------

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

    label_w = 170
    label_h = 58

    # ---------------------------------------------------------
    # PINTAR JUGADORES
    # ---------------------------------------------------------

    for (
        jugador,
        x,
        y,
    ) in (
        home_slots
        + away_slots
    ):

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
            field_top + 42,
            min(
                field_bottom
                - label_h
                - 10,
                y,
            ),
        )

        # Círculo del jugador.
        draw.ellipse(
            (
                x - 34,
                y - 34,
                x + 34,
                y + 34,
            ),
            fill=(238, 242, 244),
            outline=(8, 18, 30),
            width=3,
        )

        _rounded_label(
            draw,
            (
                x
                - label_w // 2,
                y + 34,
                x
                + label_w // 2,
                y + 34
                + label_h,
            ),
            jugador["name"],
            jugador["position_label"],
            jugador.get("points"),
            confirmed,
        )

    # ---------------------------------------------------------
    # SUPLENTES
    # ---------------------------------------------------------

    subs_top = 930

    draw.text(
        (
            65,
            subs_top,
        ),
        "SUPLENTES",
        font=_font(
            24,
            True,
        ),
        fill=(139, 219, 177),
    )

    draw.text(
        (
            width - 65,
            subs_top,
        ),
        "SUPLENTES",
        font=_font(
            24,
            True,
        ),
        fill=(139, 219, 177),
        anchor="ra",
    )

    # ---------------------------------------------------------
    # COLUMNAS DE SUPLENTES
    # ---------------------------------------------------------

    left_x = 65
    right_x = (
        width // 2
        + 65
    )

    subs_start_y = (
        subs_top + 38
    )

    line_height = 32

    # LOCAL
    if confirmed:

        if home_subs:

            for index, jugador in enumerate(
                home_subs
            ):

                texto = (
                    "⬆ "
                    + _texto_suplente(
                        jugador
                    )
                )

                draw.text(
                    (
                        left_x,
                        subs_start_y
                        + index
                        * line_height,
                    ),
                    texto,
                    font=_font(
                        20
                    ),
                    fill=(245, 248, 250),
                )

        else:

            draw.text(
                (
                    left_x,
                    subs_start_y,
                ),
                "Sin suplentes que hayan entrado",
                font=_font(20),
                fill=(170, 184, 195),
            )

        # VISITANTE
        if away_subs:

            for index, jugador in enumerate(
                away_subs
            ):

                texto = (
                    "⬆ "
                    + _texto_suplente(
                        jugador
                    )
                )

                draw.text(
                    (
                        right_x,
                        subs_start_y
                        + index
                        * line_height,
                    ),
                    texto,
                    font=_font(
                        20
                    ),
                    fill=(245, 248, 250),
                )

        else:

            draw.text(
                (
                    right_x,
                    subs_start_y,
                ),
                "Sin suplentes que hayan entrado",
                font=_font(20),
                fill=(170, 184, 195),
            )

    else:

        draw.text(
            (
                left_x,
                subs_start_y,
            ),
            "Suplentes no disponibles todavía",
            font=_font(20),
            fill=(170, 184, 195),
        )

        draw.text(
            (
                right_x,
                subs_start_y,
            ),
            "Suplentes no disponibles todavía",
            font=_font(20),
            fill=(170, 184, 195),
        )

    # ---------------------------------------------------------
    # PIE
    # ---------------------------------------------------------

    footer = (
        "Alineaciones confirmadas · "
        "suplentes = jugadores con type 5"
        if confirmed
        else
        "Alineaciones probables"
    )

    draw.text(
        (
            width // 2,
            height - 18,
        ),
        footer,
        font=_font(
            17
        ),
        fill=(170, 184, 195),
        anchor="ms",
    )

    # ---------------------------------------------------------
    # SALIDA
    # ---------------------------------------------------------

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

    return (
        output,
        confirmed,
    )


def _draw_logo_placeholder(draw, center, radius, team):
    """
    Dibuja un placeholder para el escudo mientras no tengamos
    el logo real del equipo.
    """
    cx, cy = center

    # Círculo exterior.
    draw.ellipse(
        (
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
        ),
        fill=(24, 32, 43),
        outline=(90, 105, 120),
        width=3,
    )

    # Iniciales del equipo.
    name = (
        team.get("name")
        or team.get("team_name")
        or ""
    ).strip()

    words = name.split()

    if len(words) >= 2:
        initials = "".join(word[0] for word in words[:2]).upper()
    elif name:
        initials = name[:2].upper()
    else:
        initials = "?"

    draw.text(
        (cx, cy),
        initials,
        font=_font(32, True),
        fill=(245, 248, 250),
        anchor="mm",
    )


def _score_text(score):
    """Normaliza el marcador para mostrarlo en la imagen."""
    if score is None:
        return "0"

    if isinstance(score, bool):
        return str(int(score))

    if isinstance(score, (int, float)):
        return str(int(score))

    if isinstance(score, dict):
        for key in ("value", "goals", "score", "total"):
            value = score.get(key)
            if value is not None:
                return _score_text(value)

    if isinstance(score, (list, tuple)) and score:
        return _score_text(score[0])

    text = str(score).strip()

    # Por si llega algo tipo "2", "2.0", etc.
    try:
        return str(int(float(text)))
    except (ValueError, TypeError):
        return text or "0"


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