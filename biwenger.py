import requests
import time
import logging
import re

from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from config import BIWENGER_USERNAME, BIWENGER_PASSWORD

BASE_URL = "https://biwenger.as.com/api/v2"
PLAYERS_URL = "https://cf.biwenger.com/api/v2/competitions/la-liga/data"
ROUNDS_URL = "https://cf.biwenger.com/api/v2/rounds/la-liga"
SALDO_INICIAL = 20_000_000
MADRID_TZ = ZoneInfo("Europe/Madrid")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("biwenger")

TEAM_ABBR = {
    1: "ATH", 2: "ATM", 3: "FCB", 5: "CEL", 6: "DEP", 7: "ESP",
    8: "GET", 10: "LEV", 13: "RSO", 15: "RM", 17: "SEV", 18: "VAL",
    19: "VIL", 65: "MAL", 70: "RAY", 75: "ELC", 87: "BET", 91: "ALA",
    93: "OSA", 812: "RAC",
}
TEAM_NAMES = {
    1: "Athletic Club", 2: "Atlético de Madrid", 3: "FC Barcelona",
    5: "RC Celta", 6: "RC Deportivo", 7: "RCD Espanyol", 8: "Getafe CF",
    10: "Levante UD", 13: "Real Sociedad", 15: "Real Madrid", 17: "Sevilla FC",
    18: "Valencia CF", 19: "Villarreal CF", 65: "Málaga CF", 70: "Rayo Vallecano",
    75: "Elche CF", 87: "Real Betis", 91: "Deportivo Alavés", 93: "CA Osasuna",
    812: "Racing de Santander",
}

_PLAYERS_CACHE = {}
_PLAYERS_CACHE_TIME = 0
PLAYERS_CACHE_TTL = 3600
_REPORT_CACHE = {}
_REPORT_CACHE_TIME = {}
REPORT_CACHE_TTL = 90


def _normalizar_texto(texto):
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    for origen, destino in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "-": " ", "_": " "}.items():
        texto = texto.replace(origen, destino)
    return " ".join(texto.split())


