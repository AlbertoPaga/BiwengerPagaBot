"""Generador de imágenes de alineaciones para Telegram.

Diseño:
- Una sola imagen horizontal para el partido.
- Escudos reales de Biwenger cuando están disponibles.
- Fotos reales de jugadores desde el CDN de Biwenger.
- XI local y visitante enfrentados y reflejados.
- Acciones reales de los reports (gol, tarjetas, cambios, etc.).
- Suplentes con foto, minuto de entrada y acciones.
- Mantiene la API pública que usa bot.py / partido_alineaciones.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

from biwenger import (
    TEAM_NAMES,
    EVENT_TYPES,
    obtener_titulares_partido,
)


POSITION_LABELS = {
    1: "POR",
    2: "DEF",
    3: "MED",
    4: "DEL",
}


# ===========================================================================
# COLORES
# ===========================================================================

BG = (7, 14, 24)

PANEL = (8, 18, 30)
PANEL_2 = (11, 24, 38)

TEXT = (245, 248, 250)
MUTED = (170, 184, 195)

GREEN = (139, 219, 177)

FIELD = (35, 116, 65)
FIELD_ALT = (31, 106, 59)
FIELD_LINE = (220, 238, 222)

BORDER = (65, 88, 105)


# Caché de imágenes remotas.
_IMAGE_CACHE: dict[str, bytes | None] = {}
_IMAGE_CACHE_MAX = 512


class LineupImageError(ValueError):
    """Error de datos al construir una imagen de alineación."""


# ===========================================================================
# FUENTES
# ===========================================================================


def _font(
    size: int,
    bold: bool = False,
):
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
            return ImageFont.truetype(
                candidate,
                size,
            )

    return ImageFont.load_default()


# ===========================================================================
# UTILIDADES
# ===========================================================================


def _truncate(
    text: Any,
    max_length: int = 18,
) -> str:
    value = str(
        text or "Jugador"
    ).strip()

    if len(value) <= max_length:
        return value

    return (
        value[: max_length - 1]
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


def _timestamp_partido(
    game: dict[str, Any],
) -> str:
    value = (
        game.get("date")
        or game.get("timestamp")
        or game.get("startTimestamp")
    )

    if value is None:
        return ""

    try:
        timestamp = float(value)

        if timestamp > 10_000_000_000:
            timestamp /= 1000

        return datetime.fromtimestamp(
            timestamp,
        ).strftime(
            "%d/%m/%Y · %H:%M"
        )

    except (
        TypeError,
        ValueError,
        OSError,
        OverflowError,
    ):
        return ""


def _score_text(
    score: Any,
) -> str:
    if score is None:
        return "0"

    if isinstance(
        score,
        bool,
    ):
        return str(
            int(score)
        )

    if isinstance(
        score,
        (int, float),
    ):
        return str(
            int(score)
        )

    if isinstance(
        score,
        dict,
    ):
        for key in (
            "value",
            "goals",
            "score",
            "total",
        ):
            if score.get(key) is not None:
                return _score_text(
                    score[key]
                )

    if isinstance(
        score,
        (list, tuple),
    ) and score:
        return _score_text(
            score[0]
        )

    text = str(
        score
    ).strip()

    try:
        return str(
            int(float(text))
        )
    except (
        TypeError,
        ValueError,
    ):
        return text or "0"


def _event_type(
    evento: Any,
) -> int | None:
    if not isinstance(
        evento,
        dict,
    ):
        return None

    try:
        return int(
            evento.get("type")
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def _event_minute(
    evento: Any,
) -> int | None:
    if not isinstance(
        evento,
        dict,
    ):
        return None

    value = (
        evento.get("minute")
        if evento.get("minute") is not None
        else evento.get("metadata")
    )

    if isinstance(
        value,
        dict,
    ):
        value = (
            value.get("minute")
            or value.get("minutes")
            or value.get("value")
        )

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _event_name(
    evento: Any,
) -> str:
    if not isinstance(
        evento,
        dict,
    ):
        return ""

    return str(
        evento.get("name")
        or evento.get("event")
        or EVENT_TYPES.get(
            _event_type(evento),
            "",
        )
        or ""
    ).strip().lower()


# ===========================================================================
# IMÁGENES REMOTAS
# ===========================================================================


def _download_image(
    url: str | None,
) -> bytes | None:
    if not url or not isinstance(
        url,
        str,
    ):
        return None

    url = url.strip()

    if not url.startswith(
        (
            "http://",
            "https://",
        )
    ):
        return None

    if url in _IMAGE_CACHE:
        return _IMAGE_CACHE[url]

    data: bytes | None = None

    try:
        response = requests.get(
            url,
            timeout=4,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; BiwengerPagaBot/1.0)"
                )
            },
        )

        response.raise_for_status()

        data = response.content

    except Exception:
        data = None

    _IMAGE_CACHE[url] = data

    if len(_IMAGE_CACHE) > _IMAGE_CACHE_MAX:
        _IMAGE_CACHE.pop(
            next(
                iter(
                    _IMAGE_CACHE
                )
            )
        )

    return data


def _open_remote_image(
    url: str | None,
) -> Image.Image | None:
    data = _download_image(
        url
    )

    if not data:
        return None

    try:
        return Image.open(
            BytesIO(data)
        ).convert("RGBA")
    except Exception:
        return None


def _recortar_cuadrado(
    image: Image.Image,
    size: int,
) -> Image.Image:
    width, height = image.size

    side = min(
        width,
        height,
    )

    left = (
        width - side
    ) // 2

    top = (
        height - side
    ) // 2

    image = image.crop(
        (
            left,
            top,
            left + side,
            top + side,
        )
    )

    return image.resize(
        (
            size,
            size,
        ),
        Image.Resampling.LANCZOS,
    )


def _pegar_circular(
    draw,
    remote_url: str | None,
    x: int,
    y: int,
    radius: int,
) -> bool:
    remote = _open_remote_image(
        remote_url
    )

    if remote is None:
        return False

    diameter = radius * 2

    remote = _recortar_cuadrado(
        remote,
        diameter,
    )

    mask = Image.new(
        "L",
        (
            diameter,
            diameter,
        ),
        0,
    )

    mask_draw = ImageDraw.Draw(
        mask
    )

    mask_draw.ellipse(
        (
            0,
            0,
            diameter - 1,
            diameter - 1,
        ),
        fill=255,
    )

    layer = Image.new(
        "RGBA",
        (
            diameter,
            diameter,
        ),
        (
            0,
            0,
            0,
            0,
        ),
    )

    layer.paste(
        remote,
        (0, 0),
        mask,
    )

    draw._image.paste(
        layer,
        (
            x - radius,
            y - radius,
        ),
        layer,
    )

    draw.ellipse(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        ),
        outline=(8, 18, 30),
        width=3,
    )

    return True


# ===========================================================================
# NORMALIZACIÓN DE JUGADORES
# ===========================================================================


def _normalizar_jugador(
    jugador: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(
        jugador,
        dict,
    ):
        return None

    player = jugador.get(
        "player"
    )

    if isinstance(
        player,
        dict,
    ):
        datos = dict(
            player
        )

        datos.update(
            {
                key: value
                for key, value in jugador.items()
                if key != "player"
            }
        )
    else:
        datos = dict(
            jugador
        )

    try:
        position = int(
            datos.get("position")
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if position not in POSITION_LABELS:
        return None

    player_id = datos.get(
        "id"
    )

    photo = (
        datos.get("photo")
        or datos.get("image")
        or datos.get("imageUrl")
    )

    if isinstance(
        photo,
        dict,
    ):
        photo = (
            photo.get("url")
            or photo.get("src")
        )

    if (
        not photo
        and player_id is not None
    ):
        photo = (
            "https://cdn.biwenger.com/i/p/"
            f"{player_id}.png"
        )

    events = (
        datos.get("events")
        or []
    )

    if not isinstance(
        events,
        list,
    ):
        events = []

    return {
        "id": player_id,

        "name": str(
            datos.get("name")
            or datos.get("nombre")
            or "Jugador"
        ),

        "position": position,

        "position_label": POSITION_LABELS[
            position
        ],

        "alt_positions": (
            datos.get("altPositions")
            or []
        ),

        "points": datos.get(
            "points"
        ),

        "photo": photo,

        "events": events,

        "breakdown": datos.get(
            "breakdown"
        ),

        "star": bool(
            datos.get(
                "star",
                False,
            )
        ),

        "mvp": bool(
            datos.get(
                "mvp",
                False,
            )
        ),

        "substitute": bool(
            datos.get(
                "substitute",
                False,
            )
        ),

        "entry_minute": datos.get(
            "entry_minute"
        ),

        "minutes": (
            datos.get("minutes")
            or datos.get("minutesPlayed")
            or datos.get("playedMinutes")
        ),
    }


def _aplanar_jugadores(
    valor: Any,
) -> list[dict[str, Any]]:
    if isinstance(
        valor,
        list,
    ):
        return [
            item
            for item in valor
            if isinstance(
                item,
                dict,
            )
        ]

    if not isinstance(
        valor,
        dict,
    ):
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
        nested = valor.get(
            key
        )

        if isinstance(
            nested,
            list,
        ):
            return [
                item
                for item in nested
                if isinstance(
                    item,
                    dict,
                )
            ]

        if isinstance(
            nested,
            dict,
        ):
            result = _aplanar_jugadores(
                nested
            )

            if result:
                return result

    values = list(
        valor.values()
    )

    if values and all(
        isinstance(
            item,
            dict,
        )
        for item in values
    ):
        return values

    return []


def _normalizar_lista_jugadores(
    jugadores: list[Any],
) -> list[dict[str, Any]]:
    resultado: list[dict[str, Any]] = []
    vistos: set[Any] = set()

    for jugador in jugadores:

        normalizado = _normalizar_jugador(
            jugador
        )

        if normalizado is None:
            continue

        player_id = normalizado.get(
            "id"
        )

        if (
            player_id is not None
            and player_id in vistos
        ):
            continue

        if player_id is not None:
            vistos.add(
                player_id
            )

        resultado.append(
            normalizado
        )

        if len(resultado) == 11:
            break

    return resultado


# ===========================================================================
# ALINEACIONES
# ===========================================================================


def _report_player(
    report: dict[str, Any],
) -> dict[str, Any] | None:
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

        for key in (
            "points",
            "breakdown",
            "events",
            "star",
            "mvp",
            "minutes",
            "minutesPlayed",
            "playedMinutes",
        ):
            if key in report:
                jugador[key] = report.get(
                    key
                )

        return jugador

    return dict(
        report
    )


def normalizar_alineacion(
    team: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Obtiene el posible XI de PREVIEW.
    """

    if not isinstance(
        team,
        dict,
    ):
        return []

    reports = team.get(
        "reports"
    )

    if not isinstance(
        reports,
        list,
    ):
        return []

    resultado = []

    for report in reports:

        if not isinstance(
            report,
            dict,
        ):
            continue

        jugador_raw = _report_player(
            report
        )

        if jugador_raw is None:
            continue

        jugador = _normalizar_jugador(
            jugador_raw
        )

        if jugador is None:
            continue

        resultado.append(
            jugador
        )

        if len(resultado) == 11:
            break

    return resultado


