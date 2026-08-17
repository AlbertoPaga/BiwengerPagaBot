"""Generador de imágenes de alineaciones para Telegram."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

POSITION_LABELS = {1: "POR", 2: "DEF", 3: "MED", 4: "DEL"}
_ROW_Y = {1: 0.88, 2: 0.68, 3: 0.45, 4: 0.20}


class Line