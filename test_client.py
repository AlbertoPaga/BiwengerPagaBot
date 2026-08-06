import json

from biwenger_client import BiwengerClient

client = BiwengerClient()

print("Login...")
client.login()

print("\n========== ACCOUNT ==========")

account = client.account()

print(json.dumps(account, indent=2, ensure_ascii=False))

print("\n========== BUSCANDO LIGA ==========")

liga = client.get_league_by_name("Los más sucios")

print(json.dumps(liga, indent=2, ensure_ascii=False))

league_id = liga["id"]
user_id = liga["user"]["id"]
secret = liga["settings"]["secret"]

print("\nLeague ID :", league_id)
print("User ID   :", user_id)
print("Secret    :", secret)

print("\n========== PRUEBA 1 ==========")
print("/league/{id}")

try:
    datos = client.league(
        league_id,
        user_id
    )

    print(json.dumps(datos, indent=2, ensure_ascii=False))

except Exception as e:
    print(e)

print("\n========== PRUEBA 2 ==========")
print("/league?secret=")

try:
    datos = client.league_by_secret(secret)

    print(json.dumps(datos, indent=2, ensure_ascii=False))

except Exception as e:
    print(e)