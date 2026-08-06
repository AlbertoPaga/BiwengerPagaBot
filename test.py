import pybiwenger
from pybiwenger import LeagueAPI

from config import BIWENGER_USER, BIWENGER_PASSWORD

pybiwenger.authenticate(
    username=BIWENGER_USER,
    password=BIWENGER_PASSWORD
)

league = LeagueAPI()

print("OK")
print(league.account.leagues)