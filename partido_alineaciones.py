"""Helpers de presentación de alineaciones dentro de la ficha de partido."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from lineup_image import (
    alineacion_confirmada,
    normalizar_alineacion,
    obtener_alineacion_mostrable,
    generar_imagen_alineacion,
)


def _jugadores(team: dict[str, Any]) -> list[dict[str, Any]]:
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
    game: dict[str, Any],
    team_key: str,
    confirmada: bool,
) -> str:
    jugadores, estado = obtener_alineacion_mostrable(game, team_key)
    # El estado calculado por el helper es la fuente de verdad.
    confirmada = estado
    team = game.get(team_key) or {}
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
    confirmada = alineacion_confirmada(game, now=now)
    texto = "\n\n".join(
        (
            construir_bloque_alineacion(game, "home", confirmada),
            construir_bloque_alineacion(game, "away", confirmada),
        )
    )
    return texto, confirmada


def generar_imagenes_partido(
    game: dict[str, Any],
    now: datetime | None = None,
) -> tuple[BytesIO, BytesIO, bool]:
    confirmada = alineacion_confirmada(game, now=now)
    home = game.get("home") or {}
    away = game.get("away") or {}

    home_image = generar_imagen_alineacion(
        home,
        opponent=away,
        confirmed=confirmada,
        game=game,
        team_key="home",
    )
    away_image = generar_imagen_alineacion(
        away,
        opponent=home,
        confirmed=confirmada,
        game=game,
        team_key="away",
    )

    return home_image, away_image, confirmada


def generar_imagen_partido_completa(
    game: dict[str, Any],
    now: datetime | None = None,
) -> tuple[BytesIO, bool]:
    """Genera una única imagen vertical pensada para Telegram."""
    confirmada = alineacion_confirmada(game, now=now)
    home = game.get("home") or {}
    away = game.get("away") or {}

    home_image = generar_imagen_alineacion(
        home,
        opponent=away,
        confirmed=confirmada,
        game=game,
        team_key="home",
    )
    away_image = generar_imagen_alineacion(
        away,
        opponent=home,
        confirmed=confirmada,
        game=game,
        team_key="away",
    )

    from PIL import Image

    top = Image.open(home_image).convert("RGB")
    bottom = Image.open(away_image).convert("RGB")
    gap = 24

    canvas = Image.new(
        "RGB",
        (max(top.width, bottom.width), top.height + bottom.height + gap),
        (7, 14, 24),
    )
    canvas.paste(top, ((canvas.width - top.width) // 2, 0))
    canvas.paste(bottom, ((canvas.width - bottom.width) // 2, top.height + gap))

    output = BytesIO()
    output.name = "alineaciones_partido.png"
    canvas.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output, confirmada