class BiwengerClient:
    def __init__(self):
        self.session = requests.Session()
        self.public_session = requests.Session()
        self.public_session.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
        self.token = None
        self.league_id = None
        self.user_id = None
        self.login_time = 0

    def set_context(self, league_id=None, user_id=None):
        self.league_id = int(league_id) if league_id is not None else None
        self.user_id = int(user_id) if user_id is not None else None

    def clear_context(self):
        self.league_id = None
        self.user_id = None

    def login(self):
        if self.token and time.time() - self.login_time < 3600:
            return
        response = self.session.post(
            f"{BASE_URL}/auth/login",
            json={"email": BIWENGER_USERNAME, "password": BIWENGER_PASSWORD},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["token"]
        self.login_time = time.time()
        self.session.headers.update({"Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        return data

    def get(self, endpoint, params=None, use_context=True):
        self.login()
        headers = {}
        if use_context:
            if self.league_id is not None:
                headers["X-League"] = str(self.league_id)
            if self.user_id is not None:
                headers["X-User"] = str(self.user_id)
        response = self.session.get(BASE_URL + endpoint, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def account(self):
        return self.get("/account", use_context=False)

    def leagues(self):
        data = self.account()
        root = data.get("data", {}) if isinstance(data, dict) else {}
        return root.get("leagues", []) if isinstance(root, dict) else []

    def find_league_user(self, league_id):
        target = str(league_id)
        for liga in self.leagues():
            if not isinstance(liga, dict) or str(liga.get("id")) != target:
                continue
            usuario = liga.get("user")
            if isinstance(usuario, dict) and usuario.get("id") is not None:
                return int(usuario["id"])
            if isinstance(usuario, (int, str)) and str(usuario).isdigit():
                return int(usuario)
            for key in ("userId", "user_id"):
                if liga.get(key) is not None:
                    return int(liga[key])
            return None
        return None

    def prepare_context(self, league_id):
        self.clear_context()
        league_id = int(league_id)
        user_id = self.find_league_user(league_id)
        if user_id is None:
            raise ValueError(f"No se encontró usuario para liga {league_id}")
        self.set_context(league_id, user_id)
        return {"league_id": self.league_id, "user_id": self.user_id}

    def league(self, league_id):
        self.prepare_context(league_id)
        return self.get("/league", params={"include": "all", "fields": "*,standings,tournaments,group,settings(description)"})

    def league_members(self, league_id):
        return self.league(league_id)

    def user_team(self, user_id):
        if self.league_id is None:
            raise ValueError("No hay liga configurada en el contexto.")
        user_id = int(user_id)
        return self.get(f"/user/{user_id}", params={"fields": "*,players(id,owner),league(id,name,competition,mode,scoreID)"})

    def board(self, league_id):
        self.prepare_context(league_id)
        return self.get(f"/league/{self.league_id}/board")

    def players(self):
        response = self.public_session.get(PLAYERS_URL, params={"lang": "es", "score": 2}, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info("Respuesta pública jugadores recibida: tipo=%s", type(data).__name__)
        return data

    def board_history(self, league_id, date=None, limit=100):
        self.prepare_context(league_id)
        params = {"type": "transfer,market", "limit": limit}
        if date is not None:
            params["date"] = date
        return self.get(f"/league/{self.league_id}/board", params=params)


def _extraer_standings(league_response):
    if not isinstance(league_response, dict):
        return []
    data = league_response.get("data", {})
    if not isinstance(data, dict):
        return []
    standings = data.get("standings", [])
    return standings if isinstance(standings, list) else []


def _datos_standing(miembro):
    if not isinstance(miembro, dict):
        return {"id": None, "nombre": "Desconocido", "numero_jugadores": 0, "valor_equipo": 0, "lineup": {}}
    nombre = miembro.get("name") or miembro.get("username") or "Desconocido"
    team_size = miembro.get("teamSize", 0)
    team_value = miembro.get("teamValue", 0)
    try:
        team_size = int(team_size)
    except (TypeError, ValueError):
        team_size = 0
    try:
        team_value = int(team_value)
    except (TypeError, ValueError):
        team_value = 0
    lineup = miembro.get("lineup")
    if not isinstance(lineup, dict):
        lineup = {}
    players = lineup.get("players", [])
    if not isinstance(players, list):
        players = []
    return {
        "id": miembro.get("id"),
        "nombre": str(nombre).strip(),
        "numero_jugadores": team_size,
        "valor_equipo": team_value,
        "lineup": lineup,
        "lineup_players": players,
        "lineup_formation": lineup.get("type") or lineup.get("formation") or lineup.get("system") or "",
    }


def obtener_miembros_liga(liga_id):
    """Devuelve los managers de ``standings`` con su once de jornada.

    Antes esta función obtenía ``standings`` pero no devolvía nada. Además,
    la pantalla de onces necesita conservar ``lineup.players`` y ``lineup.type``.
    """
    league_response = _CLIENT.league(liga_id)
    standings = _extraer_standings(league_response)
    miembros = []
    for miembro in standings:
        datos = _datos_standing(miembro)
        if datos["id"] is not None:
            miembros.append(datos)
    logger.info("Miembros de liga cargados: liga=%s miembros=%s", liga_id, len(miembros))
    return miembros


def obtener_ligas():
    return _CLIENT.leagues()


def _timestamp_partido(partido):
    if not isinstance(partido, dict):
        return None
    for clave in ("date", "start", "startDate", "timestamp"):
        valor = partido.get(clave)
        if isinstance(valor, (int, float)):
            return float(valor)
        if isinstance(valor, str):
            try:
                return datetime.fromisoformat(valor.replace("Z", "+00:00")).timestamp()
            except (TypeError, ValueError):
                continue
    return None


# ---------------------------------------------------------------------------
# El resto de la lógica existente del módulo se mantiene en la rama.
# ---------------------------------------------------------------------------
