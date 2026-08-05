import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BIWENGER_USER = os.getenv("BIWENGER_USER")
BIWENGER_PASSWORD = os.getenv("BIWENGER_PASSWORD")