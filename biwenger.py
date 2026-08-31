import requests
import time
import logging
import re

from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from config import BIWENGER_USERNAME, BIWENGER_PASSWORD

BASE_URL = "https://biwenger.as.com/api/v2"

PLAYERS_URL = (
    "https://cf.biwenger.com/api/v2/competitions/la-liga/data"
)

ROUNDS_URL = (
    "https://cf.biwenger.com/api/v2/rounds/la-liga"
)

SALDO_INICIAL = 20_000_000

MADRID_TZ = ZoneInfo(
    "Europe/Madrid"
)

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


    def user_team(
        self,
        user_id,
    ):
        """
        Obtiene la plantilla de un usuario de la liga.
        """

        if self.league_id is None:
            raise ValueError(
                "No hay liga configurada en el contexto."
            )

        try:
            user_id = int(
                user_id
            )

        except (
            TypeError,
            ValueError,
        ):
            raise ValueError(
                f"ID de usuario inválido: {user_id}"
            )

        return self.get(
            f"/user/{user_id}",
            params={
                "fields": (
                    "*,"
                    "players(id,owner),"
                    "league(id,name,competition,mode,scoreID)"
                )
            },
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

    def get_round_rewards(
        self,
        league_id,
    ):
        """
        Obtiene los abonos definitivos de las jornadas.

        Biwenger puede publicar una jornada más de una vez:

        - primero como cierre provisional si existen partidos
          aplazados o pendientes;
        - posteriormente como cierre definitivo/rectificado
          cuando todos los partidos de la jornada han terminado.

        Para cada jornada se conserva únicamente el último
        roundFinished publicado por Biwenger.

        Devuelve:

            {
                user_id: bonus_total
            }

        donde bonus_total es la suma de los abonos definitivos
        de todas las jornadas.
        """

        self.prepare_context(
            league_id
        )

        response = self.get(
            f"/league/{self.league_id}/board",
            params={
                "type": "roundFinished",
            },
        )

        data = (
            response.get("data", [])
            if isinstance(response, dict)
            else []
        )

        cierres_por_jornada = {}

        for event in data:

            if not isinstance(
                event,
                dict,
            ):
                continue

            if event.get(
                "type"
            ) != "roundFinished":
                continue

            content = event.get(
                "content"
            )

            if not isinstance(
                content,
                dict,
            ):
                continue

            resultados = content.get(
                "results",
                [],
            )

            if not isinstance(
                resultados,
                list,
            ):
                continue

            # -------------------------------------------------
            # Identificar la jornada.
            # -------------------------------------------------

            jornada = content.get(
                "round"
            )

            if jornada is None:
                jornada = content.get(
                    "roundId"
                )

            if jornada is None:
                jornada = content.get(
                    "round_id"
                )

            if isinstance(
                jornada,
                dict,
            ):
                jornada_id = jornada.get(
                    "id"
                )

                if jornada_id is None:
                    jornada_id = jornada.get(
                        "roundId"
                    )

                if jornada_id is None:
                    jornada_id = jornada.get(
                        "round_id"
                    )

                jornada_nombre = jornada.get(
                    "name"
                )

                jornada_part = jornada.get(
                    "part"
                )

            else:
                jornada_id = jornada
                jornada_nombre = None
                jornada_part = None

            if jornada_id is None:
                jornada_id = event.get(
                    "id"
                )

            if jornada_id is None:
                continue

            jornada_id = str(
                jornada_id
            )

            # -------------------------------------------------
            # Fecha del cierre.
            # El último evento publicado para esa jornada
            # sustituye al anterior.
            # -------------------------------------------------

            fecha = event.get(
                "date",
                0,
            )

            try:
                fecha = float(
                    fecha
                )
            except (
                TypeError,
                ValueError,
            ):
                fecha = 0

            actual = cierres_por_jornada.get(
                jornada_id
            )

            if (
                actual is not None
                and actual["date"] >= fecha
            ):
                continue

            cierres_por_jornada[jornada_id] = {
                "date": fecha,
                "results": resultados,
                "name": jornada_nombre,
                "part": jornada_part,
            }

        # -------------------------------------------------
        # Sumamos únicamente el último cierre de cada
        # jornada.
        # -------------------------------------------------

        premios = defaultdict(
            int
        )

        for jornada_id, cierre in (
            cierres_por_jornada.items()
        ):

            resultados = cierre.get(
                "results",
                [],
            )

            logger.info(
                "Cierre definitivo seleccionado: "
                "jornada_id=%s nombre=%s part=%s fecha=%s",
                jornada_id,
                cierre.get("name"),
                cierre.get("part"),
                cierre.get("date"),
            )

            for resultado in resultados:

                if not isinstance(
                    resultado,
                    dict,
                ):
                    continue

                usuario = resultado.get(
                    "user"
                )

                if not isinstance(
                    usuario,
                    dict,
                ):
                    continue

                user_id = usuario.get(
                    "id"
                )

                try:
                    user_id = int(
                        user_id
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                bonus = resultado.get(
                    "bonus",
                    0,
                )

                try:
                    bonus = int(
                        bonus
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    bonus = 0

                premios[user_id] += bonus

                logger.info(
                    "Premio jornada: "
                    "jornada_id=%s usuario=%s bonus=%s "
                    "acumulado=%s",
                    jornada_id,
                    user_id,
                    bonus,
                    premios[user_id],
                )

        logger.info(
            "Premios de jornadas obtenidos: "
            "liga=%s cierres=%s usuarios=%s premios=%s",
            league_id,
            len(cierres_por_jornada),
            len(premios),
            dict(premios),
        )

        return dict(
            premios
        
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

        premios = {}

        if self.league_id is not None:

            try:

                premios = (
                    self.get_round_rewards(
                        self.league_id
                    )
                )

            except Exception as exc:

                logger.warning(
                    "No se pudieron obtener "
                    "los premios de jornadas: %s",
                    exc,
                )

                premios = {}

        report = defaultdict(
            lambda: {
                "compras": [],
                "ventas": [],
                "total_compras": 0,
                "total_ventas": 0,
                "numero_compras": 0,
                "numero_ventas": 0,
                "premios": 0,
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

                user_id = buyer.get(
                    "id"
                )

                try:
                    user_id = int(
                        user_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    user_id = None

                if user_id is not None:
                    report[nombre][
                        "premios"
                    ] = premios.get(
                        user_id,
                        0,
                    )

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

                user_id = seller.get(
                    "id"
                )

                try:
                    user_id = int(
                        user_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    user_id = None

                if user_id is not None:
                    report[nombre][
                        "premios"
                    ] = premios.get(
                        user_id,
                        0,
                    )

        return report


    def obtener_jornadas(
        self,
        start_id=4899,
        max_jornadas=38,
    ):
        """
        Obtiene todas las jornadas recorriendo los IDs de Biwenger.

        Los IDs son consecutivos, pero una jornada aplazada tiene
        un ID diferente y conserva el mismo `short`.

        Ejemplo:
 
            4899 -> J1 -> Jornada 1
            4900 -> J2 -> Jornada 2
            ...
            4937 -> J1 -> Jornada 1 (aplazada)

        Devuelve una lista con todas las jornadas encontradas.
        """

        import re

        jornadas = []

        # Evitamos duplicados por ID
        ids_vistos = set()

        # Necesitamos seguir buscando después de encontrar la J38,
        # porque puede haber jornadas aplazadas con IDs posteriores.
        #
        # El límite evita hacer peticiones infinitas si Biwenger
        # devuelve errores o cambia el comportamiento.
        max_ids = 100

        logger.info(
            "Obteniendo jornadas recorriendo IDs desde %s",
            start_id,
        )

        for offset in range(max_ids):

            round_id = start_id + offset

            if round_id in ids_vistos:
                continue

            ids_vistos.add(round_id)
 
            try:
                response = self.public_session.get(
                    f"{ROUNDS_URL}/{round_id}",
                    params={
                        "score": 2,
                        "lang": "es",
                        "v": 631,
                    },
                    timeout=15,
                )

                if response.status_code == 404:
                    logger.info(
                        "ID %s no existe. Fin de búsqueda.",
                        round_id,
                    )
                    break

                response.raise_for_status()

                data = response.json()

            except Exception as exc:
                logger.warning(
                    "Error obteniendo jornada ID %s: %s",
                    round_id,
                    exc,
                )
                continue

            if not isinstance(data, dict):
                logger.warning(
                    "Respuesta inesperada para jornada %s: %s",
                    round_id,
                    type(data).__name__,
                )
                continue

        # -------------------------------------------------
        # Extraer información de la jornada
        # -------------------------------------------------

            root = data.get("data", data)

            if not isinstance(root, dict):
                continue

            short = root.get("short")
            name = root.get("name")

            # Algunas respuestas pueden tener la información
            # en otro nivel.
            if short is None:
                short = data.get("short")

            if name is None:
                name = data.get("name")

            # Si no encontramos short, probablemente ese ID no
            # corresponde a una jornada.
            if not short:
                logger.warning(
                    "ID %s sin short. Keys=%s",
                    round_id,
                    list(root.keys()),
                )
                continue

            # Normalizamos
            short = str(short).strip()

            if name is None:
                name = f"Jornada {short}"

            name = str(name).strip()

        # -------------------------------------------------
        # Partidos
        # -------------------------------------------------

            games = root.get("games", [])

            if not isinstance(games, list):
                games = []

            if games:
                logger.warning(
                    "DEBUG PARTIDO JORNADA %s: %r",
                    round_id,
                    games[0],
                )

            jornada = {
                "id": round_id,
                "short": short,
                "name": name,
                "games": games,
                "data": data,
            }

            jornadas.append(jornada)

            logger.info(
                "Jornada encontrada: id=%s short=%s name=%s games=%s",
                round_id,
                short,
                name,
                len(games),
            )

    # -----------------------------------------------------
    # Ordenación
    # -----------------------------------------------------

        jornadas.sort(
            key=lambda j: (
                int(
                    re.search(
                        r"\d+",
                        j["short"],
                    ).group()
                )
                if re.search(
                    r"\d+",
                    j["short"],
                )
                else 999,
                j["id"],
            )
        )

    # -----------------------------------------------------
    # Diagnóstico
    # -----------------------------------------------------

        logger.warning(
            "JORNADAS ENCONTRADAS: %s",
            [
                (
                    j["id"],
                    j["name"],
                    j["short"],
                    len(j["games"]),
                )
                for j in jornadas
            ],
        )

        return {
            "data": jornadas
        }


    def obtener_jornada_actual(self):
        """
        Obtiene únicamente la jornada actual de Biwenger.
        """

        try:
            response = self.public_session.get(
                ROUNDS_URL,
                params={
                    "score": 2,
                    "lang": "es",
                    "v": 631,
                },
                timeout=15,
            )

            response.raise_for_status()

            data = response.json()

        except Exception as exc:
            logger.error(
                "Error obteniendo jornada actual: %s",
                exc,
                exc_info=True,
            )
            return None

        if not isinstance(data, dict):
            logger.warning(
                "Respuesta inesperada para jornada actual: %s",
                type(data).__name__,
            )
            return None

        root = data.get(
            "data",
            data,
        )

        if not isinstance(root, dict):
            logger.warning(
                "Datos inesperados para jornada actual"
            )
            return None

        short = root.get("short")
        name = root.get("name")

        if short is None:
            short = data.get("short")

        if name is None:
            name = data.get("name")

        if not short:
            logger.warning(
                "La jornada actual no contiene short. Keys=%s",
                list(root.keys()),
            )
            return None

        short = str(short).strip()

        if name is None:
            name = f"Jornada {short}"

        name = str(name).strip()


        games = root.get(
            "games",
            [],
        )

        if not isinstance(games, list):
            games = []

        if games:
            logger.warning(
                "DEBUG JORNADA ACTUAL GAME: %r",
                games[0],
            )

        jornada = {
            "id": root.get("id"),
            "short": short,
            "name": name,
            "games": games,
            "data": data,
        }

        logger.info(
            "Jornada actual: id=%s short=%s name=%s games=%s",
            jornada["id"],
            jornada["short"],
            jornada["name"],
            len(jornada["games"]),
        )

        return jornada


_CLIENT = BiwengerClient()

# ============================================================
# DIAGNÓSTICO DE DESPLIEGUE
# ============================================================

import inspect
import hashlib
import os

try:
    _CLIENT_FILE = inspect.getfile(BiwengerClient)

    with open(
        _CLIENT_FILE,
        "rb",
    ) as _f:
        _CLIENT_SHA256 = hashlib.sha256(
            _f.read()
        ).hexdigest()

    logger.warning(
        "========== BIWENGER CLIENT DIAGNOSTIC =========="
    )

    logger.warning(
        "BiwengerClient class: %s",
        BiwengerClient,
    )

    logger.warning(
        "BiwengerClient file: %s",
        _CLIENT_FILE,
    )

    logger.warning(
        "BiwengerClient file exists: %s",
        os.path.exists(_CLIENT_FILE),
    )

    logger.warning(
        "BiwengerClient SHA256: %s",
        _CLIENT_SHA256,
    )

    logger.warning(
        "obtener_jornadas exists: %s",
        hasattr(
            BiwengerClient,
            "obtener_jornadas",
        ),
    )

    logger.warning(
        "obtener_jornadas method: %s",
        getattr(
            BiwengerClient,
            "obtener_jornadas",
            None,
        ),
    )

    logger.warning(
        "================================================"
    )

except Exception as exc:
    logger.exception(
        "ERROR EN DIAGNOSTICO BIWENGER CLIENT: %s",
        exc,
    )


def obtener_jornada_actual():
    """
    Obtiene únicamente la jornada actual de Biwenger.
    """

    try:
        jornada = _CLIENT.obtener_jornada_actual()

        if jornada is None:
            logger.warning(
                "No se pudo obtener la jornada actual"
            )
            return None

        logger.info(
            "Jornada actual: id=%s short=%s name=%s games=%s",
            jornada.get("id"),
            jornada.get("short"),
            jornada.get("name"),
            len(jornada.get("games", [])),
        )

        return jornada

    except Exception as exc:
        logger.exception(
            "Error obteniendo jornada actual: %s",
            exc,
        )

        return None

def obtener_jornadas():
    """
    Obtiene todas las jornadas de LaLiga.

    El cliente ya recorre los IDs de las jornadas
    y obtiene los partidos de cada una.
    """

    try:

        response = _CLIENT.obtener_jornadas()

        # El cliente devuelve:
        #
        # {
        #     "data": [
        #         {
        #             "id": 4899,
        #             "short": "J1",
        #             "name": "Jornada 1",
        #             "games": [...]
        #         },
        #         ...
        #     ]
        # }

        if not isinstance(response, dict):

            logger.error(
                "Respuesta de jornadas inesperada: %r",
                type(response).__name__,
            )

            return []

        jornadas = response.get(
            "data",
            [],
        )

        if not isinstance(jornadas, list):

            logger.error(
                "Campo data de jornadas inesperado: %r",
                type(jornadas).__name__,
            )

            return []

        logger.warning(
            "JORNADAS ENCONTRADAS: %s",
            [
                (
                    jornada.get("id"),
                    jornada.get("name"),
                    jornada.get("short"),
                    len(
                        jornada.get(
                            "games",
                            [],
                        )
                    ),
                )
                for jornada in jornadas
                if isinstance(jornada, dict)
            ],
        )

        return jornadas

    except Exception as exc:

        logger.exception(
            "Error obteniendo jornadas: %s",
            exc,
        )

        return []


def obtener_jornada(
    jornada_id,
):
    """
    Obtiene una única jornada concreta directamente desde Biwenger.

    Usa:
        GET /rounds/la-liga/{jornada_id}
    """

    try:
        jornada_id = int(
            jornada_id
        )

    except (
        TypeError,
        ValueError,
    ):
        logger.warning(
            "ID de jornada inválido: %r",
            jornada_id,
        )
        return None

    try:
        response = _CLIENT.public_session.get(
            f"{ROUNDS_URL}/{jornada_id}",
            params={
                "score": 2,
                "lang": "es",
                "v": 631,
            },
            timeout=15,
        )

        if response.status_code == 404:
            logger.info(
                "Jornada ID %s no existe.",
                jornada_id,
            )
            return None

        response.raise_for_status()

        data = response.json()

    except Exception as exc:
        logger.exception(
            "Error obteniendo jornada ID %s: %s",
            jornada_id,
            exc,
        )
        return None

    if not isinstance(
        data,
        dict,
    ):
        return None

    root = data.get(
        "data",
        data,
    )

    if not isinstance(
        root,
        dict,
    ):
        return None

    short = root.get(
        "short"
    )

    name = root.get(
        "name"
    )

    if short is None:
        short = data.get(
            "short"
        )

    if name is None:
        name = data.get(
            "name"
        )

    if not short:
        logger.warning(
            "Jornada ID %s sin short. Keys=%s",
            jornada_id,
            list(root.keys()),
        )
        return None

    short = str(
        short
    ).strip()

    if name is None:
        name = f"Jornada {short}"

    name = str(
        name
    ).strip()

    games = root.get(
        "games",
        [],
    )

    if not isinstance(
        games,
        list,
    ):
        games = []

    jornada = {
        "id": root.get(
            "id",
            jornada_id,
        ),
        "short": short,
        "name": name,
        "games": games,
        "data": data,
    }

    logger.info(
        "Jornada obtenida directamente: id=%s short=%s games=%s",
        jornada["id"],
        jornada["short"],
        len(jornada["games"]),
    )

    return jornada


def _timestamp_partido(
    partido,
):
    """
    Intenta obtener el timestamp del comienzo
    de un partido.
    """

    if not isinstance(
        partido,
        dict,
    ):
        return None

    for clave in (
        "date",
        "start",
        "startDate",
        "timestamp",
    ):

        valor = partido.get(
            clave
        )

        if isinstance(
            valor,
            (int, float),
        ):
            return float(
                valor
            )

        if isinstance(
            valor,
            str,
        ):

            try:

                return datetime.fromisoformat(
                    valor.replace(
                        "Z",
                        "+00:00",
                    )
                ).timestamp()

            except (
                TypeError,
                ValueError,
            ):
                continue

    return None

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

def _extraer_mapa_propietarios(
    liga_id,
    forzar=False,
):
    """
    Construye un mapa:

        player_id -> nombre del propietario

    usando las plantillas reales de los usuarios
    de la liga.
    """

    cache_key = f"propietarios:{liga_id}"

    cache = getattr(
        _extraer_mapa_propietarios,
        "_cache",
        {},
    )

    if (
        not forzar
        and cache_key in cache
    ):
        return cache[cache_key]

    propietarios = {}

    try:
        league_response = _CLIENT.league(
            liga_id
        )

        standings = _extraer_standings(
            league_response
        )

    except Exception as exc:

        logger.exception(
            "No se pudieron obtener "
            "los usuarios de la liga %s: %s",
            liga_id,
            exc,
        )

        return propietarios

    for miembro in standings:

        datos = _datos_standing(
            miembro
        )

        user_id = datos.get(
            "id"
        )

        nombre_usuario = datos.get(
            "nombre",
            "Desconocido",
        )

        if user_id is None:
            continue

        try:

            respuesta_usuario = (
                _CLIENT.user_team(
                    user_id
                )
            )

        except Exception as exc:

            logger.warning(
                "No se pudo obtener la plantilla "
                "de %s (%s): %s",
                nombre_usuario,
                user_id,
                exc,
            )

            continue

        if not isinstance(
            respuesta_usuario,
            dict,
        ):
            continue

        data_usuario = respuesta_usuario.get(
            "data",
            {}
        )

        if not isinstance(
            data_usuario,
            dict,
        ):
            continue

        jugadores_usuario = data_usuario.get(
            "players",
            []
        )

        if not isinstance(
            jugadores_usuario,
            list,
        ):
            continue

        for jugador_usuario in jugadores_usuario:

            if not isinstance(
                jugador_usuario,
                dict,
            ):
                continue

            player_id = jugador_usuario.get(
                "id"
            )

            if player_id is None:
                continue

            try:

                player_id = int(
                    player_id
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            propietario = (
                jugador_usuario.get(
                    "owner"
                )
            )

            if isinstance(
                propietario,
                dict,
            ):

                propietario = (
                    propietario.get("name")
                    or propietario.get("username")
                    or nombre_usuario
                )

            if not isinstance(
                propietario,
                str,
            ) or not propietario.strip():

                propietario = nombre_usuario

            propietarios[player_id] = (
                propietario.strip()
            )

    cache[cache_key] = propietarios

    _extraer_mapa_propietarios._cache = cache

    logger.info(
        "Mapa de propietarios cargado: %s jugadores",
        len(propietarios),
    )

    return propietarios

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
    propietarios=None,
):
    """
    Obtiene el propietario de un jugador.

    Primero intenta encontrarlo en el propio objeto
    del jugador y después utiliza el mapa de propietarios
    de la liga.
    """

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

    if propietarios:

        player_id = jugador.get(
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

            propietario = propietarios.get(
                player_id
            )

            if (
                isinstance(
                    propietario,
                    str,
                )
                and propietario.strip()
            ):
                return propietario.strip()

    return "No disponible"


def _numero_jornada(
    jornada,
):
    """
    Extrae el número de jornada desde valores como:
        J1
        J2
        Jornada 3
    """

    if not isinstance(
        jornada,
        dict,
    ):
        return None

    for valor in (
        jornada.get("short"),
        jornada.get("name"),
    ):
        if valor is None:
            continue

        coincidencia = re.search(
            r"\d+",
            str(valor),
        )

        if coincidencia:
            try:
                return int(
                    coincidencia.group()
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

    return None


def _obtener_jornada_anterior(
    jornada_actual,
):
    """
    Obtiene la jornada inmediatamente anterior
    a la jornada actual.
    """

    numero_actual = _numero_jornada(
        jornada_actual
    )

    if (
        numero_actual is None
        or numero_actual <= 1
    ):
        return None

    jornadas = obtener_jornadas()

    if not isinstance(
        jornadas,
        list,
    ):
        return None

    numero_anterior = (
        numero_actual - 1
    )

    for jornada in jornadas:

        if not isinstance(
            jornada,
            dict,
        ):
            continue

        numero = _numero_jornada(
            jornada
        )

        if numero == numero_anterior:
            return jornada

    logger.warning(
        "No se encontró la jornada anterior: J%s",
        numero_anterior,
    )

    return None


def _extraer_ultimo_puntos(
    player_id,
    jornada_actual=None,
):
    """
    Obtiene los puntos del jugador en su último partido
    terminado disponible en el historial de jornadas.

    No depende de que la jornada actual sea consecutiva,
    por lo que funciona correctamente con jornadas aplazadas.
    """

    try:
        player_id = int(player_id)

    except (
        TypeError,
        ValueError,
    ):
        return 0

    jornadas = obtener_jornadas()

    if not isinstance(
        jornadas,
        list,
    ):
        return 0

    candidatos = []

    for jornada in jornadas:

        if not isinstance(
            jornada,
            dict,
        ):
            continue

        games = jornada.get(
            "games",
            []
        )

        if not isinstance(
            games,
            list,
        ):
            continue

        for partido in games:

            if not isinstance(
                partido,
                dict,
            ):
                continue

            estado = partido.get(
                "status"
            )

            if estado != "finished":
                continue

            fecha = partido.get(
                "date",
                0,
            )

            try:
                fecha = float(fecha)

            except (
                TypeError,
                ValueError,
            ):
                fecha = 0

            for lado in (
                "home",
                "away",
            ):

                equipo = partido.get(
                    lado
                )

                if not isinstance(
                    equipo,
                    dict,
                ):
                    continue

                reports = equipo.get(
                    "reports",
                    []
                )

                if not isinstance(
                    reports,
                    list,
                ):
                    continue

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

                    try:
                        report_player_id = int(
                            player.get("id")
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):
                        continue

                    if report_player_id != player_id:
                        continue

                    puntos = report.get(
                        "points"
                    )

                    if not isinstance(
                        puntos,
                        (int, float),
                    ):
                        continue

                    candidatos.append(
                        (
                            fecha,
                            puntos,
                        )
                    )

    if not candidatos:
        return 0

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidatos[0][1]

def _extraer_media_puntos(
    jugador,
    jornada_actual=None,
):
    """
    Calcula la media real de puntos Biwenger:

        puntos de la temporada / partidos jugados

    La información se obtiene de `seasons`, que contiene
    tanto los partidos jugados como los puntos acumulados
    para cada sistema de puntuación.

    No utiliza la jornada actual como divisor.
    No utiliza el precio ni scoreStats para calcular la media.
    """

    if not isinstance(
        jugador,
        dict,
    ):
        return 0

    temporadas = jugador.get(
        "seasons",
        []
    )

    if not isinstance(
        temporadas,
        list,
    ):
        return 0

    # -------------------------------------------------
    # Buscar la temporada actual
    # -------------------------------------------------

    temporada_actual = None

    for temporada in temporadas:

        if not isinstance(
            temporada,
            dict,
        ):
            continue

        if temporada.get(
            "selected"
        ) is True:

            temporada_actual = temporada
            break

    if temporada_actual is None:
        return 0

    # -------------------------------------------------
    # Partidos jugados
    # -------------------------------------------------

    try:
        partidos_jugados = int(
            temporada_actual.get(
                "games",
                0,
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        partidos_jugados = 0

    if partidos_jugados <= 0:
        return 0

    # -------------------------------------------------
    # Puntos de la temporada
    # -------------------------------------------------

    puntos = temporada_actual.get(
        "points",
        {}
    )

    if not isinstance(
        puntos,
        dict,
    ):
        return 0

    # -------------------------------------------------
    # Determinar el sistema de puntuación
    #
    # La ficha de jugador puede contener varios
    # sistemas de puntuación simultáneamente.
    #
    # Intentamos identificar primero el sistema
    # configurado en la liga.
    # -------------------------------------------------

    sistema_liga = None

    try:

        if _CLIENT is not None:

            # Dependiendo de la respuesta de la API,
            # el sistema puede estar disponible en
            # distintos lugares.

            league = getattr(
                _CLIENT,
                "league",
                None,
            )

            if isinstance(
                league,
                dict,
            ):

                sistema_liga = (
                    league.get(
                        "scoring"
                    )
                    or league.get(
                        "scoringSystem"
                    )
                    or league.get(
                        "scoreSystem"
                    )
                )

    except Exception:
        sistema_liga = None

    # -------------------------------------------------
    # Normalizar identificador del sistema
    # -------------------------------------------------

    if sistema_liga is not None:

        sistema_liga = str(
            sistema_liga
        ).strip()

    # -------------------------------------------------
    # Intentar utilizar el sistema de la liga
    # -------------------------------------------------

    if (
        sistema_liga
        and sistema_liga in puntos
    ):

        try:

            puntos_totales = float(
                puntos[
                    sistema_liga
                ]
            )

            return round(
                puntos_totales
                / partidos_jugados,
                2,
            )

        except (
            TypeError,
            ValueError,
            ZeroDivisionError,
        ):
            pass

    # -------------------------------------------------
    # Fallback:
    #
    # En la respuesta de Biwenger el sistema SofaScore
    # corresponde normalmente al identificador "7".
    #
    # Lo usamos antes de recurrir a cualquier otro
    # sistema porque es el que utiliza esta liga.
    # -------------------------------------------------

    for sistema in (
        "7",
        7,
    ):

        if sistema not in puntos:
            continue

        try:

            puntos_totales = float(
                puntos[
                    sistema
                ]
            )

            return round(
                puntos_totales
                / partidos_jugados,
                2,
            )

        except (
            TypeError,
            ValueError,
            ZeroDivisionError,
        ):
            continue

    # -------------------------------------------------
    # Último fallback
    #
    # Si Biwenger cambia el identificador del sistema,
    # utilizamos el primer valor numérico disponible.
    # -------------------------------------------------

    for valor in puntos.values():

        if not isinstance(
            valor,
            (int, float),
        ):
            continue

        try:

            puntos_totales = float(
                valor
            )

            return round(
                puntos_totales
                / partidos_jugados,
                2,
            )

        except (
            TypeError,
            ValueError,
            ZeroDivisionError,
        ):
            continue

    return 0

def _obtener_puntos_jornada(
    player_id,
    jornada,
):
    """
    Busca los puntos de un jugador dentro de los
    partidos de una jornada.

    Devuelve None si todavía no hay puntuación.
    """

    if not isinstance(
        jornada,
        dict,
    ):
        return None

    try:

        player_id = int(
            player_id
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    games = jornada.get(
        "games",
        []
    )

    if not isinstance(
        games,
        list,
    ):
        return None

    encontrados = []

    for partido in games:

        if not isinstance(
            partido,
            dict,
        ):
            continue

        for lado in (
            "home",
            "away",
        ):

            equipo = partido.get(
                lado
            )

            if not isinstance(
                equipo,
                dict,
            ):
                continue

            reports = equipo.get(
                "reports",
                []
            )

            if not isinstance(
                reports,
                list,
            ):
                continue

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

                try:

                    report_player_id = int(
                        player.get("id")
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    continue

                if report_player_id != player_id:
                    continue

                puntos = report.get(
                    "points"
                )

                if isinstance(
                    puntos,
                    (int, float),
                ):
                    encontrados.append(
                        puntos
                    )

    if not encontrados:
        return None

    return encontrados[-1]

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

    # -------------------------------------------------
    # Jornada actual
    # -------------------------------------------------

    jornada_actual = (
        obtener_jornada_actual()
    )

    # -------------------------------------------------
    # Propietarios reales de la liga
    # -------------------------------------------------

    propietarios = {}

    try:

        if _CLIENT.league_id is not None:

            propietarios = (
                _extraer_mapa_propietarios(
                    _CLIENT.league_id
                )
            )

    except Exception as exc:

        logger.warning(
            "No se pudo cargar el mapa "
            "de propietarios: %s",
            exc,
        )

    # -------------------------------------------------
    # Datos básicos
    # -------------------------------------------------

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

    # -------------------------------------------------
    # Precio
    # -------------------------------------------------

    precio = jugador.get(
        "price",
        0,
    )

    try:
        precio = int(
            precio
        )

    except (
        TypeError,
        ValueError,
    ):
        precio = 0

    incremento_precio = jugador.get(
        "priceIncrement",
        0,
    )

    try:
        incremento_precio = int(
            incremento_precio
        )

    except (
        TypeError,
        ValueError,
    ):
        incremento_precio = 0

    # -------------------------------------------------
    # Puntos
    # -------------------------------------------------

    puntos = jugador.get(
        "points",
        0,
    )

    try:
        puntos = float(
            puntos
        )

    except (
        TypeError,
        ValueError,
    ):
        puntos = 0

    # Si es un número entero, no mostrar .0
    if puntos.is_integer():
        puntos = int(
            puntos
        )

    ultimo_puntos = _extraer_ultimo_puntos(
        player_id,
        jornada_actual,
    )

    # -------------------------------------------------
    # Media
    #
    # La media debe basarse en los partidos realmente
    # jugados, no en la jornada actual.
    #
    # Primero intentamos obtener los partidos jugados
    # de la temporada actual desde scoreStats.
    # -------------------------------------------------

    media_puntos = 0

    score_stats = jugador.get(
        "scoreStats",
        {}
    )

    if isinstance(
        score_stats,
        dict,
    ):

        puntos_por_sistema = []

        for datos_sistema in score_stats.values():

            if not isinstance(
                datos_sistema,
                dict,
            ):
                continue

            valor = datos_sistema.get(
                "points"
            )

            if isinstance(
                valor,
                (int, float),
            ):
                puntos_por_sistema.append(
                    float(valor)
                )

        if puntos_por_sistema:

            # Biwenger devuelve los puntos acumulados
            # por cada sistema de puntuación.
            #
            # El sistema de la liga se obtiene de
            # la puntuación disponible para el jugador.
            #
            # Si hay datos de la temporada seleccionada,
            # usamos el primero disponible.
            puntos_sistema = (
                puntos_por_sistema[0]
            )

            temporadas = jugador.get(
                "seasons",
                []
            )

            partidos_jugados = 0

            if isinstance(
                temporadas,
                list,
            ):

                for temporada in temporadas:

                    if not isinstance(
                        temporada,
                        dict,
                    ):
                        continue

                    if temporada.get(
                        "selected"
                    ) is True:

                        try:
                            partidos_jugados = int(
                                temporada.get(
                                    "games",
                                    0,
                                )
                            )

                        except (
                            TypeError,
                            ValueError,
                        ):
                            partidos_jugados = 0

                        # Los puntos de la temporada
                        # seleccionada son más fiables
                        # para calcular la media.
                        puntos_temporada = temporada.get(
                            "points"
                        )

                        if isinstance(
                            puntos_temporada,
                            dict,
                        ):

                            puntos_temporada_validos = [
                                valor
                                for valor in puntos_temporada.values()
                                if isinstance(
                                    valor,
                                    (int, float),
                                )
                            ]

                            if puntos_temporada_validos:

                                puntos_sistema = float(
                                    puntos_temporada_validos[0]
                                )

                        break

            if partidos_jugados > 0:

                media_puntos = round(
                    puntos_sistema
                    / partidos_jugados,
                    2,
                )

    # -------------------------------------------------
    # Propietario
    # -------------------------------------------------

    propietario = _extraer_propietario(
        jugador,
        propietarios,
    )

    if propietario == "No disponible":
        propietario = None

    # -------------------------------------------------
    # Próximos partidos
    # -------------------------------------------------

    proximo_partido = []

    equipo = jugador.get(
        "team",
        {}
    )

    if isinstance(
        equipo,
        dict,
    ):

        proximo_partido = equipo.get(
            "nextGames",
            []
        )

        if not isinstance(
            proximo_partido,
            list,
        ):
            proximo_partido = []

    # -------------------------------------------------
    # Estado
    # -------------------------------------------------

    estado = jugador.get(
        "status"
    )

    if (
        not isinstance(
            estado,
            str,
        )
        or not estado.strip()
    ):
        estado = "ok"

    else:
        estado = estado.strip().lower()

    # -------------------------------------------------
    # Probable titular / disponible
    #
    # probableIn contiene los IDs de los partidos en
    # los que Biwenger considera que el jugador puede
    # aparecer.
    # -------------------------------------------------

    probable_en = jugador.get(
        "probableIn",
        []
    )

    if not isinstance(
        probable_en,
        list,
    ):
        probable_en = []

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

        "incremento_precio": incremento_precio,

        "puntos": puntos,

        "puntos_ultima_jornada": ultimo_puntos,

        "media_puntos": media_puntos,

        "partidos_jugados": (
            next(
                (
                    int(
                        temporada.get(
                            "games",
                            0,
                        )
                    )
                    for temporada in jugador.get(
                        "seasons",
                        []
                    )
                    if isinstance(
                        temporada,
                        dict,
                    )
                    and temporada.get(
                        "selected"
                    ) is True
                ),
                0,
            )
            if isinstance(
                jugador.get(
                    "seasons",
                    []
                ),
                list,
            )
            else 0
        ),

        "propietario": propietario,

        "estado": estado,

        "probable_en": probable_en,

        "proximo_partido": proximo_partido,

        "score_stats": jugador.get(
            "scoreStats",
            {}
        ),

        "temporadas": jugador.get(
            "seasons",
            []
        ),

        "precios": jugador.get(
            "prices",
            []
        ),

        "noticias": jugador.get(
            "news",
            []
        ),

        "hilos": jugador.get(
            "threads",
            []
        ),

        "reportes": jugador.get(
            "reports",
            []
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
    premios=0,
):
    return (
        SALDO_INICIAL
        + ventas
        - compras
        + premios
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

    logger.warning(
        "DEBUG LEAGUE KEYS: %s",
        (
            list(league_response.keys())
            if isinstance(
                league_response,
                dict,
            )
            else type(league_response).__name__
        ),
    )

    if isinstance(
        league_response,
        dict,
    ):
        logger.warning(
            "DEBUG LEAGUE DATA: %r",
            league_response.get(
                "data"
            ),
        )

    standings = _extraer_standings(
        league_response
    )


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

    # -------------------------------------------------
    # Premios acumulados de jornadas terminadas
    # -------------------------------------------------

    try:

        premios = (
            _CLIENT.get_round_rewards(
                liga_id
            )
        )

    except Exception as exc:

        logger.warning(
            "No se pudieron obtener "
            "los premios de jornadas: %s",
            exc,
        )

        premios = {}

    resultado = {}

    for miembro in standings:

        datos_standing = _datos_standing(
            miembro
        )

        nombre = datos_standing[
            "nombre"
        ]

        user_id = datos_standing[
            "id"
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

        # -------------------------------------------------
        # Premio acumulado del usuario
        #
        # Los premios vienen indexados por ID de usuario.
        # -------------------------------------------------

        try:

            user_id_int = int(
                user_id
            )

        except (
            TypeError,
            ValueError,
        ):

            user_id_int = None

        premios_usuario = (
            premios.get(
                user_id_int,
                0,
            )
            if user_id_int is not None
            else 0
        )

        # -------------------------------------------------
        # Saldo actual
        #
        # Saldo inicial
        # + ventas
        # - compras
        # + premios
        # -------------------------------------------------

        saldo_actual = (
            _calcular_saldo_actual(
                compras,
                ventas,
                premios_usuario,
            )
        )

        puja_maxima = (
            _calcular_puja_maxima(
                saldo_actual,
                valor_equipo,
            )
        )

        resultado[nombre] = {
            "user_id": user_id,
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
            "premios": (
                premios_usuario
            ),
            "saldo_actual": (
                saldo_actual
            ),
            "puja_maxima": (
                puja_maxima
            ),
        }

    # -------------------------------------------------
    # Usuarios que aparecen en movimientos pero no
    # están actualmente en standings
    # -------------------------------------------------

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

        premios_usuario = datos.get(
            "premios",
            0,
        )

        saldo_actual = (
            _calcular_saldo_actual(
                compras,
                ventas,
                premios_usuario,
            )
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
            "premios": premios_usuario,
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
    ofertas_market=None,
):
    """
    Obtiene las ofertas recibidas para una venta.

    Biwenger puede devolver las ofertas:
    - dentro de la propia venta
    - o en el campo global "offers" de /market
    """

    if not isinstance(
        sale,
        dict,
    ):
        return []

    # ---------------------------------
    # 1. Ofertas dentro de la propia venta
    # ---------------------------------

    candidatos = (
        "offers",
        "bids",
        "offersReceived",
        "bidsReceived",
    )

    for key in candidatos:

        valor = sale.get(
            key
        )

        if isinstance(
            valor,
            list,
        ):
            return valor

        if isinstance(
            valor,
            dict,
        ):

            for subkey in (
                "data",
                "items",
                "results",
                "offers",
                "bids",
            ):

                subvalor = valor.get(
                    subkey
                )

                if isinstance(
                    subvalor,
                    list,
                ):
                    return subvalor

    # ---------------------------------
    # 2. Player ID de la venta
    # ---------------------------------

    player_id = _extraer_player_id_venta(
        sale
    )

    if player_id is None:
        return []

    # ---------------------------------
    # 3. Ofertas globales de /market
    # ---------------------------------

    if not isinstance(
        ofertas_market,
        list,
    ):
        return []

    ofertas_encontradas = []

    for oferta in ofertas_market:

        if not isinstance(
            oferta,
            dict,
        ):
            continue

        # Solo nos interesan ofertas de compra
        if oferta.get(
            "type"
        ) != "purchase":
            continue

        # Solo ofertas pendientes
        if oferta.get(
            "status"
        ) != "waiting":
            continue

        requested_players = (
            oferta.get(
                "requestedPlayers",
                [],
            )
        )

        if not isinstance(
            requested_players,
            list,
        ):
            continue

        jugadores_solicitados = []

        for requested_player in (
            requested_players
        ):

            try:

                jugadores_solicitados.append(
                    int(
                        requested_player
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

        if player_id not in (
            jugadores_solicitados
        ):
            continue

        ofertas_encontradas.append(
            oferta
        )

    return ofertas_encontradas


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


def _extraer_precio_compra_jugador(
    player_id,
    user_id,
    historial,
):
    """
    Busca la última compra conocida del jugador
    realizada por el usuario.

    Devuelve:
        - importe de compra si existe
        - None si no existe una compra registrada
    """

    if not isinstance(
        historial,
        dict,
    ):
        return None

    eventos = historial.get(
        "data",
        [],
    )

    if not isinstance(
        eventos,
        list,
    ):
        return None

    try:
        player_id = int(
            player_id
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    try:
        user_id = int(
            user_id
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    operaciones = []

    for event in eventos:

        if not isinstance(
            event,
            dict,
        ):
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

        event_date = event.get(
            "date",
            0,
        )

        for operation in content:

            if not isinstance(
                operation,
                dict,
            ):
                continue

            operation_player = (
                operation.get(
                    "player"
                )
            )

            try:
                operation_player = int(
                    operation_player
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                operation_player
                != player_id
            ):
                continue

            comprador = operation.get(
                "to"
            )

            if not isinstance(
                comprador,
                dict,
            ):
                continue

            comprador_id = (
                comprador.get(
                    "id"
                )
            )

            try:
                comprador_id = int(
                    comprador_id
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                comprador_id
                != user_id
            ):
                continue

            importe = operation.get(
                "amount"
            )

            try:
                importe = float(
                    importe
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            operaciones.append(
                (
                    event_date,
                    importe,
                )
            )

    if not operaciones:
        return None

    operaciones.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return operaciones[0][1]


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

    ofertas_market = []

    if isinstance(
        response,
        dict,
    ):
        response_data = response.get(
            "data",
            {},
        )

        if isinstance(
            response_data,
            dict,
        ):
            ofertas_market = response_data.get(
                "offers",
                [],
            )

        if not isinstance(
            ofertas_market,
            list,
        ):
            ofertas_market = []

    logger.info(
        "Mercado: ventas=%s ofertas=%s",
        len(sales),
        len(ofertas_market),
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

    historial = None

    try:
        historial = (
            _CLIENT.get_full_market_history(
                liga_id
            )
        )
    except Exception as exc:
        logger.warning(
            "No se pudo cargar el historial "
            "para calcular precios de compra: %s",
            exc,
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

        precio_compra = None

        if es_mia:

            precio_compra = (
                _extraer_precio_compra_jugador(
                    player_id,
                    mi_user_id,
                    historial,
                )
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
        	sale,
        	ofertas_market,
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
            "purchase_price": precio_compra,
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
