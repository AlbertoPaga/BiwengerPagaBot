import requests

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



    def set_context(
        self,
        league_id=None,
        user_id=None
    ):

        if league_id is not None:
            self.league_id = league_id

        if user_id is not None:
            self.user_id = user_id



    # --------------------------------------------------
    # LOGIN
    # --------------------------------------------------

    def login(self):

        print(
            "LOGIN USER:",
            BIWENGER_USERNAME
        )


        response = self.session.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": BIWENGER_USERNAME,
                "password": BIWENGER_PASSWORD,
            }
        )


        print(
            "LOGIN STATUS:",
            response.status_code
        )


        response.raise_for_status()


        data = response.json()


        self.token = data["token"]


        self.session.headers.update(
            {
                "Authorization":
                    f"Bearer {self.token}",

                "Accept":
                    "application/json",

                "Content-Type":
                    "application/json",
            }
        )


        # Guardar usuario automáticamente

        account = self.account()


        self.user_id = (
            account["data"]
            ["account"]
            ["id"]
        )


        print(
            "USER ID:",
            self.user_id
        )


        return data



    # --------------------------------------------------
    # REQUEST
    # --------------------------------------------------

    def get(
        self,
        endpoint
    ):


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
            headers=headers
        )


        self.debug(response)


        response.raise_for_status()


        return response.json()



    # --------------------------------------------------
    # DEBUG
    # --------------------------------------------------

    def debug(
        self,
        response
    ):

        print("===================")

        print(
            response.url
        )

        print(
            response.status_code
        )


        try:

            print(
                response.json()
            )

        except:

            print(
                response.text
            )


        print("===================")



    # --------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------

    def account(self):

        return self.get(
            "/account"
        )



    def leagues(self):

        data = self.account()

        return (
            data["data"]
            ["leagues"]
        )



    # --------------------------------------------------
    # LIGA
    # --------------------------------------------------

    def league(
        self,
        league_id
    ):


        self.set_context(
            league_id=league_id
        )


        return self.get(
            f"/league/{league_id}"
        )



    # --------------------------------------------------
    # TABLON
    # --------------------------------------------------

    def board(
        self,
        league_id
    ):


        self.set_context(
            league_id=league_id
        )


        return self.get(
            f"/league/{league_id}/board"
        )