def _lista_candidatos_alineacion(
    game: dict[str, Any],
    team_key: str,
) -> list[Any]:
    team = game.get(
        team_key
    ) or {}

    candidatos: list[Any] = []

    if isinstance(
        team,
        dict,
    ):
        for key in (
            "initialLineup",
            "initialLineups",
            "lineup",
            "lineups",
            "starters",
            "startingXI",
        ):
            value = team.get(
                key
            )

            if value:
                candidatos.append(
                    value
                )

    initial = game.get(
        "initialLineups"
    )

    if isinstance(
        initial,
        dict,
    ):
        value = initial.get(
            team_key
        )

        if value:
            candidatos.append(
                value
            )

    elif isinstance(
        initial,
        list,
    ):
        candidatos.append(
            initial
        )

    for key in (
        "lineups",
        "initialLineup",
        "starters",
        "startingXI",
    ):
        value = game.get(
            key
        )

        if isinstance(
            value,
            dict,
        ):
            value = value.get(
                team_key
            )

        if value:
            candidatos.append(
                value
            )

    return candidatos


def _reports_index(
    team: dict[str, Any],
) -> dict[Any, dict[str, Any]]:
    result: dict[
        Any,
        dict[str, Any],
    ] = {}

    reports = team.get(
        "reports"
    )

    if not isinstance(
        reports,
        list,
    ):
        return result

    for report in reports:

        if not isinstance(
            report,
            dict,
        ):
            continue

        player = report.get(
            "player"
        )

        if not isinstance(
            player,
            dict,
        ):
            continue

        player_id = player.get(
            "id"
        )

        if player_id is None:
            continue

        result[player_id] = report

        try:
            result[
                int(player_id)
            ] = report
        except (
            TypeError,
            ValueError,
        ):
            pass

    return result


def _enriquecer_desde_report(
    jugador: dict[str, Any],
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(
        report,
        dict,
    ):
        return jugador

    result = dict(
        jugador
    )

    events = report.get(
        "events"
    )

    if isinstance(
        events,
        list,
    ):
        result["events"] = events

    if result.get(
        "points"
    ) is None:
        result["points"] = report.get(
            "points"
        )

    for key in (
        "breakdown",
        "star",
        "mvp",
        "minutes",
        "minutesPlayed",
        "playedMinutes",
    ):
        if report.get(
            key
        ) is not None:
            result[key] = report.get(
                key
            )

    return result


def normalizar_alineacion_confirmada(
    game: dict[str, Any],
    team_key: str,
) -> list[dict[str, Any]]:
    """
    Obtiene el XI inicial real.

    Primero busca un XI explícito.

    Si no existe, utiliza los reports y type 5 como entrada
    de un suplente.
    """

    team = game.get(
        team_key
    ) or {}

    if not isinstance(
        team,
        dict,
    ):
        return []

    report_index = _reports_index(
        team
    )

    # ---------------------------------------------------------
    # 1. XI explícito
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

            return [
                _enriquecer_desde_report(
                    jugador,
                    report_index.get(
                        jugador.get("id")
                    ),
                )
                for jugador in resultado
            ]

    # ---------------------------------------------------------
    # 2. Fallback desde reports
    # ---------------------------------------------------------

    titulares = obtener_titulares_partido(
        team
    )

    if not titulares:

        titulares = []

        reports = team.get(
            "reports"
        )

        if isinstance(
            reports,
            list,
        ):
            for report in reports:

                if not isinstance(
                    report,
                    dict,
                ):
                    continue

                events = (
                    report.get("events")
                    or []
                )

                if not isinstance(
                    events,
                    list,
                ):
                    events = []

                entra = any(
                    _event_type(evento) == 5
                    for evento in events
                    if isinstance(
                        evento,
                        dict,
                    )
                )

                if not entra:
                    jugador = _report_player(
                        report
                    )

                    if jugador:
                        titulares.append(
                            jugador
                        )

    resultado = []

    for jugador in titulares:

        normalizado = _normalizar_jugador(
            jugador
        )

        if normalizado is None:
            continue

        normalizado = _enriquecer_desde_report(
            normalizado,
            report_index.get(
                normalizado.get("id")
            ),
        )

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
    if not isinstance(
        game,
        dict,
    ):
        return False

    if game.get(
        "initialLineups"
    ) is True:
        return True

    timestamp = (
        game.get("date")
        or game.get("timestamp")
        or game.get("startTimestamp")
    )

    if timestamp is None:
        return False

    try:
        value = float(
            timestamp
        )

        if value > 10_000_000_000:
            value /= 1000

        partido = datetime.fromtimestamp(
            value,
            tz=timezone.utc,
        )

        actual = (
            now
            or datetime.now(
                timezone.utc
            )
        )

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
) -> tuple[
    list[dict[str, Any]],
    bool,
]:
    if not isinstance(
        game,
        dict,
    ):
        return [], False

    team = game.get(
        team_key
    ) or {}

    if not isinstance(
        team,
        dict,
    ):
        return [], False

    status = str(
        game.get("status")
        or ""
    ).lower()

    if (
        status == "preview"
        and not alineacion_confirmada(
            game,
            now=now,
        )
    ):
        return (
            normalizar_alineacion(
                team
            ),
            False,
        )

    jugadores = normalizar_alineacion_confirmada(
        game,
        team_key,
    )

    if jugadores:
        return jugadores, True

    return [], True


