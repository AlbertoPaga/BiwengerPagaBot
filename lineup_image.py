"""Generador de imágenes de alineaciones para Telegram."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

POSITION_LABELS = {1: "POR", 2: "DEF", 3: "MED", 4: "DEL"}
_ROW_Y = {1: 0.88, 2: 0.68, 3: 0.45, 4: 0.20}


class LineupImageError(ValueError):
    """Error de datos al construir una imagen de alineación."""


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


def _normalizar_jugador(jugador: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(jugador, dict):
        return None

    # Algunas respuestas envuelven al jugador en ``player``.
    player = jugador.get("player")
    if isinstance(player, dict):
        datos = dict(player)
        datos.update({k: v for k, v in jugador.items() if k != "player"})
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
        "name": str(datos.get("name") or "Jugador"),
        "position": position,
        "position_label": POSITION_LABELS[position],
        "alt_positions": datos.get("altPositions") or [],
        "points": datos.get("points"),
    }


def _normalizar_report(report: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None
    return _normalizar_jugador(report)


def _lista_candidatos_alineacion(
    game: dict[str, Any],
    team_key: str,
) -> list[Any]:
    """Busca los datos de once confirmado sin asumir una única forma de API.

    Biwenger ha usado estructuras distintas según endpoint/versión. Cuando
    existen datos explícitos de titulares tienen prioridad sobre ``reports``.
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
        for key in (team_key, "home" if team_key == "home" else "away"):
            value = initial.get(key)
            if value:
                candidatos.append(value)
    elif isinstance(initial, list):
        candidatos.append(initial)

    for key in ("lineups", "initialLineup", "starters", "startingXI"):
        value = game.get(key)
        if isinstance(value, dict):
            value = value.get(team_key)
        if value:
            candidatos.append(value)

    return candidatos


def _aplanar_jugadores(valor: Any) -> list[dict[str, Any]]:
    if isinstance(valor, list):
        return [item for item in valor if isinstance(item, dict)]

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
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict):
            result = _aplanar_jugadores(nested)
            if result:
                return result

    # También aceptamos un mapa player_id -> jugador.
    valores = list(valor.values())
    if valores and all(isinstance(item, dict) for item in valores):
        return valores

    return []


def _normalizar_lista_jugadores(jugadores: list[Any]) -> list[dict[str, Any]]:
    resultado = []
    vistos = set()

    for jugador in jugadores:
        normalizado = _normalizar_jugador(jugador)
        if normalizado is None:
            continue

        player_id = normalizado.get("id")
        if player_id is not None and player_id in vistos:
            continue
        if player_id is not None:
            vistos.add(player_id)

        resultado.append(normalizado)

        if len(resultado) == 11:
            break

    return resultado


