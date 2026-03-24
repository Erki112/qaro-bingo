import os
import uuid
import json
import random
import logging
import time
import threading
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Flask, request, jsonify, render_template, send_from_directory
import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()

# Config
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))  # Sizning Telegram ID
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://your-domain.com')
PORT = int(os.getenv('PORT', 5000))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# === IN-MEMORY STORAGE ===
games: Dict[str, 'BingoGame'] = {}
user_games: Dict[int, str] = {}
user_balances: Dict[int, float] = {}  # user_id -> ETB balance
deposit_requests: Dict[int, Dict] = {}  # user_id -> deposit info
withdraw_requests: Dict[int, Dict] = {}  # user_id -> withdraw info

BINGO_NUMBERS = list(range(1, 76))
game_cleanup_time = 7200

class BingoGame:
    def __init__(self, host_id: int):
        self.host_id = host_id
        self.game_id = str(uuid.uuid4())[:8]
        self.players: List[Dict] = []
        self.host_grid = self._generate_grid()
        self.called_numbers: List[int] = []
        self.status = "waiting"
        self.winner = None
        self.created_at = datetime.now()
        self.entry_fee = 10.0  # ETB
        self.winnings = 100.0  # ETB for winner
    
    def _generate_grid(self) -> List[List[int]]:
        numbers = BINGO_NUMBERS.copy()
        random.shuffle(numbers)
        grid = [[0]*5 for _ in range(5)]
        idx = 0
        for i in range(5):
            for j in range(5):
                if i == 2 and j == 2:
                    grid[i][j] = 0  # FREE
                else:
                    grid[i][j] = numbers[idx]
                    idx += 1
        return grid
    
    def mark_number(self, number: int) -> bool:
        if number in self.called_numbers:
            return False
        self.called_numbers.append(number)
        
        if self._check_bingo(self.host_grid):
            self.winner = self.host_id
            return True
        
        for player in self.players:
            if self._check_bingo(player['grid']):
                self.winner = player['user_id']
                return True
        return False
    
    def _check_bingo(self, grid: List[List[int]]) -> bool:
        # Rows
        for row in grid:
            if all(cell == 0 or cell in self.called_numbers for cell in row):
                return True
        # Columns
        for col in range(5):
            if all(grid[row][col] == 0 or grid[row][col] in self.called_numbers for row in range(5)):
                return True
        # Diagonals
        if all(grid[i][i] == 0 or grid[i][i] in self.called_numbers for i in range(5)):
            return True
        if all(grid[i][4-i] == 0 or grid[i][4-i] in self.called_numbers for i in range(5)):
            return True
        return False
    
    def is_expired(self) -> bool:
        return (datetime.now() - self.created_at).total_seconds() > game_cleanup_time

# === UTILITY FUNCTIONS ===
def get_balance(user_id: int) -> float:
    return user_balances.get(user_id, 0.0)

def add_balance(user_id: int, amount: float):
    user_balances[user_id] = get_balance(user_id) + amount
    logger.info(f"Balance updated: {user_id} +{amount} = {user_balances[user_id]} ETB")

def deduct_balance(user_id: int, amount: float) -> bool:
    balance = get_balance(user_id)
    if balance >= amount:
        user_balances[user_id] = balance - amount
        return True
    return False

def notify_game_update(game_id: str, message: str):
    if game_id not in games:
        return
    game = games[game_id]
    try:
        bot.send_message(game.host_id, f"🎰 {message}\nID: <code>{game_id}</code>", parse_mode='HTML')
    except: pass
    for player in game.players:
        try:
            bot.send_message(player['user_id'], f"🎰 {message}\nID: <code>{game_id}</code>", parse_mode='HTML')
        except: pass

def cleanup_old_games():
    while True:
        try:
            expired = []
            for game_id, game in list(games.items()):
                if game.is_expired():
                    expired.append(game_id)
            for game_id in expired:
                del games[game_id]
                if games[game_id].host_id in user_games:
                    del user_games[games[game_id].host_id]
            time.sleep(300)
        except: time.sleep(60)

# === ADMIN COMMANDS ===
@bot.message_handler(commands=['addbalance'])
def admin_add_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Sizda ruxsat yo'q!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ /addbalance [user_id] [amount]\nMasalan: /addbalance 123456 50")
            return
        
        user_id = int(parts[1])
        amount = float(parts[2])
        
        add_balance(user_id, amount)
        bot.reply_to(message, f"✅ {user_id} ga {amount} ETB qo\'shildi\nYangi balans: {get_balance(user_id)} ETB")
        logger.info(f"Admin added {amount} ETB to {user_id}")
    except:
        bot.reply_to(message, "❌ Noto'g'ri format!")

