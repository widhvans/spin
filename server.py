from flask import Flask, request, jsonify, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import logging
import os
import random
import requests
from database import Database
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, WEB_APP_URL, PORT
import uuid
import asyncio
from threading import Thread
import gunicorn.app.base
from gunicorn.arbiter import Arbiter

# Initialize Flask app
app = Flask(__name__, static_folder="static")

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize MongoDB
db = Database()

# Function to get public IP
def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        return response.json()['ip']
    except Exception as e:
        logger.error(f"Failed to get public IP: {e}")
        return os.getenv("VPS_PUBLIC_IP", "YOUR_VPS_PUBLIC_IP")  # Fallback to .env or manual input

# Update .env with WEB_APP_URL
def update_web_app_url():
    public_ip = get_public_ip()
    web_app_url = f"http://{public_ip}:{PORT}"
    with open(".env", "r") as f:
        lines = f.readlines()
    with open(".env", "w") as f:
        found = False
        for line in lines:
            if line.startswith("WEB_APP_URL="):
                f.write(f"WEB_APP_URL={web_app_url}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"\nWEB_APP_URL={web_app_url}\n")
    os.environ["WEB_APP_URL"] = web_app_url
    logger.info(f"Set WEB_APP_URL to {web_app_url}")
    return web_app_url

# Serve static files (Mini App)
@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# API endpoints
@app.route('/api/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = db.get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "user_id": user["user_id"],
        "username": user["username"],
        "balance": user["balance"],
        "spins_left": user["spins_left"],
        "referrals": user["referrals"],
        "referral_code": user["referral_code"],
        "referral_earnings": user["referral_earnings"],
        "last_spin_date": user["last_spin_date"]
    })

@app.route('/api/spin/<int:user_id>', methods=['POST'])
def perform_spin(user_id):
    user = db.get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user["spins_left"] <= 0:
        return jsonify({"error": "No spins left"}), 400

    rewards = [10, 20, 30, 50, 0]
    weights = [0.4, 0.3, 0.2, 0.05, 0.05]
    reward = random.choices(rewards, weights=weights, k=1)[0]

    db.update_spin(user_id, reward)
    user = db.get_user(user_id)
    return jsonify({
        "reward": reward,
        "spins_left": user["spins_left"],
        "balance": user["balance"]
    })

@app.route('/api/withdraw/<int:user_id>', methods=['POST'])
def request_withdrawal(user_id):
    user = db.get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if len(user["referrals"]) < 15 or user["balance"] < 100:
        return jsonify({"error": "Need 15 referrals and ₹100 balance"}), 400

    data = request.json
    upi_details = data.get("upi_details")
    if not upi_details:
        return jsonify({"error": "UPI details required"}), 400

    db.log_withdrawal_request(user_id, upi_details, user["balance"])
    # Notify admin (handled via bot)
    return jsonify({"message": "Withdrawal request sent"})

# Telegram bot logic
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    referral_code = str(uuid.uuid4())[:8]

    if not db.get_user(user_id):
        db.create_user(user_id, username, referral_code)

    keyboard = [
        [InlineKeyboardButton("🎰 Launch Spin & Win Mini App", web_app={"url": WEB_APP_URL})],
        [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")],
        [InlineKeyboardButton("👥 Refer Friends", callback_data="refer")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"Welcome, {username}! 🎉\n"
        "Launch the Spin & Win Mini App to play and earn rewards! "
        "You get 3 free spins daily. Invite friends to unlock more spins and withdrawals! 🚀"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "dashboard":
        await show_dashboard(query, user_id)
    elif data == "refer":
        await show_referral(query, user_id)
    elif data == "withdraw":
        await initiate_withdrawal(query, user_id)
    elif data == "confirm_withdrawal":
        await context.bot.send_message(user_id, "Please enter your UPI ID and Name (e.g., name@upi):")
        context.user_data["awaiting_withdrawal"] = True
    elif data == "back":
        await show_main_menu(query)

async def show_dashboard(query, user_id):
    user = db.get_user(user_id)
    balance = user.get("balance", 0)
    spins_left = user.get("spins_left", 0)
    referrals = len(user.get("referrals", []))
    referral_earnings = user.get("referral_earnings", 0)

    message = (
        f"📊 *Your Dashboard* 📊\n"
        f"💰 Balance: ₹{balance}\n"
        f"🎰 Spins Left: {spins_left}\n"
        f"👥 Referrals: ${referrals}/15\n"
        f"🎁 Referral Earnings: ₹{referral_earnings}\n"
        f"{'✅ Ready to withdraw!' if referrals >= 15 and balance >= 100 else '🔒 Need 15 referrals and ₹100 to withdraw'}"
    )
    keyboard = [
        [InlineKeyboardButton("🎰 Launch Mini App", web_app={"url": WEB_APP_URL})],
        [InlineKeyboardButton("🏠 Home", callback_data="back")]
    ]
    await query.message.reply_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_referral(query, user_id):
    user = db.get_user(user_id)
    referral_code = user.get("referral_code", "")
    referral_link = f"https://t.me/{context.bot.username}?start={referral_code}"
    referrals = len(user.get("referrals", []))

    message = (
        f"👥 *Invite Friends & Earn!*\n"
        f"Share your referral link below and earn 1 spin per referral!\n"
        f"📎 Referral Link: `{referral_link}`\n"
        f"👥 Current Referrals: ${referrals}/15\n"
        f"💡 *Note*: You need 15 referrals to unlock ₹100 withdrawal."
    )
    keyboard = [
        [InlineKeyboardButton("🎰 Launch Mini App", web_app={"url": WEB_APP_URL})],
        [InlineKeyboardButton("🏠 Home", callback_data="back")]
    ]
    await query.message.reply_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def initiate_withdrawal(query, user_id):
    user = db.get_user(user_id)
    balance = user.get("balance", 0)
    referrals = len(user.get("referrals", []))

    if referrals < 15 or balance < 100:
        await query.message.reply_text(
            "🔒 You need at least 15 referrals and ₹100 balance to withdraw!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥 Refer", callback_data="refer")]])
        )
        return

    keyboard = [
        [InlineKeyboardButton("💸 Confirm Withdrawal", callback_data="confirm_withdrawal")],
        [InlineKeyboardButton("🏠 Home", callback_data="back")]
    ]
    await query.message.reply_text(
        f"💸 Your balance: ₹{balance}\nClick below to proceed with withdrawal.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_withdrawal_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_withdrawal"):
        return

    user_id = update.effective_user.id
    user = db.get_user(user_id)
    upi_details = update.message.text
    username = user.get("username", "Unknown")
    balance = user.get("balance", 0)

    admin_message = (
        f"💸 *New Withdrawal Request*\n"
        f"User ID: {user_id}\n"
        f"Username: {username}\n"
        f"UPI Details: {upi_details}\n"
        f"Amount: ₹{balance}\n"
        f"Action: /confirm_{user_id} or /reject_{user_id}"
    )
    await context.bot.send_message(ADMIN_CHAT_ID, admin_message, parse_mode="Markdown")

    await update.message.reply_text(
        "✅ Your withdrawal request has been sent to the admin. You'll be notified once processed!"
    )
    context.user_data["awaiting_withdrawal"] = False
    db.log_withdrawal_request(user_id, upi_details, balance)

