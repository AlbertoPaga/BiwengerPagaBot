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

    # =========================================================
    # CONTEXTO
    # =========================================================

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

    # =========================================================
    # LOGIN
    # =========================================================

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

    # =========================================================
    # GET GENERAL
    # =========================================================

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
                headers["X-League"] = str(self.league_id)

            if self.user_id is not None:
                headers["X-User"] = str(self.user_id)

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
        # No mostramos tokens ni credenciales.
        if isinstance(data, dict):
            contenido = data.get("data")

            if isinstance(contenido, (list, dict)):
                data_len = len(contenido)
            else:
                data_len = "n/a"

            logger.info(
                "RESPUESTA %s -> keys=%s data_type=%s data_len=%s",
                endpoint,
                list(data.keys()),
                type(contenido).__name__,
                data_len,
            )

        return data

    # =========================================================
    # ACCOUNT / LIGAS
    # =========================================================

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
            # user es un objeto.
            if isinstance(usuario, dict):
                uid = usuario.get("id")

                if uid is not None:
                    return int(uid)

            # Compatibilidad:
            # user podría ser directamente un ID.
            if (
                isinstance(usuario, (int, str))
                and str(usuario).isdigit()
            ):
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
                "Liga %r encontrada pero no se pudo extraer "
                "user_id. Registro=%r",
                league_id,
                liga,
            )

            return None

        logger.warning(
            "No se encontró league_id=%r en /account",
            league_id,
        )

        return None

    # =========================================================
    # PREPARAR CONTEXTO
    # =========================================================

    def prepare_context(self, league_id):
        # MUY IMPORTANTE:
        # no reutilizar contexto de otra liga.
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

    # =========================================================
    # DATOS DE LIGA
    # =========================================================

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

    # =========================================================
    # JUGADORES PÚBLICOS
    # =========================================================

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

    # =========================================================
    # HISTORIAL
    # =========================================================

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

    # =========================================================
    # OPERACIONES
    # =========================================================

    def extract_operations(self, history):
        operations = []

        if isinstance(history, dict):
            events = history.get("data", [])

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

            if not isinstance(content, list):
                continue

            for item in content:
                if not isinstance(item, dict):
                    continue

                operation = dict(item)

                operation.update({
                    "_event_date": event.get("date"),
                    "_event_type": event.get("type"),
                    "_event_title": event.get(
                        "title",
                        "",
                    ),
                })

                operations.append(operation)

        return operations

    # =========================================================
    # INFORME INTERNO
    # =========================================================

    def calculate_market_report(self, history):
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
            player_id = operation.get("player")

            if isinstance(buyer, dict):
                nombre = buyer.get(
                    "name",
                    "Desconocido",
                )

                report[nombre]["compras"].append({
                    "player_id": player_id,
                    "amount": amount,
                    "date": operation.get(
                        "_event_date"
                    ),
                })

                report[nombre]["total_compras"] += amount
                report[nombre]["numero_compras"] += 1

            if isinstance(seller, dict):
                nombre = seller.get(
                    "name",
                    "Desconocido",
                )

                report[nombre]["ventas"].append({
                    "player_id": player_id,
                    "amount": amount,
                    "date": operation.get(
                        "_event_date"
                    ),
                })

                report[nombre]["total_ventas"] += amount
                report[nombre]["numero_ventas"] += 1

        return report

    def build_final_report(self, report):
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


# =============================================================
# CLIENTE GLOBAL
# =============================================================

# IMPORTANTE:
# Esto corrige el error:
#
# NameError: name 'Bi' is not defined
#
# Debe ser exactamente BiwengerClient().
_CLIENT = BiwengerClient()


# =============================================================
# FUNCIONES PÚBLICAS
# =============================================================

def obtener_ligas():
    return _CLIENT.leagues()


def diagnostico_liga(liga_id):
    """
    Devuelve información segura para comprobar
    qué contexto se está usando.
    """

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


# =============================================================
# USUARIOS DE LA LIGA
# =============================================================

def _extraer_usuarios_liga(respuesta):
    """
    Busca usuarios dentro de la respuesta de /league/{id}.

    Se hace de forma recursiva porque la estructura exacta
    puede variar dependiendo del estado de la liga.
    """

    usuarios = {}

    def recorrer(objeto):
        if isinstance(objeto, dict):
            uid = objeto.get("id")
            nombre = objeto.get("name")

            if (
                isinstance(uid, (int, str))
                and str(uid).isdigit()
                and isinstance(nombre, str)
                and nombre.strip()
            ):
                uid = int(uid)

                usuarios[uid] = {
                    "id": uid,
                    "name": nombre.strip(),
                }

            for clave, valor in objeto.items():
                if clave in (
                    "icon",
                    "image",
                    "photo",
                ):
                    continue

                recorrer(valor)

        elif isinstance(objeto, list):
            for valor in objeto:
                recorrer(valor)

    recorrer(respuesta)

    return list(usuarios.values())