def normalizar_alineacion(team: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza el 11 posible almacenado en ``reports``."""
    reports = team.get("reports", []) if isinstance(team, dict) else []
    return _normalizar_lista_jugadores(reports)


def normalizar_alineacion_confirmada(
    game: dict[str, Any],
    team_key: str,
) -> list[dict[str, Any]]:
    """Obtiene el 11 inicial explícito si la API lo proporciona."""
    for candidato in _lista_candidatos_alineacion(game, team_key):
        jugadores = _aplanar_jugadores(candidato)
        resultado = _normalizar_lista_jugadores(jugadores)
        if resultado:
            return resultado

    # Fallback: en algunos payloads ``reports`` se transforma en el once real
    # cuando el partido arranca. No inventamos jugadores si la API no los da.
    team = game.get(team_key) or {}
    return normalizar_alineacion(team)


def alineacion_confirmada(game: dict[str, Any], now: datetime | None = None) -> bool:
    """Indica si debemos mostrar el once real y la columna de puntos.

    ``initialLineups=True`` tiene prioridad. Si Biwenger aún no marca el campo
    pero ya ha comenzado el partido, pasamos al modo confirmado para intentar
    obtener los titulares reales del payload actualizado.
    """
    if not isinstance(game, dict):
        return False

    if game.get("initialLineups") is True:
        return True

    timestamp = game.get("date")
    if timestamp is None:
        return False

    try:
        partido = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
        actual = now or datetime.now(timezone.utc)
        return actual >= partido
    except (TypeError, ValueError, OSError, OverflowError):
        return False


def obtener_alineacion_mostrable(
    game: dict[str, Any],
    team_key: str,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Selecciona el 11 posible antes del partido y el real después."""
    confirmed = alineacion_confirmada(game, now=now)

    if confirmed:
        return normalizar_alineacion_confirmada(game, team_key), True

    team = game.get(team_key, {}) if isinstance(game, dict) else {}
    return normalizar_alineacion(team), False


def _jugadores_para_imagen(
    team: dict[str, Any],
    game: dict[str, Any] | None,
    team_key: str | None,
    confirmed: bool,
) -> list[dict[str, Any]]:
    if confirmed and game is not None and team_key is not None:
        jugadores = normalizar_alineacion_confirmada(game, team_key)
        if jugadores:
            return jugadores
    return normalizar_alineacion(team)


def _slots_por_posicion(jugadores: list[dict[str, Any]], width: int):
    grouped = {1: [], 2: [], 3: [], 4: []}
    for jugador in jugadores:
        grouped[jugador["position"]].append(jugador)
    slots = []
    left, right = int(width * 0.09), int(width * 0.91)
    for position in (1, 2, 3, 4):
        row = grouped[position]
        if not row:
            continue
        if len(row) == 1:
            xs = [(left + right) // 2]
        else:
            step = (right - left) / (len(row) - 1)
            xs = [round(left + step * i) for i in range(len(row))]
        for jugador, x in zip(row, xs):
            slots.append((jugador, x, round(width * _ROW_Y[position])))
    return slots


def _truncate(text: str, max_length: int = 16) -> str:
    return text if len(text) <= max_length else text[: max_length - 1].rstrip() + "…"


def _rounded_label(draw, xy, name, position, points=None, confirmed=False):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=10, fill=(8, 18, 30), outline=(86, 112, 132), width=1)
    name_font, pos_font = _font(19, True), _font(14, True)
    name_text = _truncate(name)
    box = draw.textbbox((0, 0), name_text, font=name_font)
    draw.text(((x1 + x2 - box[2] + box[0]) // 2, y1 + 7), name_text, font=name_font, fill=(245, 248, 250))
    position_text = position
    if confirmed and points is not None:
        try:
            position_text = f"{position}  •  {int(float(points))} pts"
        except (TypeError, ValueError):
            pass
    box = draw.textbbox((0, 0), position_text, font=pos_font)
    draw.text(((x1 + x2 - box[2] + box[0]) // 2, y1 + 34), position_text, font=pos_font, fill=(139, 219, 177))


def generar_imagen_alineacion(
    team: dict[str, Any],
    opponent=None,
    confirmed=False,
    width=1200,
    height=1500,
    game: dict[str, Any] | None = None,
    team_key: str | None = None,
) -> BytesIO:
    if not isinstance(team, dict):
        raise LineupImageError("El equipo debe ser un diccionario")

    players = _jugadores_para_imagen(team, game, team_key, confirmed)
    if not players:
        raise LineupImageError("No hay jugadores en la alineación")

    team_name = str(team.get("name") or "Equipo")
    opponent_name = str((opponent or {}).get("name") or "")
    title = "11 INICIAL" if confirmed else "11 POSIBLE"
    image = Image.new("RGB", (width, height), (7, 14, 24))
    draw = ImageDraw.Draw(image)
    draw.text((55, 40), team_name, font=_font(38, True), fill=(245, 248, 250))
    draw.text((55, 90), title, font=_font(25, True), fill=(139, 219, 177))
    if opponent_name:
        versus = f"vs {opponent_name}"
        box = draw.textbbox((0, 0), versus, font=_font(22))
        draw.text((width - 55 - (box[2] - box[0]), 48), versus, font=_font(22), fill=(170, 184, 195))
    field_top, field_bottom, field_left, field_right = 155, height - 55, 45, width - 45
    draw.rounded_rectangle((field_left, field_top, field_right, field_bottom), radius=24, fill=(34, 112, 63), outline=(117, 190, 130), width=3)
    mid_y, cx = (field_top + field_bottom) // 2, width // 2
    draw.line((field_left, mid_y, field_right, mid_y), fill=(183, 224, 187), width=2)
    radius = 115
    draw.ellipse((cx - radius, mid_y - radius, cx + radius, mid_y + radius), outline=(183, 224, 187), width=2)
    box_width, box_height = int(width * 0.34), int((field_bottom - field_top) * 0.15)
    draw.rectangle((cx - box_width // 2, field_top, cx + box_width // 2, field_top + box_height), outline=(183, 224, 187), width=2)
    draw.rectangle((cx - box_width // 2, field_bottom - box_height, cx + box_width // 2, field_bottom), outline=(183, 224, 187), width=2)
    label_w, label_h = 170, 66
    for jugador, x, y in _slots_por_posicion(players, width):
        x = max(field_left + label_w // 2, min(field_right - label_w // 2, x))
        y = max(field_top + label_h // 2, min(field_bottom - label_h // 2, y))
        draw.ellipse((x - 30, y - 30, x + 30, y + 30), fill=(238, 242, 244), outline=(8, 18, 30), width=3)
        _rounded_label(draw, (x - label_w // 2, y + 35, x + label_w // 2, y + 35 + label_h), jugador["name"], jugador["position_label"], jugador.get("points"), confirmed)
    footer = "Alineación confirmada" if confirmed else "Alineación probable"
    font = _font(19)
    box = draw.textbbox((0, 0), footer, font=font)
    draw.text(((width - box[2] + box[0]) // 2, height - 38), footer, font=font, fill=(170, 184, 195))
    output = BytesIO()
    output.name = "alineacion.png"
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
