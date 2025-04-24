import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("7605997710:AAFEA7cgAmx34sC8MXzHIFOWgy-Gk4UsHCc")
MONGO_URI = os.getenv("mongodb+srv://soniji:chaloji@cluster0.i5zy74f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
ADMIN_CHAT_ID = int(os.getenv("1938030055"))
PORT = int(os.getenv("PORT", 5000))
WEB_APP_URL = os.getenv("WEB_APP_URL", f"http://116.203.92.20:{PORT}")