def obtener_usuarios_liga(liga_id):
    """
    Obtiene los miembros de la liga.

    IMPORTANTE:
    No depende del historial del mercado.

    Esto permite que una liga completamente vacía
    siga mostrando sus miembros en /informe.
    """

    usuarios = {}

    # ---------------------------------------------------------
    # 1. Intentar obtener usuarios desde /league/{id}
    # ---------------------------------------------------------

    try:
        _CLIENT.prepare_context(
            liga_id
        )

        respuesta = _CLIENT.get(
            f"/league/{_CLIENT.league_id}",
            params={
                "fields": "users"
            },
        )

        encontrados = _extraer_usuarios_liga(
            respuesta
        )

        for usuario in encontrados:
            uid = usuario.get("id")

            if uid is not None:
                usuarios[int(uid)] = usuario

    except Exception:
        logger.exception(
            "ERROR obteniendo usuarios desde "
            "/league/%s",
            liga_id,
        )

    # ---------------------------------------------------------
    # 2. Fallback usando /account
    # ---------------------------------------------------------
    #
    # Esto garantiza al menos el usuario asociado
    # a la liga aunque /league/{id} esté prácticamente vacío.
    # ---------------------------------------------------------

    try:
        for liga in _CLIENT.leagues():
            if not isinstance(liga, dict):
                continue

            if str(liga.get("id")) != str(liga_id):
                continue

            usuario = liga.get("user")

            if isinstance(usuario, dict):
                uid = usuario.get("id")
                nombre = usuario.get("name")

                if (
                    uid is not None
                    and isinstance(nombre, str)
                    and nombre.strip()
                ):
                    usuarios[int(uid)] = {
                        "id": int(uid),
                        "name": nombre.strip(),
                    }

            break

    except Exception:
        logger.exception(
            "ERROR usando fallback de /account "
            "para liga %s",
            liga_id,
        )

    resultado = list(
        usuarios.values()
    )

    logger.info(
        "USUARIOS LIGA -> liga=%s usuarios=%s",
        liga_id,
        resultado,
    )

    return resultado


# =============================================================
# JUGADORES
# =============================================================

def _extraer_mapa_jugadores():
    try:
        respuesta = _CLIENT.players()

    except Exception:
        logger.exception(
            "ERROR obteniendo jugadores públicos"
        )
        return {}

    mapa = {}

    def recorrer(objeto):
        if isinstance(objeto, dict):
            player_id = objeto.get("id")
            nombre = objeto.get("name")

            if (
                isinstance(player_id, int)
                and isinstance(nombre, str)
            ):
                mapa[player_id] = nombre.strip()

            for valor in objeto.values():
                recorrer(valor)

        elif isinstance(objeto, list):
            for valor in objeto:
                recorrer(valor)

    recorrer(respuesta)

    return mapa


# =============================================================
# FECHAS
# =============================================================

def _timestamp_datetime(timestamp):
    try:
        return datetime.fromtimestamp(
            float(timestamp),
            tz=timezone.utc,
        ).astimezone(MADRID_TZ)

    except Exception:
        return None


def _nombre_fecha(timestamp):
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


def _hora(timestamp):
    fecha = _timestamp_datetime(
        timestamp
    )

    return (
        fecha.strftime("%H:%M")
        if fecha
        else ""
    )


# =============================================================
# FORMATO
# =============================================================

def _formatear_importe(amount):
    try:
        return f"{int(amount):,}€"

    except Exception:
        return "0€"


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

    importe = operation.get(
        "amount",
        0,
    )

    hora = ""

    if incluir_hora:
        valor = _hora(
            operation.get(
                "_event_date"
            )
        )

        if valor:
            hora = f"🕐 {valor} | "

    comprador = operation.get(
        "to"
    )

    vendedor = operation.get(
        "from"
    )

    if isinstance(comprador, dict):
        return (
            f"🟢 {hora}"
            f"{comprador.get('name', 'Desconocido')} "
            f"ficha a {jugador} "
            f"por {_formatear_importe(importe)}"
        )

    if isinstance(vendedor, dict):
        return (
            f"🔴 {hora}"
            f"{vendedor.get('name', 'Desconocido')} "
            f"vende a {jugador} "
            f"por {_formatear_importe(importe)}"
        )

    return None


