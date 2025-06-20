from dotenv import load_dotenv
from os import getenv

load_dotenv()

# TG config
API_ID = int(getenv("API_ID"))
API_HASH = getenv("API_HASH")
SESSION_NAME = getenv("SESSION_NAME")

# Socket server conifg
HOST = getenv("HOST", "127.0.0.1")
PORT = int(getenv("PORT", "4375"))