import requests
import time

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from config import (
    BIWENGER_USERNAME,
    BIWENGER_PASSWORD,
)


BASE_URL = "https://biwenger.as.com/api/v2"

PLAYERS_URL = (
    "https://cf.biwenger.com/api/v2/"
    "competitions/la-liga/data"
)

SALDO_INICIAL = 20_000_000

MADRID_TZ = ZoneInfo("Europe/Madrid")


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
    # HISTORIAL DEL MERCADO
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

                event_key = (
                    event_date,
                    event.get("type"),
                    event.get("title"),
                )

                if event_key in seen_events:
                    continue

                seen_events.add(event_key)

                new_events.append(event)

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

            if not new_events:
                break

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
    # HISTORIAL ÚLTIMAS 24 HORAS
    # ==============================================================

    def get_market_history_last_24h(
        self,
        league_id,
        limit=100,
        max_pages=20,
    ):
        """
        Descarga únicamente las páginas necesarias para cubrir
        las últimas 24 horas.

        Se empieza por el mercado actual y se retrocede hasta
        alcanzar la marca temporal de hace 24 horas.
        """

        ahora = time.time()

        desde = ahora - (
            24 * 60 * 60
        )

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

            for event in data:

                if not isinstance(event, dict):
                    continue

                event_date = event.get("date")

                if not isinstance(
                    event_date,
                    (int, float),
                ):
                    continue

                event_key = (
                    event_date,
                    event.get("type"),
                    event.get("title"),
                )

                if event_key in seen_events:
                    continue

                seen_events.add(event_key)

                if event_date >= desde:

                    all_events.append(
                        event
                    )

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

            # Ya hemos llegado a más de 24h hacia atrás.
            if oldest_date < desde:
                break

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
            event_title = event.get(
                "title",
                "",
            )
            event_fixed = event.get(
                "fixed",
                False,
            )

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

                operation["_event_date"] = (
                    event_date
                )

                operation["_event_type"] = (
                    event_type
                )

                operation["_event_title"] = (
                    event_title
                )

                operation["_event_fixed"] = (
                    event_fixed
                )

                operations.append(
                    operation
                )

        return operations

    # ==============================================================
    # INFORME DEL MERCADO
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

            buyer = operation.get(
                "to"
            )

            seller = operation.get(
                "from"
            )

            # ------------------------------------------------------
            # COMPRA
            # ------------------------------------------------------

            if isinstance(
                buyer,
                dict,
            ):

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
                        "player_id":
                            player_id,

                        "amount":
                            amount,

                        "date":
                            operation.get(
                                "_event_date"
                            ),

                        "user_id":
                            buyer_id,
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

            if isinstance(
                seller,
                dict,
            ):

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
                        "player_id":
                            player_id,

                        "amount":
                            amount,

                        "date":
                            operation.get(
                                "_event_date"
                            ),

                        "user_id":
                            seller_id,
                    }
                )

                report[seller_name][
                    "total_ventas"
                ] += amount

                report[seller_name][
                    "numero_ventas"
                ] += 1

        # ==========================================================
        # CALCULAR SALDO ACTUAL
        # ==========================================================

        final_report = {}

        for manager, data in report.items():

            total_compras = data[
                "total_compras"
            ]

            total_ventas = data[
                "total_ventas"
            ]

            saldo_actual = (
                SALDO_INICIAL
                + total_ventas
                - total_compras
            )

            final_report[manager] = {

                "compras":
                    data["compras"],

                "ventas":
                    data["ventas"],

                "total_compras":
                    total_compras,

                "total_ventas":
                    total_ventas,

                "numero_compras":
                    data[
                        "numero_compras"
                    ],

                "numero_ventas":
                    data[
                        "numero_ventas"
                    ],

                "saldo_actual":
                    saldo_actual,
            }

        return final_report


# ==============================================================
# CLIENTE GLOBAL
# ==============================================================

_CLIENT = BiwengerClient()


# ==============================================================
# FUNCIONES DE COMPATIBILIDAD
# ==============================================================

def obtener_ligas():

    return _CLIENT.leagues()


# ==============================================================
# MAPA DE JUGADORES
# ==============================================================

