import requests
import time
from collections import defaultdict

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

        # ==========================================================
        # API PRIVADA
        # ==========================================================

        self.session = requests.Session()

        # ==========================================================
        # API PÚBLICA DE JUGADORES
        # ==========================================================

        self.public_session = requests.Session()

        self.public_session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            }
        )

        # ==========================================================
        # AUTENTICACIÓN / CONTEXTO
        # ==========================================================

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
    # PLANTILLAS DE LOS USUARIOS
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
    # HISTORIAL COMPLETO DEL MERCADO
    #
    # IMPORTANTE:
    #
    # La API devuelve eventos.
    #
    # Un evento puede contener varias operaciones dentro de
    # "content".
    #
    # Por eso NO debemos considerar cada evento como un movimiento
    # individual.
    #
    # Ejemplo:
    #
    # evento 1
    #   content -> 7 operaciones
    #
    # evento 2
    #   content -> 1 operación
    #
    # etc.
    #
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
    # DESCARGAR TODO EL HISTORIAL
    #
    # Va retrocediendo usando la fecha del último evento recibido.
    #
    # Esto permite recuperar eventos anteriores a los primeros
    # que devuelve la primera petición.
    # ==============================================================

    def get_full_market_history(
        self,
        league_id,
        limit=100,
        max_pages=100,
    ):

        all_events = []

        current_date = None

        seen_dates = set()

        for page in range(max_pages):

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

                event_date = event.get("date")

                # Evitar duplicados
                if event_date in seen_dates:
                    continue

                seen_dates.add(event_date)

                new_events.append(event)

            all_events.extend(new_events)

            # ------------------------------------------------------
            # Buscar la fecha más antigua recibida
            # ------------------------------------------------------

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

            # ------------------------------------------------------
            # Si ya no hemos conseguido eventos nuevos,
            # no seguimos haciendo peticiones.
            # ------------------------------------------------------

            if not new_events:
                break

            # ------------------------------------------------------
            # Retrocedemos hasta antes del evento más antiguo.
            # ------------------------------------------------------

            if current_date is not None:

                if oldest_date >= current_date:
                    break

            current_date = oldest_date - 1

            # ------------------------------------------------------
            # Si la respuesta tiene menos elementos que el límite,
            # puede que ya no haya más páginas.
            #
            # Aun así hacemos una última comprobación cuando sea
            # necesario.
            # ------------------------------------------------------

            if len(data) < limit:
                break

        # ==========================================================
        # ORDEN CRONOLÓGICO DESCENDENTE
        # ==========================================================

        all_events.sort(
            key=lambda x: x.get("date", 0),
            reverse=True,
        )

        return {
            "status": 200,
            "data": all_events,
        }

    # ==============================================================
    # CONVERTIR CONTENT EN OPERACIONES INDIVIDUALES
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

                operations.append(
                    operation
                )

        return operations

    # ==============================================================
    # INFORME DEL MERCADO
    #
    # Devuelve:
    #
    # {
    #   manager: {
    #       compras,
    #       ventas,
    #       gasto,
    #       ingresos,
    #       balance,
    #       ...
    #   }
    # }
    #
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

        # ==========================================================
        # PROCESAR OPERACIONES
        # ==========================================================

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

            buyer = operation.get(
                "to"
            )

            seller = operation.get(
                "from"
            )

            # ------------------------------------------------------
            # COMPRA / FICHAJE
            #
            # En la API:
            #
            # to = usuario comprador
            # from = None
            #
            # ------------------------------------------------------

            if isinstance(buyer, dict):

                buyer_name = buyer.get(
                    "name",
                    "Desconocido",
                )

                buyer_id = buyer.get(
                    "id"
                )

                report[buyer_name][
                    "compras"
                ].append(
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
            #
            # En la API:
            #
            # from = usuario vendedor
            # to = None
            #
            # ------------------------------------------------------

            if isinstance(seller, dict):

                seller_name = seller.get(
                    "name",
                    "Desconocido",
                )

                seller_id = seller.get(
                    "id"
                )

                report[seller_name][
                    "ventas"
                ].append(
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

        # ==========================================================
        # CALCULAR BALANCES
        # ==========================================================

        final_report = {}

        for manager, data in report.items():

            total_compras = data[
                "total_compras"
            ]

            total_ventas = data[
                "total_ventas"
            ]

            balance = (
                total_ventas
                - total_compras
            )

            final_report[manager] = {
                "compras": data["compras"],
                "ventas": data["ventas"],

                "total_compras":
                    total_compras,

                "total_ventas":
                    total_ventas,

                "numero_compras":
                    data["numero_compras"],

                "numero_ventas":
                    data["numero_ventas"],

                "balance":
                    balance,
            }

        return final_report

    # ==============================================================
    # RESUMEN GENERAL DEL INFORME
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

        # ----------------------------------------------------------
        # Mayor gasto
        # ----------------------------------------------------------

        mayor_gasto = max(
            report.items(),
            key=lambda item:
                item[1]["total_compras"],
        )

        # ----------------------------------------------------------
        # Mayor ingreso
        # ----------------------------------------------------------

        mayor_ingreso = max(
            report.items(),
            key=lambda item:
                item[1]["total_ventas"],
        )

        # ----------------------------------------------------------
        # Mejor balance
        # ----------------------------------------------------------

        mejor_balance = max(
            report.items(),
            key=lambda item:
                item[1]["balance"],
        )

        # ----------------------------------------------------------
        # Peor balance
        # ----------------------------------------------------------

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
                "manager":
                    mayor_gasto[0],

                "amount":
                    mayor_gasto[1][
                        "total_compras"
                    ],
            },

            "mayor_ingreso": {
                "manager":
                    mayor_ingreso[0],

                "amount":
                    mayor_ingreso[1][
                        "total_ventas"
                    ],
            },

            "mejor_balance": {
                "manager":
                    mejor_balance[0],

                "amount":
                    mejor_balance[1][
                        "balance"
                    ],
            },

            "peor_balance": {
                "manager":
                    peor_balance[0],

                "amount":
                    peor_balance[1][
                        "balance"
                    ],
            },
        }
```

Este fichero **no cambia la interpretación que ya hemos comprobado que funciona**. La diferencia importante es que ahora tenemos:

* `get_full_market_history()` → obtiene todo el historial.
* `extract_operations()` → convierte los 19 eventos en las operaciones individuales contenidas en `content`.
* `calculate_market_report()` → calcula compras, ventas y balance por manager.
* `market_report_summary()` → obtiene los totales y rankings generales.

**Ojo con una cosa:** en los datos que nos has enseñado, un evento `market` puede tener varias compras, y las ventas aparecen como eventos `transfer`. Por eso el cálculo se hace sobre cada elemento de `content`, no sobre el número de eventos.

El siguiente paso sería conectar `market_report_summary()` con `/informe` en Telegram y comprobar las cifras contra la aplicación de Biwenger.
