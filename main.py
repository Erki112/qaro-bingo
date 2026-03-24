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

# Load environment
load_dotenv()

# Config
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://your-domain.com')
PORT = int(os.getenv('PORT', 5000))
HOST = os.getenv('HOST', '0.0.0.0')

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# === IN-MEMORY STORAGE (DICTIONARY) ===
games: Dict[str, 'BingoGame'] = {}
user_games: Dict[int, str] = {}  # user_id -> game_id
game_cleanup_time = 7200  # 2 hours TTL

BINGO_NUMBERS = list(range(1, 76))

class BingoGame:
    def __init__(self, host_id: int):
        self.host_id = host_id
        self.game_id = str(uuid.uuid4())[:8]  # Short ID
        self.players: List[Dict] = []
        self.host_grid = self._generate_grid()
        self.called_numbers: List[int] = []
        self.status = "waiting"  # waiting, active, finished
        self.winner = None
        self.created_at = datetime.now()
    
    def _generate_grid(self) -> List[List[int]]:
        numbers = BINGO_NUMBERS.copy()
        random.shuffle(numbers)
        grid = []
        for i in range(5):
            row = []
            for j in range(5):
                if i == 2 and j == 2:
                    row.append(0)  # FREE
                else:
                    row.append(numbers.pop())
            grid.append(row)
        return grid
    
    def to_dict(self):
        return {
            'host_id': self.host_id,
            'game_id': self.game_id,
            'players': self.players,
            'host_grid': self.host_grid,
            'called_numbers': self.called_numbers,
            'status': self.status,
            'winner': self.winner,
            'created_at': self.created_at.isoformat()
        }
    
    def mark_number(self, number: int) -> bool:
        if number in self.called_numbers:
            return False
        self.called_numbers.append(number)
        
        # Check host bingo
        if self._check_bingo(self.host_grid):
            self.winner = self.host_id
            self.status = "finished"
            return True
        
        # Check players
        for player in self.players:
            if self._check_bingo(player['grid']):
                self.winner = player['user_id']
                self.status = "finished"
                return True
        return False
    
    def _check_bingo(self, grid: List[List[int]]) -> bool:
        # Rows, Columns, Diagonals check
        for i in range(5):
            # Rows
            if all(grid[i][j] == 0 or grid[i][j] in self.called_numbers for j in range(5)):
                return True
            # Columns
            if all(grid[j][i] == 0 or grid[j][i] in self.called_numbers for j in range(5)):
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
def notify_game_update(game_id: str, message: str):
    """Notify all players via Telegram"""
    if game_id not in games:
        return
    
    game = games[game_id]
    
    # Notify host
    try:
        bot.send_message(
            game.host_id, 
            f"🎰 <b>{message}</b>\n\nGame ID: <code>{game_id}</code>", 
            parse_mode='HTML'
        )
    except:
        pass
    
    # Notify players
    for player in game.players:
        try:
            bot.send_message(
                player['user_id'], 
                f"🎰 <b>{message}</b>\n\nGame ID: <code>{game_id}</code>", 
                parse_mode='HTML'
            )
        except:
            pass

def cleanup_old_games():
    """Remove expired games every 5 minutes"""
    while True:
        try:
            current_time = datetime.now()
            expired_games = []
            
            # Find expired games
            for game_id, game in list(games.items()):
                if game.is_expired():
                    expired_games.append(game_id)
            
            # Cleanup
            for game_id in expired_games:
                del games[game_id]
                # Remove user references
                if game.host_id in user_games and user_games[game.host_id] == game_id:
                    del user_games[game.host_id]
                for player in games.get(game_id, BingoGame(0)).players:
                    if player['user_id'] in user_games and user_games[player['user_id']] == game_id:
                        del user_games[player['user_id']]
                logger.info(f"🧹 Cleaned expired game: {game_id}")
            
            time.sleep(300)  # 5 minutes
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            time.sleep(60)

