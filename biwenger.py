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


# ==============================================================
# CLIENTE BIWENGER
# ==============================================================


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


        self.token = data.get(
            "token"
        )


        if not self.token:

            raise ValueError(
                "No se recibió token de Biwenger"
            )


        self.login_time = time.time()


        self.session.headers.update(
            {
                "Authorization":
                    f"Bearer {self.token}",

                "Accept":
                    "application/json",
            }
        )



    # ==========================================================
    # PETICIONES PRIVADAS
    # ==========================================================


    def get(
        self,
        endpoint,
        params=None,
    ):


        self.login()


        headers = {}


        if self.league_id:

            headers["X-League"] = str(
                self.league_id
            )


        if self.user_id:

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


        return (
            data
            .get(
                "data",
                {}
            )
            .get(
                "leagues",
                []
            )
        )



    # ==========================================================
    # USUARIO DE LIGA
    # ==========================================================


    def find_league_user(
        self,
        league_id,
    ):

        for liga in self.leagues():

            if liga.get(
                "id"
            ) == league_id:

                user = liga.get(
                    "user",
                    {}
                )

                return user.get(
                    "id"
                )


        return None



    # ==========================================================
    # INFORMACIÓN LIGA
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
                "No se encontró usuario de liga"
            )


        self.set_context(
            league_id,
            user_id,
        )


        return self.get(
            f"/league/{league_id}"
        )



    # ==========================================================
    # BOARD
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
                "No se encontró usuario de liga"
            )


        self.set_context(
            league_id,
            user_id,
        )


        params = {
            "type":
                "transfer,market",

            "limit":
                limit,
        }


        if date:

            params["date"] = date



        return self.get(
            f"/league/{league_id}/board",
            params=params,
        )

    # ==========================================================
    # HISTORIAL COMPLETO MERCADO
    # ==========================================================


    def get_full_market_history(
        self,
        league_id,
        limit=100,
        max_pages=100,
    ):

        eventos = []

        fecha_actual = None

        vistos = set()


        for _ in range(
            max_pages
        ):


            respuesta = self.board_history(
                league_id,
                date=fecha_actual,
                limit=limit,
            )


            if not isinstance(
                respuesta,
                dict,
            ):

                break


            datos = respuesta.get(
                "data",
                []
            )


            if not isinstance(
                datos,
                list,
            ) or not datos:

                break



            nuevas = []



            for evento in datos:


                if not isinstance(
                    evento,
                    dict,
                ):

                    continue


                clave = (
                    evento.get(
                        "date"
                    ),

                    evento.get(
                        "type"
                    ),

                    evento.get(
                        "title"
                    ),
                )



                if clave in vistos:

                    continue


                vistos.add(
                    clave
                )


                nuevas.append(
                    evento
                )



            eventos.extend(
                nuevas
            )



            fechas = [

                e.get(
                    "date"
                )

                for e in datos

                if isinstance(
                    e.get(
                        "date"
                    ),
                    (int, float),
                )

            ]



            if not fechas:

                break



            antigua = min(
                fechas
            )



            if not nuevas:

                break



            if fecha_actual:

                if antigua >= fecha_actual:

                    break



            fecha_actual = (
                antigua - 1
            )



            if len(datos) < limit:

                break



        eventos.sort(
            key=lambda x:
                x.get(
                    "date",
                    0
                ),
            reverse=True,
        )



        return {
            "status": 200,
            "data": eventos,
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


        desde = (
            ahora
            -
            (24 * 60 * 60)
        )


        eventos = []


        fecha_actual = None


        vistos = set()



        for _ in range(
            max_pages
        ):



            respuesta = self.board_history(
                league_id,
                date=fecha_actual,
                limit=limit,
            )



            if not isinstance(
                respuesta,
                dict,
            ):

                break



            datos = respuesta.get(
                "data",
                []
            )



            if not isinstance(
                datos,
                list,
            ) or not datos:

                break



            fechas = []



            for evento in datos:



                if not isinstance(
                    evento,
                    dict,
                ):

                    continue



                fecha_evento = evento.get(
                    "date"
                )



                if isinstance(
                    fecha_evento,
                    (int, float),
                ):

                    fechas.append(
                        fecha_evento
                    )



                    clave = (

                        fecha_evento,

                        evento.get(
                            "type"
                        ),

                        evento.get(
                            "title"
                        ),

                    )



                    if (
                        clave not in vistos
                        and fecha_evento >= desde
                    ):

                        vistos.add(
                            clave
                        )

                        eventos.append(
                            evento
                        )



            if not fechas:

                break



            antigua = min(
                fechas
            )



            if antigua < desde:

                break



            if fecha_actual:

                if antigua >= fecha_actual:

                    break



            fecha_actual = (
                antigua - 1
            )



            if len(datos) < limit:

                break



        eventos.sort(
            key=lambda x:
                x.get(
                    "date",
                    0
                ),
            reverse=True,
        )



        return {
            "status":200,
            "data":eventos,
        }




    # ==========================================================
    # EXTRAER OPERACIONES
    # ==========================================================


    def extract_operations(
        self,
        history,
    ):


        operaciones = []



        if isinstance(
            history,
            dict,
        ):

            eventos = history.get(
                "data",
                []
            )

        else:

            eventos = history



        if not isinstance(
            eventos,
            list,
        ):

            return []



        for evento in eventos:



            if not isinstance(
                evento,
                dict,
            ):

                continue



            contenido = evento.get(
                "content",
                []
            )



            if not isinstance(
                contenido,
                list,
            ):

                continue



            for item in contenido:



                if not isinstance(
                    item,
                    dict,
                ):

                    continue



                op = dict(
                    item
                )


                op["_event_date"] = (
                    evento.get(
                        "date"
                    )
                )


                op["_event_type"] = (
                    evento.get(
                        "type"
                    )
                )


                op["_event_title"] = (
                    evento.get(
                        "title",
                        ""
                    )
                )


                operaciones.append(
                    op
                )



        return operaciones

# ==============================================================
# INFORME DE MERCADO
# ==============================================================


    def calculate_market_report(
        self,
        history,
    ):

        operaciones = self.extract_operations(
            history
        )


        reporte = defaultdict(
            lambda: {

                "compras": [],

                "ventas": [],

                "total_compras": 0,

                "total_ventas": 0,

                "numero_compras": 0,

                "numero_ventas": 0,

            }
        )



        for op in operaciones:


            cantidad = op.get(
                "amount",
                0
            )


            if not isinstance(
                cantidad,
                (int, float),
            ):

                cantidad = 0



            comprador = op.get(
                "to"
            )


            vendedor = op.get(
                "from"
            )



            if isinstance(
                comprador,
                dict,
            ):


                nombre = comprador.get(
                    "name",
                    "Desconocido"
                )


                reporte[nombre][
                    "compras"
                ].append(
                    op
                )


                reporte[nombre][
                    "total_compras"
                ] += cantidad


                reporte[nombre][
                    "numero_compras"
                ] += 1



            if isinstance(
                vendedor,
                dict,
            ):


                nombre = vendedor.get(
                    "name",
                    "Desconocido"
                )


                reporte[nombre][
                    "ventas"
                ].append(
                    op
                )


                reporte[nombre][
                    "total_ventas"
                ] += cantidad


                reporte[nombre][
                    "numero_ventas"
                ] += 1



        resultado = {}



        for manager, datos in reporte.items():


            resultado[manager] = {

                **datos,

                "saldo_actual":
                    (
                        SALDO_INICIAL
                        +
                        datos["total_ventas"]
                        -
                        datos["total_compras"]
                    )
            }



        return resultado





# ==============================================================
# CLIENTE GLOBAL
# ==============================================================


_CLIENT = BiwengerClient()



# ==============================================================
# FUNCIONES PARA BOT.PY
# ==============================================================


def obtener_ligas():

    return _CLIENT.leagues()



def obtener_nombre_liga(
    liga_id,
):

    for liga in obtener_ligas():

        if liga.get(
            "id"
        ) == liga_id:

            return liga.get(
                "name",
                "Liga sin nombre"
            )


    return "Liga desconocida"




# ==============================================================
# JUGADORES
# ==============================================================


def _mapa_jugadores():

    try:

        datos = _CLIENT.players()

    except Exception:

        return {}



    mapa = {}



    def recorrer(
        elemento,
    ):


        if isinstance(
            elemento,
            dict,
        ):


            jugador_id = elemento.get(
                "id"
            )


            nombre = elemento.get(
                "name"
            )


            if (
                isinstance(
                    jugador_id,
                    int
                )
                and isinstance(
                    nombre,
                    str
                )
            ):

                mapa[jugador_id] = nombre



            for valor in elemento.values():

                recorrer(
                    valor
                )



        elif isinstance(
            elemento,
            list,
        ):


            for valor in elemento:

                recorrer(
                    valor
                )



    recorrer(
        datos
    )


    return mapa





# ==============================================================
# FORMATEOS
# ==============================================================


def _fecha(
    timestamp,
):

    try:

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).astimezone(
            MADRID_TZ
        )

    except Exception:

        return None




