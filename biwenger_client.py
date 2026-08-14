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

    def obtener_jornadas(
        self,
        start_id=4899,
        max_ids=100,
    ):
        """
        Obtiene las jornadas recorriendo los IDs consecutivos
        de Biwenger.

        Las jornadas normales y aplazadas pueden tener IDs
        diferentes, pero mantienen el mismo short.
        """

        jornadas = []
        ids_vistos = set()

        logger.info(
            "Obteniendo jornadas recorriendo IDs desde %s",
            start_id,
        )

        for offset in range(max_ids):

            round_id = start_id + offset

            if round_id in ids_vistos:
                continue

            ids_vistos.add(round_id)

            try:
                response = self.public_session.get(
                    f"{ROUNDS_URL}/{round_id}",
                    params={
                        "score": 2,
                        "lang": "es",
                        "v": 631,
                    },
                    timeout=15,
                )

                if response.status_code == 404:
                    logger.info(
                        "ID %s no existe. Fin de búsqueda.",
                        round_id,
                    )
                    break

                response.raise_for_status()

                data = response.json()

            except Exception as exc:
                logger.warning(
                    "Error obteniendo jornada ID %s: %s",
                    round_id,
                    exc,
                )
                continue

            if not isinstance(data, dict):
                logger.warning(
                    "Respuesta inesperada para jornada %s: %s",
                    round_id,
                    type(data).__name__,
                )
                continue

            root = data.get(
                "data",
                data,
            )

            if not isinstance(root, dict):
                continue

            short = root.get("short")
            name = root.get("name")

            if short is None:
                short = data.get("short")

            if name is None:
                name = data.get("name")

            if not short:
                logger.warning(
                    "ID %s sin short. Keys=%s",
                    round_id,
                    list(root.keys()),
                )
                continue

            short = str(short).strip()

            if name is None:
                name = f"Jornada {short}"

            name = str(name).strip()

            games = root.get(
                "games",
                [],
            )

            if not isinstance(games, list):
                games = []

            jornada = {
                "id": round_id,
                "short": short,
                "name": name,
                "games": games,
                "data": data,
            }

            jornadas.append(jornada)

            logger.info(
                "Jornada encontrada: id=%s short=%s name=%s games=%s",
                round_id,
                short,
                name,
                len(games),
            )

        jornadas.sort(
            key=lambda j: (
                j["id"],
            )
        )

        logger.warning(
            "JORNADAS ENCONTRADAS: %s",
            [
                (
                    j["id"],
                    j["name"],
                    j["short"],
                    len(j["games"]),
                )
                for j in jornadas
            ],
        )

        return jornadas

    def obtener_jornada_actual(self):
        """
        Obtiene únicamente la jornada actual de Biwenger.
        """

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
            logger.warning(
                "Respuesta inesperada para jornada actual: %s",
                type(data).__name__,
            )
            return None

        root = data.get(
            "data",
            data,
        )

        if not isinstance(root, dict):
            logger.warning(
                "Datos inesperados para jornada actual"
            )
            return None

        short = root.get(
            "short"
        )

        name = root.get(
            "name"
        )

        if short is None:
            short = data.get(
                "short"
            )

        if name is None:
            name = data.get(
                "name"
            )

        if not short:
            logger.warning(
                "La jornada actual no contiene short. Keys=%s",
                list(root.keys()),
            )
            return None

        short = str(
            short
        ).strip()

        if name is None:
            name = f"Jornada {short}"

        name = str(
            name
        ).strip()

        games = root.get(
            "games",
            [],
        )

        if not isinstance(
            games,
            list,
        ):
            games = []

        jornada = {
            "id": root.get(
                "id"
            ),
            "short": short,
            "name": name,
            "games": games,
            "data": data,
        }

        logger.info(
            "Jornada actual: id=%s short=%s name=%s games=%s",
            jornada["id"],
            jornada["short"],
            jornada["name"],
            len(jornada["games"]),
        )

        return jornada