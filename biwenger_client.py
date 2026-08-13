import time
import logging
import requests

from config import (
    BIWENGER_USERNAME,
    BIWENGER_PASSWORD,
)


BASE_URL = "https://biwenger.as.com/api/v2"

PLAYERS_URL = (
    "https://cf.biwenger.com/api/v2/"
    "competitions/la-liga/data"
)

ROUNDS_URL = (
    "https://cf.biwenger.com/api/v2/"
    "rounds/la-liga"
)


class BiwengerClient:

    def __init__(self):

        # ---------------------------------------------------------
        # API privada de Biwenger
        # ---------------------------------------------------------

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                ),
            }
        )

        # ---------------------------------------------------------
        # API pública
        # ---------------------------------------------------------

        self.public_session = requests.Session()

        self.public_session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "es-ES,es;q=0.9",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                ),
                "Referer": "https://biwenger.as.com/",
                "Origin": "https://biwenger.as.com",
            }
        )

        self.token = None
        self.league_id = None
        self.user_id = None
        self.login_time = 0


    # =============================================================
    # CONTEXTO
    # =============================================================

    def set_context(
        self,
        league_id=None,
        user_id=None,
    ):

        if league_id is not None:
            self.league_id = int(league_id)

        if user_id is not None:
            self.user_id = int(user_id)


    def clear_context(self):

        self.league_id = None
        self.user_id = None


    # =============================================================
    # LOGIN
    # =============================================================

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


    # =============================================================
    # GET API PRIVADA
    # =============================================================

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


    # =============================================================
    # CUENTA
    # =============================================================

    def account(self):

        return self.get(
            "/account",
            use_context=False,
        )


    # =============================================================
    # LIGAS
    # =============================================================

    def leagues(self):

        data = self.account()

        if not isinstance(data, dict):
            return []

        root = data.get("data", {})

        if not isinstance(root, dict):
            return []

        leagues = root.get("leagues", [])

        if not isinstance(leagues, list):
            return []

        return leagues


    def find_league_user(
        self,
        league_id,
    ):

        target = str(league_id)

        for liga in self.leagues():

            if not isinstance(liga, dict):
                continue

            if str(liga.get("id")) != target:
                continue

            usuario = liga.get("user")

            if isinstance(usuario, dict):

                user_id = usuario.get("id")

                if user_id is not None:
                    return int(user_id)

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

            for key in (
                "userId",
                "user_id",
            ):

                user_id = liga.get(key)

                if user_id is not None:
                    return int(user_id)

            return None

        return None


    def prepare_context(
        self,
        league_id,
    ):

        league_id = int(league_id)

        user_id = self.find_league_user(
            league_id
        )

        if user_id is None:
            raise ValueError(
                f"No se encontró el usuario "
                f"para la liga {league_id}"
            )

        self.set_context(
            league_id=league_id,
            user_id=user_id,
        )

        return {
            "league_id": self.league_id,
            "user_id": self.user_id,
        }


    # =============================================================
    # LIGA
    # =============================================================

    def league(
        self,
        league_id,
    ):

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

        return self.league(
            league_id
        )


    # =============================================================
    # BOARD
    # =============================================================

    def board(
        self,
        league_id,
    ):

        self.prepare_context(
            league_id
        )

        return self.get(
            f"/league/{self.league_id}/board"
        )


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


    # =============================================================
    # HISTORIAL COMPLETO
    # =============================================================

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

                event_date = event.get("date")

                if isinstance(
                    event_date,
                    (int, float),
                ):
                    fechas.append(event_date)

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

        return {
            "status": 200,
            "data": all_events,
        }


    # =============================================================
    # PLANTILLAS
    # =============================================================

    def league_players(
        self,
        league_id,
    ):

        self.prepare_context(
            league_id
        )

        return self.get(
            f"/league/{self.league_id}",
            params={
                "fields": "users(players)"
            },
        )


    # =============================================================
    # JUGADORES - API PÚBLICA
    # =============================================================

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


    # =============================================================
    # JORNADAS - API PÚBLICA
    # =============================================================

        def obtener_jornadas(self):
        """
        Obtiene todas las jornadas de LaLiga.

        Primero consulta:

            /rounds/la-liga

        para obtener los IDs de las jornadas.

        Después consulta cada jornada individualmente:

            /rounds/la-liga/{id}

        Esto es necesario porque la respuesta general no contiene
        necesariamente todos los partidos de todas las jornadas.

        El campo "short" identifica la jornada deportiva (J1, J2...)
        y el "id" identifica la instancia concreta de la jornada.

        Por tanto, una jornada aplazada puede tener:

            id=4899 -> short=J1
            id=4937 -> short=J1

        y deben conservarse ambas.
        """

        logger = logging.getLogger(__name__)

        # ---------------------------------------------------------
        # 1. PETICIÓN GENERAL
        # ---------------------------------------------------------

        response = self.public_session.get(
            ROUNDS_URL,
            params={
                "score": 2,
                "lang": "es",
                "v": 631,
            },
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError(
                "Respuesta inesperada de la API de jornadas"
            )

        logger.info(
            "JORNADAS: respuesta general recibida: tipo=%s",
            type(data).__name__,
        )

        # ---------------------------------------------------------
        # 2. EXTRAER LOS IDs DE LAS JORNADAS
        # ---------------------------------------------------------

        root = data.get("data", {})

        if not isinstance(root, dict):
            root = {}

        games = root.get("games", [])

        if not isinstance(games, list):
            games = []

        logger.warning(
            "JORNADAS: respuesta general contiene %s games",
            len(games),
        )

        jornadas_ids = {}

        for game in games:

            if not isinstance(game, dict):
                continue

            round_data = game.get("round")

            if not isinstance(round_data, dict):
                continue

            round_id = round_data.get("id")

            if round_id is None:
                continue

            try:
                round_id = int(round_id)
            except (
                TypeError,
                ValueError,
            ):
                continue

            jornadas_ids[round_id] = {
                "id": round_id,
                "name": round_data.get(
                    "name",
                    f"Jornada {round_id}",
                ),
                "short": round_data.get(
                    "short",
                    "?",
                ),
                "part": round_data.get(
                    "part"
                ),
            }

        logger.warning(
            "JORNADAS: IDs encontrados en respuesta general: %s",
            sorted(jornadas_ids.keys()),
        )

        # ---------------------------------------------------------
        # 3. SI LA RESPUESTA GENERAL NO TRAE IDs,
        #    NO PODEMOS CONTINUAR
        # ---------------------------------------------------------

        if not jornadas_ids:
            logger.error(
                "JORNADAS: no se encontraron IDs de jornadas"
            )

            return []

        # ---------------------------------------------------------
        # 4. CONSULTAR CADA JORNADA POR SU ID
        # ---------------------------------------------------------

        jornadas = []

        for round_id in sorted(jornadas_ids.keys()):

            meta = jornadas_ids[round_id]

            logger.info(
                "JORNADAS: consultando jornada "
                "id=%s short=%s name=%s",
                round_id,
                meta.get("short"),
                meta.get("name"),
            )

            try:

                round_response = self.public_session.get(
                    f"{ROUNDS_URL}/{round_id}",
                    params={
                        "score": 2,
                        "lang": "es",
                        "v": 631,
                    },
                    timeout=15,
                )

                round_response.raise_for_status()

                round_data = round_response.json()

            except Exception as exc:

                logger.exception(
                    "JORNADAS: error consultando "
                    "id=%s: %s",
                    round_id,
                    exc,
                )

                continue

            # -----------------------------------------------------
            # 5. NORMALIZAR LA RESPUESTA
            # -----------------------------------------------------

            if not isinstance(round_data, dict):
                logger.warning(
                    "JORNADAS: id=%s devuelve tipo inesperado: %s",
                    round_id,
                    type(round_data).__name__,
                )

                continue

            jornada_root = round_data.get(
                "data",
                {}
            )

            if not isinstance(
                jornada_root,
                dict,
            ):
                jornada_root = {}

            jornada_games = jornada_root.get(
                "games",
                []
            )

            if not isinstance(
                jornada_games,
                list,
            ):
                jornada_games = []

            # -----------------------------------------------------
            # 6. ASEGURAR LOS DATOS DE LA JORNADA
            # -----------------------------------------------------

            jornada = dict(meta)

            jornada["games"] = jornada_games

            # La respuesta individual puede traer información
            # más precisa de la jornada. La aprovechamos.
            response_round = jornada_root.get(
                "round"
            )

            if isinstance(
                response_round,
                dict,
            ):

                if response_round.get("id") is not None:
                    try:
                        jornada["id"] = int(
                            response_round.get("id")
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

                if response_round.get("name"):
                    jornada["name"] = (
                        response_round.get("name")
                    )

                if response_round.get("short"):
                    jornada["short"] = (
                        response_round.get("short")
                    )

                if response_round.get("part") is not None:
                    jornada["part"] = (
                        response_round.get("part")
                    )

            jornadas.append(jornada)

            logger.info(
                "JORNADAS: id=%s short=%s -> %s partidos",
                jornada.get("id"),
                jornada.get("short"),
                len(jornada_games),
            )

        # ---------------------------------------------------------
        # 7. ORDENAR
        # ---------------------------------------------------------

        jornadas.sort(
            key=lambda jornada: (
                int(
                    jornada.get(
                        "id",
                        0,
                    )
                ),
            )
        )

        logger.warning(
            "JORNADAS: TOTAL JORNADAS CARGADAS = %s",
            len(jornadas),
        )

        logger.warning(
            "JORNADAS: RESUMEN = %s",
            [
                (
                    jornada.get("id"),
                    jornada.get("name"),
                    jornada.get("short"),
                    len(
                        jornada.get(
                            "games",
                            [],
                        )
                    ),
                )
                for jornada in jornadas
            ],
        )

        return jornadas