def _extraer_mapa_jugadores():

    try:

        respuesta = _CLIENT.players()

    except Exception:

        return {}

    mapa = {}

    def recorrer(obj):

        if isinstance(
            obj,
            dict,
        ):

            player_id = obj.get(
                "id"
            )

            nombre = obj.get(
                "name"
            )

            if (
                isinstance(
                    player_id,
                    int,
                )
                and isinstance(
                    nombre,
                    str,
                )
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

                    mapa[
                        player_id
                    ] = nombre.strip()

            for valor in obj.values():

                recorrer(valor)

        elif isinstance(
            obj,
            list,
        ):

            for valor in obj:

                recorrer(valor)

    recorrer(respuesta)

    return mapa


# ==============================================================
# FECHAS
# ==============================================================

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


def _formatear_fecha(
    timestamp,
):

    fecha = _timestamp_datetime(
        timestamp
    )

    if fecha is None:

        return str(timestamp)

    return fecha.strftime(
        "%d/%m/%Y %H:%M"
    )


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


def _hora(
    timestamp,
):

    fecha = _timestamp_datetime(
        timestamp
    )

    if fecha is None:

        return ""

    return fecha.strftime(
        "%H:%M"
    )


# ==============================================================
# IMPORTES
# ==============================================================

def _formatear_importe(
    amount,
):

    try:

        return f"{int(amount):,}€"

    except Exception:

        return "0€"


# ==============================================================
# FORMATEAR MOVIMIENTO
# ==============================================================

def _formatear_movimiento(
    operation,
    jugadores,
    incluir_hora=False,
):

    player_id = operation.get(
        "player"
    )

    jugador = jugadores.get(
        player_id,
        f"Jugador {player_id}",
    )

    amount = operation.get(
        "amount",
        0,
    )

    buyer = operation.get(
        "to"
    )

    seller = operation.get(
        "from"
    )

    hora = ""

    if incluir_hora:

        hora_valor = _hora(
            operation.get(
                "_event_date"
            )
        )

        if hora_valor:

            hora = (
                f"🕐 {hora_valor} | "
            )

    # ----------------------------------------------------------
    # COMPRA
    # ----------------------------------------------------------

    if isinstance(
        buyer,
        dict,
    ):

        nombre = buyer.get(
            "name",
            "Desconocido",
        )

        return (
            f"🟢 {hora}"
            f"{nombre} ficha a "
            f"{jugador} por "
            f"{_formatear_importe(amount)}"
        )

    # ----------------------------------------------------------
    # VENTA
    # ----------------------------------------------------------

    if isinstance(
        seller,
        dict,
    ):

        nombre = seller.get(
            "name",
            "Desconocido",
        )

        return (
            f"🔴 {hora}"
            f"{nombre} vende a "
            f"{jugador} por "
            f"{_formatear_importe(amount)}"
        )

    return None


# ==============================================================
# OBTENER OPERACIONES
# ==============================================================

def _obtener_operaciones(
    history,
):

    operations = _CLIENT.extract_operations(
        history
    )

    def fecha_operacion(
        operation,
    ):

        try:

            return float(
                operation.get(
                    "_event_date",
                    0,
                )
            )

        except Exception:

            return 0

    return sorted(
        operations,
        key=fecha_operacion,
        reverse=True,
    )


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

    operations = _obtener_operaciones(
        history
    )

    jugadores = _extraer_mapa_jugadores()

    movimientos = []

    for operation in operations:

        texto = _formatear_movimiento(
            operation,
            jugadores,
            incluir_hora=True,
        )

        if texto:

            movimientos.append(
                texto
            )

    return usuarios, movimientos


# ==============================================================
# MERCADO COMPLETO AGRUPADO POR FECHA
# ==============================================================

def obtener_mercado_completo(
    liga_id,
):

    history = _CLIENT.get_full_market_history(
        liga_id,
        limit=100,
        max_pages=100,
    )

    operations = _obtener_operaciones(
        history
    )

    jugadores = _extraer_mapa_jugadores()

    grupos = {}

    orden_fechas = []

    for operation in operations:

        timestamp = operation.get(
            "_event_date"
        )

        fecha = _timestamp_datetime(
            timestamp
        )

        if fecha is None:

            clave = "desconocida"

        else:

            clave = fecha.strftime(
                "%Y-%m-%d"
            )

        if clave not in grupos:

            grupos[clave] = []

            orden_fechas.append(
                clave
            )

        texto = _formatear_movimiento(
            operation,
            jugadores,
            incluir_hora=False,
        )

        if texto:

            grupos[clave].append(
                texto
            )

    partes = []

    for clave in orden_fechas:

        if clave == "desconocida":

            titulo = (
                "📅 FECHA DESCONOCIDA"
            )

        else:

            timestamp = None

            for operation in operations:

                fecha = _timestamp_datetime(
                    operation.get(
                        "_event_date"
                    )
                )

                if (
                    fecha is not None
                    and fecha.strftime(
                        "%Y-%m-%d"
                    ) == clave
                ):

                    timestamp = (
                        operation.get(
                            "_event_date"
                        )
                    )

                    break

            titulo = (
                "📅 "
                + _nombre_fecha(
                    timestamp
                )
            )

        bloque = [
            titulo,
            "",
        ]

        bloque.extend(
            grupos[clave]
        )

        partes.append(
            "\n".join(bloque)
        )

    if not partes:

        return (
            "🔄 MERCADO COMPLETO\n\n"
            "Sin movimientos."
        )

    return (
        "🔄 MERCADO COMPLETO\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n\n".join(partes)
    )


# ==============================================================
# MERCADO ÚLTIMAS 24 HORAS
# ==============================================================

def obtener_mercado_24h(
    liga_id,
):

    history = (
        _CLIENT.get_market_history_last_24h(
            liga_id,
            limit=100,
            max_pages=20,
        )
    )

    operations = _obtener_operaciones(
        history
    )

    jugadores = _extraer_mapa_jugadores()

    if not operations:

        return (
            "⏱️ MERCADO — ÚLTIMAS 24 HORAS\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos en las últimas "
            "24 horas."
        )

    lineas = [
        "⏱️ MERCADO — ÚLTIMAS 24 HORAS",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for operation in operations:

        texto = _formatear_movimiento(
            operation,
            jugadores,
            incluir_hora=True,
        )

        if texto:

            lineas.append(
                texto
            )

    return "\n".join(
        lineas
    )


# ==============================================================
# INFORME
# ==============================================================

def obtener_informe(
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


# ==============================================================
# INFORME DETALLADO
# ==============================================================

def obtener_informe_detallado(
    liga_id,
):

    return obtener_informe(
        liga_id
    )