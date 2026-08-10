import requests
import time
import logging

from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import BIWENGER_USERNAME, BIWENGER_PASSWORD


# ============================================================
# CONFIGURACIÓN
# ============================================================

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

    # --------------------------------------------------------
    # CONTEXTO
    # --------------------------------------------------------

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

    def clear_context(self):

        self.league_id = None
        self.user_id = None

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CUENTA / LIGAS
    # --------------------------------------------------------

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

    def find_league_user(self, league_id):

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
                isinstance(usuario, (int, str))
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

    def prepare_context(self, league_id):

        self.clear_context()

        league_id = int(league_id)

        user_id = self.find_league_user(
            league_id
        )

        if user_id is None:

            raise ValueError(
                f"No se encontró usuario "
                f"para liga {league_id}"
            )

        self.set_context(
            league_id,
            user_id,
        )

        return {
            "league_id": self.league_id,
            "user_id": self.user_id,
        }

    # --------------------------------------------------------
    # DATOS COMPLETOS DE LA LIGA
    # --------------------------------------------------------

    def league(self, league_id):

        """
        Obtiene la liga completa incluyendo standings.

        La respuesta contiene directamente:

            standings[].name
            standings[].teamSize
            standings[].teamValue

        Por ejemplo:

            {
                "name": "Huetillos FC",
                "teamSize": 15,
                "teamValue": 58130000
            }
        """

        league_id = int(league_id)

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
            use_context=False,
        )

    # --------------------------------------------------------
    # DATOS DE STANDINGS
    # --------------------------------------------------------

    def league_standings(self, league_id):

        response = self.league(
            league_id
        )

        data = (
            response.get("data", {})
            if isinstance(response, dict)
            else {}
        )

        standings = (
            data.get("standings", [])
            if isinstance(data, dict)
            else []
        )

        return standings


