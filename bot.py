### bot.py
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import random
from database import Database
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
import uuid

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize MongoDB
db = Database()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    referral_code = str(uuid.uuid4())[:8]

    # Check if user exists, if not, create new user
    if not db.get_user(user_id):
        db.create_user(user_id, username, referral_code)

    keyboard = [
        [InlineKeyboardButton("🎰 Spin & Win", callback_data="spin")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")],
        [InlineKeyboardButton("👥 Refer Friends", callback_data="refer")],
        [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"Welcome, {username}! 🎉\n"
        "Play Spin & Win to earn rewards! You get 3 free spins daily. "
        "Invite friends to earn more spins and unlock withdrawals! 🚀"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "spin":
        await handle_spin(query, user_id)
    elif data == "dashboard":
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

async def handle_spin(query, user_id):
    user = db.get_user(user_id)
    spins_left = user.get("spins_left", 0)

    if spins_left <= 0:
        await query.message.reply_text(
            "No spins left! Invite friends to earn more spins. 👥",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👥 Refer", callback_data="refer")]])
        )
        return

    # Spin logic
    rewards = [10, 20, 30, 50, 0]  # Possible rewards
    weights = [0.4, 0.3, 0.2, 0.05, 0.05]  # Probabilities
    reward = random.choices(rewards, weights=weights, k=1)[0]

    db.update_spin(user_id, reward)
    spins_left -= 1
    balance = user.get("balance", 0) + reward

    message = (
        f"🎰 Spin Result: You won ₹{reward}! 🎉\n"
        f"Spins Left: {spins_left}\n"
        f"Current Balance: ₹{balance}"
    )
    keyboard = [
        [InlineKeyboardButton("🔄 Spin Again", callback_data="spin")],
        [InlineKeyboardButton("🏠 Home", callback_data="back")]
    ]
    await query.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

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
        f"👥 Referrals: {referrals}/15\n"
        f"🎁 Referral Earnings: ₹{referral_earnings}\n"
        f"{'✅ Ready to withdraw!' if referrals >= 15 and balance >= 100 else '🔒 Need 15 referrals and ₹100 to withdraw'}"
    )
    keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="back")]]
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
        f"👥 Current Referrals: {referrals}/15\n"
        f"💡 *Note*: You need 15 referrals to unlock ₹100 withdrawal."
    )
    keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="back")]]
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

    # Send withdrawal request to admin
    admin_message = (
        f"💸 *New Withdrawal Request*\n"
        f"User ID: {user_id}\n"
        f"Username: {username}\n"
        f"UPI Details: {upi_details}\n"
        f"Amount: ₹{balance}\n"
        f"Action: /confirm_{user_id} or /reject_{user_id}"
    )
    await context.bot.send_message(ADMIN_CHAT_ID, admin_message, parse_mode="Markdown")

    # Notify user
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
        [InlineKeyboardButton("🎰 Spin & Win", callback_data="spin")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")],
        [InlineKeyboardButton("👥 Refer Friends", callback_data="refer")],
        [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
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
                f"🎉 You've joined via {referrer['username']}'s referral! Start spinning now!"
            )
        else:
            await update.message.reply_text("Invalid or self-referral link!")
    else:
        await start(update, context)

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", referral_start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdrawal_details))
    application.add_handler(CommandHandler("confirm", admin_confirm))
    application.add_handler(CommandHandler("reject", admin_reject))

    application.run_polling()

if __name__ == "__main__":
    main()
