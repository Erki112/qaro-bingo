import os
import random
import logging
from datetime import datetime
from typing import Dict, List
from flask import Flask, request, jsonify, render_template, send_from_directory
from threading import Thread
import telebot
from dotenv import load_dotenv
import time

# Load env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.onrender.com")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN required!")

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
bot = telebot.TeleBot(BOT_TOKEN)

# Game state (thread-safe)
games: Dict[str, Dict] = {}
called_numbers: set = set()

class BingoGame:
    def __init__(self):
        self.grid = self._generate_grid()
        self.marked = [[False] * 5 for _ in range(5)]
        self.wins = []
    
    def _generate_grid(self) -> List[List[int]]:
        columns = [random.sample(range(1 + i*15, 16 + i*15), 5) for i in range(5)]
        for col in columns: col.sort()
        columns[2][2] = 0
        return list(map(list, zip(*columns)))
    
    def mark_number(self, number: int) -> bool:
        for i in range(5):
            for j in range(5):
                if self.grid[i][j] == number:
                    self.marked[i][j] = True
                    return self._check_win()
        return False
    
    def _check_win(self) -> bool:
        for i in range(5):
            if all(self.marked[i][j] for j in range(5)):
                if f"Row {i+1}" not in self.wins: self.wins.append(f"Row {i+1}")
        for j in range(5):
            if all(self.marked[i][j] for i in range(5)):
                if f"Col {j+1}" not in self.wins: self.wins.append(f"Col {j+1}")
        if all(self.marked[i][i] for i in range(5)):
            if "Main Diagonal" not in self.wins: self.wins.append("Main Diagonal")
        if all(self.marked[i][4-i] for i in range(5)):
            if "Anti Diagonal" not in self.wins: self.wins.append("Anti Diagonal")
        return bool(self.wins)

# ========== TELEGRAM BOT HANDLERS ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🎮 Play Bingo", web_app=telebot.types.WebAppInfo(WEBAPP_URL)))
    bot.reply_to(message, 
        "🎉 **Telegram Bingo Bot**\n\n👆 WebApp furma\n\n**/new /call /reset**",
        reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['new'])
def new_game(message):
    user_id = str(message.from_user.id)
    games[user_id] = {"game": BingoGame(), "created": datetime.now().isoformat(), "wins": []}
    bot.reply_to(message, "🎫 **Kaardii haaraa barame!** 🎮", parse_mode='Markdown')

@bot.message_handler(commands=['call'])
def call_number(message):
    global called_numbers
    number = random.randint(1, 75)
    while number in called_numbers: number = random.randint(1, 75)
    called_numbers.add(number)
    letter = "BINGO"[number//15]
    bot.reply_to(message, f"🔊 **{letter} {number}**", parse_mode='Markdown')

@bot.message_handler(commands=['reset'])
def reset(message):
    user_id = str(message.from_user.id)
    games.pop(user_id, None)
    bot.reply_to(message, "🔄 **Reset!** `/new` gamadhu", parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status(message):
    user_id = str(message.from_user.id)
    total_games = len(games)
    total_called = len(called_numbers)
    status = f"📊 **Status**\n• Games: {total_games}\n• Called: {total_called}"
    bot.reply_to(message, status, parse_mode='Markdown')

# ========== FLASK ROUTES ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/api/new/<user_id>', methods=['POST'])
def api_new_game(user_id):
    games[user_id] = {"game": BingoGame(), "created": datetime.now().isoformat(), "wins": []}
    logger.info(f"🎮 WebApp new game: {user_id}")
    return jsonify({'success': True})

@app.route('/api/game/<user_id>')
def api_game(user_id):
    if user_id not in games:
        games[user_id] = {"game": BingoGame(), "created": datetime.now().isoformat(), "wins": []}
    data = games[user_id]
    return jsonify({
        'grid': data['game'].grid,
        'marked': data['game'].marked,
        'wins': data['game'].wins,
        'called_numbers': list(called_numbers)
    })

@app.route('/api/game/<user_id>/mark', methods=['POST'])
def api_mark(user_id):
    data = request.json
    number = data.get('number')
    if user_id not in games: 
        return jsonify({'error': 'No game'}), 404
    game = games[user_id]['game']
    won = game.mark_number(number)
    return jsonify({'success': True, 'won': won, 'wins': game.wins})

# ========== STARTUP ==========
def run_bot():
    """Bot polling thread"""
    logger.info("🤖 Starting Telegram Bot polling...")
    try:
        bot.infinity_polling(none_stop=True, timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"Bot error: {e}")
        time.sleep(5)
        run_bot()  # Restart

def run_flask():
    """Flask server"""
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

def main():
    logger.info("🚀 Bingo Bot + Flask Starting...")
    logger.info(f"🌐 WebApp: {WEBAPP_URL}")
    
    # Start threads
    flask_thread = Thread(target=run_flask, daemon=True)
    bot_thread = Thread(target=run_bot, daemon=True)
    
    flask_thread.start()
    bot_thread.start()
    
    # Keep main thread alive
    flask_thread.join()

if __name__ == "__main__":
    main()