# ============================================================
# JUGADORES PÚBLICOS
# ============================================================

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

    # --------------------------------------------------------
    # HISTORIAL
    # --------------------------------------------------------

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
            "Historial completo: "
            "liga=%s eventos=%s",
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

        desde = (
            ahora
            - 24 * 60 * 60
        )

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

                fechas.append(event_date)

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

        return {
            "status": 200,
            "data": all_events,
        }

    # --------------------------------------------------------
    # OPERACIONES
    # --------------------------------------------------------

    def extract_operations(
        self,
        history,
    ):

        operations = []

        if isinstance(history, dict):

            events = history.get(
                "data",
                []
            )

        elif isinstance(history, list):

            events = history

        else:

            return operations

        for event in events:

            if not isinstance(
                event,
                dict,
            ):
                continue

            content = event.get(
                "content",
                []
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

    # --------------------------------------------------------
    # INFORME DE MOVIMIENTOS
    # --------------------------------------------------------

    def calculate_market_report(
        self,
        history,
    ):

        operations = (
            self.extract_operations(
                history
            )
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

            # ------------------------------------------------
            # COMPRA
            # ------------------------------------------------

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

            # ------------------------------------------------
            # VENTA
            # ------------------------------------------------

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


# ============================================================
# FUNCIONES PÚBLICAS
# ============================================================

def obtener_ligas():

    return _CLIENT.leagues()


# ============================================================
# STANDINGS DE LA LIGA
# ============================================================

def obtener_standings(
    liga_id,
):

    """
    Devuelve los datos oficiales de standings
    proporcionados por Biwenger.

    Cada manager contiene:

        id
        name
        teamSize
        teamValue
        position
        points
    """

    standings = _CLIENT.league_standings(
        liga_id
    )

    resultado = {}

    for manager in standings:

        if not isinstance(
            manager,
            dict,
        ):
            continue

        nombre = manager.get(
            "name",
            "Desconocido",
        )

        team_size = manager.get(
            "teamSize",
            0,
        )

        team_value = manager.get(
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

        resultado[nombre] = {
            "user_id": manager.get(
                "id"
            ),
            "numero_jugadores": team_size,
            "valor_equipo": team_value,
            "position": manager.get(
                "position"
            ),
            "points": manager.get(
                "points",
                0,
            ),
        }

    return resultado


# ============================================================
# DIAGNÓSTICO
# ============================================================

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

    standings = obtener_standings(
        liga_id
    )

    return {
        "league_id": contexto[
            "league_id"
        ],
        "user_id": contexto[
            "user_id"
        ],
        "eventos_board": (
            len(data)
            if isinstance(data, list)
            else None
        ),
        "board_keys": (
            list(respuesta.keys())
            if isinstance(
                respuesta,
                dict,
            )
            else []
        ),
        "managers": len(
            standings
        ),
    }


# ============================================================
# MAPA DE JUGADORES
# ============================================================

def _extraer_mapa_jugadores():

    try:

        respuesta = _CLIENT.players()

    except Exception as exc:

        logger.warning(
            "No se pudo cargar el mapa "
            "público de jugadores: %s",
            exc,
        )

        return {}

    mapa = {}

    def recorrer(objeto):

        if isinstance(
            objeto,
            dict,
        ):

            player_id = objeto.get(
                "id"
            )

            nombre = objeto.get(
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
            ):

                mapa[
                    player_id
                ] = nombre.strip()

            for valor in objeto.values():

                recorrer(valor)

        elif isinstance(
            objeto,
            list,
        ):

            for valor in objeto:

                recorrer(valor)

    recorrer(respuesta)

    return mapa


# ============================================================
# UTILIDADES
# ============================================================

def _numero(valor):

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

        except (
            ValueError,
            TypeError,
        ):
            return None

    return None


def _formatear_importe(
    amount,
):

    try:

        return f"{int(amount):,}€"

    except (
        TypeError,
        ValueError,
    ):

        return "0€"


# ============================================================
# SALDO ACTUAL
# ============================================================

def _calcular_saldo_actual(
    compras,
    ventas,
):

    """
    Saldo actual según la regla establecida:

        20.000.000
        + ventas
        - compras
    """

    return (
        SALDO_INICIAL
        + ventas
        - compras
    )


# ============================================================
# PUJA MÁXIMA
# ============================================================

def _calcular_puja_maxima(
    saldo,
    valor_equipo,
):

    """
    Fórmula actual utilizada:

        saldo + (valor_equipo / 4)

    Se mantiene separada para poder modificarla
    fácilmente cuando confirmemos la fórmula exacta
    utilizada por Biwenger.
    """

    try:

        return (
            saldo
            + (
                valor_equipo
                / 4
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        return saldo


# ============================================================
# INFORME COMPLETO
# ============================================================

def obtener_informe(
    liga_id,
):

    # --------------------------------------------------------
    # 1. OBTENER STANDINGS
    #
    # Aquí obtenemos directamente de Biwenger:
    #
    #   name
    #   teamSize
    #   teamValue
    #
    # Ya NO intentamos encontrar players dentro de users.
    # --------------------------------------------------------

    standings = obtener_standings(
        liga_id
    )

    # --------------------------------------------------------
    # 2. OBTENER HISTORIAL
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 3. CONSTRUIR INFORME
    # --------------------------------------------------------

    resultado = {}

    for nombre, datos_api in standings.items():

        # ----------------------------------------------------
        # DATOS DIRECTOS DE BIWENGER
        # ----------------------------------------------------

        numero_jugadores = datos_api.get(
            "numero_jugadores",
            0,
        )

        valor_equipo = datos_api.get(
            "valor_equipo",
            0,
        )

        # ----------------------------------------------------
        # DATOS DEL HISTORIAL
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # SALDO
        #
        # 20.000.000 + ventas - compras
        # ----------------------------------------------------

        saldo_actual = (
            _calcular_saldo_actual(
                compras,
                ventas,
            )
        )

        # ----------------------------------------------------
        # PUJA MÁXIMA
        # ----------------------------------------------------

        puja_maxima = (
            _calcular_puja_maxima(
                saldo_actual,
                valor_equipo,
            )
        )

        # ----------------------------------------------------
        # RESULTADO
        # ----------------------------------------------------

        resultado[nombre] = {

            "user_id": datos_api.get(
                "user_id"
            ),

            "compras": datos_movimientos.get(
                "compras",
                [],
            ),

            "ventas": datos_movimientos.get(
                "ventas",
                [],
            ),

            "total_compras": compras,

            "total_ventas": ventas,

            "numero_compras": (
                numero_compras
            ),

            "numero_ventas": (
                numero_ventas
            ),

            # DIRECTAMENTE DE BIWENGER
            "numero_jugadores": (
                numero_jugadores
            ),

            # DIRECTAMENTE DE BIWENGER
            "valor_equipo": (
                valor_equipo
            ),

            # CALCULADO
            "saldo_actual": (
                saldo_actual
            ),

            # CALCULADO
            "puja_maxima": (
                puja_maxima
            ),

            "position": datos_api.get(
                "position"
            ),

            "points": datos_api.get(
                "points",
                0,
            ),
        }

    # --------------------------------------------------------
    # 4. COMPATIBILIDAD
    #
    # Si aparece alguien en el historial pero no en standings,
    # lo añadimos para no perder sus movimientos.
    #
    # En condiciones normales no debería ocurrir.
    # --------------------------------------------------------

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
            _calcular_saldo_actual(
                compras,
                ventas,
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

            "saldo_actual": (
                saldo_actual
            ),

            "puja_maxima": (
                saldo_actual
            ),

            "position": None,

            "points": 0,
        }

    return resultado


def obtener_informe_detallado(
    liga_id,
):

    return obtener_informe(
        liga_id
    )


# ============================================================
# FECHAS
# ============================================================

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


def _hora(
    timestamp,
):

    fecha = _timestamp_datetime(
        timestamp
    )

    return (
        fecha.strftime("%H:%M")
        if fecha
        else ""
    )


# ============================================================
# FORMATEAR MOVIMIENTO
# ============================================================

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

            hora = (
                f"🕐 {valor} | "
            )

    comprador = operation.get(
        "to"
    )

    vendedor = operation.get(
        "from"
    )

    # --------------------------------------------------------
    # COMPRA
    # --------------------------------------------------------

    if isinstance(
        comprador,
        dict,
    ):

        return (
            f"🟢 {hora}"
            f"{comprador.get('name', 'Desconocido')} "
            f"ficha a {jugador} "
            f"por "
            f"{_formatear_importe(importe)}"
        )

    # --------------------------------------------------------
    # VENTA
    # --------------------------------------------------------

    if isinstance(
        vendedor,
        dict,
    ):

        return (
            f"🔴 {hora}"
            f"{vendedor.get('name', 'Desconocido')} "
            f"vende a {jugador} "
            f"por "
            f"{_formatear_importe(importe)}"
        )

    return None


# ============================================================
# OPERACIONES
# ============================================================

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


# ============================================================
# MERCADO COMPLETO
# ============================================================

def obtener_mercado_completo(
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

    grupos = {}
    orden = []

    for operacion in operaciones:

        fecha = _timestamp_datetime(
            operacion.get(
                "_event_date"
            )
        )

        clave = (
            fecha.strftime(
                "%Y-%m-%d"
            )
            if fecha
            else "desconocida"
        )

        if clave not in grupos:

            grupos[clave] = []
            orden.append(
                clave
            )

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
        + "\n\n".join(
            bloques
        )
    )


# ============================================================
# MERCADO 24 HORAS
# ============================================================

def obtener_mercado_24h(
    liga_id,
):

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

    return "\n".join(
        lineas
    )


# ============================================================
# ALIAS
# ============================================================

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