# ===========================================================================
# ONCE DE MANAGER
# ===========================================================================


def normalizar_once_manager(
    players: list[Any],
) -> list[dict[str, Any]]:
    if not isinstance(
        players,
        list,
    ):
        return []

    resultado: list[
        dict[str, Any]
    ] = []

    vistos: set[Any] = set()

    for jugador in players:

        normalizado = _normalizar_jugador(
            jugador
        )

        if normalizado is None:
            continue

        player_id = normalizado.get(
            "id"
        )

        if (
            player_id is not None
            and player_id in vistos
        ):
            continue

        if player_id is not None:
            vistos.add(
                player_id
            )

        resultado.append(
            normalizado
        )

        if len(resultado) == 11:
            break

    return resultado


def obtener_once_manager(
    miembro: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    str,
]:
    if not isinstance(
        miembro,
        dict,
    ):
        return [], ""

    lineup = miembro.get(
        "lineup"
    )

    formation = ""

    if isinstance(
        lineup,
        dict,
    ):
        formation = str(
            lineup.get("formation")
            or lineup.get("system")
            or lineup.get("style")
            or ""
        )

        players = lineup.get(
            "players"
        )

        if isinstance(
            players,
            list,
        ):
            return (
                normalizar_once_manager(
                    players
                ),
                formation,
            )

        return (
            normalizar_once_manager(
                _aplanar_jugadores(
                    lineup
                )
            ),
            formation,
        )

    if isinstance(
        lineup,
        list,
    ):
        return (
            normalizar_once_manager(
                lineup
            ),
            formation,
        )

    for key in (
        "selectedLineup",
        "startingXI",
        "startingLineup",
        "players",
    ):
        value = miembro.get(
            key
        )

        if isinstance(
            value,
            list,
        ):
            return (
                normalizar_once_manager(
                    value
                ),
                formation,
            )

    return [], formation


# ===========================================================================
# POSICIONAMIENTO
# ===========================================================================


def _agrupar_por_posicion(
    jugadores: list[dict[str, Any]],
) -> dict[
    int,
    list[dict[str, Any]],
]:
    grouped = {
        1: [],
        2: [],
        3: [],
        4: [],
    }

    for jugador in jugadores:

        position = jugador.get(
            "position"
        )

        if position in grouped:
            grouped[position].append(
                jugador
            )

    return grouped


def _ys_repartidas(
    cantidad: int,
    field_top: float,
    field_bottom: float,
) -> list[int]:
    if cantidad <= 0:
        return []

    height = (
        field_bottom
        - field_top
    )

    return [
        round(
            field_top
            + (
                index
                + 0.5
            )
            * height
            / cantidad
        )
        for index in range(
            cantidad
        )
    ]


def _slots_partido(
    jugadores: list[dict[str, Any]],
    field_left: float,
    field_right: float,
    field_top: float,
    field_bottom: float,
    lado: str,
) -> list[
    tuple[
        dict[str, Any],
        int,
        int,
    ]
]:
    """
    Mantiene la distribución horizontal actual:

        LOCAL:      POR | DEF | MED | DEL
        VISITANTE:  DEL | MED | DEF | POR

    Cada equipo ocupa exclusivamente su mitad.
    """

    grouped = _agrupar_por_posicion(
        jugadores
    )

    fw = (
        field_right
        - field_left
    )

    fh = (
        field_bottom
        - field_top
    )

    if fw <= 0 or fh <= 0:
        return []

    half_width = fw / 2

    if lado == "home":

        team_left = field_left

        position_columns = {
            1: 0,
            2: 1,
            3: 2,
            4: 3,
        }

    else:

        team_left = (
            field_left
            + half_width
        )

        position_columns = {
            1: 3,
            2: 2,
            3: 1,
            4: 0,
        }

    column_width = (
        half_width
        / 4
    )

    slots = []

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

        column_index = (
            position_columns[
                position
            ]
        )

        x = (
            team_left
            + column_width
            * (
                column_index
                + 0.5
            )
        )

        count = len(row)

        # El portero único queda exactamente centrado.
        if (
            position == 1
            and count == 1
        ):
            ys = [
                (
                    field_top
                    + field_bottom
                )
                / 2
            ]
        else:
            ys = [
                field_top
                + fh
                * (
                    index
                    + 0.5
                )
                / count
                for index in range(
                    count
                )
            ]

        for jugador, y in zip(
            row,
            ys,
        ):
            slots.append(
                (
                    jugador,
                    round(x),
                    round(y),
                )
            )

    return slots


def _slots_por_posicion(
    jugadores: list[dict[str, Any]],
    width: int | None = None,
    *,
    left: int | None = None,
    right: int | None = None,
    field_left: int | None = None,
    field_right: int | None = None,
    field_top: int = 155,
    field_bottom: int | None = None,
) -> list[
    tuple[
        dict[str, Any],
        int,
        int,
    ]
]:
    """
    Posiciones para imágenes individuales/manager.

    Campo vertical:
        DEL
        MED
        DEF
        POR
    """

    if field_left is None:
        field_left = (
            left
            if left is not None
            else 45
        )

    if field_right is None:
        field_right = (
            right
            if right is not None
            else (
                width - 45
                if width is not None
                else 1155
            )
        )

    if field_bottom is None:
        field_bottom = (
            1400
            if width is not None
            and width <= 1200
            else 1430
        )

    grouped = _agrupar_por_posicion(
        jugadores
    )

    center_x = (
        field_left
        + field_right
    ) / 2

    row_y = {
        1: 0.84,
        2: 0.63,
        3: 0.42,
        4: 0.20,
    }

    slots = []

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

        y = round(
            field_top
            + (
                field_bottom
                - field_top
            )
            * row_y[position]
        )

        if len(row) == 1:

            xs = [
                center_x
            ]

        else:

            margin = min(
                180,
                (
                    field_right
                    - field_left
                )
                * 0.28,
            )

            step = (
                margin * 2
                / (
                    len(row)
                    - 1
                )
            )

            xs = [
                center_x
                - margin
                + step * index
                for index in range(
                    len(row)
                )
            ]

        for jugador, x in zip(
            row,
            xs,
        ):
            slots.append(
                (
                    jugador,
                    round(x),
                    y,
                )
            )

    return slots


# ===========================================================================
# EVENTOS
# ===========================================================================


