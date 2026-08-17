"""Helpers de presentación de alineaciones dentro de la ficha de partido."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from lineup_image import (
    alineacion_confirmada,
    normalizar_alineacion,
    generar_imagen_alineacion,
)

POSITION_LABELS = {
    1: "POR",
    2: "DEF",
    3: "MED",
    4: "DEL",
}


def _jugadores(team: dict[str, Any]) -> list[dict[str, Any]]:
    """Devuelve los reports normalizados, conservando como máximo 11."""
    return normalizar_alineacion(team)


def _linea_jugador(jugador: dict[str, Any], mostrar_puntos: bool) -> str:
    posicion = jugador.get("position_label", "?")
    nombre = jugador.get("name", "Jugador")

    if mostrar_puntos and jugador.get("points") is not None:
        try:
            puntos = int(float(jugador["points"]))
            return f"{posicion} · {nombre} · {puntos} pts"
        except (TypeError, ValueError):
            pass

    return f"{posicion} · {nombre}"


def construir_bloque_alineacion(
    team: dict[str, Any],
    confirmada: bool,
) -> str:
    """Construye el bloque textual de un equipo para la ficha del partido."""
    jugadores = _jugadores(team)
    nombre = str(team.get("name") or "Equipo")
    titulo = "11 INICIAL" if confirmada else "11 POSIBLE"

    lineas = [f"⚽ {nombre} — {titulo}"]

    if not jugadores:
        lineas.append("Sin alineación disponible.")
        return "\n".join(lineas)

    for jugador in jugadores:
        lineas.append(_linea_jugador(jugador, confirmada))

    return "\n".join(lineas)


def construir_ficha_alineaciones(
    game: dict[str, Any],
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Genera la parte de alineaciones de la ficha.

    Antes del comienzo del partido muestra ``reports`` como 11 posible y no
    enseña puntos. Al confirmarse ``initialLineups`` o llegar la hora del
    encuentro muestra el mismo bloque con puntos cuando estén disponibles.
    """
    confirmada = alineacion_confirmada(game, now=now)
    home = game.get("home") or {}
    away = game.get("away") or {}

    texto = "\n\n".join(
        (
            construir_bloque_alineacion(home, confirmada),
            construir_bloque_alineacion(away, confirmada),
        )
    )

    return texto, confirmada


def generar_imagenes_partido(
    game: dict[str, Any],
    now: datetime | None = None,
) -> tuple[BytesIO, BytesIO, bool]:
    """Genera una imagen para cada equipo del partido."""
    confirmada = alineacion_confirmada(game, now=now)
    home = game.get("home") or {}
    away = game.get("away") or {}

    home_image = generar_imagen_alineacion(
        home,
        opponent=away,
        confirmed=confirmada,
    )
    away_image = generar_imagen_alineacion(
        away,
        opponent=home,
        confirmed=confirmada,
    )

    return home_image, away_image, confirmada


def generar_imagen_partido_completa(
    game: dict[str, Any],
    now: datetime | None = None,
) -> tuple[BytesIO, bool]:
    """Genera una única imagen con los dos equipos.

    Se reserva para el envío al bot: la imagen contiene primero el local y
    después el visitante, manteniendo el mismo estado (posible/confirmada).
    """
    confirmada = alineacion_confirmada(game, now=now)
    home = game.get("home") or {}
    away = game.get("away") or {}

    # La imagen actual de lineup_image.py representa un solo equipo. Para no
    # duplicar el motor gráfico, usamos ambas imágenes y las componemos.
    from PIL import Image, ImageDraw, ImageFont

    home_image = generar_imagen_alineacion(
        home,
        opponent=away,
        confirmed=confirmada,
    )
    away_image = generar_imagen_alineacion(
        away,
        opponent=home,
        confirmed=confirmada,
    )

    left = Image.open(home_image).convert("RGB")
    right = Image.open(away_image).convert("RGB")

    gap = 30
    canvas = Image.new(
        "RGB",
        (left.width + right.width + gap, max(left.height, right.height)),
        (7, 14, 24),
    )
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + gap, 0))

    output = BytesIO()
    output.name = "alineaciones_partido.png"
    canvas.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output, confirmada