@bot.message_handler(commands=['balance'])
def admin_balance(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_id = message.reply_to_message.from_user.id if message.reply_to_message else message.from_user.id
    bal = get_balance(user_id)
    bot.reply_to(message, f"💰 {user_id} balans: <b>{bal} ETB</b>", parse_mode='HTML')

@bot.message_handler(commands=['deposits'])
def admin_deposits(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not deposit_requests:
        bot.reply_to(message, "📥 Deposit so'rovlari yo'q")
        return
    text = "📥 <b>Deposit So'rovlari:</b>\n\n"
    for user_id, req in list(deposit_requests.items())[:10]:
        text += f"ID: <code>{user_id}</code> - {req['amount']} ETB\n"
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['withdraws'])
def admin_withdraws(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not withdraw_requests:
        bot.reply_to(message, "💸 Withdraw so'rovlari yo'q")
        return
    text = "💸 <b>Withdraw So'rovlari:</b>\n\n"
    for user_id, req in list(withdraw_requests.items())[:10]:
        text += f"ID: <code>{user_id}</code> - {req['amount']} ETB\n"
    bot.reply_to(message, text, parse_mode='HTML')

# === DEPOSIT HANDLER (Screenshot) ===
@bot.message_handler(content_types=['photo', 'document'])
def handle_deposit_photo(message):
    user_id = message.from_user.id
    if user_id in deposit_requests:
        # Already has pending deposit
        bot.reply_to(message, "⏳ Deposit so'rovingiz ko\'rib chiqilmoqda. Iltimos kuting!")
        return
    
    deposit_requests[user_id] = {
        'amount': 0,
        'screenshot_id': message.photo[-1].file_id if message.photo else message.document.file_id,
        'username': message.from_user.username or message.from_user.first_name,
        'time': datetime.now().isoformat()
    }
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Balansni tekshirish", web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/webapp")))
    
    bot.reply_to(
        message,
        "📸 To'lov skrinshoti qabul qilindi!\n\n"
        "✅ Admin tekshirgandan keyin balansingiz to'ldiriladi\n"
        "💰 <b>Telebirr/CBE</b> orqali quyidagi raqamga yuboring:\n"
        "<code>+251-9XX-XXX-XXX</code>\n\n"
        "Miqdorni /deposit [amount] deb yuboring",
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(commands=['deposit'])
def handle_deposit_amount(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ /deposit 50 (ETB miqdori)")
            return
        
        amount = float(parts[1])
        if amount < 10:
            bot.reply_to(message, "❌ Minimal 10 ETB")
            return
        
        user_id = message.from_user.id
        deposit_requests[user_id] = deposit_requests.get(user_id, {})
        deposit_requests[user_id]['amount'] = amount
        
        bot.reply_to(
            message,
            f"✅ {amount} ETB deposit so'rovi qabul qilindi!\n"
            "📱 Admin tasdiqlagach balans ko'rsatiladi\n"
            "⏳ Kuting..."
        )
        logger.info(f"Deposit request: {user_id} - {amount} ETB")
    except:
        bot.reply_to(message, "❌ Noto'g'ri miqdor!")

# === GAME COMMANDS ===
@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    deposit_btn = types.KeyboardButton("💰 Deposit", request_photo=True)
    balance_btn = types.KeyboardButton("💳 Balans", web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/webapp"))
    play_btn = types.KeyboardButton("🎮 Bingo O'ynash", web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/webapp"))
    
    markup.add(deposit_btn, balance_btn)
    markup.add(play_btn)
    
    bot.send_message(
        message.chat.id,
        "🎉 <b>Bingo Royale Ethiopia</b>\n\n"
        "💰 <b>Deposit:</b> Telebirr/CBE → Screenshot yuboring\n"
        "🎮 <b>O'ynash:</b> 10 ETB → 100 ETB yutish!\n"
        "💸 <b>Withdraw:</b> WebApp dan so'rang\n\n"
        "🇪🇹 Telebirr: +251-9XX-XXX-XXX",
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "💰 Deposit")
def deposit_prompt(message):
    bot.send_photo(
        message.chat.id,
        "https://i.imgur.com/telebirr.jpg",  # Placeholder
        caption="📸 Telebirr/CBE to'lov skrinshotini yuboring!\n"
                "Keyin /deposit [miqdor] deb yozing\n\n"
                "💳 Hisob: +251-9XX-XXX-XXX"
    )

@bot.message_handler(func=lambda m: m.text == "💳 Balans")
def balance_webapp(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Balans & Withdraw", web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/webapp")))
    bot.send_message(message.chat.id, "💳 Balansingiz:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎮 Bingo O'ynash")
def bingo_webapp(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎮 Bingo Mini App", web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/webapp")))
    bot.send_message(message.chat.id, "🎮 Bingo o'ynash:", reply_markup=markup)

# === BINGO GAME COMMANDS ===
@bot.message_handler(commands=['call'])
def call_handler(message):
    # Same as before...
    pass  # (Previous call_handler code)

@bot.message_handler(commands=['mygame'])
def mygame_handler(message):
    # Same as before...
    pass  # (Previous mygame_handler code)

# === FLASK API (BALANCE + WITHDRAW) ===
@app.route('/api/balance/<int:user_id>')
def get_balance_api(user_id: int):
    return jsonify({'balance': get_balance(user_id)})

@app.route('/api/withdraw', methods=['POST'])
def request_withdraw():
    data = request.json or {}
    user_id = data.get('user_id', 0)
    amount = float(data.get('amount', 0))
    
    if amount < 50:
        return jsonify({'error': 'Minimal 50 ETB'})
    
    balance = get_balance(user_id)
    if balance < amount:
        return jsonify({'error': 'Yetarli balans yo\'q'})
    
    withdraw_requests[user_id] = {
        'amount': amount,
        'username': data.get('username', ''),
        'time': datetime.now().isoformat()
    }
    
    bot.send_message(
        ADMIN_ID,
        f"💸 <b>Withdraw So'rovi</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"💰 Miqdor: {amount} ETB\n"
        f"📱 Telebirr: +251-9XX-XXX-XXX",
        parse_mode='HTML'
    )
    
    return jsonify({'success': True, 'message': 'So\'rov yuborildi!'})

# === BINGO API ROUTES (Previous code remains same) ===
# ... (All previous /api/game/* routes stay exactly the same)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    return 'OK', 200

# === STARTUP ===
def signal_handler(sig, frame):
    logger.info("Shutting down...")
    try:
        bot.remove_webhook()
    except: pass
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    cleanup_thread = threading.Thread(target=cleanup_old_games, daemon=True)
    cleanup_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    webhook_url = f"{WEBAPP_URL}/webhook"
    
    try:
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook: {webhook_url}")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    
    if port == 5000:
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        logger.info("✅ Production - Gunicorn ready")