def _acciones_jugador(
    jugador: dict[str, Any],
) -> list[
    tuple[
        str,
        int | None,
    ]
]:
    """
    Traduce los eventos reales de Biwenger a acciones visuales.

    EVENT_TYPES está definido en biwenger.py.
    """

    events = (
        jugador.get("events")
        or []
    )

    if not isinstance(
        events,
        list,
    ):
        events = []

    acciones: list[
        tuple[
            str,
            int | None,
        ]
    ] = []

    def add(
        name: str,
        minute: int | None = None,
    ):
        if not any(
            current == name
            and (
                minute is None
                or current_minute
                == minute
            )
            for (
                current,
                current_minute,
            ) in acciones
        ):
            acciones.append(
                (
                    name,
                    minute,
                )
            )

    for evento in events:

        event_type = _event_type(
            evento
        )

        if event_type is None:
            continue

        event_name = _event_name(
            evento
        )

        minute = _event_minute(
            evento
        )

        # 1 = gol
        # 2 = gol de penalti
        if event_type in (
            1,
            2,
        ):
            add(
                "goal",
                minute,
            )

        # 3 = asistencia
        elif event_type == 3:
            add(
                "assist",
                minute,
            )

        # 4 = sale
        elif event_type == 4:
            add(
                "sub_out",
                minute,
            )

        # 5 = entra
        elif event_type == 5:
            add(
                "sub_in",
                minute,
            )

        # 6 = amarilla
        elif event_type == 6:
            add(
                "yellow",
                minute,
            )

        # 7 = roja
        # 8 = segunda amarilla
        elif event_type in (
            7,
            8,
        ):
            add(
                "red",
                minute,
            )

        # 9 = gol en propia
        elif event_type == 9:
            add(
                "own_goal",
                minute,
            )

        # 10 = palo
        elif event_type == 10:
            add(
                "post",
                minute,
            )

        # 13 = gol anulado
        elif event_type == 13:
            add(
                "disallowed",
                minute,
            )

        # 14 = lesión
        elif event_type == 14:
            add(
                "injury",
                minute,
            )

        # 16 = penalti cometido
        elif event_type == 16:
            add(
                "penalty",
                minute,
            )

        # Compatibilidad adicional.
        elif "gol anulado" in event_name:
            add(
                "disallowed",
                minute,
            )

        elif "gol" in event_name:
            add(
                "goal",
                minute,
            )

        elif "asistencia" in event_name:
            add(
                "assist",
                minute,
            )

        elif "amarilla" in event_name:
            add(
                "yellow",
                minute,
            )

        elif "roja" in event_name:
            add(
                "red",
                minute,
            )

        elif "lesion" in event_name:
            add(
                "injury",
                minute,
            )

    if jugador.get(
        "mvp"
    ):
        add("mvp")

    return acciones


# ===========================================================================
# ICONOS VECTORIALES
# ===========================================================================


def _icon_goal(
    draw,
    x: int,
    y: int,
    scale: float = 1.0,
):
    r = max(
        6,
        int(
            8 * scale
        ),
    )

    draw.ellipse(
        (
            x - r,
            y - r,
            x + r,
            y + r,
        ),
        outline=TEXT,
        width=max(
            1,
            int(
                2 * scale
            ),
        ),
    )

    inner = max(
        2,
        int(
            2 * scale
        ),
    )

    draw.ellipse(
        (
            x - inner,
            y - inner,
            x + inner,
            y + inner,
        ),
        fill=TEXT,
    )


def _icon_card(
    draw,
    x: int,
    y: int,
    red: bool = False,
    scale: float = 1.0,
):
    width = max(
        8,
        int(
            11 * scale
        ),
    )

    height = max(
        11,
        int(
            16 * scale
        ),
    )

    fill = (
        (225, 72, 72)
        if red
        else (244, 196, 55)
    )

    draw.rounded_rectangle(
        (
            x - width // 2,
            y - height // 2,
            x + width // 2,
            y + height // 2,
        ),
        radius=max(
            2,
            int(
                2 * scale
            ),
        ),
        fill=fill,
    )


def _icon_sub(
    draw,
    x: int,
    y: int,
    direction: str = "in",
    scale: float = 1.0,
):
    radius = max(
        7,
        int(
            9 * scale
        ),
    )

    width = max(
        1,
        int(
            2 * scale
        ),
    )

    if direction == "in":

        draw.line(
            (
                x - radius,
                y,
                x + radius - 3,
                y,
            ),
            fill=GREEN,
            width=width,
        )

        draw.polygon(
            (
                (
                    x + radius,
                    y,
                ),
                (
                    x + radius - 5,
                    y - 4,
                ),
                (
                    x + radius - 5,
                    y + 4,
                ),
            ),
            fill=GREEN,
        )

    else:

        draw.line(
            (
                x + radius,
                y,
                x - radius + 3,
                y,
            ),
            fill=GREEN,
            width=width,
        )

        draw.polygon(
            (
                (
                    x - radius,
                    y,
                ),
                (
                    x - radius + 5,
                    y - 4,
                ),
                (
                    x - radius + 5,
                    y + 4,
                ),
            ),
            fill=GREEN,
        )


def _icon_assist(
    draw,
    x: int,
    y: int,
    scale: float = 1.0,
):
    radius = max(
        7,
        int(
            9 * scale
        ),
    )

    width = max(
        1,
        int(
            2 * scale
        ),
    )

    draw.ellipse(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        ),
        outline=GREEN,
        width=width,
    )

    draw.text(
        (
            x,
            y,
        ),
        "A",
        font=_font(
            max(
                9,
                int(
                    11 * scale
                ),
            ),
            True,
        ),
        fill=GREEN,
        anchor="mm",
    )


def _icon_injury(
    draw,
    x: int,
    y: int,
    scale: float = 1.0,
):
    radius = max(
        7,
        int(
            9 * scale
        ),
    )

    width = max(
        1,
        int(
            2 * scale
        ),
    )

    draw.line(
        (
            x - radius,
            y,
            x + radius,
            y,
        ),
        fill=(235, 80, 80),
        width=width,
    )

    draw.line(
        (
            x,
            y - radius,
            x,
            y + radius,
        ),
        fill=(235, 80, 80),
        width=width,
    )


def _icon_post(
    draw,
    x: int,
    y: int,
    scale: float = 1.0,
):
    radius = max(
        7,
        int(
            9 * scale
        ),
    )

    width = max(
        1,
        int(
            2 * scale
        ),
    )

    draw.rectangle(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        ),
        outline=(225, 215, 120),
        width=width,
    )


def _icon_disallowed(
    draw,
    x: int,
    y: int,
    scale: float = 1.0,
):
    radius = max(
        7,
        int(
            9 * scale
        ),
    )

    width = max(
        1,
        int(
            2 * scale
        ),
    )

    draw.ellipse(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        ),
        outline=(235, 80, 80),
        width=width,
    )

    draw.line(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        ),
        fill=(235, 80, 80),
        width=width,
    )


def _icon_penalty(
    draw,
    x: int,
    y: int,
    scale: float = 1.0,
):
    draw.text(
        (
            x,
            y,
        ),
        "P",
        font=_font(
            max(
                10,
                int(
                    13 * scale
                ),
            ),
            True,
        ),
        fill=(244, 196, 55),
        anchor="mm",
    )


def _icon_mvp(
    draw,
    x: int,
    y: int,
    scale: float = 1.0,
):
    radius = max(
        7,
        int(
            9 * scale
        ),
    )

    draw.polygon(
        (
            (
                x - radius,
                y - radius // 2,
            ),
            (
                x - radius // 2,
                y + radius,
            ),
            (
                x,
                y + radius // 2,
            ),
            (
                x + radius // 2,
                y + radius,
            ),
            (
                x + radius,
                y - radius // 2,
            ),
            (
                x,
                y,
            ),
        ),
        fill=(245, 214, 92),
    )


