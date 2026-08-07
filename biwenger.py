import requests
import time

from collections import defaultdict
from datetime import datetime, timezone
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

MADRID_TZ = ZoneInfo(
    "Europe/Madrid"
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



    # ==========================================================
    # CONTEXTO
    # ==========================================================

    def set_context(
        self,
        league_id=None,
        user_id=None,
    ):

        if league_id is not None:
            self.league_id = league_id

        if user_id is not None:
            self.user_id = user_id



    def clear_context(self):

        self.league_id = None
        self.user_id = None



    # ==========================================================
    # LOGIN
    # ==========================================================

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
                "Authorization":
                    f"Bearer {self.token}",

                "Accept":
                    "application/json",
            }
        )


        return data



    # ==========================================================
    # GET API PRIVADA
    # ==========================================================

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



    # ==========================================================
    # CUENTA
    # ==========================================================

    def account(self):

        return self.get(
            "/account",
            use_context=False,
        )



    # ==========================================================
    # LIGAS
    # ==========================================================

    def leagues(self):

        data = self.account()

        return data.get(
            "data",
            {}
        ).get(
            "leagues",
            []
        )



    # ==========================================================
    # BUSCAR USUARIO LIGA
    # ==========================================================

    def find_league_user(
        self,
        league_id,
    ):

        for liga in self.leagues():

            if liga.get("id") == league_id:

                usuario = liga.get(
                    "user"
                )

                if isinstance(
                    usuario,
                    dict,
                ):

                    return usuario.get(
                        "id"
                    )


        return None



    # ==========================================================
    # INFORMACIÓN DE LIGA
    # ==========================================================

    def league(
        self,
        league_id,
    ):

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


        return self.get(
            f"/league/{league_id}"
        )



    # ==========================================================
    # BOARD ACTUAL
    # ==========================================================

    def board(
        self,
        league_id,
    ):

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


        return self.get(
            f"/league/{league_id}/board"
        )



    # ==========================================================
    # PLANTILLAS USUARIOS
    # ==========================================================

    def league_players(
        self,
        league_id,
    ):

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


        return self.get(
            f"/league/{league_id}",
            params={
                "fields": "users(players)"
            },
        )



    # ==========================================================
    # JUGADORES PÚBLICOS
    # ==========================================================

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



    # ==========================================================
    # HISTORIAL MERCADO
    # ==========================================================

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
                f"No se encontró usuario para liga {league_id}"
            )


        self.set_context(
            league_id,
            user_id,
        )


        params = {
            "type": "transfer,market",
            "limit": limit,
        }


        if date is not None:

            params["date"] = date


        return self.get(
            f"/league/{league_id}/board",
            params=params,
        )



    # ==========================================================
    # DESCARGAR HISTORIAL COMPLETO
    # ==========================================================

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


            data = response.get(
                "data",
                []
            )


            if not data:

                break


            fechas = []


            for event in data:

                key = (
                    event.get("date"),
                    event.get("type"),
                    event.get("title"),
                )


                if key in seen:

                    continue


                seen.add(key)

                all_events.append(
                    event
                )


                if isinstance(
                    event.get("date"),
                    (int, float),
                ):

                    fechas.append(
                        event["date"]
                    )


            if not fechas:

                break


            antigua = min(
                fechas
            )


            if current_date is not None and antigua >= current_date:

                break


            current_date = antigua - 1


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

    # ==========================================================
    # HISTORIAL ÚLTIMAS 24 HORAS
    # ==========================================================

    def get_market_history_last_24h(
        self,
        league_id,
        limit=100,
        max_pages=20,
    ):

        ahora = time.time()

        desde = ahora - (
            24 * 60 * 60
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


            data = response.get(
                "data",
                []
            )


            if not data:

                break


            fechas = []


            for event in data:

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


                seen.add(
                    key
                )


                fechas.append(
                    event_date
                )


                if event_date >= desde:

                    all_events.append(
                        event
                    )


            if not fechas:

                break


            antigua = min(
                fechas
            )


            if antigua < desde:

                break


            if current_date is not None:

                if antigua >= current_date:

                    break


            current_date = antigua - 1


            if len(data) < limit:

                break



        all_events.sort(
            key=lambda x:
                x.get(
                    "date",
                    0
                ),
            reverse=True,
        )


        return {
            "status": 200,
            "data": all_events,
        }



    # ==========================================================
    # EXTRAER OPERACIONES
    # ==========================================================

    def extract_operations(
        self,
        history,
    ):

        operations = []


        if isinstance(
            history,
            dict,
        ):

            events = history.get(
                "data",
                []
            )

        elif isinstance(
            history,
            list,
        ):

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


                operation = dict(
                    item
                )


                operation.update(
                    {
                        "_event_date":
                            event.get(
                                "date"
                            ),

                        "_event_type":
                            event.get(
                                "type"
                            ),

                        "_event_title":
                            event.get(
                                "title",
                                "",
                            ),
                    }
                )


                operations.append(
                    operation
                )


        return operations



    # ==========================================================
    # INFORME MERCADO
    # ==========================================================

    def calculate_market_report(
        self,
        history,
    ):

        operations = self.extract_operations(
            history
        )


        report = defaultdict(
            lambda:
            {
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
                    }
                )


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
                    }
                )


                report[nombre][
                    "total_ventas"
                ] += amount


                report[nombre][
                    "numero_ventas"
                ] += 1



        return report



    # ==========================================================
    # SALDO FINAL
    # ==========================================================

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


            saldo = (
                SALDO_INICIAL
                + ventas
                - compras
            )


            resultado[manager] = {

                "compras":
                    datos.get(
                        "compras",
                        [],
                    ),

                "ventas":
                    datos.get(
                        "ventas",
                        [],
                    ),

                "total_compras":
                    compras,

                "total_ventas":
                    ventas,

                "numero_compras":
                    datos.get(
                        "numero_compras",
                        0,
                    ),

                "numero_ventas":
                    datos.get(
                        "numero_ventas",
                        0,
                    ),

                "saldo_actual":
                    saldo,
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

        return {}


    mapa = {}


    def recorrer(
        objeto,
    ):

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


            if isinstance(
                player_id,
                int,
            ) and isinstance(
                nombre,
                str,
            ):

                mapa[player_id] = nombre.strip()



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



    if isinstance(
        comprador,
        dict,
    ):

        return (
            f"🟢 {hora}"
            f"{comprador.get('name','Desconocido')} "
            f"ficha a {jugador} "
            f"por {_formatear_importe(importe)}"
        )



    if isinstance(
        vendedor,
        dict,
    ):

        return (
            f"🔴 {hora}"
            f"{vendedor.get('name','Desconocido')} "
            f"vende a {jugador} "
            f"por {_formatear_importe(importe)}"
        )


    return None



# ==============================================================
# OPERACIONES ORDENADAS
# ==============================================================

def _obtener_operaciones(
    history,
):

    operaciones = _CLIENT.extract_operations(
        history
    )


    return sorted(
        operaciones,
        key=lambda x:
            x.get(
                "_event_date",
                0,
            ),
        reverse=True,
    )



# ==============================================================
# MERCADO COMPLETO
# ==============================================================

def obtener_mercado_completo(
    liga_id,
):

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

            timestamp = None


            for op in operaciones:

                fecha = _timestamp_datetime(
                    op.get(
                        "_event_date"
                    )
                )


                if fecha and fecha.strftime(
                    "%Y-%m-%d"
                ) == clave:

                    timestamp = op.get(
                        "_event_date"
                    )

                    break


            titulo = (
                "📅 "
                + _nombre_fecha(
                    timestamp
                )
            )


        bloques.append(
            "\n".join(
                [
                    titulo,
                    "",
                    *grupos[clave],
                ]
            )
        )


    if not bloques:

        return (
            "🔄 MERCADO COMPLETO\n\n"
            "Sin movimientos."
        )


    return (
        "🔄 MERCADO COMPLETO\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n\n".join(
            bloques
        )
    )

# ==============================================================
# MERCADO ÚLTIMAS 24 HORAS
# ==============================================================

def obtener_mercado_24h(
    liga_id,
):

    history = _CLIENT.get_market_history_last_24h(
        liga_id
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
        liga_id
    )


    report = _CLIENT.calculate_market_report(
        history
    )


    return _CLIENT.build_final_report(
        report
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



# ==============================================================
# COMPATIBILIDAD VERSIONES ANTIGUAS
# ==============================================================

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



# ==============================================================
# FIN DEL ARCHIVO
# ==============================================================