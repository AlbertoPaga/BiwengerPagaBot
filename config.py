import os

from dotenv import load_dotenv


load_dotenv()



def obtener_variable(nombre):

    valor = os.getenv(
        nombre
    )

    if not valor:

        raise RuntimeError(
            f"Falta la variable de entorno: {nombre}"
        )

    return valor



TELEGRAM_TOKEN = obtener_variable(
    "TELEGRAM_TOKEN"
)


BIWENGER_USERNAME = obtener_variable(
    "BIWENGER_USERNAME"
)


BIWENGER_PASSWORD = obtener_variable(
    "BIWENGER_PASSWORD"
)