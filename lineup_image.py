"""
Generador de imágenes de alineaciones para Telegram.

Recibe directamente la estructura `home` / `away` de un partido de
Biwenger y genera un PNG en memoria, sin necesidad de guardar archivos
permanentes en el servidor.
"""

from __future__ import annotations

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

# Posición vertical de cada línea del campo.
_ROW_Y = {
    1: 0.88,
    2: 0.68,
    3: 0.45,
    4: 0.20,
}


class LineupImageError(ValueError):
    """Error de datos al construir una imagen de alineación."""


def _font(size: int, bold: bool = False):
    candidates = []

    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            ]
        )

    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)

    return ImageFont.load_default()


def _normalizar_report(report: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(report, dict):
        return None

    player = report.get("player")
    if not isinstance(player, dict):
        return None

    player_id = player.get("id")
    name = player.get("name") or "Jugador"

    try:
        position = int(player.get("position"))
    except (TypeError, ValueError):
        return None

    if position not in POSITION_LABELS:
        return None

    return {
        "id": player_id,
        "name": str(name),
        "position": position,
        "position_label": POSITION_LABELS[position],
        "alt_positions": player.get("altPositions") or [],
        "points": report.get("points"),
    }


def normalizar_alineacion(team: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrae los jugadores de `reports` manteniendo su posición primaria."""
    reports = team.get("reports", []) if isinstance(team, dict) else []
    jugadores = []

    for report in reports:
        jugador = _normalizar_report(report)
        if jugador is not None:
            jugadores.append(jugador)

    return jugadores[:11]


def _slots_por_posicion(jugadores: list[dict[str, Any]], width: int) -> list[tuple[dict[str, Any], int, int]]:
    """Distribuye los jugadores de cada línea horizontalmente."""
    grouped = {1: [], 2: [], 3: [], 4: []}

    for jugador in jugadores:
        grouped[jugador["position"]].append(jugador)

    slots = []
    left = int(width * 0.09)
    right = int(width * 0.91)

    for position in (1, 2, 3, 4):
        row = grouped[position]
        if not row:
            continue

        if len(row) == 1:
            xs = [(left + right) // 2]
        else:
            step = (right - left) / (len(row) - 1)
            xs = [round(left + step * index) for index in range(len(row))]

        for jugador, x in zip(row, xs):
            y = round(width * _ROW_Y[position])
            slots.append((jugador, x, y))

    return slots


def _truncate(text: str, max_length: int = 16) -> str:
    text = str(text)
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _rounded_label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    name: str,
    position: str,
    points: Any = None,
    confirmed: bool = False,
):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=10, fill=(8, 18, 30), outline=(86, 112, 132), width=1)

    name_font = _font(19, bold=True)
    pos_font = _font(14, bold=True)

    name_text = _truncate(name)
    name_box = draw.textbbox((0, 0), name_text, font=name_font)
    name_x = (x1 + x2 - (name_box[2] - name_box[0])) // 2
    draw.text((name_x, y1 + 7), name_text, font=name_font, fill=(245, 248, 250))

    position_text = position
    if confirmed and points is not None:
        try:
            position_text = f"{position}  •  {int(float(points))} pts"
        except (TypeError, ValueError):
            pass

    pos_box = draw.textbbox((0, 0), position_text, font=pos_font)
    pos_x = (x1 + x2 - (pos_box[2] - pos_box[0])) // 2
    draw.text((pos_x, y1 + 34), position_text, font=pos_font, fill=(139, 219, 177))


def generar_imagen_alineacion(
    team: dict[str, Any],
    opponent: dict[str, Any] | None = None,
    confirmed: bool = False,
    width: int = 1200,
    height: int = 1500,
) -> BytesIO:
    """Genera un PNG listo para `telegram.Bot.send_photo`."""
    if not isinstance(team, dict):
        raise LineupImageError("El equipo debe ser un diccionario")

    players = normalizar_alineacion(team)
    if not players:
        raise LineupImageError("No hay jugadores en reports")

    team_name = str(team.get("name") or "Equipo")
    opponent_name = str((opponent or {}).get("name") or "")
    title = "11 INICIAL" if confirmed else "11 POSIBLE"

    image = Image.new("RGB", (width, height), (7, 14, 24))
    draw = ImageDraw.Draw(image)

    # Cabecera.
    draw.text((55, 40), team_name, font=_font(38, bold=True), fill=(245, 248, 250))
    draw.text((55, 90), title, font=_font(25, bold=True), fill=(139, 219, 177))

    if opponent_name:
        versus = f"vs {opponent_name}"
        box = draw.textbbox((0, 0), versus, font=_font(22))
        draw.text((width - 55 - (box[2] - box[0]), 48), versus, font=_font(22), fill=(170, 184, 195))

    # Campo.
    field_top = 155
    field_bottom = height - 55
    field_left = 45
    field_right = width - 45

    draw.rounded_rectangle(
        (field_left, field_top, field_right, field_bottom),
        radius=24,
        fill=(34, 112, 63),
        outline=(117, 190, 130),
        width=3,
    )

    mid_y = (field_top + field_bottom) // 2
    draw.line((field_left, mid_y, field_right, mid_y), fill=(183, 224, 187), width=2)

    cx = width // 2
    cy = mid_y
    radius = 115
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(183, 224, 187), width=2)

    box_width = int(width * 0.34)
    box_height = int((field_bottom - field_top) * 0.15)
    draw.rectangle(
        (cx - box_width // 2, field_top, cx + box_width // 2, field_top + box_height),
        outline=(183, 224, 187),
        width=2,
    )
    draw.rectangle(
        (cx - box_width // 2, field_bottom - box_height, cx + box_width // 2, field_bottom),
        outline=(183, 224, 187),
        width=2,
    )

    # Línea de jugadores.
    slots = _slots_por_posicion(players, width)
    label_w = 170
    label_h = 66

    for jugador, x, y in slots:
        # Ajuste para evitar que la etiqueta se salga del campo.
        x = max(field_left + label_w // 2, min(field_right - label_w // 2, x))
        y = max(field_top + label_h // 2, min(field_bottom - label_h // 2, y))

        draw.ellipse(
            (x - 30, y - 30, x + 30, y + 30),
            fill=(238, 242, 244),
            outline=(8, 18, 30),
            width=3,
        )

        _rounded_label(
            draw,
            (x - label_w // 2, y + 35, x + label_w // 2, y + 35 + label_h),
            jugador["name"],
            jugador["position_label"],
            jugador.get("points"),
            confirmed=confirmed,
        )

    # Pie informativo.
    footer = "Alineación confirmada" if confirmed else "Alineación probable"
    footer_font = _font(19)
    footer_box = draw.textbbox((0, 0), footer, font=footer_font)
    draw.text(
        ((width - (footer_box[2] - footer_box[0])) // 2, height - 38),
        footer,
        font=footer_font,
        fill=(170, 184, 195),
    )

    output = BytesIO()
    output.name = "alineacion.png"
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
