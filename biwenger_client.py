import requests
import time

from config import (
    BIWENGER_USERNAME,
    BIWENGER_PASSWORD,
)


BASE_URL = "https://biwenger.as.com/api/v2"


class BiwengerClient:


    def __init__(self):

        self.session = requests.Session()

        self.token = None

        self.league_id = None

        self.user_id = None

        self.login_time = 0



    def set_context(
        self,
        league_id=None,
        user_id=None
    ):

        if league_id:
            self.league_id = league_id

        if user_id:
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
        endpoint
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


        self.set_context(
            league_id,
            user_id
        )


        return self.get(
            f"/league/{league_id}/board"
        )



    def players(self):

        """
        Obtiene jugadores autenticado.
        """

        self.login()


        response = self.session.get(
            "https://cf.biwenger.com/api/v2/competitions/la-liga/data",
            params={
                "lang": "es",
                "score": 2
            },
            timeout=15
        )


        response.raise_for_status()


        return response.json()