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
    ):

        self.login()


        headers = {}


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
            "/account"
        )



    # ==========================================================
    # LIGAS
    # ==========================================================

    def leagues(self):

        data = self.account()

        return data["data"]["leagues"]



    # ==========================================================
    # BUSCAR USUARIO LIGA
    # ==========================================================

    def find_league_user(
        self,
        league_id,
    ):

        leagues = self.leagues()


        for liga in leagues:

            if liga["id"] == league_id:

                return liga["user"]["id"]


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
                f"No se encontró el usuario "
                f"para la liga {league_id}"
            )


        self.set_context(
            league_id,
            user_id,
        )


        self.login()


        headers = {
            "Authorization":
                f"Bearer {self.token}",

            "Accept":
                "application/json",

            "X-League":
                str(self.league_id),

            "X-User":
                str(self.user_id),
        }


        response = self.session.get(
            f"{BASE_URL}/league/{league_id}",
            headers=headers,
            params={
                "fields":
                    "users(players)"
            },
            timeout=15,
        )


        response.raise_for_status()


        return response.json()



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
                f"No se encontró el usuario "
                f"para la liga {league_id}"
            )


        self.set_context(
            league_id,
            user_id,
        )


        self.login()


        headers = {
            "Authorization":
                f"Bearer {self.token}",

            "Accept":
                "application/json",

            "X-League":
                str(self.league_id),

            "X-User":
                str(self.user_id),
        }


        params = {
            "type":
                "transfer,market",

            "limit":
                limit,
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



    # ==========================================================
    # DESCARGAR TODO EL HISTORIAL
    # ==========================================================

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
                league_id,
                date=current_date,
                limit=limit,
            )


            if not isinstance(
                response,
                dict,
            ):
                break


            data = response.get(
                "data"
            )


            if not isinstance(
                data,
                list,
            ):
                break


            if not data:

                break


            new_events = []


            for event in data:

                if not isinstance(
                    event,
                    dict,
                ):
                    continue


                event_key = (
                    event.get("date"),
                    event.get("type"),
                    event.get("title"),
                )


                if event_key in seen_events:

                    continue


                seen_events.add(
                    event_key
                )


                new_events.append(
                    event
                )


            all_events.extend(
                new_events
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


            oldest_date = min(
                dates
            )


            if not new_events:

                break


            if current_date is not None:

                if oldest_date >= current_date:

                    break


            current_date = (
                oldest_date - 1
            )


            if len(data) < limit:

                break


        all_events.sort(
            key=lambda x:
                x.get(
                    "date",
                    0,
                ),
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

        seen_events = set()


        for _ in range(max_pages):

            response = self.board_history(
                league_id,
                date=current_date,
                limit=limit,
            )


            if not isinstance(
                response,
                dict,
            ):
                break


            data = response.get(
                "data"
            )


            if not isinstance(
                data,
                list,
            ):
                break


            if not data:

                break



            for event in data:

                if not isinstance(
                    event,
                    dict,
                ):
                    continue


                event_date = event.get(
                    "date"
                )


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


                seen_events.add(
                    event_key
                )


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


            oldest_date = min(
                dates
            )


            if oldest_date < desde:

                break



            if current_date is not None:

                if oldest_date >= current_date:

                    break



            current_date = (
                oldest_date - 1
            )



            if len(data) < limit:

                break



        all_events.sort(
            key=lambda x:
                x.get(
                    "date",
                    0,
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
                [],
            )

        elif isinstance(
            history,
            list,
        ):

            events = history

        else:

            return operations



        if not isinstance(
            events,
            list,
        ):

            return operations



        for event in events:


            if not isinstance(
                event,
                dict,
            ):
                continue


            event_date = event.get(
                "date"
            )

            event_type = event.get(
                "type"
            )

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



                operation = dict(
                    item
                )


                operation[
                    "_event_date"
                ] = event_date


                operation[
                    "_event_type"
                ] = event_type


                operation[
                    "_event_title"
                ] = event_title


                operation[
                    "_event_fixed"
                ] = event_fixed



                operations.append(
                    operation
                )



        return operations



    # ==========================================================
    # CALCULAR INFORME MERCADO
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



            player_id = operation.get(
                "player"
            )


            buyer = operation.get(
                "to"
            )


            seller = operation.get(
                "from"
            )



            # --------------------------------------------------
            # COMPRA
            # --------------------------------------------------

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


                report[
                    buyer_name
                ][
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


                report[
                    buyer_name
                ][
                    "total_compras"
                ] += amount


                report[
                    buyer_name
                ][
                    "numero_compras"
                ] += 1



            # --------------------------------------------------
            # VENTA
            # --------------------------------------------------

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


                report[
                    seller_name
                ][
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


                report[
                    seller_name
                ][
                    "total_ventas"
                ] += amount


                report[
                    seller_name
                ][
                    "numero_ventas"
                ] += 1

        return report

    # ==========================================================
    # SALDO FINAL POR MANAGER
    # ==========================================================

    def build_final_report(
        self,
        report,
    ):

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


            final_report[
                manager
            ] = {

                "compras":
                    data["compras"],

                "ventas":
                    data["ventas"],

                "total_compras":
                    total_compras,

                "total_ventas":
                    total_ventas,

                "numero_compras":
                    data["numero_compras"],

                "numero_ventas":
                    data["numero_ventas"],

                "saldo_actual":
                    saldo_actual,
            }


        return final_report



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
        obj,
    ):


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
            ):

                mapa[
                    player_id
                ] = nombre.strip()



            for valor in obj.values():

                recorrer(
                    valor
                )



        elif isinstance(
            obj,
            list,
        ):

            for valor in obj:

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

        valor = _hora(
            operation.get(
                "_event_date"
            )
        )

        if valor:

            hora = (
                f"🕐 {valor} | "
            )



    if isinstance(
        buyer,
        dict,
    ):

        return (
            f"🟢 {hora}"
            f"{buyer.get('name','Desconocido')} "
            f"ficha a {jugador} "
            f"por {_formatear_importe(amount)}"
        )



    if isinstance(
        seller,
        dict,
    ):

        return (
            f"🔴 {hora}"
            f"{seller.get('name','Desconocido')} "
            f"vende a {jugador} "
            f"por {_formatear_importe(amount)}"
        )


    return None



# ==============================================================
# OBTENER OPERACIONES ORDENADAS
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


    for op in operaciones:

        fecha = _timestamp_datetime(
            op.get(
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

            grupos[
                clave
            ] = []

            orden.append(
                clave
            )


        texto = _formatear_movimiento(
            op,
            jugadores,
        )


        if texto:

            grupos[
                clave
            ].append(
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

                if (
                    fecha
                    and fecha.strftime(
                        "%Y-%m-%d"
                    )
                    == clave
                ):

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
# MERCADO 24 HORAS
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


    for op in operaciones:

        texto = _formatear_movimiento(
            op,
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