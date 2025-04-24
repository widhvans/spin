from pymongo import MongoClient
from config import MONGO_URI
from datetime import datetime, timedelta

class Database:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client["spin_and_win"]
        self.users = self.db["users"]
        self.withdrawals = self.db["withdrawals"]

    def create_user(self, user_id, username, referral_code):
        user = {
            "user_id": user_id,
            "username": username,
            "referral_code": referral_code,
            "balance": 0,
            "spins_left": 3,
            "referrals": [],
            "referral_earnings": 0,
            "last_spin_date": None,
            "created_at": datetime.utcnow()
        }
        self.users.insert_one(user)

    def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})

    def get_user_by_referral_code(self, referral_code):
        return self.users.find_one({"referral_code": referral_code})

    def update_spin(self, user_id, reward):
        user = self.get_user(user_id)
        today = datetime.utcnow().date()
        last_spin_date = user.get("last_spin_date")

        if last_spin_date and datetime.fromisoformat(last_spin_date).date() != today:
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {"spins_left": 3, "last_spin_date": today.isoformat()}}
            )
        else:
            self.users.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"spins_left": -1, "balance": reward},
                    "$set": {"last_spin_date": today.isoformat()}
                }
            )

    def add_referral(self, referrer_id, referred_id):
        self.users.update_one(
            {"user_id": referrer_id},
            {
                "$push": {"referrals": referred_id},
                "$inc": {"spins_left": 1, "referral_earnings": 10}
            }
        )

    def log_withdrawal_request(self, user_id, upi_details, amount):
        withdrawal = {
            "user_id": user_id,
            "upi_details": upi_details,
            "amount": amount,
            "status": "pending",
            "requested_at": datetime.utcnow()
        }
        self.withdrawals.insert_one(withdrawal)

    def confirm_withdrawal(self, user_id):
        self.withdrawals.update_one(
            {"user_id": user_id, "status": "pending"},
            {"$set": {"status": "confirmed", "confirmed_at": datetime.utcnow()}}
        )
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"balance": 0}}
        )

    def reject_withdrawal(self, user_id):
        self.withdrawals.update_one(
            {"user_id": user_id, "status": "pending"},
            {"$set": {"status": "rejected", "rejected_at": datetime.utcnow()}}
        )
