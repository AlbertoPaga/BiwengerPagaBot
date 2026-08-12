import requests
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from config import BIWENGER_USERNAME, BIWENGER_PASSWORD

BASE_URL = "https://biwenger.as.com/api/v2"
PLAYERS_URL = "https://cf.biwenger.com/api/v2/competitions/la-liga/data"
SALDO_INICIAL = 20_000_000
MADRID_TZ = ZoneInfo("Europe/Madrid")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("biwenger")

TEAM_ABBR = {
    1: "ATH",
    2: "ATM",
    3: "FCB",
    5: "CEL",
    6: "DEP",
    7: "ESP",
    8: "GET",
    10: "LEV",
    13: "RSO",
    15: "RM",
    17: "SEV",
    18: "VAL",
    19: "VIL",
    65: "MAL",
    70: "RAY",
    75: "ELC",
    87: "BET",
    91: "ALA",
    93: "OSA",
    812: "RAC",
}

TEAM_NAMES = {
    1: "Athletic Club",
    2: "Atlético de Madrid",
    3: "FC Barcelona",
    5: "RC Celta",
    6: "RC Deportivo",
    7: "RCD Espanyol",
    8: "Getafe CF",
    10: "Levante UD",
    13: "Real Sociedad",
    15: "Real Madrid",
    17: "Sevilla FC",
    18: "Valencia CF",
    19: "Villarreal CF",
    65: "Málaga CF",
    70: "Rayo Vallecano",
    75: "Elche CF",
    87: "Real Betis",
    91: "Deportivo Alavés",
    93: "CA Osasuna",
    812: "Racing de Santander",
}

_PLAYERS_CACHE = {}
_PLAYERS_CACHE_TIME = 0
PLAYERS_CACHE_TTL = 3600


def _normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto).strip().lower()

    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "-": " ",
        "_": " ",
    }

    for origen, destino in reemplazos.items():
        texto = texto.replace(
            origen,
            destino,
        )

    return " ".join(texto.split())