def _icon_clock(
    draw,
    x: int,
    y: int,
    scale: float = 1.0,
):
    radius = max(
        7,
        int(
            9 * scale
        ),
    )

    width = max(
        1,
        int(
            2 * scale
        ),
    )

    draw.ellipse(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        ),
        outline=FIELD_LINE,
        width=width,
    )

    draw.line(
        (
            x,
            y,
            x,
            y - radius + 3,
        ),
        fill=FIELD_LINE,
        width=width,
    )

    draw.line(
        (
            x,
            y,
            x + radius - 3,
            y + 2,
        ),
        fill=FIELD_LINE,
        width=width,
    )


def _dibujar_icono(
    draw,
    kind: str,
    x: int,
    y: int,
    scale: float = 1.0,
):
    if kind in (
        "goal",
        "own_goal",
    ):
        _icon_goal(
            draw,
            x,
            y,
            scale,
        )

    elif kind == "yellow":
        _icon_card(
            draw,
            x,
            y,
            False,
            scale,
        )

    elif kind == "red":
        _icon_card(
            draw,
            x,
            y,
            True,
            scale,
        )

    elif kind == "sub_in":
        _icon_sub(
            draw,
            x,
            y,
            "in",
            scale,
        )

    elif kind == "sub_out":
        _icon_sub(
            draw,
            x,
            y,
            "out",
            scale,
        )

    elif kind == "assist":
        _icon_assist(
            draw,
            x,
            y,
            scale,
        )

    elif kind == "injury":
        _icon_injury(
            draw,
            x,
            y,
            scale,
        )

    elif kind == "post":
        _icon_post(
            draw,
            x,
            y,
            scale,
        )

    elif kind == "disallowed":
        _icon_disallowed(
            draw,
            x,
            y,
            scale,
        )

    elif kind == "penalty":
        _icon_penalty(
            draw,
            x,
            y,
            scale,
        )

    elif kind == "mvp":
        _icon_mvp(
            draw,
            x,
            y,
            scale,
        )

    elif kind == "clock":
        _icon_clock(
            draw,
            x,
            y,
            scale,
        )


def _dibujar_acciones(
    draw,
    jugador: dict[str, Any],
    x: int,
    y: int,
    max_items: int = 5,
    scale: float = 0.72,
):
    acciones = _acciones_jugador(
        jugador
    )

    if not acciones:
        return

    acciones = acciones[
        :max_items
    ]

    spacing = int(
        18 * scale
    )

    start_x = (
        x
        - (
            (
                len(acciones)
                - 1
            )
            * spacing
            / 2
        )
    )

    for index, (
        kind,
        _minute,
    ) in enumerate(
        acciones
    ):
        _dibujar_icono(
            draw,
            kind,
            round(
                start_x
                + index * spacing
            ),
            y,
            scale=scale,
        )


# ===========================================================================
# FOTOS Y ESCUDOS
# ===========================================================================


def _foto_url_jugador(
    jugador: dict[str, Any],
) -> str | None:
    value = (
        jugador.get("photo")
        or jugador.get("image")
        or jugador.get("imageUrl")
    )

    if isinstance(
        value,
        dict,
    ):
        value = (
            value.get("url")
            or value.get("src")
        )

    if value:
        return str(value)

    player_id = jugador.get(
        "id"
    )

    if player_id is not None:
        return (
            "https://cdn.biwenger.com/i/p/"
            f"{player_id}.png"
        )

    return None


def _dibujar_foto_jugador(
    draw,
    jugador,
    x,
    y,
    radio=34,
):
    """
    Dibuja exclusivamente la foto/círculo del jugador.
    """

    photo_url = _foto_url_jugador(
        jugador
    )

    if _pegar_circular(
        draw,
        photo_url,
        int(x),
        int(y),
        int(radio),
    ):
        return

    draw.ellipse(
        (
            x - radio,
            y - radio,
            x + radio,
            y + radio,
        ),
        fill=(238, 242, 244),
        outline=(8, 18, 30),
        width=3,
    )


def _team_id(
    team: dict[str, Any],
) -> int | None:
    if not isinstance(
        team,
        dict,
    ):
        return None

    candidates = [
        team.get("id"),
        team.get("teamId"),
        team.get("teamID"),
    ]

    nested = team.get(
        "team"
    )

    if isinstance(
        nested,
        dict,
    ):
        candidates.extend(
            [
                nested.get("id"),
                nested.get("teamId"),
            ]
        )

    for value in candidates:

        try:
            if value is not None:
                return int(value)
        except (
            TypeError,
            ValueError,
        ):
            pass

    name = str(
        team.get("name")
        or team.get("team_name")
        or ""
    ).strip().lower()

    if name:

        for (
            team_id,
            team_name,
        ) in TEAM_NAMES.items():

            normal_name = str(
                team_name
            ).strip().lower()

            if (
                name == normal_name
                or name in normal_name
                or normal_name in name
            ):
                return team_id

    return None


def _logo_url(
    team: dict[str, Any],
) -> str | None:
    if not isinstance(
        team,
        dict,
    ):
        return None

    for key in (
        "logo",
        "crest",
        "badge",
        "image",
        "imageUrl",
        "logoUrl",
        "shield",
        "shieldUrl",
    ):

        value = team.get(
            key
        )

        if isinstance(
            value,
            dict,
        ):
            value = (
                value.get("url")
                or value.get("src")
            )

        if (
            isinstance(
                value,
                str,
            )
            and value.startswith(
                (
                    "http://",
                    "https://",
                )
            )
        ):
            return value

    team_id = _team_id(
        team
    )

    if team_id is not None:
        return (
            "https://cdn.biwenger.com/i/t/"
            f"{team_id}.png"
        )

    return None


def _dibujar_escudo(
    draw,
    team: dict[str, Any],
    x: int,
    y: int,
    size: int = 92,
):
    url = _logo_url(
        team
    )

    remote = _open_remote_image(
        url
    )

    if remote is not None:

        remote = _recortar_cuadrado(
            remote,
            size,
        )

        draw._image.paste(
            remote,
            (
                x - size // 2,
                y - size // 2,
            ),
            remote,
        )

        return

    # Fallback.
    draw.ellipse(
        (
            x - size // 2,
            y - size // 2,
            x + size // 2,
            y + size // 2,
        ),
        fill=PANEL_2,
        outline=BORDER,
        width=3,
    )

    name = str(
        team.get("name")
        or team.get("team_name")
        or "?"
    ).strip()

    words = name.split()

    if len(words) >= 2:

        initials = "".join(
            word[0]
            for word in words[:2]
        ).upper()

    else:

        initials = (
            name[:2].upper()
            or "?"
        )

    draw.text(
        (
            x,
            y,
        ),
        initials,
        font=_font(
            28,
            True,
        ),
        fill=TEXT,
        anchor="mm",
    )


# ===========================================================================
# TARJETA DE JUGADOR
# ===========================================================================


