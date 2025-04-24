import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
PORT = int(os.getenv("PORT", 7070))
WEB_APP_URL = os.getenv("WEB_APP_URL", f"http://localhost:{PORT}")