# === TELEGRAM BOT HANDLERS ===
@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = types.InlineKeyboardMarkup()
    webapp_btn = types.InlineKeyboardButton("🎮 Play Bingo", web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/webapp"))
    markup.add(webapp_btn)
    
    bot.send_message(
        message.chat.id,
        "🎉 <b>Telegram Bingo Bot</b>\n\n"
        "👇 5x5 Bingo o'ynash uchun bosing!\n"
        "📱 WebApp da o'yin yarating\n"
        "🔢 /call 42 - Raqam chaqiring\n"
        "ℹ️ /mygame - O'yiningiz holati",
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(commands=['call'])
def call_handler(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ <code>/call 42</code> (1-75)", parse_mode='HTML')
            return
        
        number = int(parts[1])
        if not (1 <= number <= 75):
            bot.reply_to(message, "❌ Raqam 1-75 oralig'ida bo'lishi kerak!")
            return
        
        user_id = message.from_user.id
        if user_id not in user_games:
            bot.reply_to(message, "❌ Avval WebApp orqali o'yin qo'shiling!")
            return
        
        game_id = user_games[user_id]
        if game_id not in games:
            del user_games[user_id]
            bot.reply_to(message, "❌ O'yin topilmadi!")
            return
        
        game = games[game_id]
        if game.status != "active":
            bot.reply_to(message, "❌ O'yin faol emas! Yangi raund boshlang.")
            return
        
        if game.mark_number(number):
            notify_game_update(game_id, f"🎉 <b>BINGO!</b>\nG'olib: {game.winner}")
        else:
            notify_game_update(game_id, f"✅ Raqam <b>{number}</b> chaqirildi!")
        
        bot.reply_to(message, f"✅ {number} raqam chaqirildi!")
        
    except ValueError:
        bot.reply_to(message, "❌ Noto'g'ri raqam!")
    except Exception as e:
        logger.error(f"Call error: {e}")
        bot.reply_to(message, "❌ Xatolik yuz berdi!")

@bot.message_handler(commands=['mygame'])
def mygame_handler(message):
    user_id = message.from_user.id
    if user_id not in user_games:
        bot.reply_to(message, "❌ Sizda faol o'yin yo'q. WebApp orqali qo'shiling!")
        return
    
    game_id = user_games[user_id]
    if game_id not in games:
        del user_games[user_id]
        bot.reply_to(message, "❌ O'yin topilmadi!")
        return
    
    game = games[game_id]
    status = f"Status: {game.status.upper()}\nO'yinchilar: {len(game.players) + 1}\nChaqirilgan: {len(game.called_numbers)}"
    text = f"🎰 O'yin <code>{game_id}</code>\n\n{status}"
    if game.winner:
        text += f"\n🏆 G'olib: {game.winner}"
    
    bot.reply_to(message, text, parse_mode='HTML')

# === FLASK API ROUTES ===
@app.route('/')
@app.route('/webapp')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/api/game/create', methods=['POST'])
def create_game():
    data = request.json or {}
    user_id = data.get('user_id', 0)
    
    game = BingoGame(host_id=user_id)
    games[game.game_id] = game
    user_games[user_id] = game.game_id
    
    logger.info(f"New game created: {game.game_id} by user {user_id}")
    return jsonify({
        'game_id': game.game_id,
        'grid': game.host_grid,
        'status': game.status,
        'players': 1
    })

@app.route('/api/game/<game_id>')
def get_game(game_id: str):
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    if game.is_expired():
        del games[game_id]
        for uid, gid in list(user_games.items()):
            if gid == game_id:
                del user_games[uid]
        return jsonify({'error': 'Game expired'}), 404
    
    return jsonify({
        'game_id': game.game_id,
        'players': len(game.players),
        'status': game.status,
        'called_numbers': game.called_numbers,
        'winner': game.winner
    })

@app.route('/api/game/<game_id>/join', methods=['POST'])
def join_game(game_id: str):
    data = request.json or {}
    user_id = data.get('user_id', 0)
    username = data.get('username', f'User{user_id}')
    
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    if game.is_expired():
        del games[game_id]
        return jsonify({'error': 'Game expired'}), 404
    
    if any(p['user_id'] == user_id for p in game.players):
        return jsonify({'error': 'Already joined'})
    
    player_grid = game._generate_grid()
    game.players.append({
        'user_id': user_id,
        'username': username,
        'grid': player_grid
    })
    
    user_games[user_id] = game_id
    notify_game_update(game_id, f"{username} qo'shildi! ({len(game.players)} o'yinchi)")
    
    logger.info(f"Player {user_id} joined game {game_id}")
    return jsonify({
        'success': True,
        'grid': player_grid,
        'players': len(game.players)
    })

@app.route('/api/game/<game_id>/call/<int:number>', methods=['POST'])
def call_number(game_id: str, number: int):
    if game_id not in games or not (1 <= number <= 75):
        return jsonify({'error': 'Invalid game or number'}), 400
    
    game = games[game_id]
    if game.is_expired():
        del games[game_id]
        return jsonify({'error': 'Game expired'}), 404
    
    if game.status != "active":
        return jsonify({'error': 'Game not active'}), 400
    
    if game.mark_number(number):
        notify_game_update(game_id, f"🎉 <b>BINGO!</b>\nG'olib: {game.winner}")
        return jsonify({'bingo': True, 'winner': game.winner})
    
    notify_game_update(game_id, f"Raqam <b>{number}</b> chaqirildi!")
    return jsonify({'success': True, 'bingo': False})

@app.route('/api/game/<game_id>/newround', methods=['POST'])
def new_round(game_id: str):
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    game.status = "active"
    game.called_numbers = []
    game.winner = None
    game.created_at = datetime.now()  # Reset timer
    
    notify_game_update(game_id, "🔄 Yangi raund boshlandi!")
    return jsonify({'success': True})

# === TELEGRAM WEBHOOK ===
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK'
    return 'OK', 200

# === SIGNAL HANDLER & STARTUP ===
def signal_handler(sig, frame):
    logger.info("Shutting down gracefully...")
    try:
        bot.remove_webhook()
    except:
        pass
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_games, daemon=True)
    cleanup_thread.start()
    
    # Production vs Development
    port = int(os.environ.get('PORT', 5000))
    webhook_url = f"{WEBAPP_URL}/webhook"
    
    try:
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook set: {webhook_url}")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    
    if port == 5000:  # Local dev
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:  # Production
        logger.info("✅ Production ready - Gunicorn will start")
