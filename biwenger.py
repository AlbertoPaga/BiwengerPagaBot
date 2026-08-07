import requests
import time
from collections import defaultdict
from datetime import datetime, timezone

from config import (
    BIWENGER_USERNAME,
    BIWENGER_PASSWORD,
)


BASE_URL = "https://biwenger.as.com/api/v2"

PLAYERS_URL = (
    "https://cf.biwenger.com/api/v2/"
    "competitions/la-liga/data"
)


class BiwengerClient:

    def __init__(self):

        self.session = requests.Session()

        self.public_session = requests.Session()

        self.public_session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            }
        )

        self.token = None
        self.league_id = None
        self.user_id = None
        self.login_time = 0

    # ==============================================================
    # CONTEXTO
    # ==============================================================

    def set_context(
        self,
        league_id=None,
        user_id=None,
    ):

        if league_id is not None:
            self.league_id = league_id

        if user_id is not None:
            self.user_id = user_id

    # ==============================================================
    # LOGIN
    # ==============================================================

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

        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
        )

        return data

    # ==============================================================
    # GET API PRIVADA
    # ==============================================================

    def get(
        self,
        endpoint,
        params=None,
    ):

        self.login()

        headers = {}

        if self.league_id is not None:
            headers["X-League"] = str(self.league_id)

        if self.user_id is not None:
            headers["X-User"] = str(self.user_id)

        response = self.session.get(
            BASE_URL + endpoint,
            headers=headers,
            params=params,
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    # ==============================================================
    # CUENTA
    # ==============================================================

    def account(self):

        return self.get("/account")

    # ==============================================================
    # LIGAS
    # ==============================================================

    def leagues(self):

        data = self.account()

        return data["data"]["leagues"]

    # ==============================================================
    # BUSCAR USUARIO DE UNA LIGA
    # ==============================================================

    def find_league_user(
        self,
        league_id,
    ):

        leagues = self.leagues()

        for liga in leagues:

            if liga["id"] == league_id:
                return liga["user"]["id"]

        return None

    # ==============================================================
    # INFORMACIÓN DE LIGA
    # ==============================================================

    def league(
        self,
        league_id,
    ):

        user_id = self.find_league_user(
            league_id
        )

        if user_id is None:

            raise ValueError(
                f"No se encontró el usuario "
                f"para la liga {league_id}"
            )

        self.set_context(
            league_id,
            user_id,
        )

        return self.get(
            f"/league/{league_id}"
        )

    # ==============================================================
    # BOARD ACTUAL
    # ==============================================================

    def board(
        self,
        league_id,
    ):

        user_id = self.find_league_user(
            league_id
        )

        if user_id is None:

            raise ValueError(
                f"No se encontró el usuario "
                f"para la liga {league_id}"
            )

        self.set_context(
            league_id,
            user_id,
        )

        return self.get(
            f"/league/{league_id}/board"
        )

    # ==============================================================
    # PLANTILLAS
    # ==============================================================

    def league_players(
        self,
        league_id,
    ):

        user_id = self.find_league_user(
            league_id
        )

        if user_id is None:

            raise ValueError(
                f"No se encontró el usuario "
                f"para la liga {league_id}"
            )

        self.set_context(
            league_id,
            user_id,
        )

        self.login()

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "X-League": str(self.league_id),
            "X-User": str(self.user_id),
        }

        response = self.session.get(
            f"{BASE_URL}/league/{league_id}",
            headers=headers,
            params={
                "fields": "users(players)"
            },
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    # ==============================================================
    # JUGADORES PÚBLICOS
    # ==============================================================

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

    # ==============================================================
    # HISTORIAL
    # ==============================================================

    def board_history(
        self,
        league_id,
        date=None,
        limit=100,
    ):

        user_id = self.find_league_user(
            league_id
        )

        if user_id is None:

            raise ValueError(
                f"No se encontró el usuario "
                f"para la liga {league_id}"
            )

        self.set_context(
            league_id,
            user_id,
        )

        self.login()

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "X-League": str(self.league_id),
            "X-User": str(self.user_id),
        }

        params = {
            "type": "transfer,market",
            "limit": limit,
        }

        if date is not None:
            params["date"] = date

        response = self.session.get(
            f"{BASE_URL}/league/{league_id}/board",
            headers=headers,
            params=params,
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    # ==============================================================
    # HISTORIAL COMPLETO
    # ==============================================================

    def get_full_market_history(
        self,
        league_id,
        limit=100,
        max_pages=100,
    ):

        all_events = []

        current_date = None
        seen_events = set()

        for _ in range(max_pages):

            response = self.board_history(
                league_id=league_id,
                date=current_date,
                limit=limit,
            )

            if not isinstance(response, dict):
                break

            data = response.get("data")

            if not isinstance(data, list):
                break

            if not data:
                break

            new_events = []

            for event in data:

                if not isinstance(event, dict):
                    continue

                event_date = event.get("date")

                # Usamos también tipo y contenido como parte
                # de la identificación para evitar perder eventos.
                event_key = (
                    event_date,
                    event.get("type"),
                    event.get("title"),
                    str(event.get("content", "")),
                )

                if event_key in seen_events:
                    continue

                seen_events.add(event_key)

                new_events.append(event)

            if not new_events:
                break

            all_events.extend(new_events)

            dates = [
                event.get("date")
                for event in data
                if isinstance(
                    event.get("date"),
                    (int, float),
                )
            ]

            if not dates:
                break

            oldest_date = min(dates)

            if current_date is not None:
                if oldest_date >= current_date:
                    break

            current_date = oldest_date - 1

            if len(data) < limit:
                break

        all_events.sort(
            key=lambda x: x.get("date", 0),
            reverse=True,
        )

        return {
            "status": 200,
            "data": all_events,
        }

    # ==============================================================
    # EXTRAER OPERACIONES INDIVIDUALES
    # ==============================================================

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

        if not isinstance(events, list):
            return operations

        for event in events:

            if not isinstance(event, dict):
                continue

            event_date = event.get("date")
            event_type = event.get("type")
            event_title = event.get("title", "")
            event_fixed = event.get("fixed", False)

            content = event.get(
                "content",
                [],
            )

            if not isinstance(content, list):
                continue

            for item in content:

                if not isinstance(item, dict):
                    continue

                operation = dict(item)

                operation["_event_date"] = event_date
                operation["_event_type"] = event_type
                operation["_event_title"] = event_title
                operation["_event_fixed"] = event_fixed

                operations.append(operation)

        return operations

    # ==============================================================
    # INFORME DE MERCADO
    # ==============================================================

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

            player_id = operation.get(
                "player"
            )

            buyer = operation.get("to")
            seller = operation.get("from")

            # ------------------------------------------------------
            # COMPRA
            # ------------------------------------------------------

            if isinstance(buyer, dict):

                buyer_name = buyer.get(
                    "name",
                    "Desconocido",
                )

                buyer_id = buyer.get("id")

                report[buyer_name]["compras"].append(
                    {
                        "player_id": player_id,
                        "amount": amount,
                        "date": operation.get(
                            "_event_date"
                        ),
                        "user_id": buyer_id,
                    }
                )

                report[buyer_name][
                    "total_compras"
                ] += amount

                report[buyer_name][
                    "numero_compras"
                ] += 1

            # ------------------------------------------------------
            # VENTA
            # ------------------------------------------------------

            if isinstance(seller, dict):

                seller_name = seller.get(
                    "name",
                    "Desconocido",
                )

                seller_id = seller.get("id")

                report[seller_name]["ventas"].append(
                    {
                        "player_id": player_id,
                        "amount": amount,
                        "date": operation.get(
                            "_event_date"
                        ),
                        "user_id": seller_id,
                    }
                )

                report[seller_name][
                    "total_ventas"
                ] += amount

                report[seller_name][
                    "numero_ventas"
                ] += 1

        final_report = {}

        for manager, data in report.items():

            total_compras = data[
                "total_compras"
            ]

            total_ventas = data[
                "total_ventas"
            ]

            final_report[manager] = {
                "compras": data["compras"],
                "ventas": data["ventas"],
                "total_compras": total_compras,
                "total_ventas": total_ventas,
                "numero_compras": data[
                    "numero_compras"
                ],
                "numero_ventas": data[
                    "numero_ventas"
                ],
                "balance": (
                    total_ventas
                    - total_compras
                ),
            }

        return final_report

    # ==============================================================
    # RESUMEN GENERAL
    # ==============================================================

    def market_report_summary(
        self,
        history,
    ):

        report = self.calculate_market_report(
            history
        )

        if not report:

            return {
                "managers": {},
                "total_compras": 0,
                "total_ventas": 0,
                "balance_total": 0,
                "mayor_gasto": None,
                "mayor_ingreso": None,
                "mejor_balance": None,
                "peor_balance": None,
            }

        total_compras = sum(
            manager["total_compras"]
            for manager in report.values()
        )

        total_ventas = sum(
            manager["total_ventas"]
            for manager in report.values()
        )

        mayor_gasto = max(
            report.items(),
            key=lambda item:
                item[1]["total_compras"],
        )

        mayor_ingreso = max(
            report.items(),
            key=lambda item:
                item[1]["total_ventas"],
        )

        mejor_balance = max(
            report.items(),
            key=lambda item:
                item[1]["balance"],
        )

        peor_balance = min(
            report.items(),
            key=lambda item:
                item[1]["balance"],
        )

        return {
            "managers": report,

            "total_compras":
                total_compras,

            "total_ventas":
                total_ventas,

            "balance_total":
                total_ventas - total_compras,

            "mayor_gasto": {
                "manager": mayor_gasto[0],
                "amount": mayor_gasto[1][
                    "total_compras"
                ],
            },

            "mayor_ingreso": {
                "manager": mayor_ingreso[0],
                "amount": mayor_ingreso[1][
                    "total_ventas"
                ],
            },

            "mejor_balance": {
                "manager": mejor_balance[0],
                "amount": mejor_balance[1][
                    "balance"
                ],
            },

            "peor_balance": {
                "manager": peor_balance[0],
                "amount": peor_balance[1][
                    "balance"
                ],
            },
        }


# ==============================================================
# CLIENTE GLOBAL
# ==============================================================

_CLIENT = BiwengerClient()


# ==============================================================
# FUNCIONES DE COMPATIBILIDAD CON BOT
# ==============================================================

def obtener_ligas():

    return _CLIENT.leagues()


def _extraer_mapa_jugadores():

    try:
        respuesta = _CLIENT.players()
    except Exception:
        return {}

    mapa = {}

    def recorrer(obj):

        if isinstance(obj, dict):

            player_id = obj.get("id")
            nombre = obj.get("name")

            if (
                isinstance(player_id, int)
                and isinstance(nombre, str)
                and nombre.strip()
            ):

                if any(
                    clave in obj
                    for clave in (
                        "team",
                        "position",
                        "positions",
                        "price",
                        "points",
                        "status",
                    )
                ):

                    mapa[player_id] = nombre.strip()

            for valor in obj.values():
                recorrer(valor)

        elif isinstance(obj, list):

            for valor in obj:
                recorrer(valor)

    recorrer(respuesta)

    return mapa


def _formatear_fecha(timestamp):

    try:

        return datetime.fromtimestamp(
            float(timestamp),
            tz=timezone.utc,
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception:

        return str(timestamp)


def _formatear_importe(amount):

    try:
        return f"{int(amount):,}€"
    except Exception:
        return "0€"


def _formatear_movimiento(
    operation,
    jugadores,
):

    fecha = _formatear_fecha(
        operation.get("_event_date")
    )

    player_id = operation.get("player")

    jugador = jugadores.get(
        player_id,
        f"Jugador {player_id}",
    )

    amount = operation.get(
        "amount",
        0,
    )

    buyer = operation.get("to")
    seller = operation.get("from")

    if isinstance(buyer, dict):

        nombre = buyer.get(
            "name",
            "Desconocido",
        )

        return (
            f"🟢 {fecha} | "
            f"{nombre} ficha a {jugador} "
            f"por {_formatear_importe(amount)}"
        )

    if isinstance(seller, dict):

        nombre = seller.get(
            "name",
            "Desconocido",
        )

        return (
            f"🔴 {fecha} | "
            f"{nombre} vende a {jugador} "
            f"por {_formatear_importe(amount)}"
        )

    return None


# ==============================================================
# CARGAR LIGA
# ==============================================================

def cargar_liga(
    liga_id,
):

    respuesta_liga = _CLIENT.league(
        liga_id
    )

    if not isinstance(
        respuesta_liga,
        dict,
    ):

        raise ValueError(
            "Respuesta inválida al obtener la liga"
        )

    data_liga = respuesta_liga.get(
        "data",
        {},
    )

    if not isinstance(
        data_liga,
        dict,
    ):

        data_liga = {}

    usuarios = data_liga.get(
        "users",
        [],
    )

    if not isinstance(
        usuarios,
        list,
    ):

        usuarios = []

    history = _CLIENT.get_full_market_history(
        liga_id,
        limit=100,
        max_pages=100,
    )

    operations = _CLIENT.extract_operations(
        history
    )

    jugadores = _extraer_mapa_jugadores()

    operaciones_ordenadas = sorted(
        operations,
        key=lambda op: (
            float(
                op.get(
                    "_event_date",
                    0,
                )
            )
            if isinstance(
                op.get("_event_date"),
                (int, float),
            )
            else 0
        ),
        reverse=True,
    )

    movimientos = []

    for operation in operaciones_ordenadas:

        texto = _formatear_movimiento(
            operation,
            jugadores,
        )

        if texto:
            movimientos.append(texto)

    return usuarios, movimientos


# ==============================================================
# INFORME RESUMIDO
# ==============================================================

def obtener_informe(
    liga_id,
):

    history = _CLIENT.get_full_market_history(
        liga_id,
        limit=100,
        max_pages=100,
    )

    return _CLIENT.market_report_summary(
        history
    )


# ==============================================================
# INFORME DETALLADO
# ==============================================================

def obtener_informe_detallado(
    liga_id,
):

    history = _CLIENT.get_full_market_history(
        liga_id,
        limit=100,
        max_pages=100,
    )

    return _CLIENT.calculate_market_report(
        history
    )