def _dibujar_tarjeta_jugador(
    draw,
    jugador: dict[str, Any],
    x: int,
    y: int,
    confirmado: bool = True,
):
    """
    Diseño:

              FOTO
          ┌───────────┐
          │   NOMBRE  │
          │ ⚽ 🟨  ↗  │
          │   7 pts   │
          └───────────┘
    """

    radius = 34

    _dibujar_foto_jugador(
        draw,
        jugador,
        x,
        y,
        radio=radius,
    )

    card_width = 184
    card_height = 78

    top = (
        y
        + radius
        - 1
    )

    draw.rounded_rectangle(
        (
            x - card_width // 2,
            top,
            x + card_width // 2,
            top + card_height,
        ),
        radius=10,
        fill=PANEL,
        outline=BORDER,
        width=1,
    )

    name = _truncate(
        jugador.get(
            "name"
        ),
        19,
    )

    name_font = _font(
        20,
        True,
    )

    box = draw.textbbox(
        (
            0,
            0,
        ),
        name,
        font=name_font,
    )

    draw.text(
        (
            x
            - (
                box[2]
                - box[0]
            )
            / 2,
            top + 4,
        ),
        name,
        font=name_font,
        fill=TEXT,
    )

    # Acciones.
    _dibujar_acciones(
        draw,
        jugador,
        x,
        top + 31,
        max_items=5,
        scale=0.72,
    )

    # Puntos.
    points = _texto_puntos(
        jugador.get(
            "points"
        )
    )

    if (
        confirmado
        and points is not None
    ):

        points_text = (
            f"{points} pts"
        )

        points_font = _font(
            17,
            True,
        )

        box = draw.textbbox(
            (
                0,
                0,
            ),
            points_text,
            font=points_font,
        )

        draw.text(
            (
                x
                - (
                    box[2]
                    - box[0]
                )
                / 2,
                top + 53,
            ),
            points_text,
            font=points_font,
            fill=GREEN,
        )


# ===========================================================================
# CAMPO HORIZONTAL
# ===========================================================================


def _dibujar_campo_partido(
    draw,
    field_left,
    field_right,
    field_top,
    field_bottom,
):
    width = (
        field_right
        - field_left
    )

    height = (
        field_bottom
        - field_top
    )

    radius = 28

    draw.rounded_rectangle(
        (
            field_left,
            field_top,
            field_right,
            field_bottom,
        ),
        radius=radius,
        fill=FIELD,
    )

    # Franjas verticales.
    stripe_width = max(
        80,
        width // 12,
    )

    for index, x in enumerate(
        range(
            field_left,
            field_right,
            stripe_width,
        )
    ):

        if index % 2:

            draw.rectangle(
                (
                    x,
                    field_top,
                    min(
                        x + stripe_width,
                        field_right,
                    ),
                    field_bottom,
                ),
                fill=FIELD_ALT,
            )

    # Borde.
    draw.rounded_rectangle(
        (
            field_left,
            field_top,
            field_right,
            field_bottom,
        ),
        radius=radius,
        outline=FIELD_LINE,
        width=3,
    )

    center_x = (
        field_left
        + field_right
    ) // 2

    center_y = (
        field_top
        + field_bottom
    ) // 2

    # Línea central.
    draw.line(
        (
            center_x,
            field_top,
            center_x,
            field_bottom,
        ),
        fill=FIELD_LINE,
        width=3,
    )

    # Círculo central.
    center_radius = min(
        105,
        int(
            width * 0.085
        ),
    )

    draw.ellipse(
        (
            center_x
            - center_radius,
            center_y
            - center_radius,
            center_x
            + center_radius,
            center_y
            + center_radius,
        ),
        outline=FIELD_LINE,
        width=3,
    )

    draw.ellipse(
        (
            center_x - 5,
            center_y - 5,
            center_x + 5,
            center_y + 5,
        ),
        fill=FIELD_LINE,
    )

    # Áreas grandes.
    area_depth = int(
        width * 0.12
    )

    area_height = int(
        height * 0.46
    )

    area_top = (
        center_y
        - area_height // 2
    )

    area_bottom = (
        center_y
        + area_height // 2
    )

    draw.rectangle(
        (
            field_left,
            area_top,
            field_left
            + area_depth,
            area_bottom,
        ),
        outline=FIELD_LINE,
        width=3,
    )

    draw.rectangle(
        (
            field_right
            - area_depth,
            area_top,
            field_right,
            area_bottom,
        ),
        outline=FIELD_LINE,
        width=3,
    )

    # Áreas pequeñas.
    small_depth = int(
        width * 0.052
    )

    small_height = int(
        height * 0.22
    )

    small_top = (
        center_y
        - small_height // 2
    )

    small_bottom = (
        center_y
        + small_height // 2
    )

    draw.rectangle(
        (
            field_left,
            small_top,
            field_left
            + small_depth,
            small_bottom,
        ),
        outline=FIELD_LINE,
        width=3,
    )

    draw.rectangle(
        (
            field_right
            - small_depth,
            small_top,
            field_right,
            small_bottom,
        ),
        outline=FIELD_LINE,
        width=3,
    )


# ===========================================================================
# CAMPO VERTICAL
# ===========================================================================


