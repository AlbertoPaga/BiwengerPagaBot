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


    # --------------------------------------------------
    # LOGIN
    # --------------------------------------------------

    def login(self):

        print(
            "LOGIN USER:",
            BIWENGER_USERNAME
        )

        print(
            "PASSWORD LENGTH:",
            len(BIWENGER_PASSWORD)
        )


        response = self.session.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": BIWENGER_USERNAME,
                "password": BIWENGER_PASSWORD,
            },
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


        return data



    # --------------------------------------------------
    # REQUESTS
    # --------------------------------------------------

    def get(
        self,
        endpoint,
        headers=None,
        params=None
    ):


        final_headers = {}


        if headers:

            final_headers.update(
                headers
            )


        if self.league_id:

            final_headers[
                "X-League"
            ] = str(
                self.league_id
            )


        if self.user_id:

            final_headers[
                "X-User"
            ] = str(
                self.user_id
            )


        response = self.session.get(
            f"{BASE_URL}{endpoint}",
            headers=final_headers,
            params=params,
        )


        self.debug(response)


        response.raise_for_status()


        return response.json()



    def post(
        self,
        endpoint,
        payload=None
    ):

        response = self.session.post(
            f"{BASE_URL}{endpoint}",
            json=payload or {},
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

        print("==============================")

        print(
            "URL:",
            response.url
        )

        print(
            "STATUS:",
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


        print("==============================")



    # --------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------

    def account(self):

        return self.get(
            "/account"
        )



    # --------------------------------------------------
    # LIGAS
    # --------------------------------------------------

    def get_league_by_name(
        self,
        name
    ):


        account = self.account()


        for liga in account["data"]["leagues"]:


            if liga["name"] == name:

                return liga



        raise Exception(
            f"Liga {name} no encontrada"
        )



    def league(
        self,
        league_id
    ):

        return self.get(
            f"/league/{league_id}"
        )



    # --------------------------------------------------
    # DATOS
    # --------------------------------------------------

    def players(
        self
    ):

        return self.get(
            "/players"
        )


    def league_players(
        self,
        league_id
    ):

        return self.get(
            f"/league/{league_id}/players"
        )



    def league_user_players(
        self,
        league_id,
        user_id
    ):

        return self.get(
            f"/league/{league_id}/user/{user_id}/players"
        )



    def board(
        self,
        league_id
    ):

        return self.get(
            f"/league/{league_id}/board"
        )