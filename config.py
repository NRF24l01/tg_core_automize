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

# S3 config
S3_ENDPOINT = getenv("S3_ENDPOINT", "http://127.0.0.1:9000")
S3_USERNAME = getenv("S3_USERNAME")
S3_PASSWORD = getenv("S3_PASSWORD")
S3_BUCKET = getenv("S3_BUCKET")
SAVE_MEDIA = getenv("SAVE_MEDIA", "true").lower() in ("true", "1", "yes")

# Db config
TORTOISE_ORM = {
    "connections": {"default": "sqlite://db.sqlite3"},
    "apps": {
        "models": {
            "models": ["models", "aerich.models"],
            "default_connection": "default",
        }
    }
}