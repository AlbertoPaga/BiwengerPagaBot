import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from config import (
    BIWENGER_USERNAME,
    BIWENGER_PASSWORD,
)


logger = logging.getLogger("biwenger")


# ============================================================
# URLs
# ============================================================

BASE_URL = "https://biwenger.as.com/api/v2"

PUBLIC_BASE_URL = "https://cf.biwenger.com/api/v2"

PLAYERS_URL = (
    f"{PUBLIC_BASE_URL}/competitions/la-liga/data"
)

ROUNDS_URL = (
    f"{PUBLIC_BASE_URL}/rounds/la-liga"
)


# ============================================================
# Configuración
# ============================================================

LOGIN_TTL = 3600
REQUEST_TIMEOUT = 15

MADRID_TZ = ZoneInfo("Europe/Madrid")


# ============================================================
# Cliente
# ============================================================

class BiwengerClient:

    def __init__(self):

        # ----------------------------------------------------
        # Sesión API privada
        # ----------------------------------------------------

        self.session = requests.Session()

        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
        })


        # ----------------------------------------------------
        # Sesión API pública
        # ----------------------------------------------------

        self.public_session = requests.Session()

        self.public_session.headers.update({
            "Accept": (
                "application/json, "
                "text/plain, "
                "*/*"
            ),
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            ),
            "Referer": "https://biwenger.as.com/",
            "Origin": "https://biwenger.as.com",
        })


        # ----------------------------------------------------
        # Estado de autenticación
        # ----------------------------------------------------

        self.token = None
        self.login_time = 0


        # ----------------------------------------------------
        # Contexto de liga
        # ----------------------------------------------------

        self.league_id = None
        self.user_id = None


    # ========================================================
    # CONTEXTO
    # ========================================================

    def set_context(
        self,
        league_id=None,
        user_id=None,
    ):
        """
        Establece el contexto de una liga.

        X-League:
            ID de la liga.

        X-User:
            ID del usuario dentro de esa liga.
        """

        if league_id is not None:
            self.league_id = int(league_id)

        if user_id is not None:
            self.user_id = int(user_id)


    def clear_context(self):
        """
        Elimina el contexto actual de liga.
        """

        self.league_id = None
        self.user_id = None


    # ========================================================
    # LOGIN
    # ========================================================

    def login(self):
        """
        Inicia sesión contra la API privada de Biwenger.

        El token se reutiliza durante LOGIN_TTL segundos.
        """

        if (
            self.token
            and (
                time.time() - self.login_time
                < LOGIN_TTL
            )
        ):
            return self.token


        logger.info(
            "Iniciando sesión en Biwenger"
        )


        response = self.session.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": BIWENGER_USERNAME,
                "password": BIWENGER_PASSWORD,
            },
            timeout=REQUEST_TIMEOUT,
        )


        if not response.ok:

            logger.error(
                "Error login Biwenger: "
                "status=%s body=%s",
                response.status_code,
                response.text[:1000],
            )

            response.raise_for_status()


        data = response.json()


        token = data.get("token")

        if not token:

            raise ValueError(
                "La respuesta de login de Biwenger "
                "no contiene 'token'"
            )


        self.token = token
        self.login_time = time.time()


        self.session.headers.update({
            "Authorization": (
                f"Bearer {self.token}"
            ),
            "Accept": "application/json",
        })


        logger.info(
            "Login Biwenger correcto"
        )


        return self.token


    # ========================================================
    # REQUEST API PRIVADA
    # ========================================================

    def get(
        self,
        endpoint,
        params=None,
        use_context=True,
    ):
        """
        GET contra la API privada.

        Si use_context=True se añaden:

            X-League
            X-User
        """

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


        url = (
            endpoint
            if endpoint.startswith("http")
            else BASE_URL + endpoint
        )


        response = self.session.get(
            url,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )


        if not response.ok:

            logger.error(
                "Error API privada Biwenger: "
                "status=%s url=%s params=%s "
                "body=%s",
                response.status_code,
                response.url,
                params,
                response.text[:1000],
            )

            response.raise_for_status()


        return response.json()


    # ========================================================
    # ACCOUNT
    # ========================================================

    def account(self):
        """
        Obtiene la cuenta del usuario.

        /account no necesita X-League ni X-User.
        """

        return self.get(
            "/account",
            use_context=False,
        )


    # ========================================================
    # LIGAS
    # ========================================================

    def leagues(self):
        """
        Devuelve las ligas asociadas a la cuenta.
        """

        data = self.account()


        if not isinstance(data, dict):
            return []


        root = data.get(
            "data",
            {},
        )


        if not isinstance(root, dict):
            return []


        leagues = root.get(
            "leagues",
            [],
        )


        if not isinstance(leagues, list):
            return []


        return leagues


    def find_league_user(
        self,
        league_id,
    ):
        """
        Busca el user_id correspondiente a una liga.

        Se soportan las estructuras conocidas:

            user: {
                id: ...
            }

        o:

            user: 123

        y también:

            userId
            user_id
        """

        target = str(league_id)


        for liga in self.leagues():

            if not isinstance(
                liga,
                dict,
            ):
                continue


            if str(
                liga.get("id")
            ) != target:
                continue


            # ----------------------------------------------
            # user como objeto
            # ----------------------------------------------

            usuario = liga.get(
                "user"
            )


            if isinstance(
                usuario,
                dict,
            ):

                uid = usuario.get(
                    "id"
                )

                if uid is not None:
                    return int(uid)


            # ----------------------------------------------
            # user como ID
            # ----------------------------------------------

            if isinstance(
                usuario,
                (int, str),
            ):

                try:
                    return int(usuario)
                except (
                    TypeError,
                    ValueError,
                ):
                    pass


            # ----------------------------------------------
            # Otros formatos
            # ----------------------------------------------

            for key in (
                "userId",
                "user_id",
            ):

                uid = liga.get(
                    key
                )

                if uid is not None:

                    try:
                        return int(uid)
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass


            return None


        return None


    def prepare_context(
        self,
        league_id,
    ):
        """
        Prepara automáticamente:

            league_id
            user_id

        para las peticiones privadas de la liga.
        """

        league_id = int(
            league_id
        )


        user_id = self.find_league_user(
            league_id
        )


        if user_id is None:

            raise ValueError(
                "No se encontró el usuario "
                f"para la liga {league_id}"
            )


        self.set_context(
            league_id,
            user_id,
        )


        logger.debug(
            "Contexto Biwenger preparado: "
            "league=%s user=%s",
            self.league_id,
            self.user_id,
        )


        return {
            "league_id": self.league_id,
            "user_id": self.user_id,
        }


    # ========================================================
    # LEAGUE
    # ========================================================

    def league(
        self,
        league_id,
    ):
        """
        Obtiene la información completa de una liga.
        """

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
        )


    def league_members(
        self,
        league_id,
    ):
        """
        Alias de league().
        """

        return self.league(
            league_id
        )


    # ========================================================
    # BOARD
    # ========================================================

    def board(
        self,
        league_id,
    ):
        """
        Obtiene el tablón de una liga.
        """

        self.prepare_context(
            league_id
        )


        return self.get(
            f"/league/{self.league_id}/board"
        )


    # ========================================================
    # BOARD HISTORY
    # ========================================================

    def board_history(
        self,
        league_id,
        date=None,
        limit=100,
    ):
        """
        Obtiene movimientos del mercado/transferencias.

        La API utiliza:

            type=transfer,market
            limit=100

        y opcionalmente:

            date=<timestamp>
        """

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


    # ========================================================
    # HISTORIAL COMPLETO
    # ========================================================

    def get_full_market_history(
        self,
        league_id,
        limit=100,
        max_pages=100,
    ):
        """
        Descarga todo el historial disponible
        utilizando la paginación por date.
        """

        all_events = []

        current_date = None

        seen = set()


        for page in range(
            max_pages
        ):

            response = self.board_history(
                league_id,
                current_date,
                limit,
            )


            if not isinstance(
                response,
                dict,
            ):
                break


            data = response.get(
                "data",
                [],
            )


            if not isinstance(
                data,
                list,
            ):
                break


            if not data:
                break


            fechas = []


            for event in data:

                if not isinstance(
                    event,
                    dict,
                ):
                    continue


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


            antigua = min(
                fechas
            )


            if (
                current_date is not None
                and antigua >= current_date
            ):
                break


            current_date = (
                antigua - 1
            )


            if len(data) < limit:
                break


            logger.debug(
                "Página historial %s: "
                "%s eventos",
                page + 1,
                len(data),
            )


        all_events.sort(
            key=lambda event: event.get(
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


    # ========================================================
    # HISTORIAL ÚLTIMAS 24H
    # ========================================================

    def get_market_history_last_24h(
        self,
        league_id,
        limit=100,
        max_pages=20,
    ):
        """
        Obtiene las operaciones del día actual
        utilizando la zona horaria de Madrid.
        """

        ahora = datetime.now(
            MADRID_TZ
        )


        inicio_dia = datetime(
            ahora.year,
            ahora.month,
            ahora.day,
            0,
            0,
            0,
            tzinfo=MADRID_TZ,
        )


        desde = (
            inicio_dia.timestamp()
        )


        all_events = []

        current_date = None

        seen = set()


        for page in range(
            max_pages
        ):

            response = self.board_history(
                league_id,
                current_date,
                limit,
            )


            if not isinstance(
                response,
                dict,
            ):
                break


            data = response.get(
                "data",
                [],
            )


            if not isinstance(
                data,
                list,
            ):
                break


            if not data:
                break


            fechas = []


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


                key = (
                    event_date,
                    event.get("type"),
                    event.get("title"),
                )


                if key in seen:
                    continue


                seen.add(key)


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


            if (
                current_date is not None
                and antigua >= current_date
            ):
                break


            current_date = (
                antigua - 1
            )


            if len(data) < limit:
                break


        all_events.sort(
            key=lambda event: event.get(
                "date",
                0,
            ),
            reverse=True,
        )


        logger.info(
            "Historial del día actual: "
            "liga=%s fecha=%s eventos=%s",
            league_id,
            ahora.strftime(
                "%Y-%m-%d"
            ),
            len(all_events),
        )


        return {
            "status": 200,
            "data": all_events,
        }


    # ========================================================
    # OPERACIONES
    # ========================================================

    def extract_operations(
        self,
        history,
    ):
        """
        Extrae las operaciones individuales
        contenidas dentro de cada evento del board.
        """

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


                operation.update({
                    "_event_date": (
                        event.get("date")
                    ),
                    "_event_type": (
                        event.get("type")
                    ),
                    "_event_title": (
                        event.get(
                            "title",
                            "",
                        )
                    ),
                })


                operations.append(
                    operation
                )


        return operations


    # ========================================================
    # API PÚBLICA - JUGADORES
    # ========================================================

    def players(self):
        """
        Obtiene los jugadores de LaLiga.

        IMPORTANTE:

        Esta petición NO utiliza:

            Authorization
            X-League
            X-User

        porque pertenece a la API pública
        cf.biwenger.com.
        """

        params = {
            "lang": "es",
            "score": 2,
        }


        response = self.public_session.get(
            PLAYERS_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )


        if not response.ok:

            logger.error(
                "Error API pública jugadores: "
                "status=%s url=%s body=%s",
                response.status_code,
                response.url,
                response.text[:1000],
            )

            response.raise_for_status()


        data = response.json()


        logger.info(
            "Respuesta pública jugadores: "
            "tipo=%s",
            type(data).__name__,
        )


        return data


    # ========================================================
    # API PÚBLICA - JORNADAS
    # ========================================================

    def rounds(
        self,
        version=631,
        lang="es",
        score=2,
    ):
        """
        Obtiene los partidos/jornadas de LaLiga.

        Endpoint:

            /api/v2/rounds/la-liga

        La respuesta conocida de Biwenger tiene esta forma:

            {
                "data": {
                    "games": [
                        {
                            ...
                            "round": {
                                "id": 4899,
                                "name": "Jornada 1",
                                "short": "J1",
                                "part": 1
                            }
                        }
                    ]
                }
            }

        IMPORTANTE:

        Esta petición es pública.

        NO se utiliza el token de login.
        NO se utilizan X-League/X-User.
        """

        params = {
            "score": score,
            "lang": lang,
            "v": version,
        }


        response = self.public_session.get(
            ROUNDS_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )


        if not response.ok:

            logger.error(
                "Error API pública jornadas: "
                "status=%s url=%s",
                response.status_code,
                response.url,
            )

            logger.error(
                "Headers enviados: %s",
                dict(
                    self.public_session.headers
                ),
            )

            logger.error(
                "Respuesta Biwenger: %s",
                response.text[:2000],
            )


            response.raise_for_status()


        data = response.json()


        if not isinstance(
            data,
            dict,
        ):

            raise ValueError(
                "Respuesta de jornadas "
                "inesperada: "
                f"{type(data).__name__}"
            )


        root = data.get(
            "data",
            {},
        )


        if not isinstance(
            root,
            dict,
        ):

            raise ValueError(
                "Respuesta de jornadas: "
                "'data' no es un objeto"
            )


        games = root.get(
            "games",
            [],
        )


        if not isinstance(
            games,
            list,
        ):

            raise ValueError(
                "Respuesta de jornadas: "
                "'data.games' no es una lista"
            )


        logger.info(
            "Jornadas: recibidos %s partidos",
            len(games),
        )


        return data


    # ========================================================
    # OBTENER JORNADAS AGRUPADAS
    # ========================================================

    def get_rounds(
        self,
        version=631,
        lang="es",
        score=2,
    ):
        """
        Obtiene las jornadas agrupando los partidos
        por round.id.

        Devuelve:

            [
                {
                    "id": 4899,
                    "short": "J1",
                    "name": "Jornada 1",
                    "part": 1,
                    "games": [...]
                },
                ...
            ]
        """

        response = self.rounds(
            version=version,
            lang=lang,
            score=score,
        )


        root = response.get(
            "data",
            {},
        )


        games = root.get(
            "games",
            [],
        )


        rounds_by_id = {}


        for game in games:

            if not isinstance(
                game,
                dict,
            ):
                continue


            round_data = game.get(
                "round",
                {},
            )


            if not isinstance(
                round_data,
                dict,
            ):
                continue


            round_id = round_data.get(
                "id"
            )


            if round_id is None:
                continue


            key = str(
                round_id
            )


            if key not in rounds_by_id:

                rounds_by_id[key] = {
                    "id": round_data.get(
                        "id"
                    ),
                    "short": round_data.get(
                        "short",
                        "",
                    ),
                    "name": round_data.get(
                        "name",
                        "",
                    ),
                    "part": round_data.get(
                        "part"
                    ),
                    "games": [],
                }


            rounds_by_id[key][
                "games"
            ].append(
                game
            )


        rounds = list(
            rounds_by_id.values()
        )


        rounds.sort(
            key=self._round_first_game_timestamp
        )


        logger.info(
            "Jornadas reconstruidas: %s",
            len(rounds),
        )


        for jornada in rounds:

            logger.info(
                "Jornada %s (%s): %s partidos",
                jornada.get("id"),
                jornada.get("name"),
                len(
                    jornada.get(
                        "games",
                        [],
                    )
                ),
            )


        return rounds


    def get_round(
        self,
        round_id,
        version=631,
        lang="es",
        score=2,
    ):
        """
        Devuelve una jornada concreta.
        """

        target = str(
            round_id
        )


        rounds = self.get_rounds(
            version=version,
            lang=lang,
            score=score,
        )


        for jornada in rounds:

            if str(
                jornada.get("id")
            ) == target:

                return jornada


        return None


    # ========================================================
    # UTILIDAD FECHA PARTIDO
    # ========================================================

    @staticmethod
    def _round_first_game_timestamp(
        jornada,
    ):
        """
        Obtiene el timestamp del primer partido
        de una jornada para poder ordenarla.
        """

        timestamps = []


        games = jornada.get(
            "games",
            [],
        )


        if not isinstance(
            games,
            list,
        ):
            return float("inf")


        for game in games:

            if not isinstance(
                game,
                dict,
            ):
                continue


            timestamp = (
                BiwengerClient._game_timestamp(
                    game
                )
            )


            if timestamp is not None:
                timestamps.append(
                    timestamp
                )


        if timestamps:
            return min(
                timestamps
            )


        return float("inf")


    @staticmethod
    def _game_timestamp(
        game,
    ):
        """
        Intenta obtener la fecha de comienzo
        de un partido.
        """

        if not isinstance(
            game,
            dict,
        ):
            return None


        for key in (
            "date",
            "start",
            "startDate",
            "timestamp",
        ):

            value = game.get(
                key
            )


            if isinstance(
                value,
                (int, float),
            ):

                return float(
                    value
                )


            if isinstance(
                value,
                str,
            ):

                try:

                    return datetime.fromisoformat(
                        value.replace(
                            "Z",
                            "+00:00",
                        )
                    ).timestamp()

                except (
                    TypeError,
                    ValueError,
                ):
                    continue


        return None


# ============================================================
# Cliente global
# ============================================================

_CLIENT = BiwengerClient()