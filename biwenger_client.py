import logging
import time

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
# Cliente Biwenger
# ============================================================

class BiwengerClient:

    def __init__(self):

        # ----------------------------------------------------
        # Sesión API privada
        # ----------------------------------------------------

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 "
                    "Safari/537.36"
                ),
            }
        )

        # ----------------------------------------------------
        # Sesión API pública
        # ----------------------------------------------------

        self.public_session = requests.Session()

        self.public_session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Origin": "https://biwenger.as.com",
                "Referer": "https://biwenger.as.com/",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 "
                    "Safari/537.36"
                ),
            }
        )

        # ----------------------------------------------------
        # Estado de autenticación
        # ----------------------------------------------------

        self.token = None
        self.login_time = 0

        # ----------------------------------------------------
        # Contexto actual
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
        Establece el contexto de liga/usuario utilizado
        por la API privada.
        """

        if league_id is not None:
            self.league_id = league_id

        if user_id is not None:
            self.user_id = user_id

    # ========================================================
    # LOGIN
    # ========================================================

    def login(self):
        """
        Inicia sesión en Biwenger y guarda el token.

        El token se reutiliza durante una hora.
        """

        if (
            self.token
            and time.time() - self.login_time < 3600
        ):
            return self.token

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

        token = data.get("token")

        if not token:
            raise RuntimeError(
                "La respuesta de login de Biwenger "
                "no contiene 'token'."
            )

        self.token = token
        self.login_time = time.time()

        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
            }
        )

        return self.token

    # ========================================================
    # HEADERS API PRIVADA
    # ========================================================

    def _private_headers(self):
        """
        Construye los headers necesarios para la API privada.
        """

        self.login()

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

        if self.league_id is not None:
            headers["X-League"] = str(self.league_id)

        if self.user_id is not None:
            headers["X-User"] = str(self.user_id)

        return headers

    # ========================================================
    # GET API PRIVADA
    # ========================================================

    def get(
        self,
        endpoint,
        params=None,
    ):
        """
        GET contra la API privada de Biwenger.

        Los headers X-League y X-User se añaden
        automáticamente si existe contexto.
        """

        headers = self._private_headers()

        url = (
            endpoint
            if endpoint.startswith("http")
            else BASE_URL + endpoint
        )

        response = self.session.get(
            url,
            headers=headers,
            params=params,
            timeout=15,
        )

        if response.status_code == 401:

            logger.warning(
                "Token de Biwenger rechazado. "
                "Renovando sesión."
            )

            self.token = None
            self.login_time = 0

            headers = self._private_headers()

            response = self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=15,
            )

        response.raise_for_status()

        return response.json()

    # ========================================================
    # ACCOUNT
    # ========================================================

    def account(self):

        return self.get(
            "/account"
        )

    # ========================================================
    # LIGAS
    # ========================================================

    def leagues(self):

        data = self.account()

        account_data = data.get(
            "data",
            {},
        )

        return account_data.get(
            "leagues",
            [],
        )

    # ========================================================
    # USUARIO DE UNA LIGA
    # ========================================================

    def find_league_user(
        self,
        league_id,
    ):
        """
        Busca el usuario perteneciente a una liga.

        La respuesta esperada de /account contiene:

            leagues[
                {
                    "id": ...,
                    "user": {
                        "id": ...
                    }
                }
            ]
        """

        leagues = self.leagues()

        for liga in leagues:

            if int(liga.get("id")) == int(league_id):

                user = liga.get(
                    "user",
                    {},
                )

                user_id = user.get("id")

                if user_id is not None:
                    return user_id

        return None

    # ========================================================
    # LIGA
    # ========================================================

    def league(
        self,
        league_id,
    ):
        """
        Obtiene la información de una liga.
        """

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

        return self.get(
            f"/league/{league_id}"
        )

    # ========================================================
    # TABLÓN
    # ========================================================

    def board(
        self,
        league_id,
    ):
        """
        Obtiene el tablón actual de una liga.
        """

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

        return self.get(
            f"/league/{league_id}/board"
        )

    # ========================================================
    # HISTORIAL DEL TABLÓN
    # ========================================================

    def board_history(
        self,
        league_id,
        date=None,
        limit=100,
    ):
        """
        Obtiene movimientos del tablón.

        Parámetros:

            type=transfer,market
            limit=100

        Para paginar:

            date=<timestamp>
        """

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

    # ========================================================
    # PLANTILLAS DE LA LIGA
    # ========================================================

    def league_players(
        self,
        league_id,
    ):
        """
        Obtiene las plantillas actuales de todos
        los usuarios de una liga.

        Utiliza:

            /league/{league_id}?fields=users(players)

        """

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

        return self.get(
            f"/league/{league_id}",
            params={
                "fields": "users(players)",
            },
        )

    # ========================================================
    # JORNADAS - API PÚBLICA
    # ========================================================

    def rounds(
        self,
        score=2,
        lang="es",
        version=631,
    ):
        """
        Obtiene las jornadas de LaLiga desde la API pública.

        Endpoint:

            /rounds/la-liga

        Esta llamada NO utiliza el token de la cuenta.
        """

        params = {
            "score": score,
            "lang": lang,
            "v": version,
        }

        response = self.public_session.get(
            ROUNDS_URL,
            params=params,
            timeout=15,
        )

        if response.status_code == 403:

            logger.error(
                "Biwenger devolvió 403 para jornadas. "
                "URL=%s params=%s",
                ROUNDS_URL,
                params,
            )

            logger.error(
                "Respuesta Biwenger: %s",
                response.text[:1000],
            )

        response.raise_for_status()

        return response.json()

    # ========================================================
    # ALIAS EN ESPAÑOL
    # ========================================================

    def obtener_jornadas(
        self,
        score=2,
        lang="es",
        version=631,
    ):
        """
        Alias de rounds() para mantener compatibilidad
        con el resto del proyecto.
        """

        return self.rounds(
            score=score,
            lang=lang,
            version=version,
        )

    # ========================================================
    # JUGADORES - API PÚBLICA
    # ========================================================

    def players(self):
        """
        Obtiene los datos públicos de los jugadores
        de LaLiga.

        No utiliza la API privada ni el token.
        """

        params = {
            "lang": "es",
            "score": 2,
        }

        response = self.public_session.get(
            PLAYERS_URL,
            params=params,
            timeout=15,
        )

        if response.status_code == 403:

            logger.error(
                "Biwenger devolvió 403 para jugadores. "
                "URL=%s params=%s",
                PLAYERS_URL,
                params,
            )

            logger.error(
                "Respuesta Biwenger: %s",
                response.text[:1000],
            )

        response.raise_for_status()

        return response.json()

    # ========================================================
    # ALIAS
    # ========================================================

    def obtener_jugadores(self):

        return self.players()