async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    command = update.message.text
    if command.startswith("/confirm_"):
        user_id = int(command.split("_")[1])
        user = db.get_user(user_id)
        if not user:
            await update.message.reply_text("User not found!")
            return

        db.confirm_withdrawal(user_id)
        await context.bot.send_message(
            user_id,
            "🎉 Your withdrawal has been processed successfully! Check your account."
        )
        await update.message.reply_text(f"Withdrawal for user {user_id} confirmed!")

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    command = update.message.text
    if command.startswith("/reject_"):
        user_id = int(command.split("_")[1])
        user = db.get_user(user_id)
        if not user:
            await update.message.reply_text("User not found!")
            return

        db.reject_withdrawal(user_id)
        await context.bot.send_message(
            user_id,
            "❌ Your withdrawal request was rejected. Please contact support."
        )
        await update.message.reply_text(f"Withdrawal for user {user_id} rejected!")

async def show_main_menu(query):
    keyboard = [
        [InlineKeyboardButton("🎰 Launch Spin & Win Mini App", web_app={"url": WEB_APP_URL})],
        [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")],
        [InlineKeyboardButton("👥 Refer Friends", callback_data="refer")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("🏠 Welcome back! Choose an option:", reply_markup=reply_markup)

async def referral_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    if args and args[0]:
        referral_code = args[0]
        referrer = db.get_user_by_referral_code(referral_code)
        if referrer and referrer["user_id"] != user_id:
            db.add_referral(referrer["user_id"], user_id)
            db.create_user(user_id, username, str(uuid.uuid4())[:8])
            await update.message.reply_text(
                f"🎉 You've joined via {referrer['username']}'s referral! Launch the Mini App to start spinning!"
            )
        else:
            await update.message.reply_text("Invalid or self-referral link!")
    else:
        await start(update, context)

# Gunicorn application class
class StandaloneGunicornApplication(gunicorn.app.base.BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        for key, value in self.options.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

# Function to run Flask app with Gunicorn
def run_flask():
    logger.info(f"Starting Flask server on port {PORT}")
    options = {
        'bind': f'0.0.0.0:{PORT}',
        'workers': 1,
        'threads': 1,
        'timeout': 30,
    }
    StandaloneGunicornApplication(app, options).run()

# Function to run Telegram bot
async def run_bot():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", referral_start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdrawal_details))
    application.add_handler(CommandHandler("confirm", admin_confirm))
    application.add_handler(CommandHandler("reject", admin_reject))

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Telegram bot started polling")
        # Keep the bot running
        while True:
            await asyncio.sleep(3600)  # Sleep to keep the loop alive
    except Exception as e:
        logger.error(f"Error in bot polling: {e}")
        raise
    finally:
        logger.info("Shutting down Telegram bot")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def main():
    # Update WEB_APP_URL
    update_web_app_url()

    # Create a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    logger.info("Initialized new event loop for Telegram bot")

    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Run Telegram bot in the main thread
    try:
        loop.run_until_complete(run_bot())
    except Exception as e:
        logger.error(f"Failed to run bot: {e}")
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        logger.info("Event loop closed")

if __name__ == "__main__":
    main()
