import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from config import (
    BIWENGER_USERNAME,
    BIWENGER_PASSWORD,
)


BASE_URL = "https://biwenger.as.com/api/v2"
PLAYERS_URL = "https://cf.biwenger.com/api/v2/competitions/la-liga/data"

SALDO_INICIAL = 20_000_000
MADRID_TZ = ZoneInfo("Europe/Madrid")

log = logging.getLogger(__name__)


class BiwengerClient:
    """
    Cliente Biwenger.

    Importante:
    - El ID de la liga se usa siempre explícitamente en las URLs.
    - El contexto X-League/X-User se reconstruye en cada petición de liga.
    - No se reutiliza el user_id de una liga distinta.
    """

    def __init__(self):
        self.session = requests.Session()
        self.public_session = requests.Session()

        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        })
        self.public_session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        })

        self.token = None
        self.login_time = 0

        # Contexto actual, solo informativo.
        self.league_id = None
        self.user_id = None

        # user_id resuelto por liga. Evita arrastrar el usuario
        # de la liga anterior al cambiar de liga.
        self._league_user_cache = {}

        # Cache de jugadores públicos.
        self._players_cache = None
        self._players_cache_time = 0

    # ==========================================================
    # UTILIDADES
    # ==========================================================

    @staticmethod
    def _same_id(a, b):
        if a is None or b is None:
            return False
        return str(a) == str(b)

    @staticmethod
    def _as_id(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _unwrap_data(data):
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    # ==========================================================
    # CONTEXTO
    # ==========================================================

    def set_context(self, league_id=None, user_id=None):
        if league_id is not None:
            self.league_id = self._as_id(league_id)
        if user_id is not None:
            self.user_id = self._as_id(user_id)

    def clear_context(self):
        self.league_id = None
        self.user_id = None

    # ==========================================================
    # LOGIN
    # ==========================================================

    def login(self):
        if self.token and time.time() - self.login_time < 3600:
            return

        response = self.session.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": BIWENGER_USERNAME,
                "password": BIWENGER_PASSWORD,
            },
            timeout=20,
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

    # ==========================================================
    # GET API PRIVADA
    # ==========================================================

    def get(self, endpoint, params=None, use_context=True, league_id=None, user_id=None):
        self.login()

        headers = {}

        if use_context:
            effective_league = (
                league_id if league_id is not None else self.league_id
            )
            effective_user = (
                user_id if user_id is not None else self.user_id
            )

            if effective_league is not None:
                headers["X-League"] = str(effective_league)

            if effective_user is not None:
                headers["X-User"] = str(effective_user)

        response = self.session.get(
            BASE_URL + endpoint,
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    # ==========================================================
    # CUENTA
    # ==========================================================

    def account(self):
        return self.get("/account", use_context=False)

    # ==========================================================
    # LIGAS
    # ==========================================================

    def leagues(self):
        data = self.account()
        payload = self._unwrap_data(data)

        if isinstance(payload, dict):
            ligas = payload.get("leagues", [])
        elif isinstance(payload, list):
            ligas = payload
        else:
            ligas = []

        return ligas if isinstance(ligas, list) else []

    # ==========================================================
    # BUSCAR USUARIO DE UNA LIGA
    # ==========================================================

    def find_league_user(self, league_id):
        key = str(league_id)

        if key in self._league_user_cache:
            return self._league_user_cache[key]

        for liga in self.leagues():
            if not isinstance(liga, dict):
                continue

            if not self._same_id(liga.get("id"), league_id):
                continue

            # Formato habitual: {"user": {"id": ...}}
            usuario = liga.get("user")
            if isinstance(usuario, dict):
                user_id = usuario.get("id")
                if user_id is not None:
                    user_id = self._as_id(user_id)
                    self._league_user_cache[key] = user_id
                    return user_id

            # Algunos formatos pueden devolver directamente userId.
            for field in ("userId", "user_id"):
                user_id = liga.get(field)
                if user_id is not None:
                    user_id = self._as_id(user_id)
                    self._league_user_cache[key] = user_id
                    return user_id

            # Último recurso: buscar una estructura anidada.
            encontrado = self._find_user_id_recursive(liga, league_id)
            if encontrado is not None:
                self._league_user_cache[key] = encontrado
                return encontrado

        return None

    def _find_user_id_recursive(self, obj, league_id):
        if isinstance(obj, dict):
            if "user" in obj and isinstance(obj["user"], dict):
                uid = obj["user"].get("id")
                if uid is not None:
                    return self._as_id(uid)

            for value in obj.values():
                found = self._find_user_id_recursive(value, league_id)
                if found is not None:
                    return found

        elif isinstance(obj, list):
            for value in obj:
                found = self._find_user_id_recursive(value, league_id)
                if found is not None:
                    return found

        return None

    # ==========================================================
    # CONTEXTO DE LIGA
    # ==========================================================

    def prepare_league_context(self, league_id):
        league_id = self._as_id(league_id)
        user_id = self.find_league_user(league_id)

        if user_id is None:
            raise ValueError(
                f"No se encontró el usuario de la liga {league_id}. "
                f"Revisa la respuesta de /account."
            )

        # Sobrescribe SIEMPRE el contexto anterior.
        self.league_id = league_id
        self.user_id = user_id

        return league_id, user_id

    # ==========================================================
    # INFORMACIÓN DE LIGA
    # ==========================================================

    def league(self, league_id):
        league_id, user_id = self.prepare_league_context(league_id)
        return self.get(
            f"/league/{league_id}",
            league_id=league_id,
            user_id=user_id,
        )

    # ==========================================================
    # BOARD ACTUAL
    # ==========================================================

    def board(self, league_id):
        league_id, user_id = self.prepare_league_context(league_id)
        return self.get(
            f"/league/{league_id}/board",
            league_id=league_id,
            user_id=user_id,
        )

    # ==========================================================
    # PLANTILLAS
    # ==========================================================

    def league_players(self, league_id):
        league_id, user_id = self.prepare_league_context(league_id)
        return self.get(
            f"/league/{league_id}",
            params={"fields": "users(players)"},
            league_id=league_id,
            user_id=user_id,
        )

    # ==========================================================
    # JUGADORES PÚBLICOS
    # ==========================================================

    def players(self):
        # No depende de la liga seleccionada.
        if (
            self._players_cache is not None
            and time.time() - self._players_cache_time < 86400
        ):
            return self._players_cache

        response = self.public_session.get(
            PLAYERS_URL,
            params={"lang": "es", "score": 2},
            timeout=20,
        )
        response.raise_for_status()

        data = response.json()
        self._players_cache = data
        self._players_cache_time = time.time()
        return data

    # ==========================================================
    # HISTORIAL MERCADO
    # ==========================================================

    def board_history(self, league_id, date=None, limit=100):
        league_id, user_id = self.prepare_league_context(league_id)

        params = {
            "type": "transfer,market",
            "limit": limit,
        }

        if date is not None:
            params["date"] = date

        response = self.get(
            f"/league/{league_id}/board",
            params=params,
            league_id=league_id,
            user_id=user_id,
        )

        # Diagnóstico útil sin imprimir datos sensibles.
        if not isinstance(response, dict):
            log.warning(
                "Respuesta board no es dict para liga %s: %s",
                league_id,
                type(response).__name__,
            )

        return response

    # ==========================================================
    # NORMALIZAR EVENTOS
    # ==========================================================

    @staticmethod
    def _extract_events(response):
        if isinstance(response, list):
            return response

        if not isinstance(response, dict):
            return []

        data = response.get("data", [])

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Algunas respuestas pueden envolver el board.
            for key in ("board", "events", "items", "content"):
                value = data.get(key)
                if isinstance(value, list):
                    return value

        for key in ("board", "events", "items"):
            value = response.get(key)
            if isinstance(value, list):
                return value

        return []

    # ==========================================================
    # HISTORIAL COMPLETO
    # ==========================================================

    def get_full_market_history(self, league_id, limit=100, max_pages=100):
        league_id = self._as_id(league_id)

        all_events = []
        current_date = None
        seen = set()

        for _ in range(max_pages):
            response = self.board_history(
                league_id=league_id,
                date=current_date,
                limit=limit,
            )

            data = self._extract_events(response)

            if not data:
                break

            fechas = []

            for event in data:
                if not isinstance(event, dict):
                    continue

                event_date = event.get("date")

                key = (
                    event.get("id"),
                    event_date,
                    event.get("type"),
                    event.get("title"),
                    repr(event.get("content")),
                )

                if key in seen:
                    continue

                seen.add(key)
                all_events.append(event)

                if isinstance(event_date, (int, float)):
                    fechas.append(float(event_date))

            if not fechas:
                break

            antigua = min(fechas)

            if current_date is not None and antigua >= float(current_date):
                break

            # Retrocedemos un segundo para no repetir la página.
            current_date = antigua - 1

            # No cortar por len(data) < limit: el backend puede aplicar
            # límites internos distintos.
            if len(data) == 0:
                break

        all_events.sort(
            key=lambda x: x.get("date", 0) or 0,
            reverse=True,
        )

        return {
            "status": 200,
            "data": all_events,
        }

    # ==========================================================
    # ÚLTIMAS 24 HORAS
    # ==========================================================

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

        for _ in range(max_pages):
            response = self.board_history(
                league_id=league_id,
                date=current_date,
                limit=limit,
            )

            data = self._extract_events(response)

            if not data:
                break

            fechas = []

            for event in data:
                if not isinstance(event, dict):
                    continue

                event_date = event.get("date")

                if not isinstance(event_date, (int, float)):
                    continue

                key = (
                    event.get("id"),
                    event_date,
                    event.get("type"),
                    event.get("title"),
                    repr(event.get("content")),
                )

                if key in seen:
                    continue

                seen.add(key)
                fechas.append(float(event_date))

                if event_date >= desde:
                    all_events.append(event)

            if not fechas:
                break

            antigua = min(fechas)

            if antigua < desde:
                break

            if current_date is not None and antigua >= float(current_date):
                break

            current_date = antigua - 1

        all_events.sort(
            key=lambda x: x.get("date", 0) or 0,
            reverse=True,
        )

        return {
            "status": 200,
            "data": all_events,
        }

    # ==========================================================
    # EXTRAER OPERACIONES
    # ==========================================================

    def extract_operations(self, history):
        operations = []

        if isinstance(history, dict):
            events = history.get("data", [])
        elif isinstance(history, list):
            events = history
        else:
            return operations

        if not isinstance(events, list):
            return operations

        for event in events:
            if not isinstance(event, dict):
                continue

            content = event.get("content", [])

            # Algunas respuestas pueden traer directamente la operación.
            if isinstance(content, dict):
                content = [content]

            if not isinstance(content, list):
                continue

            for item in content:
                if not isinstance(item, dict):
                    continue

                operation = dict(item)
                operation.update({
                    "_event_date": event.get("date"),
                    "_event_type": event.get("type"),
                    "_event_title": event.get("title", ""),
                })
                operations.append(operation)

        return operations

    # ==========================================================
    # INFORME MERCADO
    # ==========================================================

    def calculate_market_report(self, history):
        operations = self.extract_operations(history)

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
            amount = operation.get("amount", 0)

            try:
                amount = float(amount)
            except (TypeError, ValueError):
                amount = 0

            buyer = operation.get("to")
            seller = operation.get("from")
            player_id = operation.get("player")

            if isinstance(buyer, dict):
                nombre = str(
                    buyer.get("name") or "Desconocido"
                ).strip()

                report[nombre]["compras"].append({
                    "player_id": player_id,
                    "amount": amount,
                    "date": operation.get("_event_date"),
                })
                report[nombre]["total_compras"] += amount
                report[nombre]["numero_compras"] += 1

            if isinstance(seller, dict):
                nombre = str(
                    seller.get("name") or "Desconocido"
                ).strip()

                report[nombre]["ventas"].append({
                    "player_id": player_id,
                    "amount": amount,
                    "date": operation.get("_event_date"),
                })
                report[nombre]["total_ventas"] += amount
                report[nombre]["numero_ventas"] += 1

        return report

    # ==========================================================
    # SALDO FINAL
    # ==========================================================

    def build_final_report(self, report):
        if not isinstance(report, dict):
            return {}

        resultado = {}

        for manager, datos in report.items():
            if not isinstance(datos, dict):
                continue

            compras = datos.get("total_compras", 0) or 0
            ventas = datos.get("total_ventas", 0) or 0

            resultado[manager] = {
                "compras": datos.get("compras", []),
                "ventas": datos.get("ventas", []),
                "total_compras": compras,
                "total_ventas": ventas,
                "numero_compras": datos.get("numero_compras", 0) or 0,
                "numero_ventas": datos.get("numero_ventas", 0) or 0,
                "saldo_actual": SALDO_INICIAL + ventas - compras,
            }

        return resultado


# ==============================================================
# CLIENTE GLOBAL
# ==============================================================

_CLIENT = BiwengerClient()


# ==============================================================
# FUNCIONES COMPATIBILIDAD BOT
# ==============================================================

def obtener_ligas():
    return _CLIENT.leagues()


# ==============================================================
# MAPA JUGADORES
# ==============================================================

def _extraer_mapa_jugadores():
    try:
        respuesta = _CLIENT.players()
    except Exception:
        log.exception("No se pudo obtener el listado público de jugadores")
        return {}

    mapa = {}

    def recorrer(objeto):
        if isinstance(objeto, dict):
            player_id = objeto.get("id")
            nombre = objeto.get("name")

            if player_id is not None and isinstance(nombre, str):
                try:
                    mapa[int(player_id)] = nombre.strip()
                except (TypeError, ValueError):
                    pass

            for valor in objeto.values():
                recorrer(valor)

        elif isinstance(objeto, list):
            for valor in objeto:
                recorrer(valor)

    recorrer(respuesta)
    return mapa


# ==============================================================
# FECHAS
# ==============================================================

def _timestamp_datetime(timestamp):
    try:
        return datetime.fromtimestamp(
            float(timestamp),
            tz=timezone.utc,
        ).astimezone(MADRID_TZ)
    except Exception:
        return None


def _nombre_fecha(timestamp):
    fecha = _timestamp_datetime(timestamp)

    if fecha is None:
        return "FECHA DESCONOCIDA"

    meses = [
        "ENERO", "FEBRERO", "MARZO", "ABRIL",
        "MAYO", "JUNIO", "JULIO", "AGOSTO",
        "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
    ]

    return f"{fecha.day} {meses[fecha.month - 1]} {fecha.year}"


def _hora(timestamp):
    fecha = _timestamp_datetime(timestamp)
    return fecha.strftime("%H:%M") if fecha else ""


# ==============================================================
# IMPORTES
# ==============================================================

def _formatear_importe(amount):
    try:
        return f"{int(float(amount)):,}€"
    except (TypeError, ValueError):
        return "0€"


# ==============================================================
# FORMATEAR MOVIMIENTO
# ==============================================================

def _formatear_movimiento(operation, jugadores, incluir_hora=False):
    player_id = operation.get("player")

    try:
        player_key = int(player_id)
    except (TypeError, ValueError):
        player_key = player_id

    jugador = jugadores.get(
        player_key,
        f"Jugador {player_id}",
    )

    importe = operation.get("amount", 0)

    hora = ""
    if incluir_hora:
        valor = _hora(operation.get("_event_date"))
        if valor:
            hora = f"🕐 {valor} | "

    comprador = operation.get("to")
    vendedor = operation.get("from")

    if isinstance(comprador, dict):
        nombre = comprador.get("name") or "Desconocido"
        return (
            f"🟢 {hora}{nombre} "
            f"ficha a {jugador} "
            f"por {_formatear_importe(importe)}"
        )

    if isinstance(vendedor, dict):
        nombre = vendedor.get("name") or "Desconocido"
        return (
            f"🔴 {hora}{nombre} "
            f"vende a {jugador} "
            f"por {_formatear_importe(importe)}"
        )

    return None


# ==============================================================
# OPERACIONES ORDENADAS
# ==============================================================

def _obtener_operaciones(history):
    operaciones = _CLIENT.extract_operations(history)

    return sorted(
        operaciones,
        key=lambda x: x.get("_event_date", 0) or 0,
        reverse=True,
    )


# ==============================================================
# MERCADO COMPLETO
# ==============================================================

def obtener_mercado_completo(liga_id):
    history = _CLIENT.get_full_market_history(liga_id)
    operaciones = _obtener_operaciones(history)
    jugadores = _extraer_mapa_jugadores()

    grupos = {}
    orden = []

    for operacion in operaciones:
        fecha = _timestamp_datetime(
            operacion.get("_event_date")
        )

        clave = (
            fecha.strftime("%Y-%m-%d")
            if fecha
            else "desconocida"
        )

        if clave not in grupos:
            grupos[clave] = []
            orden.append(clave)

        texto = _formatear_movimiento(
            operacion,
            jugadores,
        )

        if texto:
            grupos[clave].append(texto)

    bloques = []

    for clave in orden:
        if clave == "desconocida":
            titulo = "📅 FECHA DESCONOCIDA"
        else:
            # Como las operaciones ya están ordenadas, usamos la primera
            # de ese día para obtener el título sin volver a recorrer todo.
            timestamp = next(
                (
                    op.get("_event_date")
                    for op in operaciones
                    if (
                        _timestamp_datetime(op.get("_event_date"))
                        and _timestamp_datetime(
                            op.get("_event_date")
                        ).strftime("%Y-%m-%d") == clave
                    )
                ),
                None,
            )
            titulo = f"📅 {_nombre_fecha(timestamp)}"

        bloques.append(
            "\n".join([
                titulo,
                "",
                *grupos[clave],
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
        + "\n\n".join(bloques)
    )


# ==============================================================
# MERCADO ÚLTIMAS 24 HORAS
# ==============================================================

def obtener_mercado_24h(liga_id):
    history = _CLIENT.get_market_history_last_24h(liga_id)
    operaciones = _obtener_operaciones(history)
    jugadores = _extraer_mapa_jugadores()

    if not operaciones:
        return (
            "⏱️ MERCADO — ÚLTIMAS 24 HORAS\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Sin movimientos."
        )

    lineas = [
        "⏱️ MERCADO — ÚLTIMAS 24 HORAS",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for operacion in operaciones:
        texto = _formatear_movimiento(
            operacion,
            jugadores,
            incluir_hora=True,
        )
        if texto:
            lineas.append(texto)

    if len(lineas) == 3:
        lineas.append("Sin movimientos.")

    return "\n".join(lineas)


# ==============================================================
# INFORME
# ==============================================================

def obtener_informe(liga_id):
    history = _CLIENT.get_full_market_history(liga_id)
    report = _CLIENT.calculate_market_report(history)
    return _CLIENT.build_final_report(report)


# ==============================================================
# INFORME DETALLADO
# ==============================================================

def obtener_informe_detallado(liga_id):
    return obtener_informe(liga_id)


# ==============================================================
# COMPATIBILIDAD VERSIONES ANTIGUAS
# ==============================================================

def obtener_movimientos(liga_id):
    return obtener_mercado_completo(liga_id)


def obtener_movimientos_24h(liga_id):
    return obtener_mercado_24h(liga_id)


# ==============================================================
# FIN
# ==============================================================