class BiwengerClient:

    def __init__(self):
        self.session = requests.Session()
        self.public_session = requests.Session()

        self.public_session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        })

        self.token = None
        self.league_id = None
        self.user_id = None
        self.login_time = 0

    def set_context(
        self,
        league_id=None,
        user_id=None,
    ):
        self.league_id = (
            int(league_id)
            if league_id is not None
            else None
        )

        self.user_id = (
            int(user_id)
            if user_id is not None
            else None
        )

    def clear_context(self):
        self.league_id = None
        self.user_id = None

    def login(self):
        if (
            self.token
            and time.time() - self.login_time < 3600
        ):
            return

        response = self.session.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": BIWENGER_USERNAME,
                "password": BIWENGER_PASSWORD,
            },
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        self.token = data["token"]
        self.login_time = time.time()

        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        })

        return data

    def get(
        self,
        endpoint,
        params=None,
        use_context=True,
    ):
        self.login()

        headers = {}

        if use_context:
            if self.league_id is not None:
                headers["X-League"] = str(
                    self.league_id
                )

            if self.user_id is not None:
                headers["X-User"] = str(
                    self.user_id
                )

        response = self.session.get(
            BASE_URL + endpoint,
            headers=headers,
            params=params,
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    def account(self):
        return self.get(
            "/account",
            use_context=False,
        )

    def leagues(self):
        data = self.account()

        root = (
            data.get("data", {})
            if isinstance(data, dict)
            else {}
        )

        leagues = (
            root.get("leagues", [])
            if isinstance(root, dict)
            else []
        )

        return leagues

    def find_league_user(
        self,
        league_id,
    ):
        target = str(league_id)

        for liga in self.leagues():

            if not isinstance(liga, dict):
                continue

            if str(liga.get("id")) != target:
                continue

            usuario = liga.get("user")

            if isinstance(usuario, dict):
                uid = usuario.get("id")

                if uid is not None:
                    return int(uid)

            if (
                isinstance(
                    usuario,
                    (int, str),
                )
                and str(usuario).isdigit()
            ):
                return int(usuario)

            for key in (
                "userId",
                "user_id",
            ):
                uid = liga.get(key)

                if uid is not None:
                    return int(uid)

            return None

        return None

    def prepare_context(
        self,
        league_id,
    ):
        self.clear_context()

        league_id = int(league_id)

        user_id = self.find_league_user(
            league_id
        )

        if user_id is None:
            raise ValueError(
                f"No se encontró usuario para liga {league_id}"
            )

        self.set_context(
            league_id,
            user_id,
        )

        return {
            "league_id": self.league_id,
            "user_id": self.user_id,
        }

    def league(
        self,
        league_id,
    ):
        self.prepare_context(
            league_id
        )

        return self.get(
            "/league",
            params={
                "include": "all",
                "fields": (
                    "*,standings,tournaments,"
                    "group,settings(description)"
                ),
            },
        )

    def league_members(
        self,
        league_id,
    ):
        return self.league(
            league_id
        )

    def board(
        self,
        league_id,
    ):
        self.prepare_context(
            league_id
        )

        return self.get(
            f"/league/{self.league_id}/board"
        )

    def players(self):
        response = self.public_session.get(
            PLAYERS_URL,
            params={
                "lang": "es",
                "score": 2,
            },
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        logger.info(
            "Respuesta pública jugadores recibida: tipo=%s",
            type(data).__name__,
        )

        return data

    def board_history(
        self,
        league_id,
        date=None,
        limit=100,
    ):
        self.prepare_context(
            league_id
        )

        params = {
            "type": "transfer,market",
            "limit": limit,
        }

        if date is not None:
            params["date"] = date

        return self.get(
            f"/league/{self.league_id}/board",
            params=params,
        )

    def get_full_market_history(
        self,
        league_id,
        limit=100,
        max_pages=100,
    ):
        all_events = []
        current_date = None
        seen = set()

        for _ in range(max_pages):

            response = self.board_history(
                league_id,
                current_date,
                limit,
            )

            data = (
                response.get("data", [])
                if isinstance(response, dict)
                else []
            )

            if not data:
                break

            fechas = []

            for event in data:

                if not isinstance(event, dict):
                    continue

                key = (
                    event.get("date"),
                    event.get("type"),
                    event.get("title"),
                )

                if key in seen:
                    continue

                seen.add(key)

                all_events.append(event)

                event_date = event.get(
                    "date"
                )

                if isinstance(
                    event_date,
                    (int, float),
                ):
                    fechas.append(
                        event_date
                    )

            if not fechas:
                break

            antigua = min(fechas)

            if (
                current_date is not None
                and antigua >= current_date
            ):
                break

            current_date = antigua - 1

            if len(data) < limit:
                break

        all_events.sort(
            key=lambda x: x.get(
                "date",
                0,
            ),
            reverse=True,
        )

        logger.info(
            "Historial completo: liga=%s eventos=%s",
            league_id,
            len(all_events),
        )

        return {
            "status": 200,
            "data": all_events,
        }

    def get_market_history_last_24h(
        self,
        league_id,
        limit=100,
        max_pages=20,
    ):
        ahora = datetime.now(
            MADRID_TZ
        )

        inicio_dia = datetime(
            ahora.year,
            ahora.month,
            ahora.day,
            0,
            0,
            0,
            tzinfo=MADRID_TZ,
        )

        desde = inicio_dia.timestamp()

        all_events = []
        current_date = None
        seen = set()

        for _ in range(max_pages):

            response = self.board_history(
                league_id,
                current_date,
                limit,
            )

            data = (
                response.get("data", [])
                if isinstance(response, dict)
                else []
            )

            if not data:
                break

            fechas = []

            for event in data:

                if not isinstance(event, dict):
                    continue

                event_date = event.get(
                    "date"
                )

                if not isinstance(
                    event_date,
                    (int, float),
                ):
                    continue

                key = (
                    event_date,
                    event.get("type"),
                    event.get("title"),
                )

                if key in seen:
                    continue

                seen.add(key)

                fechas.append(
                    event_date
                )

                if event_date >= desde:
                    all_events.append(
                        event
                    )

            if not fechas:
                break

            antigua = min(fechas)

            if antigua < desde:
                break

            if (
                current_date is not None
                and antigua >= current_date
            ):
                break

            current_date = antigua - 1

            if len(data) < limit:
                break

        all_events.sort(
            key=lambda x: x.get(
                "date",
                0,
            ),
            reverse=True,
        )

        logger.info(
            "Historial del día actual: "
            "liga=%s fecha=%s eventos=%s",
            league_id,
            ahora.strftime("%Y-%m-%d"),
            len(all_events),
        )

        return {
            "status": 200,
            "data": all_events,
        }

    def extract_operations(
        self,
        history,
    ):
        operations = []

        if isinstance(history, dict):
            events = history.get(
                "data",
                [],
            )

        elif isinstance(history, list):
            events = history

        else:
            return operations

        for event in events:

            if not isinstance(event, dict):
                continue

            content = event.get(
                "content",
                [],
            )

            if not isinstance(
                content,
                list,
            ):
                continue

            for item in content:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                operation = dict(item)

                operation.update({
                    "_event_date": event.get(
                        "date"
                    ),
                    "_event_type": event.get(
                        "type"
                    ),
                    "_event_title": event.get(
                        "title",
                        "",
                    ),
                })

                operations.append(
                    operation
                )

        return operations

    def calculate_market_report(
        self,
        history,
    ):
        operations = self.extract_operations(
            history
        )

        report = defaultdict(
            lambda: {
                "compras": [],
                "ventas": [],
                "total_compras": 0,
                "total_ventas": 0,
                "numero_compras": 0,
                "numero_ventas": 0,
            }
        )

        for operation in operations:

            amount = operation.get(
                "amount",
                0,
            )

            if not isinstance(
                amount,
                (int, float),
            ):
                amount = 0

            buyer = operation.get(
                "to"
            )

            seller = operation.get(
                "from"
            )

            player_id = operation.get(
                "player"
            )

            if isinstance(
                buyer,
                dict,
            ):
                nombre = buyer.get(
                    "name",
                    "Desconocido",
                )

                report[nombre][
                    "compras"
                ].append({
                    "player_id": player_id,
                    "amount": amount,
                    "date": operation.get(
                        "_event_date"
                    ),
                })

                report[nombre][
                    "total_compras"
                ] += amount

                report[nombre][
                    "numero_compras"
                ] += 1

            if isinstance(
                seller,
                dict,
            ):
                nombre = seller.get(
                    "name",
                    "Desconocido",
                )

                report[nombre][
                    "ventas"
                ].append({
                    "player_id": player_id,
                    "amount": amount,
                    "date": operation.get(
                        "_event_date"
                    ),
                })

                report[nombre][
                    "total_ventas"
                ] += amount

                report[nombre][
                    "numero_ventas"
                ] += 1

        return report


_CLIENT = BiwengerClient()


def obtener_ligas():
    return _CLIENT.leagues()


def diagnostico_liga(
    liga_id,
):
    contexto = _CLIENT.prepare_context(
        liga_id
    )

    respuesta = _CLIENT.get(
        f"/league/{_CLIENT.league_id}/board"
    )

    data = (
        respuesta.get("data", [])
        if isinstance(respuesta, dict)
        else []
    )

    return {
        "league_id": contexto["league_id"],
        "user_id": contexto["user_id"],
        "eventos_board": (
            len(data)
            if isinstance(data, list)
            else None
        ),
        "board_keys": (
            list(respuesta.keys())
            if isinstance(respuesta, dict)
            else []
        ),
    }


def _es_jugador_api(
    objeto,
):
    if not isinstance(
        objeto,
        dict,
    ):
        return False

    player_id = objeto.get(
        "id"
    )

    nombre = objeto.get(
        "name"
    )

    if player_id is None:
        return False

    if not isinstance(
        nombre,
        str,
    ):
        return False

    if not nombre.strip():
        return False

    indicadores_jugador = (
        "position",
        "price",
        "fantasyPrice",
        "status",
        "fitness",
        "points",
        "playedHome",
        "playedAway",
        "pointsHome",
        "pointsAway",
        "pointsLastSeason",
        "teamID",
        "team",
    )

    encontrados = sum(
        1
        for key in indicadores_jugador
        if key in objeto
    )

    return encontrados >= 2


def _extraer_mapa_jugadores(
    forzar=False,
):
    global _PLAYERS_CACHE
    global _PLAYERS_CACHE_TIME

    ahora = time.time()

    if (
        not forzar
        and _PLAYERS_CACHE
        and (
            ahora - _PLAYERS_CACHE_TIME
            < PLAYERS_CACHE_TTL
        )
    ):
        logger.info(
            "Usando caché de jugadores: %s jugadores",
            len(_PLAYERS_CACHE),
        )

        return _PLAYERS_CACHE

    try:
        respuesta = _CLIENT.players()

    except Exception as exc:
        logger.warning(
            "No se pudo cargar el mapa público "
            "de jugadores: %s",
            exc,
        )

        return _PLAYERS_CACHE

    jugadores = {}

    def recorrer(
        objeto,
    ):
        if isinstance(
            objeto,
            dict,
        ):

            if _es_jugador_api(
                objeto
            ):
                player_id = objeto.get(
                    "id"
                )

                try:
                    player_id = int(
                        player_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    player_id = None

                if player_id is not None:
                    jugadores[
                        player_id
                    ] = objeto

            for valor in objeto.values():
                recorrer(
                    valor
                )

        elif isinstance(
            objeto,
            list,
        ):

            for valor in objeto:
                recorrer(
                    valor
                )

    recorrer(
        respuesta
    )

    _PLAYERS_CACHE = jugadores
    _PLAYERS_CACHE_TIME = time.time()

    logger.info(
        "Mapa de jugadores cargado: %s jugadores",
        len(jugadores),
    )

    return jugadores


def _extraer_posicion_jugador(
    jugador,
):
    if not isinstance(
        jugador,
        dict,
    ):
        return "?"

    valor = jugador.get(
        "position"
    )

    if valor is None:
        valor = jugador.get(
            "pos"
        )

    if isinstance(
        valor,
        dict,
    ):
        valor = (
            valor.get("shortName")
            or valor.get("short")
            or valor.get("name")
            or valor.get("id")
        )

    texto = (
        str(valor).strip().lower()
        if valor is not None
        else ""
    )

    equivalencias = {
        "1": "PT",
        "gk": "PT",
        "por": "PT",
        "portero": "PT",
        "porteros": "PT",
        "pt": "PT",
        "2": "DF",
        "def": "DF",
        "defensa": "DF",
        "defensas": "DF",
        "df": "DF",
        "3": "MC",
        "mid": "MC",
        "med": "MC",
        "medio": "MC",
        "mediocentro": "MC",
        "mediocampista": "MC",
        "mc": "MC",
        "4": "DL",
        "fwd": "DL",
        "fw": "DL",
        "del": "DL",
        "delantero": "DL",
        "delanteros": "DL",
        "dl": "DL",
    }

    return equivalencias.get(
        texto,
        "?",
    )


def _nombre_posicion(
    posicion,
):
    return {
        "DL": "Delantero",
        "MC": "Mediocentro",
        "DF": "Defensa",
        "PT": "Portero",
    }.get(
        posicion,
        "Posición desconocida",
    )


def _extraer_nombre_equipo(
    jugador,
):
    if not isinstance(
        jugador,
        dict,
    ):
        return "Desconocido"

    for key in (
        "teamName",
        "team_name",
    ):
        valor = jugador.get(
            key
        )

        if (
            isinstance(valor, str)
            and valor.strip()
        ):
            return valor.strip()

    equipo = jugador.get(
        "team"
    )

    if isinstance(
        equipo,
        dict,
    ):
        for key in (
            "name",
            "shortName",
            "title",
        ):
            valor = equipo.get(
                key
            )

            if (
                isinstance(
                    valor,
                    str,
                )
                and valor.strip()
            ):
                return valor.strip()

    team_id = _extraer_team_id_jugador(
        jugador
    )

    if team_id in TEAM_NAMES:
        return TEAM_NAMES[
            team_id
        ]

    return "Desconocido"


def _extraer_propietario(
    jugador,
):
    if not isinstance(
        jugador,
        dict,
    ):
        return "No disponible"

    for key in (
        "ownerName",
        "owner_name",
        "owner",
    ):
        valor = jugador.get(
            key
        )

        if isinstance(
            valor,
            dict,
        ):
            valor = (
                valor.get("name")
                or valor.get("username")
            )

        if (
            isinstance(
                valor,
                str,
            )
            and valor.strip()
        ):
            return valor.strip()

    return "No disponible"


def _extraer_ultimo_puntos(
    jugador,
):
    if not isinstance(
        jugador,
        dict,
    ):
        return 0

    for key in (
        "pointsLastRound",
        "pointsLastMatchday",
        "pointsLastGameweek",
        "lastRoundPoints",
        "lastMatchdayPoints",
        "pointsLast",
    ):
        valor = jugador.get(
            key
        )

        if isinstance(
            valor,
            (int, float),
        ):
            return valor

    for contenedor_key in (
        "lastRound",
        "lastMatchday",
        "lastGameweek",
    ):
        contenedor = jugador.get(
            contenedor_key
        )

        if isinstance(
            contenedor,
            dict,
        ):
            for key in (
                "points",
                "score",
                "fantasyPoints",
            ):
                valor = contenedor.get(
                    key
                )

                if isinstance(
                    valor,
                    (int, float),
                ):
                    return valor

    return 0


def _extraer_media_puntos(
    jugador,
):
    if not isinstance(
        jugador,
        dict,
    ):
        return 0

    for key in (
        "averagePoints",
        "pointsAverage",
        "avgPoints",
        "average",
        "media",
    ):
        valor = jugador.get(
            key
        )

        if isinstance(
            valor,
            (int, float),
        ):
            return valor

    return 0


def obtener_ficha_jugador(
    player_id,
):
    jugadores = _extraer_mapa_jugadores()

    try:
        player_id = int(
            player_id
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    jugador = jugadores.get(
        player_id
    )

    if not isinstance(
        jugador,
        dict,
    ):
        return None

    team_id = _extraer_team_id_jugador(
        jugador
    )

    posicion = _extraer_posicion_jugador(
        jugador
    )

    nombre = jugador.get(
        "name",
        f"Jugador {player_id}",
    )

    if (
        not isinstance(
            nombre,
            str,
        )
        or not nombre.strip()
    ):
        nombre = f"Jugador {player_id}"

    else:
        nombre = nombre.strip()

    precio = jugador.get(
        "price",
        jugador.get(
            "fantasyPrice",
            0,
        ),
    )

    puntos = jugador.get(
        "points",
        0,
    )

    ultimo_puntos = _extraer_ultimo_puntos(
        jugador
    )

    media_puntos = _extraer_media_puntos(
        jugador
    )

    return {
        "id": player_id,
        "nombre": nombre,
        "equipo": _abreviar_equipo_id(
            team_id
        ),
        "equipo_nombre": _extraer_nombre_equipo(
            jugador
        ),
        "posicion": posicion,
        "posicion_nombre": _nombre_posicion(
            posicion
        ),
        "precio": precio,
        "puntos": puntos,
        "puntos_ultima_jornada": ultimo_puntos,
        "media_puntos": media_puntos,
        "propietario": _extraer_propietario(
            jugador
        ),
        "datos": jugador,
    }


def _extraer_team_id_jugador(
    jugador,
):
    if not isinstance(
        jugador,
        dict,
    ):
        return None

    team_id = jugador.get(
        "teamID"
    )

    if team_id is not None:
        try:
            return int(
                team_id
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    equipo = jugador.get(
        "team"
    )

    if isinstance(
        equipo,
        dict,
    ):
        team_id = equipo.get(
            "id"
        )

        if team_id is not None:
            try:
                return int(
                    team_id
                )

            except (
                TypeError,
                ValueError,
            ):
                return None

    return None


def _abreviar_equipo_id(
    equipo_id,
):
    if equipo_id is None:
        return "?"

    try:
        equipo_id = int(
            equipo_id
        )

    except (
        TypeError,
        ValueError,
    ):
        return "?"

    return TEAM_ABBR.get(
        equipo_id,
        "?",
    )


def _datos_jugador(
    jugadores,
    player_id,
):
    try:
        player_id_int = int(
            player_id
        )

    except (
        TypeError,
        ValueError,
    ):
        player_id_int = player_id

    jugador = jugadores.get(
        player_id_int
    )

    if jugador is None:
        jugador = jugadores.get(
            str(player_id)
        )

    if isinstance(
        jugador,
        dict,
    ):
        nombre = jugador.get(
            "name"
        )

        if (
            not isinstance(
                nombre,
                str,
            )
            or not nombre.strip()
        ):
            nombre = (
                f"Jugador {player_id}"
            )

        team_id = _extraer_team_id_jugador(
            jugador
        )

        equipo = _abreviar_equipo_id(
            team_id
        )

        return (
            nombre.strip(),
            equipo,
        )

    logger.warning(
        "Jugador no encontrado en mapa: id=%s",
        player_id,
    )

    return (
        f"Jugador {player_id}",
        "?",
    )


def _numero(
    valor,
):
    if isinstance(
        valor,
        (int, float),
    ):
        return float(valor)

    if isinstance(
        valor,
        str,
    ):
        texto = valor.strip()

        try:
            return float(
                texto
            )

        except Exception:
            return None

    return None


def _calcular_saldo_actual(
    compras,
    ventas,
):
    return (
        SALDO_INICIAL
        + ventas
        - compras
    )


def _calcular_puja_maxima(
    saldo,
    valor_equipo,
):
    return (
        saldo
        + valor_equipo / 4
    )


def _extraer_standings(
    league_response,
):
    if not isinstance(
        league_response,
        dict,
    ):
        return []

    data = league_response.get(
        "data",
        {},
    )

    if not isinstance(
        data,
        dict,
    ):
        return []

    standings = data.get(
        "standings",
        [],
    )

    if not isinstance(
        standings,
        list,
    ):
        return []

    return standings


def _datos_standing(
    miembro,
):
    if not isinstance(
        miembro,
        dict,
    ):
        return {
            "id": None,
            "nombre": "Desconocido",
            "numero_jugadores": 0,
            "valor_equipo": 0,
        }

    nombre = miembro.get(
        "name",
        "Desconocido",
    )

    if (
        not isinstance(
            nombre,
            str,
        )
        or not nombre.strip()
    ):
        nombre = "Desconocido"

    team_size = miembro.get(
        "teamSize",
        0,
    )

    team_value = miembro.get(
        "teamValue",
        0,
    )

    try:
        team_size = int(
            team_size
        )

    except (
        TypeError,
        ValueError,
    ):
        team_size = 0

    try:
        team_value = int(
            team_value
        )

    except (
        TypeError,
        ValueError,
    ):
        team_value = 0

    return {
        "id": miembro.get(
            "id"
        ),
        "nombre": nombre.strip(),
        "numero_jugadores": team_size,
        "valor_equipo": team_value,
    }


def obtener_miembros_liga(
    liga_id,
):
    league_response = _CLIENT.league(
        liga_id
    )

    standings = _extraer_standings(
        league_response
    )

    miembros = []

    for miembro in standings:
        datos = _datos_standing(
            miembro
        )

        if datos["id"] is None:
            continue

        miembros.append({
            "id": datos["id"],
            "nombre": datos["nombre"],
            "numero_jugadores": (
                datos["numero_jugadores"]
            ),
            "valor_equipo": (
                datos["valor_equipo"]
            ),
        })

    return miembros


def obtener_informe(
    liga_id,
):
    try:
        league_response = _CLIENT.league(
            liga_id
        )

    except Exception as exc:
        logger.exception(
            "Error obteniendo datos de la liga %s",
            liga_id,
        )

        raise exc

    standings = _extraer_standings(
        league_response
    )

    try:
        history = (
            _CLIENT.get_full_market_history(
                liga_id
            )
        )

        market_report = (
            _CLIENT.calculate_market_report(
                history
            )
        )

    except Exception as exc:
        logger.warning(
            "No se pudo obtener el historial "
            "de la liga %s: %s",
            liga_id,
            exc,
        )

        market_report = {}

    resultado = {}

    for miembro in standings:
        datos_standing = _datos_standing(
            miembro
        )

        nombre = datos_standing[
            "nombre"
        ]

        numero_jugadores = (
            datos_standing[
                "numero_jugadores"
            ]
        )

        valor_equipo = (
            datos_standing[
                "valor_equipo"
            ]
        )

        datos_movimientos = (
            market_report.get(
                nombre,
                {},
            )
        )

        compras = datos_movimientos.get(
            "total_compras",
            0,
        )

        ventas = datos_movimientos.get(
            "total_ventas",
            0,
        )

        numero_compras = (
            datos_movimientos.get(
                "numero_compras",
                0,
            )
        )

        numero_ventas = (
            datos_movimientos.get(
                "numero_ventas",
                0,
            )
        )

        saldo_actual = (
            SALDO_INICIAL
            + ventas
            - compras
        )

        puja_maxima = (
            _calcular_puja_maxima(
                saldo_actual,
                valor_equipo,
            )
        )

        resultado[nombre] = {
            "user_id": datos_standing[
                "id"
            ],
            "compras": (
                datos_movimientos.get(
                    "compras",
                    [],
                )
            ),
            "ventas": (
                datos_movimientos.get(
                    "ventas",
                    [],
                )
            ),
            "total_compras": compras,
            "total_ventas": ventas,
            "numero_compras": (
                numero_compras
            ),
            "numero_ventas": (
                numero_ventas
            ),
            "numero_jugadores": (
                numero_jugadores
            ),
            "valor_equipo": (
                valor_equipo
            ),
            "saldo_actual": (
                saldo_actual
            ),
            "puja_maxima": (
                puja_maxima
            ),
        }

    for nombre, datos in market_report.items():

        if nombre in resultado:
            continue

        compras = datos.get(
            "total_compras",
            0,
        )

        ventas = datos.get(
            "total_ventas",
            0,
        )

        saldo_actual = (
            SALDO_INICIAL
            + ventas
            - compras
        )

        resultado[nombre] = {
            "user_id": None,
            "compras": datos.get(
                "compras",
                [],
            ),
            "ventas": datos.get(
                "ventas",
                [],
            ),
            "total_compras": compras,
            "total_ventas": ventas,
            "numero_compras": datos.get(
                "numero_compras",
                0,
            ),
            "numero_ventas": datos.get(
                "numero_ventas",
                0,
            ),
            "numero_jugadores": 0,
            "valor_equipo": 0,
            "saldo_actual": saldo_actual,
            "puja_maxima": saldo_actual,
        }

    return resultado


def obtener_informe_detallado(
    liga_id,
):
    return obtener_informe(
        liga_id
    )


def _timestamp_datetime(
    timestamp,
):
    try:
        return datetime.fromtimestamp(
            float(timestamp),
            tz=timezone.utc,
        ).astimezone(
            MADRID_TZ
        )

    except Exception:
        return None


def _nombre_fecha(
    timestamp,
):
    fecha = _timestamp_datetime(
        timestamp
    )

    if fecha is None:
        return "FECHA DESCONOCIDA"

    meses = [
        "ENERO",
        "FEBRERO",
        "MARZO",
        "ABRIL",
        "MAYO",
        "JUNIO",
        "JULIO",
        "AGOSTO",
        "SEPTIEMBRE",
        "OCTUBRE",
        "NOVIEMBRE",
        "DICIEMBRE",
    ]

    return (
        f"{fecha.day} "
        f"{meses[fecha.month - 1]} "
        f"{fecha.year}"
    )


def _formatear_importe(
    amount,
):
    try:
        return f"{int(amount):,}€"
    except Exception:
        return "0€"


def _formatear_movimiento(
    operation,
    jugadores,
):
    player_id = operation.get(
        "player"
    )

    jugador, equipo = _datos_jugador(
        jugadores,
        player_id,
    )

    importe = operation.get(
        "amount",
        0,
    )

    comprador = operation.get(
        "to"
    )

    vendedor = operation.get(
        "from"
    )

    if isinstance(
        comprador,
        dict,
    ):
        texto = (
            f"🟢 "
            f"{comprador.get('name', 'Desconocido')} "
            f"ficha a "
            f"⚽ {jugador} [{equipo}] "
            f"por {_formatear_importe(importe)}"
        )

        return {
            "texto": texto,
            "player_id": player_id,
            "player_name": jugador,
        }

    if isinstance(
        vendedor,
        dict,
    ):
        texto = (
            f"🔴 "
            f"{vendedor.get('name', 'Desconocido')} "
            f"vende a "
            f"⚽ {jugador} [{equipo}] "
            f"por {_formatear_importe(importe)}"
        )

        return {
            "texto": texto,
            "player_id": player_id,
            "player_name": jugador,
        }

    return None


def _obtener_operaciones(
    history,
):
    operaciones = (
        _CLIENT.extract_operations(
            history
        )
    )

    return sorted(
        operaciones,
        key=lambda x: x.get(
            "_event_date",
            0,
        ),
        reverse=True,
    )


def _construir_grupos_mercado(
    operaciones,
    jugadores,
):
    grupos = {}
    orden = []
    timestamps = {}

    for operacion in operaciones:

        fecha = _timestamp_datetime(
            operacion.get(
                "_event_date"
            )
        )

        clave = (
            fecha.strftime("%Y-%m-%d")
            if fecha
            else "desconocida"
        )

        if clave not in grupos:
            grupos[clave] = []
            orden.append(
                clave
            )

            timestamps[clave] = (
                operacion.get(
                    "_event_date"
                )
            )

        movimiento = _formatear_movimiento(
            operacion,
            jugadores,
        )

        if movimiento:
            grupos[clave].append(
                movimiento
            )

    return {
        "grupos": grupos,
        "orden": orden,
        "timestamps": timestamps,
    }


def obtener_mercado_completo_datos(
    liga_id,
):
    history = (
        _CLIENT.get_full_market_history(
            liga_id
        )
    )

    operaciones = _obtener_operaciones(
        history
    )

    jugadores = (
        _extraer_mapa_jugadores()
    )

    return _construir_grupos_mercado(
        operaciones,
        jugadores,
    )


def obtener_mercado_miembro_datos(
    liga_id,
    miembro_id,
):
    miembros = obtener_miembros_liga(
        liga_id
    )

    miembro = next(
        (
            item
            for item in miembros
            if str(item.get("id"))
            == str(miembro_id)
        ),
        None,
    )

    if miembro is None:
        return {
            "error": (
                "❌ No se encontró el miembro "
                "seleccionado."
            )
        }

    nombre_miembro = miembro.get(
        "nombre",
        "Desconocido",
    )

    history = (
        _CLIENT.get_full_market_history(
            liga_id
        )
    )

    operaciones = _obtener_operaciones(
        history
    )

    operaciones_miembro = []

    for operacion in operaciones:

        comprador = operacion.get(
            "to"
        )

        vendedor = operacion.get(
            "from"
        )

        pertenece = False

        if isinstance(
            comprador,
            dict,
        ):
            if (
                str(comprador.get("id"))
                == str(miembro_id)
            ):
                pertenece = True

        if isinstance(
            vendedor,
            dict,
        ):
            if (
                str(vendedor.get("id"))
                == str(miembro_id)
            ):
                pertenece = True

        if pertenece:
            operaciones_miembro.append(
                operacion
            )

    jugadores = (
        _extraer_mapa_jugadores()
    )

    mercado = _construir_grupos_mercado(
        operaciones_miembro,
        jugadores,
    )

    mercado["nombre_miembro"] = (
        nombre_miembro
    )

    return mercado

def obtener_mercado_miembro(
    liga_id,
    miembro_id,
):
    datos = obtener_mercado_miembro_datos(
        liga_id,
        miembro_id,
    )

    if "error" in datos:
        return datos["error"]

    nombre_miembro = datos.get(
        "nombre_miembro",
        "Desconocido",
    )

    grupos = datos.get(
        "grupos",
        {},
    )

    orden = datos.get(
        "orden",
        [],
    )

    timestamps = datos.get(
        "timestamps",
        {},
    )

    if not orden:
        return (
            f"🧑‍💼 MERCADO — {nombre_miembro}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos."
        )

    lineas = [
        f"🧑‍💼 MERCADO — {nombre_miembro}",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for clave in orden:

        if clave == "desconocida":
            titulo = (
                "📅 FECHA DESCONOCIDA"
            )

        else:
            titulo = (
                "📅 "
                + _nombre_fecha(
                    timestamps.get(
                        clave
                    )
                )
            )

        lineas.append(
            titulo
        )

        lineas.append("")

        for movimiento in grupos.get(
            clave,
            [],
        ):
            lineas.append(
                movimiento["texto"]
            )

        lineas.append("")

    return "\n".join(
        lineas
    ).rstrip()


def obtener_mercado_completo(
    liga_id,
):
    datos = obtener_mercado_completo_datos(
        liga_id
    )

    grupos = datos.get(
        "grupos",
        {},
    )

    orden = datos.get(
        "orden",
        [],
    )

    timestamps = datos.get(
        "timestamps",
        {},
    )

    bloques = []

    for clave in orden:

        if clave == "desconocida":
            titulo = (
                "📅 FECHA DESCONOCIDA"
            )

        else:
            titulo = (
                "📅 "
                + _nombre_fecha(
                    timestamps.get(
                        clave
                    )
                )
            )

        movimientos = [
            movimiento["texto"]
            for movimiento in grupos.get(
                clave,
                [],
            )
        ]

        bloques.append(
            "\n".join([
                titulo,
                "",
                *movimientos,
            ])
        )

    if not bloques:
        return (
            "🔄 MERCADO COMPLETO\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos."
        )

    return (
        "🔄 MERCADO COMPLETO\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n\n".join(
            bloques
        )
    )


def obtener_mercado_24h_datos(
    liga_id,
):
    ahora = datetime.now(
        MADRID_TZ
    )

    fecha_hoy = ahora.strftime(
        "%Y-%m-%d"
    )

    history = (
        _CLIENT.get_market_history_last_24h(
            liga_id
        )
    )

    operaciones = _obtener_operaciones(
        history
    )

    jugadores = (
        _extraer_mapa_jugadores()
    )

    operaciones_hoy = []

    for operacion in operaciones:

        fecha = _timestamp_datetime(
            operacion.get(
                "_event_date"
            )
        )

        if (
            fecha is not None
            and fecha.strftime(
                "%Y-%m-%d"
            ) == fecha_hoy
        ):
            operaciones_hoy.append(
                operacion
            )

    movimientos = []

    for operacion in operaciones_hoy:

        movimiento = _formatear_movimiento(
            operacion,
            jugadores,
        )

        if movimiento:
            movimientos.append(
                movimiento
            )

    return {
        "fecha": ahora,
        "movimientos": movimientos,
    }


def obtener_mercado_24h(
    liga_id,
):
    datos = obtener_mercado_24h_datos(
        liga_id
    )

    ahora = datos[
        "fecha"
    ]

    movimientos = datos[
        "movimientos"
    ]

    if not movimientos:
        return (
            "⏱️ MERCADO — HOY\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos."
        )

    lineas = [
        "⏱️ MERCADO — HOY",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📅 {_nombre_fecha(ahora.timestamp())}",
        "",
    ]

    for movimiento in movimientos:
        lineas.append(
            movimiento["texto"]
        )

    return "\n".join(
        lineas
    )


def _extraer_sales_mercado(
    response,
):
    if not isinstance(
        response,
        dict,
    ):
        return []

    sales = response.get(
        "sales"
    )

    if isinstance(
        sales,
        list,
    ):
        return sales

    data = response.get(
        "data"
    )

    if isinstance(
        data,
        dict,
    ):
        sales = data.get(
            "sales"
        )

        if isinstance(
            sales,
            list,
        ):
            return sales

    return []


def _extraer_player_id_venta(
    sale,
):
    if not isinstance(
        sale,
        dict,
    ):
        return None

    player = sale.get(
        "player"
    )

    if isinstance(
        player,
        dict,
    ):
        player_id = player.get(
            "id"
        )

    else:
        player_id = player

    if player_id is None:
        player_id = sale.get(
            "playerId"
        )

    try:
        return int(
            player_id
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _esta_venta_activa(
    sale,
    ahora_timestamp=None,
):
    if not isinstance(
        sale,
        dict,
    ):
        return False

    if sale.get(
        "expired"
    ) is True:
        return False

    if ahora_timestamp is None:
        ahora_timestamp = time.time()

    until = sale.get(
        "until"
    )

    if until is not None:

        try:

            if (
                float(until)
                <= ahora_timestamp
            ):
                return False

        except (
            TypeError,
            ValueError,
        ):
            pass

    return True


def _precio_venta(
    sale,
    jugador=None,
):
    if isinstance(
        sale,
        dict,
    ):
        for key in (
            "price",
            "amount",
        ):
            value = sale.get(
                key
            )

            if value is not None:
                return value

    if isinstance(
        jugador,
        dict,
    ):
        for key in (
            "price",
            "fantasyPrice",
        ):
            value = jugador.get(
                key
            )

            if value is not None:
                return value

    return 0


def _normalizar_posicion_jugador(
    jugador,
):
    if not isinstance(
        jugador,
        dict,
    ):
        return "?"

    valor = jugador.get(
        "position"
    )

    if valor is None:
        valor = jugador.get(
            "pos"
        )

    if isinstance(
        valor,
        dict,
    ):
        valor = (
            valor.get("name")
            or valor.get("shortName")
            or valor.get("short")
            or valor.get("id")
        )

    texto = (
        str(valor).strip().lower()
        if valor is not None
        else ""
    )

    equivalencias = {
        "dl": "DL",
        "del": "DL",
        "delantero": "DL",
        "delanteros": "DL",
        "forward": "DL",
        "fw": "DL",
        "mc": "MC",
        "med": "MC",
        "medio": "MC",
        "mediocentro": "MC",
        "mediocampista": "MC",
        "midfielder": "MC",
        "mf": "MC",
        "df": "DF",
        "def": "DF",
        "defensa": "DF",
        "defensas": "DF",
        "defender": "DF",
        "defenderes": "DF",
        "pt": "PT",
        "por": "PT",
        "portero": "PT",
        "porteros": "PT",
        "goalkeeper": "PT",
        "gk": "PT",
        "1": "PT",
        "2": "DF",
        "3": "MC",
        "4": "DL",
    }

    return equivalencias.get(
        texto,
        "?",
    )


def _extraer_ofertas_venta(
    sale,
):
    """
    Intenta obtener las ofertas recibidas para una venta.

    Biwenger puede exponerlas con distintos nombres dependiendo
    de la respuesta/configuración. Si no están disponibles,
    devuelve una lista vacía.
    """
    if not isinstance(sale, dict):
        return []

    candidatos = (
        "offers",
        "bids",
        "offersReceived",
        "bidsReceived",
    )

    for key in candidatos:
        valor = sale.get(key)

        if isinstance(valor, list):
            return valor

        if isinstance(valor, dict):
            for subkey in (
                "data",
                "items",
                "results",
                "offers",
                "bids",
            ):
                subvalor = valor.get(subkey)

                if isinstance(subvalor, list):
                    return subvalor

    return []


def _extraer_importe_oferta(
    oferta,
):
    if not isinstance(oferta, dict):
        return None

    for key in (
        "amount",
        "price",
        "value",
        "offer",
        "bid",
    ):
        valor = oferta.get(key)

        if isinstance(valor, (int, float)):
            return valor

        try:
            if valor is not None:
                return float(valor)
        except (
            TypeError,
            ValueError,
        ):
            pass

    return None

def _extraer_puntos_totales(
    jugador,
):
    if not isinstance(
        jugador,
        dict,
    ):
        return 0

    valor = jugador.get(
        "points",
        0,
    )

    try:
        return float(valor)
    except (
        TypeError,
        ValueError,
    ):
        return 0


def _extraer_valor_actual_jugador(
    jugador,
):
    if not isinstance(jugador, dict):
        return 0

    for key in (
        "price",
        "fantasyPrice",
    ):
        valor = jugador.get(key)

        if valor is not None:
            try:
                return float(valor)
            except (
                TypeError,
                ValueError,
            ):
                pass

    return 0


def obtener_mercado_hoy_datos(
    liga_id,
):
    _CLIENT.prepare_context(
        liga_id
    )

    response = _CLIENT.get(
        "/market"
    )

    sales = _extraer_sales_mercado(
        response
    )

    ahora = datetime.now(
        MADRID_TZ
    )

    ahora_timestamp = (
        ahora.timestamp()
    )

    jugadores = (
        _extraer_mapa_jugadores()
    )

    jugadores_sistema = []
    jugadores_managers = []
    jugadores_mios = []

    vistos_sistema = set()
    vistos_managers = set()
    vistos_mios = set()

    mi_user_id = _CLIENT.user_id

    for sale in sales:

        if not _esta_venta_activa(
            sale,
            ahora_timestamp,
        ):
            continue

        player_id = (
            _extraer_player_id_venta(
                sale
            )
        )

        if player_id is None:
            logger.warning(
                "Venta de mercado sin player_id: %s",
                sale,
            )
            continue

        usuario = (
            sale.get("user")
            if isinstance(
                sale,
                dict,
            )
            else None
        )

        es_sistema = (
            usuario is None
        )

        user_id = None
        user_name = None

        if isinstance(
            usuario,
            dict,
        ):
            user_id = usuario.get(
                "id"
            )

            user_name = (
                usuario.get("name")
                or usuario.get("username")
                or usuario.get("email")
            )

        try:
            user_id_int = (
                int(user_id)
                if user_id is not None
                else None
            )
        except (
            TypeError,
            ValueError,
        ):
            user_id_int = None

        es_mia = (
            not es_sistema
            and mi_user_id is not None
            and user_id_int == int(mi_user_id)
        )

        if es_sistema:
            vistos = vistos_sistema
        elif es_mia:
            vistos = vistos_mios
        else:
            vistos = vistos_managers

        sale_id = (
            sale.get("id")
            if isinstance(
                sale,
                dict,
            )
            else None
        )

        dedupe_key = (
            ("sale", sale_id)
            if sale_id is not None
            else ("player", player_id)
        )

        if dedupe_key in vistos:
            continue

        vistos.add(
            dedupe_key
        )

        jugador_api = jugadores.get(
            player_id
        )

        player_from_sale = (
            sale.get("player")
            if isinstance(
                sale,
                dict,
            )
            else None
        )

        if (
            jugador_api is None
            and isinstance(
                player_from_sale,
                dict,
            )
        ):
            jugador_api = (
                player_from_sale
            )

        nombre, equipo = _datos_jugador(
            jugadores,
            player_id,
        )

        if (
            nombre == f"Jugador {player_id}"
            and isinstance(
                player_from_sale,
                dict,
            )
        ):
            nombre_api = (
                player_from_sale.get(
                    "name"
                )
            )

            if (
                isinstance(
                    nombre_api,
                    str,
                )
                and nombre_api.strip()
            ):
                nombre = (
                    nombre_api.strip()
                )

            team_id = (
                _extraer_team_id_jugador(
                    player_from_sale
                )
            )

            if team_id is not None:
                equipo = _abreviar_equipo_id(
                    team_id
                )

        until = sale.get(
            "until"
        )

        until_datetime = (
            _timestamp_datetime(
                until
            )
        )

        posicion = (
            _normalizar_posicion_jugador(
                jugador_api
            )
        )

        if (
            posicion == "?"
            and isinstance(
                player_from_sale,
                dict,
            )
        ):
            posicion = (
                _normalizar_posicion_jugador(
                    player_from_sale
                )
            )

        precio_venta = _precio_venta(
            sale,
            jugador_api,
        )

                valor_actual = (
            _extraer_valor_actual_jugador(
                jugador_api
            )
        )

        puntos_totales = (
            _extraer_puntos_totales(
                jugador_api
            )
        )

        # Si la información pública del jugador
        # no tiene los puntos, intentamos obtenerlos
        # directamente del jugador incluido en la venta.
        if (
            puntos_totales == 0
            and isinstance(
                player_from_sale,
                dict,
            )
        ):
            puntos_totales = (
                _extraer_puntos_totales(
                    player_from_sale
                )
            )

        ofertas = (
            _extraer_ofertas_venta(
                sale
            )
        )

        importes_ofertas = []

        for oferta in ofertas:
            importe = (
                _extraer_importe_oferta(
                    oferta
                )
            )

            if importe is not None:
                importes_ofertas.append(
                    importe
                )

        mejor_oferta = (
            max(importes_ofertas)
            if importes_ofertas
            else None
        )

        venta = {
            "player_id": player_id,
            "player_name": nombre,
            "team": equipo,
            "position": posicion,

            "points": puntos_totales,

            "price": precio_venta,
            "market_value": valor_actual,

            "date": sale.get(
                "date"
            ),
            "until": until,
            "until_datetime": until_datetime,

            "user_id": user_id_int,
            "user_name": user_name,

            "offers": ofertas,
            "offers_count": len(ofertas),
            "best_offer": mejor_oferta,

            "sale": sale,
        }

        if es_sistema:
            jugadores_sistema.append(
                venta
            )

        elif es_mia:
            jugadores_mios.append(
                venta
            )

        else:
            jugadores_managers.append(
                venta
            )

    def _ordenar_ventas(
        items,
    ):
        orden_posiciones = {
            "DL": 0,
            "MC": 1,
            "DF": 2,
            "PT": 3,
            "?": 4,
        }

        def numero(
            valor,
        ):
            try:
                return float(valor)
            except (
                TypeError,
                ValueError,
            ):
                return 0

        items.sort(
            key=lambda item: (
                orden_posiciones.get(
                    item.get(
                        "position",
                        "?",
                    ),
                    4,
                ),
                -numero(
                    item.get(
                        "points",
                        0,
                    )
                ),
                -numero(
                    item.get(
                        "price",
                        0,
                    )
                ),
                str(
                    item.get(
                        "player_name",
                        "",
                    )
                ).casefold(),
            )
        )


    _ordenar_ventas(
        jugadores_sistema
    )

    _ordenar_ventas(
        jugadores_managers
    )

    _ordenar_ventas(
        jugadores_mios
    )

    logger.info(
        "Mercado actual: liga=%s sistema=%s "
        "otros_managers=%s mis_ventas=%s ventas_recibidas=%s",
        liga_id,
        len(jugadores_sistema),
        len(jugadores_managers),
        len(jugadores_mios),
        len(sales),
    )

    return {
        "fecha": ahora,

        "jugadores": jugadores_sistema,

        "jugadores_sistema": jugadores_sistema,

        "jugadores_managers": jugadores_managers,

        "jugadores_mios": jugadores_mios,

        "mostrar_jugadores_managers": True,
    }


def obtener_mercado_hoy(
    liga_id,
):
    datos = obtener_mercado_hoy_datos(
        liga_id
    )

    ahora = datos.get(
        "fecha",
        datetime.now(MADRID_TZ),
    )

    jugadores = datos.get(
        "jugadores_sistema",
        datos.get(
            "jugadores",
            [],
        ),
    )

    lineas = [
        "🛒 MERCADO — HOY",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📅 {_nombre_fecha(ahora.timestamp())}",
        "",
        "🤖 JUGADORES DEL SISTEMA",
        "",
    ]

    if not jugadores:
        lineas.append(
            "No hay jugadores actualmente en venta."
        )

        lineas.append("")

    else:

        for jugador in jugadores:

            nombre = jugador.get(
                "player_name",
                "Jugador desconocido",
            )

            equipo = jugador.get(
                "team",
                "?",
            )

            precio = _formatear_importe(
                jugador.get(
                    "price",
                    0,
                )
            )

            until = jugador.get(
                "until"
            )

            hasta = _timestamp_datetime(
                until
            )

            lineas.append(
                f"⚽ {nombre} [{equipo}]"
            )

            lineas.append(
                f"💰 {precio}"
            )

            if hasta is not None:
                lineas.append(
                    f"⏳ Termina {hasta.strftime('%H:%M')}"
                )

            lineas.append("")

    lineas.extend([
        "👤 JUGADORES DE MANAGERS",
        "",
        "No hay jugadores en venta",
    ])

    return "\n".join(
        lineas
    ).rstrip()


def obtener_movimientos(
    liga_id,
):
    return obtener_mercado_completo(
        liga_id
    )


def obtener_movimientos_24h(
    liga_id,
):
    return obtener_mercado_24h(
        liga_id
    )
