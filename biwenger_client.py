```python
import requests
import time

from config import (
    BIWENGER_USERNAME,
    BIWENGER_PASSWORD,
)


BASE_URL = "https://biwenger.as.com/api/v2"

PLAYERS_URL = (
    "https://cf.biwenger.com/api/v2/"
    "competitions/la-liga/data"
)


class BiwengerClient:


    def __init__(self):

        # API privada
        self.session = requests.Session()


        # API pública jugadores
        self.public_session = requests.Session()


        self.public_session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        )


        self.token = None

        self.league_id = None

        self.user_id = None

        self.login_time = 0



    def set_context(
        self,
        league_id=None,
        user_id=None
    ):

        if league_id is not None:

            self.league_id = league_id


        if user_id is not None:

            self.user_id = user_id



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
                "password": BIWENGER_PASSWORD
            },
            timeout=15
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
                    "application/json"
            }
        )


        return data



    def get(
        self,
        endpoint,
        params=None
    ):

        """
        Realiza una petición GET a la API privada
        de Biwenger.

        params permite enviar parámetros de consulta,
        por ejemplo:

            params={
                "type": "transfer,market",
                "limit": 100,
                "date": 1234567890
            }

        Los headers X-League y X-User se añaden
        automáticamente cuando existe contexto de liga.
        """


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
            timeout=15
        )


        response.raise_for_status()


        return response.json()



    def account(self):

        return self.get(
            "/account"
        )



    def leagues(self):

        data = self.account()


        return data["data"]["leagues"]



    def find_league_user(
        self,
        league_id
    ):

        leagues = self.leagues()


        for liga in leagues:

            if liga["id"] == league_id:

                return liga["user"]["id"]


        return None



    def league(
        self,
        league_id
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
            user_id
        )


        return self.get(
            f"/league/{league_id}"
        )



    def board(
        self,
        league_id
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
            user_id
        )


        return self.get(
            f"/league/{league_id}/board"
        )



    def league_players(
        self,
        league_id
    ):

        """
        Obtiene las plantillas actuales de todos
        los usuarios de una liga.

        La API devuelve:

            users[
                {
                    players: [
                        {"id": ...},
                        ...
                    ]
                }
            ]

        Se utilizan los headers X-League y X-User
        porque esta petición los requiere.
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
            league_id,
            user_id
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
                str(self.user_id)
        }


        response = self.session.get(
            f"{BASE_URL}/league/{league_id}",
            headers=headers,
            params={
                "fields":
                    "users(players)"
            },
            timeout=15
        )


        response.raise_for_status()


        return response.json()



    def players(self):

        """
        Obtiene los datos públicos de los jugadores
        de LaLiga.

        Esta petición NO utiliza la API privada
        ni el token de autenticación.
        """


        response = self.public_session.get(
            PLAYERS_URL,
            params={
                "lang": "es",
                "score": 2
            },
            timeout=15
        )


        response.raise_for_status()


        return response.json()
```
