import os
from dotenv import load_dotenv


load_dotenv()


TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN"
)


BIWENGER_USERNAME = os.getenv(
    "BIWENGER_USERNAME"
)


BIWENGER_PASSWORD = os.getenv(
    "BIWENGER_PASSWORD"
)