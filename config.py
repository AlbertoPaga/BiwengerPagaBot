import os

from dotenv import load_dotenv

load_dotenv()


def obtener_variable(nombre: str) -> str:
    valor = os.getenv(nombre)

    if not valor:
        raise RuntimeError(f"Falta la variable de entorno: {nombre}")

    return valor


# Telegram
TELEGRAM_TOKEN = obtener_variable("TELEGRAM_TOKEN")

# Biwenger
BIWENGER_USERNAME = obtener_variable("BIWENGER_USERNAME")
BIWENGER_PASSWORD = obtener_variable("BIWENGER_PASSWORD")

# Configuración
PLAYERS_CACHE_FILE = "data/players.json"
MARKET_CACHE_FILE = "data/market.json"

# Horas que dura la caché del diccionario de jugadores
PLAYERS_CACHE_HOURS = 24