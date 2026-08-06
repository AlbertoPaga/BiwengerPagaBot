import requests

from config import BIWENGER_USER, BIWENGER_PASSWORD


BASE_URL = "https://biwenger.as.com/api/v2"


class BiwengerClient:

    def __init__(self):

        self.session = requests.Session()
        self.token = None


    # ------------------------------------------------------------------
    # LOGIN
    # ------------------------------------------------------------------

    def login(self):

        response = self.session.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": BIWENGER_USER,
                "password": BIWENGER_PASSWORD,
            },
        )

        response.raise_for_status()

        data = response.json()

        self.token = data["token"]

        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        return data



    # ------------------------------------------------------------------
    # REQUESTS
    # ------------------------------------------------------------------

    def get(
        self,
        endpoint,
        headers=None,
        params=None
    ):

        response = self.session.get(
            f"{BASE_URL}{endpoint}",
            headers=headers,
            params=params,
        )

        self._debug(response)

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

        self._debug(response)

        response.raise_for_status()

        return response.json()



    def put(
        self,
        endpoint,
        payload=None
    ):

        response = self.session.put(
            f"{BASE_URL}{endpoint}",
            json=payload or {},
        )

        self._debug(response)

        response.raise_for_status()

        return response.json()



    def delete(
        self,
        endpoint
    ):

        response = self.session.delete(
            f"{BASE_URL}{endpoint}",
        )

        self._debug(response)

        response.raise_for_status()

        return response.json()



    # ------------------------------------------------------------------
    # DEBUG
    # ------------------------------------------------------------------

    def _debug(
        self,
        response
    ):

        print("\n==============================")
        print("URL    :", response.url)
        print("STATUS :", response.status_code)

        try:
            print(response.json())

        except Exception:
            print(response.text)

        print("==============================\n")



    # ------------------------------------------------------------------
    # ACCOUNT
    # ------------------------------------------------------------------

    def account(self):

        return self.get(
            "/account"
        )



    # ------------------------------------------------------------------
    # LEAGUES
    # ------------------------------------------------------------------

    def get_league_by_name(
        self,
        league_name
    ):

        account = self.account()

        for league in account["data"]["leagues"]:

            if league["name"] == league_name:

                return league


        raise Exception(
            f"Liga '{league_name}' no encontrada"
        )



    def league(
        self,
        league_id
    ):

        return self.get(
            f"/league/{league_id}"
        )



    def league_by_secret(
        self,
        secret
    ):

        return self.get(
            "/league",
            params={
                "secret": secret
            },
        )



    # ------------------------------------------------------------------
    # ENDPOINTS GENERALES
    # ------------------------------------------------------------------

    def market(self):

        return self.get(
            "/market"
        )



    def players(self):

        return self.get(
            "/players"
        )



    def squad(self):

        return self.get(
            "/squad"
        )



    def team(self):

        return self.get(
            "/team"
        )



    def user(self):

        return self.get(
            "/user"
        )



    def user_players(
        self,
        user_id
    ):

        return self.get(
            f"/user/{user_id}/players"
        )



    # ------------------------------------------------------------------
    # ENDPOINTS DE LIGA
    # ------------------------------------------------------------------

    def league_market(
        self,
        league_id
    ):

        return self.get(
            f"/league/{league_id}/market"
        )



    def league_players(
        self,
        league_id
    ):

        return self.get(
            f"/league/{league_id}/players"
        )



    def league_team(
        self,
        league_id
    ):

        return self.get(
            f"/league/{league_id}/team"
        )



    def league_user(
        self,
        league_id,
        user_id
    ):

        return self.get(
            f"/league/{league_id}/user/{user_id}"
        )



    def league_user_players(
        self,
        league_id,
        user_id
    ):

        return self.get(
            f"/league/{league_id}/user/{user_id}/players"
        )



    def league_user_team(
        self,
        league_id,
        user_id
    ):

        return self.get(
            f"/league/{league_id}/user/{user_id}/team"
        )



    def league_user_market(
        self,
        league_id,
        user_id
    ):

        return self.get(
            f"/league/{league_id}/user/{user_id}/market"
        )