def _importe(
    cantidad,
):

    try:

        return f"{int(cantidad):,}€"

    except Exception:

        return "0€"




def _movimiento_texto(
    op,
    jugadores,
    hora=False,
):


    jugador = jugadores.get(
        op.get(
            "player"
        ),
        "Jugador desconocido"
    )


    cantidad = _importe(
        op.get(
            "amount",
            0
        )
    )



    comprador = op.get(
        "to"
    )


    vendedor = op.get(
        "from"
    )



    extra = ""



    if hora:


        fecha = _fecha(
            op.get(
                "_event_date"
            )
        )


        if fecha:

            extra = (
                f"{fecha.strftime('%H:%M')} | "
            )



    if isinstance(
        comprador,
        dict,
    ):


        return (
            f"🟢 {extra}"
            f"{comprador.get('name')} ficha "
            f"{jugador} por {cantidad}"
        )



    if isinstance(
        vendedor,
        dict,
    ):


        return (
            f"🔴 {extra}"
            f"{vendedor.get('name')} vende "
            f"{jugador} por {cantidad}"
        )



    return None




# ==============================================================
# MERCADO COMPLETO
# ==============================================================


def obtener_mercado_completo(
    liga_id,
):


    historial = _CLIENT.get_full_market_history(
        liga_id
    )


    operaciones = _CLIENT.extract_operations(
        historial
    )


    jugadores = _mapa_jugadores()



    lineas = [

        "🔄 MERCADO COMPLETO",

        "━━━━━━━━━━━━━━━━━━━━",

        "",

    ]



    for op in operaciones:


        texto = _movimiento_texto(
            op,
            jugadores,
            False,
        )


        if texto:

            lineas.append(
                texto
            )



    if len(lineas) == 3:

        lineas.append(
            "Sin movimientos."
        )



    return "\n".join(
        lineas
    )





# ==============================================================
# MERCADO 24H
# ==============================================================


def obtener_mercado_24h(
    liga_id,
):


    historial = (
        _CLIENT.get_market_history_last_24h(
            liga_id
        )
    )


    operaciones = _CLIENT.extract_operations(
        historial
    )


    jugadores = _mapa_jugadores()



    lineas = [

        "⏱️ MERCADO — ÚLTIMAS 24 HORAS",

        "━━━━━━━━━━━━━━━━━━━━",

        "",

    ]



    for op in operaciones:


        texto = _movimiento_texto(
            op,
            jugadores,
            True,
        )


        if texto:

            lineas.append(
                texto
            )



    if len(lineas) == 3:

        lineas.append(
            "Sin movimientos."
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


    historial = _CLIENT.get_full_market_history(
        liga_id
    )


    return _CLIENT.calculate_market_report(
        historial
    )




def obtener_informe_detallado(
    liga_id,
):

    return obtener_informe(
        liga_id
    )