def _dibujar_campo_vertical(
    draw,
    field_left,
    field_right,
    field_top,
    field_bottom,
):
    width = (
        field_right
        - field_left
    )

    height = (
        field_bottom
        - field_top
    )

    draw.rounded_rectangle(
        (
            field_left,
            field_top,
            field_right,
            field_bottom,
        ),
        radius=24,
        fill=FIELD,
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
        int(
            width * 0.12
        ),
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


# ===========================================================================
# SUPLENTES
# ===========================================================================


def _extraer_titulares_y_suplentes(
    team: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Reconstruye titulares y suplentes desde reports.

    Biwenger:
        type 5 = entra al campo
    """

    if not isinstance(
        team,
        dict,
    ):
        return [], []

    reports = team.get(
        "reports"
    )

    if not isinstance(
        reports,
        list,
    ):
        return [], []

    titulares: list[
        dict[str, Any]
    ] = []

    suplentes: list[
        dict[str, Any]
    ] = []

    for report in reports:

        if not isinstance(
            report,
            dict,
        ):
            continue

        jugador_raw = _report_player(
            report
        )

        if jugador_raw is None:
            continue

        eventos = (
            report.get("events")
            if isinstance(
                report.get("events"),
                list,
            )
            else jugador_raw.get(
                "events"
            )
            or []
        )

        jugador_raw["events"] = eventos

        normalizado = _normalizar_jugador(
            jugador_raw
        )

        if normalizado is None:
            continue

        entra = False
        minuto_entrada = None

        for evento in eventos:

            if _event_type(
                evento
            ) == 5:

                entra = True

                minuto_entrada = _event_minute(
                    evento
                )

                break

        normalizado[
            "substitute"
        ] = entra

        normalizado[
            "entry_minute"
        ] = (
            minuto_entrada
            if entra
            else None
        )

        if entra:
            suplentes.append(
                normalizado
            )
        else:
            titulares.append(
                normalizado
            )

    suplentes.sort(
        key=lambda jugador: (
            jugador.get(
                "entry_minute"
            )
            if jugador.get(
                "entry_minute"
            )
            is not None
            else 999
        )
    )

    return (
        titulares[:11],
        suplentes,
    )


def _dibujar_suplente(
    draw,
    jugador: dict[str, Any],
    x: int,
    y: int,
    lado: str = "home",
):
    radius = 21

    _dibujar_foto_jugador(
        draw,
        jugador,
        x,
        y,
        radio=radius,
    )

    if lado == "home":

        anchor = "lm"

        text_x = (
            x
            + radius
            + 10
        )

    else:

        anchor = "rm"

        text_x = (
            x
            - radius
            - 10
        )

    name = _truncate(
        jugador.get(
            "name"
        ),
        17,
    )

    minute = jugador.get(
        "entry_minute"
    )

    if minute is not None:

        label = (
            f"{name} · {minute}'"
        )

    else:

        label = name

    draw.text(
        (
            text_x,
            y - 9,
        ),
        label,
        font=_font(
            16,
            True,
        ),
        fill=TEXT,
        anchor=anchor,
    )

    points = _texto_puntos(
        jugador.get(
            "points"
        )
    )

    if points is not None:

        draw.text(
            (
                text_x,
                y + 11,
            ),
            f"{points} pts",
            font=_font(
                14,
                True,
            ),
            fill=GREEN,
            anchor=anchor,
        )

    acciones = _acciones_jugador(
        jugador
    )[:3]

    if acciones:

        icon_spacing = 17

        if lado == "home":
            start_x = (
                text_x + 85
            )
        else:
            start_x = (
                text_x - 85
            )

        for index, (
            kind,
            _minute,
        ) in enumerate(
            acciones
        ):

            if lado == "home":

                icon_x = (
                    start_x
                    + index
                    * icon_spacing
                )

            else:

                icon_x = (
                    start_x
                    - index
                    * icon_spacing
                )

            _dibujar_icono(
                draw,
                kind,
                int(icon_x),
                y - 1,
                scale=0.62,
            )


def _dibujar_bloque_suplentes(
    draw,
    title: str,
    jugadores: list[dict[str, Any]],
    x_left: int,
    y_top: int,
    width: int,
    lado: str,
):
    if lado == "home":

        title_x = x_left
        anchor = "la"

    else:

        title_x = (
            x_left + width
        )
        anchor = "ra"

    draw.text(
        (
            title_x,
            y_top,
        ),
        title,
        font=_font(
            20,
            True,
        ),
        fill=GREEN,
        anchor=anchor,
    )

    if not jugadores:

        draw.text(
            (
                title_x,
                y_top + 40,
            ),
            "Sin suplentes que hayan entrado",
            font=_font(15),
            fill=MUTED,
            anchor=anchor,
        )

        return

    max_players = min(
        len(jugadores),
        5,
    )

    for index in range(
        max_players
    ):

        jugador = jugadores[
            index
        ]

        y = (
            y_top
            + 46
            + index * 47
        )

        if lado == "home":

            photo_x = (
                x_left + 22
            )

        else:

            photo_x = (
                x_left
                + width
                - 22
            )

        _dibujar_suplente(
            draw,
            jugador,
            photo_x,
            y,
            lado=lado,
        )


# ===========================================================================
# LEYENDA
# ===========================================================================


def _dibujar_leyenda(
    draw,
    center_x: int,
    top: int,
):
    items = [
        (
            "goal",
            "Gol",
        ),
        (
            "yellow",
            "Amarilla",
        ),
        (
            "red",
            "Roja",
        ),
        (
            "sub_in",
            "Cambio",
        ),
        (
            "assist",
            "Asistencia",
        ),
        (
            "injury",
            "Lesión",
        ),
        (
            "disallowed",
            "Gol anulado",
        ),
        (
            "own_goal",
            "Gol propia",
        ),
        (
            "mvp",
            "MVP",
        ),
        (
            "clock",
            "Minutos",
        ),
    ]

    draw.text(
        (
            center_x,
            top,
        ),
        "LEYENDA",
        font=_font(
            18,
            True,
        ),
        fill=GREEN,
        anchor="ma",
    )

    column_width = 145
    row_height = 28

    for index, (
        kind,
        label,
    ) in enumerate(
        items
    ):

        column = (
            0
            if index < 5
            else 1
        )

        row = (
            index
            if index < 5
            else index - 5
        )

        x = (
            center_x
            - column_width
            + column
            * column_width
        )

        y = (
            top
            + 30
            + row
            * row_height
        )

        _dibujar_icono(
            draw,
            kind,
            x,
            y,
            scale=0.72,
        )

        draw.text(
            (
                x + 16,
                y,
            ),
            label,
            font=_font(12),
            fill=MUTED,
            anchor="lm",
        )


# ===========================================================================
# IMAGEN COMPLETA DEL PARTIDO
# ===========================================================================


def generar_imagen_partido(
    game: dict[str, Any],
    now: datetime | None = None,
    width: int = 1600,
    height: int = 1250,
) -> tuple[
    BytesIO,
    bool,
]:
    """
    Genera la imagen horizontal definitiva del partido.
    """

    if not isinstance(
        game,
        dict,
    ):
        raise LineupImageError(
            "El partido debe ser un diccionario"
        )

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

    # ------------------------------------------------------------------
    # JUGADORES
    # ------------------------------------------------------------------

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

        # Fallback a XI explícito.
        if len(home_players) < 11:

            fallback = (
                normalizar_alineacion_confirmada(
                    game,
                    "home",
                )
            )

            if len(fallback) == 11:
                home_players = fallback

        if len(away_players) < 11:

            fallback = (
                normalizar_alineacion_confirmada(
                    game,
                    "away",
                )
            )

            if len(fallback) == 11:
                away_players = fallback

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

    # ------------------------------------------------------------------
    # SEGURIDAD
    # ------------------------------------------------------------------

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

    home_name = str(
        home.get("name")
        or home.get("shortName")
        or "Local"
    )

    away_name = str(
        away.get("name")
        or away.get("shortName")
        or "Visitante"
    )

    # ------------------------------------------------------------------
    # IMAGEN
    # ------------------------------------------------------------------

    image = Image.new(
        "RGB",
        (
            width,
            height,
        ),
        BG,
    )

    draw = ImageDraw.Draw(
        image
    )

    center_x = width // 2

    # ------------------------------------------------------------------
    # CABECERA
    # ------------------------------------------------------------------

    _dibujar_escudo(
        draw,
        home,
        110,
        75,
        size=92,
    )

    _dibujar_escudo(
        draw,
        away,
        width - 110,
        75,
        size=92,
    )

    draw.text(
        (
            175,
            50,
        ),
        home_name,
        font=_font(
            38,
            True,
        ),
        fill=TEXT,
        anchor="lm",
    )

    draw.text(
        (
            width - 175,
            50,
        ),
        away_name,
        font=_font(
            38,
            True,
        ),
        fill=TEXT,
        anchor="rm",
    )

    # ------------------------------------------------------------------
    # FORMACIÓN
    # ------------------------------------------------------------------

    def _formation(
        team,
        players,
    ):
        formation = (
            team.get(
                "formation"
            )
            if isinstance(
                team,
                dict,
            )
            else None
        )

        if (
            not formation
            and isinstance(
                team.get("lineup"),
                dict,
            )
        ):
            formation = (
                team["lineup"].get(
                    "formation"
                )
            )

        if formation:
            return str(
                formation
            )

        grouped = _agrupar_por_posicion(
            players
        )

        return "-".join(
            str(
                len(
                    grouped[p]
                )
            )
            for p in (
                2,
                3,
                4,
            )
        )

    draw.text(
        (
            175,
            91,
        ),
        _formation(
            home,
            home_players,
        ),
        font=_font(
            17,
            True,
        ),
        fill=GREEN,
        anchor="lm",
    )

    draw.text(
        (
            width - 175,
            91,
        ),
        _formation(
            away,
            away_players,
        ),
        font=_font(
            17,
            True,
        ),
        fill=GREEN,
        anchor="rm",
    )

    # ------------------------------------------------------------------
    # MARCADOR
    # ------------------------------------------------------------------

    if (
        home.get("score")
        is not None
        or away.get("score")
        is not None
    ):

        resultado = (
            f"{_score_text(home.get('score'))}"
            f"  -  "
            f"{_score_text(away.get('score'))}"
        )

    else:

        resultado = "VS"

    draw.text(
        (
            center_x,
            42,
        ),
        resultado,
        font=_font(
            52,
            True,
        ),
        fill=TEXT,
        anchor="ma",
    )

    date_text = _timestamp_partido(
        game
    )

    if date_text:

        draw.text(
            (
                center_x,
                95,
            ),
            date_text,
            font=_font(
                17,
                True,
            ),
            fill=MUTED,
            anchor="ma",
        )

    # ------------------------------------------------------------------
    # CAMPO
    # ------------------------------------------------------------------

    field_left = 55
    field_right = (
        width - 55
    )

    field_top = 145
    field_bottom = 830

    _dibujar_campo_partido(
        draw,
        field_left,
        field_right,
        field_top,
        field_bottom,
    )

    # ------------------------------------------------------------------
    # SLOTS
    # ------------------------------------------------------------------

    home_slots = _slots_partido(
        home_players,
        field_left,
        field_right,
        field_top,
        field_bottom,
        "home",
    )

    away_slots = _slots_partido(
        away_players,
        field_left,
        field_right,
        field_top,
        field_bottom,
        "away",
    )

    # ------------------------------------------------------------------
    # JUGADORES
    # ------------------------------------------------------------------

    for jugador, x, y in (
        home_slots
        + away_slots
    ):

        x = max(
            field_left + 96,
            min(
                field_right - 96,
                x,
            ),
        )

        y = max(
            field_top + 39,
            min(
                field_bottom - 122,
                y,
            ),
        )

        _dibujar_tarjeta_jugador(
            draw,
            jugador,
            x,
            y,
            confirmado=confirmed,
        )

    # ------------------------------------------------------------------
    # SEPARADOR
    # ------------------------------------------------------------------

    separator_y = 865

    draw.line(
        (
            55,
            separator_y,
            width - 55,
            separator_y,
        ),
        fill=(60, 78, 92),
        width=1,
    )

    # ------------------------------------------------------------------
    # SUPLENTES
    # ------------------------------------------------------------------

    subs_top = 885

    _dibujar_bloque_suplentes(
        draw,
        f"SUPLENTES · {home_name}",
        home_subs,
        65,
        subs_top,
        500,
        "home",
    )

    _dibujar_bloque_suplentes(
        draw,
        f"SUPLENTES · {away_name}",
        away_subs,
        width - 565,
        subs_top,
        500,
        "away",
    )

    # ------------------------------------------------------------------
    # LEYENDA
    # ------------------------------------------------------------------

    _dibujar_leyenda(
        draw,
        center_x,
        subs_top,
    )

    # ------------------------------------------------------------------
    # PIE
    # ------------------------------------------------------------------

    footer = (
        "Alineaciones confirmadas · "
        "suplentes = jugadores con type 5"
        if confirmed
        else
        "Alineaciones probables"
    )

    draw.text(
        (
            center_x,
            height - 18,
        ),
        footer,
        font=_font(14),
        fill=MUTED,
        anchor="ms",
    )

    # ------------------------------------------------------------------
    # SALIDA
    # ------------------------------------------------------------------

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


# ===========================================================================
# IMAGEN INDIVIDUAL
# ===========================================================================


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

        jugadores = (
            normalizar_alineacion_confirmada(
                game,
                team_key,
            )
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

    if not isinstance(
        team,
        dict,
    ):
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
        (opponent or {}).get(
            "name"
        )
        or ""
    )

    image = Image.new(
        "RGB",
        (
            width,
            height,
        ),
        BG,
    )

    draw = ImageDraw.Draw(
        image
    )

    _dibujar_escudo(
        draw,
        team,
        75,
        65,
        size=72,
    )

    draw.text(
        (
            130,
            45,
        ),
        team_name,
        font=_font(
            34,
            True,
        ),
        fill=TEXT,
        anchor="lm",
    )

    draw.text(
        (
            130,
            82,
        ),
        (
            "11 INICIAL"
            if confirmed
            else "11 POSIBLE"
        ),
        font=_font(
            19,
            True,
        ),
        fill=GREEN,
        anchor="lm",
    )

    if opponent_name:

        draw.text(
            (
                width - 55,
                50,
            ),
            f"vs {opponent_name}",
            font=_font(18),
            fill=MUTED,
            anchor="ra",
        )

    field_top = 130
    field_bottom = (
        height - 80
    )

    field_left = 45
    field_right = (
        width - 45
    )

    _dibujar_campo_vertical(
        draw,
        field_left,
        field_right,
        field_top,
        field_bottom,
    )

    slots = _slots_por_posicion(
        players,
        field_left=(
            field_left + 90
        ),
        field_right=(
            field_right - 90
        ),
        field_top=field_top,
        field_bottom=field_bottom,
    )

    for jugador, x, y in slots:

        y = max(
            field_top + 35,
            min(
                field_bottom - 115,
                y,
            ),
        )

        _dibujar_tarjeta_jugador(
            draw,
            jugador,
            x,
            y,
            confirmado=confirmed,
        )

    footer = (
        "Alineación confirmada"
        if confirmed
        else "Alineación probable"
    )

    draw.text(
        (
            width // 2,
            height - 35,
        ),
        footer,
        font=_font(17),
        fill=MUTED,
        anchor="ms",
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


# ===========================================================================
# COMPATIBILIDAD HISTÓRICA
# ===========================================================================


def generar_imagen_partido_completa(
    game: dict[str, Any],
    now: datetime | None = None,
) -> tuple[
    BytesIO,
    bool,
]:
    return generar_imagen_partido(
        game,
        now=now,
    )


# ===========================================================================
# ONCE MANAGER
# ===========================================================================


def generar_imagen_alineacion_manager(
    manager_name: str,
    formation: str,
    players: list[dict[str, Any]],
    width: int = 1200,
    height: int = 1500,
) -> BytesIO:

    jugadores = normalizar_once_manager(
        players
    )

    if not jugadores:
        raise LineupImageError(
            "No hay jugadores válidos "
            "en el once elegido"
        )

    image = Image.new(
        "RGB",
        (
            width,
            height,
        ),
        BG,
    )

    draw = ImageDraw.Draw(
        image
    )

    draw.text(
        (
            55,
            38,
        ),
        str(manager_name),
        font=_font(
            38,
            True,
        ),
        fill=TEXT,
    )

    draw.text(
        (
            55,
            86,
        ),
        (
            f"⚽ {formation}"
            if formation
            else "⚽ ONCE      DE LA JORNADA"
        ),
        font=_font(
            24,
            True,
        ),
        fill=GREEN,
    )

    draw.text(
        (
            width - 55,
            48,
        ),
        "ONCE ELEGIDO",
        font=_font(
            20,
            True,
        ),
        fill=MUTED,
        anchor="ra",
    )

    field_top = 145
    field_bottom = (
        height - 70
    )

    field_left = 45
    field_right = (
        width - 45
    )

    _dibujar_campo_vertical(
        draw,
        field_left,
        field_right,
        field_top,
        field_bottom,
    )

    slots = _slots_por_posicion(
        jugadores,
        field_left=(
            field_left + 90
        ),
        field_right=(
            field_right - 90
        ),
        field_top=field_top,
        field_bottom=field_bottom,
    )

    for jugador, x, y in slots:

        y = max(
            field_top + 35,
            min(
                field_bottom - 115,
                y,
            ),
        )

        _dibujar_tarjeta_jugador(
            draw,
            jugador,
            x,
            y,
            confirmado=False,
        )

    draw.text(
        (
            width // 2,
            height - 35,
        ),
        "Once elegido por el manager",
        font=_font(17),
        fill=MUTED,
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


def generar_imagen_once_miembro(
    miembro: dict[str, Any],
    width: int = 1200,
    height: int = 1500,
) -> BytesIO:

    if not isinstance(
        miembro,
        dict,
    ):
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

    players, formation = (
        obtener_once_manager(
            miembro
        )
    )

    return generar_imagen_alineacion_manager(
        manager_name=manager_name,
        formation=formation,
        players=players,
        width=width,
        height=height,
    )