def _obtener_operaciones(history):
    operaciones = _CLIENT.extract_operations(
        history
    )

    return sorted(
        operaciones,
        key=lambda x: x.get(
            "_event_date",
            0,
        ),
        reverse=True,
    )


# =============================================================
# MERCADO COMPLETO
# =============================================================

def obtener_mercado_completo(liga_id):
    history = _CLIENT.get_full_market_history(
        liga_id
    )

    operaciones = _obtener_operaciones(
        history
    )

    jugadores = _extraer_mapa_jugadores()

    grupos = {}
    orden = []

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
            orden.append(clave)

        texto = _formatear_movimiento(
            operacion,
            jugadores,
        )

        if texto:
            grupos[clave].append(
                texto
            )

    bloques = []

    for clave in orden:
        if clave == "desconocida":
            titulo = (
                "📅 FECHA DESCONOCIDA"
            )

        else:
            timestamp = next(
                (
                    op.get(
                        "_event_date"
                    )
                    for op in operaciones
                    if (
                        _timestamp_datetime(
                            op.get(
                                "_event_date"
                            )
                        )
                        and
                        _timestamp_datetime(
                            op.get(
                                "_event_date"
                            )
                        ).strftime(
                            "%Y-%m-%d"
                        ) == clave
                    )
                ),
                None,
            )

            titulo = (
                "📅 "
                + _nombre_fecha(
                    timestamp
                )
            )

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


# =============================================================
# MERCADO ÚLTIMAS 24 HORAS
# =============================================================

def obtener_mercado_24h(liga_id):
    history = (
        _CLIENT.get_market_history_last_24h(
            liga_id
        )
    )

    operaciones = _obtener_operaciones(
        history
    )

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
            lineas.append(
                texto
            )

    return "\n".join(lineas)


# =============================================================
# INFORME
# =============================================================

def obtener_informe(liga_id):
    """
    Genera el informe de la liga.

    La diferencia importante respecto a la versión anterior
    es que los usuarios se obtienen ANTES del historial.

    Por tanto:

    - Liga con movimientos -> muestra movimientos.
    - Liga sin movimientos -> muestra igualmente usuarios.
    - Usuario sin compras -> compras 0.
    - Usuario sin ventas -> ventas 0.
    - Saldo inicial -> 20.000.000 €.
    """

    # ---------------------------------------------------------
    # 1. Obtener SIEMPRE los miembros.
    # ---------------------------------------------------------

    usuarios = obtener_usuarios_liga(
        liga_id
    )

    resultado = {}

    for usuario in usuarios:
        nombre = usuario.get(
            "name"
        )

        if not nombre:
            continue

        resultado[nombre] = {
            "compras": [],
            "ventas": [],
            "total_compras": 0,
            "total_ventas": 0,
            "numero_compras": 0,
            "numero_ventas": 0,
            "saldo_actual": SALDO_INICIAL,
        }

    # ---------------------------------------------------------
    # 2. Obtener historial.
    # ---------------------------------------------------------

    history = _CLIENT.get_full_market_history(
        liga_id
    )

    operaciones = _CLIENT.extract_operations(
        history
    )

    report = _CLIENT.calculate_market_report(
        history
    )

    # ---------------------------------------------------------
    # 3. Añadir operaciones a los usuarios.
    # ---------------------------------------------------------

    for manager, datos in report.items():
        if manager not in resultado:
            resultado[manager] = {
                "compras": [],
                "ventas": [],
                "total_compras": 0,
                "total_ventas": 0,
                "numero_compras": 0,
                "numero_ventas": 0,
                "saldo_actual": SALDO_INICIAL,
            }

        compras = datos.get(
            "total_compras",
            0,
        )

        ventas = datos.get(
            "total_ventas",
            0,
        )

        resultado[manager].update({
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
        })

    logger.info(
        "INFORME -> liga=%s usuarios=%s "
        "operaciones=%s",
        liga_id,
        len(resultado),
        len(operaciones),
    )

    return resultado


def obtener_informe_detallado(liga_id):
    return obtener_informe(
        liga_id
    )


# =============================================================
# ALIAS DE MOVIMIENTOS
# =============================================================

def obtener_movimientos(liga_id):
    return obtener_mercado_completo(
        liga_id
    )


def obtener_movimientos_24h(liga_id):
    return obtener_mercado_24h(
        liga_id
    )