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


# ============================================================
# CLIENTE BIWENGER
# ============================================================

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

    # ========================================================
    # CONTEXTO DE LIGA
    # ========================================================

    def set_context(self, league_id=None, user_id=None):
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

        logger.info(
            "CONTEXTO FIJADO -> league_id=%r user_id=%r",
            self.league_id,
            self.user_id,
        )

    def clear_context(self):
        self.league_id = None
        self.user_id = None

    # ========================================================
    # LOGIN
    # ========================================================

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

    # ========================================================
    # PETICIÓN GENÉRICA
    # ========================================================

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

        logger.info(
            "GET %s | X-League=%r X-User=%r params=%r",
            endpoint,
            headers.get("X-League"),
            headers.get("X-User"),
            params,
        )

        response = self.session.get(
            BASE_URL + endpoint,
            headers=headers,
            params=params,
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        # Diagnóstico seguro.
        if isinstance(data, dict):
            logger.info(
                "RESPUESTA %s -> keys=%s data_type=%s data_len=%s",
                endpoint,
                list(data.keys()),
                type(data.get("data")).__name__,
                (
                    len(data.get("data", []))
                    if isinstance(
                        data.get("data"),
                        (list, dict),
                    )
                    else "n/a"
                ),
            )

        return data

    # ========================================================
    # CUENTA / LIGAS
    # ========================================================

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

        logger.info(
            "LIGAS EN ACCOUNT: %r",
            [
                {
                    "id": liga.get("id"),
                    "name": liga.get("name"),
                    "user": liga.get("user"),
                }
                for liga in leagues
                if isinstance(liga, dict)
            ],
        )

        return leagues

    def find_league_user(self, league_id):
        target = str(league_id)

        for liga in self.leagues():

            if not isinstance(liga, dict):
                continue

            if str(liga.get("id")) != target:
                continue

            usuario = liga.get("user")

            # Caso normal:
            # user = {"id": ..., "name": ...}
            if isinstance(usuario, dict):
                uid = usuario.get("id")

                if uid is not None:
                    return int(uid)

            # Compatibilidad:
            # user = 123456
            if isinstance(
                usuario,
                (int, str),
            ) and str(usuario).isdigit():
                return int(usuario)

            # Otras posibles claves.
            for key in (
                "userId",
                "user_id",
            ):
                uid = liga.get(key)

                if uid is not None:
                    return int(uid)

            logger.warning(
                "Liga %r encontrada pero no se pudo "
                "extraer user_id. Registro=%r",
                league_id,
                liga,
            )

            return None

        logger.warning(
            "No se encontró league_id=%r en /account",
            league_id,
        )

        return None

    # ========================================================
    # PREPARAR CONTEXTO
    # ========================================================

    def prepare_context(self, league_id):

        # IMPORTANTE:
        # Cada cambio de liga empieza limpiando
        # completamente el contexto anterior.
        self.clear_context()

        league_id = int(league_id)

        user_id = self.find_league_user(
            league_id
        )

        if user_id is None:
            raise ValueError(
                f"No se encontró usuario para liga "
                f"{league_id}"
            )

        self.set_context(
            league_id,
            user_id,
        )

        return {
            "league_id": self.league_id,
            "user_id": self.user_id,
        }

    # ========================================================
    # DATOS DE LA LIGA
    # ========================================================

    def league(self, league_id):
        self.prepare_context(league_id)

        return self.get(
            f"/league/{self.league_id}"
        )

    def board(self, league_id):
        self.prepare_context(league_id)

        return self.get(
            f"/league/{self.league_id}/board"
        )

    def league_players(self, league_id):
        self.prepare_context(league_id)

        return self.get(
            f"/league/{self.league_id}",
            params={
                "fields": "users(players)"
            },
        )

    # ========================================================
    # JUGADORES
    # ========================================================

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

        return response.json()

    # ========================================================
    # HISTORIAL DEL BOARD
    # ========================================================

    def board_history(
        self,
        league_id,
        date=None,
        limit=100,
    ):
        self.prepare_context(league_id)

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

    # ========================================================
    # HISTORIAL COMPLETO
    # ========================================================

    def get_full_market_history(
        self,
        league_id,
        limit=100,
        max_pages=100,
    ):
        all_events = []

        current_date = None
        seen = set()

        for page in range(max_pages):

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

                if isinstance(
                    event.get("date"),
                    (int, float),
                ):
                    fechas.append(
                        event["date"]
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
            key=lambda x: x.get("date", 0),
            reverse=True,
        )

        logger.info(
            "HISTORIAL COMPLETO -> liga=%s eventos=%s",
            league_id,
            len(all_events),
        )

        return {
            "status": 200,
            "data": all_events,
        }

    # ========================================================
    # HISTORIAL ÚLTIMAS 24 HORAS
    # ========================================================

    def get_market_history_last_24h(
        self,
        league_id,
        limit=100,
        max_pages=20,
    ):
        ahora = time.time()
        desde = ahora - 24 * 60 * 60

        all_events = []

        current_date = None
        seen = set()

        for page in range(max_pages):

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

                event_date = event.get("date")

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
                fechas.append(event_date)

                if event_date >= desde:
                    all_events.append(event)

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
            key=lambda x: x.get("date", 0),
            reverse=True,
        )

        logger.info(
            "HISTORIAL 24H -> liga=%s eventos=%s",
            league_id,
            len(all_events),
        )

        return {
            "status": 200,
            "data": all_events,
        }

    # ========================================================
    # EXTRAER OPERACIONES
    # ========================================================

    def extract_operations(self, history):

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

                operations.append(operation)

        return operations

    # ========================================================
    # INFORME DE MERCADO
    # ========================================================

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

            buyer = operation.get("to")
            seller = operation.get("from")
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

    # ========================================================
    # INFORME FINAL
    # ========================================================

    def build_final_report(
        self,
        report,
    ):
        resultado = {}

        for manager, datos in report.items():

            compras = datos.get(
                "total_compras",
                0,
            )

            ventas = datos.get(
                "total_ventas",
                0,
            )

            resultado[manager] = {
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
                "saldo_actual": (
                    SALDO_INICIAL
                    + ventas
                    - compras
                ),
            }

        return resultado


# ============================================================
# CLIENTE GLOBAL
# ============================================================

_CLIENT = Bi