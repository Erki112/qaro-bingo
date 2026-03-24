import os
import uuid
import json
import random
import logging
import time
import threading
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional
from flask import Flask, request, jsonify, render_template, send_from_directory
import telebot
from telebot import types
import redis
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Config
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://your-domain.com')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
PORT = int(os.getenv('PORT', 5000))
HOST = os.getenv('HOST', '0.0.0.0')

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
rdb = redis.from_url(REDIS_URL, decode_responses=True)

# Game state
games: Dict[str, BingoGame] = {}
BINGO_NUMBERS = list(range(1, 76))

class BingoGame:
    def __init__(self, host_id: int):
        self.host_id = host_id
        self.game_id = str(uuid.uuid4())
        self.players: List[Dict] = []
        self.grid: List[List[int]] = self._generate_grid()
        self.host_grid = self.grid.copy()
        self.called_numbers: List[int] = []
        self.status = "waiting"
        self.winner = None
        self.start_time = datetime.now().isoformat()
    
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
            'start_time': self.start_time
        }
    
    @classmethod
    def from_dict(cls, data):
        game = cls(data['host_id'])
        game.game_id = data['game_id']
        game.players = data['players']
        game.host_grid = data['host_grid']
        game.called_numbers = data['called_numbers']
        game.status = data['status']
        game.winner = data['winner']
        game.start_time = data['start_time']
        return game
    
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

# Global functions
def load_games():
    global games
    try:
        all_games = rdb.hgetall('games')
        for game_id, data in all_games.items():
            games[game_id] = BingoGame.from_dict(json.loads(data))
        logger.info(f"Loaded {len(games)} games from Redis")
    except Exception as e:
        logger.error(f"Error loading games: {e}")

def save_game(game_id: str, game: BingoGame):
    rdb.hset('games', game_id, json.dumps(game.to_dict()))
    rdb.expire('games', 7200)  # 2 hours TTL

def notify_game_update(game_id: str, message: str):
    game = games.get(game_id)
    if not game:
        return
    
    # Notify host
    try:
        bot.send_message(game.host_id, f"🎰 <b>{message}</b>\nGame: <code>{game_id}</code>", parse_mode='HTML')
    except:
        pass
    
    # Notify players
    for player in game.players:
        try:
            bot.send_message(player['user_id'], f"🎰 <b>{message}</b>\nGame: <code>{game_id}</code>", parse_mode='HTML')
        except:
            pass

def cleanup_old_games():
    while True:
        try:
            current_time = time.time()
            to_delete = []
            for game_id, game in list(games.items()):
                if (current_time - datetime.fromisoformat(game.start_time).timestamp()) > 7200:
                    to_delete.append(game_id)
            
            for game_id in to_delete:
                del games[game_id]
                rdb.hdel('games', game_id)
                logger.info(f"Cleaned up old game: {game_id}")
        except:
            pass
        time.sleep(300)  # 5 minutes

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    logger.info("Shutting down gracefully...")
    try:
        bot.remove_webhook()
    except:
        pass
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# === TELEGRAM BOT HANDLERS ===
@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = types.InlineKeyboardMarkup()
    webapp_btn = types.InlineKeyboardButton("🎮 Play Bingo", web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/webapp"))
    markup.add(webapp_btn)
    
    bot.send_message(
        message.chat.id,
        "🎉 <b>Telegram Bingo Bot</b>\n\n"
        "👇 Click to play 5x5 Bingo!\n"
        "📱 Create/join games in WebApp\n"
        "🔢 /call 42 - Call numbers",
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(commands=['call'])
def call_handler(message):
    try:
        parts = message.text.split()
        number = int(parts[1])
        if 1 <= number <= 75:
            user_game = rdb.get(f"user_game:{message.from_user.id}")
            if user_game:
                game_id = user_game
                game = games.get(game_id)
                if game and game.status == "active":
                    if game.mark_number(number):
                        notify_game_update(game_id, f"🎉 BINGO! Winner: {game.winner}")
                        save_game(game_id, game)
                    else:
                        notify_game_update(game_id, f"✅ Number <b>{number}</b> called!")
                        save_game(game_id, game)
                else:
                    bot.reply_to(message, "❌ No active game")
            else:
                bot.reply_to(message, "❌ Join game first (WebApp)")
        else:
            bot.reply_to(message, "❌ Number 1-75 only")
    except:
        bot.reply_to(message, "❌ <code>/call 42</code>", parse_mode='HTML')

@bot.message_handler(commands=['mygame'])
def mygame_handler(message):
    user_game = rdb.get(f"user_game:{message.from_user.id}")
    if user_game and user_game in games:
        game = games[user_game]
        status = f"Status: {game.status.upper()}\nPlayers: {len(game.players)}\nCalled: {len(game.called_numbers)}"
        bot.reply_to(message, f"🎰 Game <code>{user_game}</code>\n{status}", parse_mode='HTML')
    else:
        bot.reply_to(message, "❌ No active game. Use WebApp!")

# === FLASK ROUTES ===
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
    save_game(game.game_id, game)
    rdb.setex(f"user_game:{user_id}", 7200, game.game_id)
    
    return jsonify({
        'game_id': game.game_id,
        'grid': game.host_grid,
        'status': game.status,
        'players': 1
    })

@app.route('/api/game/<game_id>')
def get_game(game_id: str):
    game = games.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    save_game(game_id, game)
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
    
    game = games.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    if any(p['user_id'] == user_id for p in game.players):
        return jsonify({'error': 'Already joined'})
    
    player_grid = game._generate_grid()
    game.players.append({'user_id': user_id, 'username': username, 'grid': player_grid})
    
    save_game(game_id, game)
    rdb.setex(f"user_game:{user_id}", 7200, game_id)
    
    notify_game_update(game_id, f"{username} joined! ({len(game.players)} players)")
    
    return jsonify({'success': True, 'grid': player_grid, 'players': len(game.players)})

@app.route('/api/game/<game_id>/call/<int:number>', methods=['POST'])
def call_number(game_id: str, number: int):
    game = games.get(game_id)
    if not game or game.status != "active":
        return jsonify({'error': 'Game not active'}), 400
    
    if game.mark_number(number):
        notify_game_update(game_id, f"🎉 BINGO! Winner: {game.winner}!")
        save_game(game_id, game)
        return jsonify({'bingo': True, 'winner': game.winner})
    
    notify_game_update(game_id, f"Number {number} called!")
    save_game(game_id, game)
    return jsonify({'success': True, 'bingo': False})

@app.route('/api/game/<game_id>/newround', methods=['POST'])
def new_round(game_id: str):
    game = games.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    game.status = "active"
    game.called_numbers = []
    game.winner = None
    save_game(game_id, game)
    
    notify_game_update(game_id, "🔄 New round started!")
    return jsonify({'success': True})

# === WEBHOOK ===
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK'
    return 'OK', 200

# === MAIN ===
if __name__ == '__main__':
    # Production vs Development
    port = int(os.environ.get('PORT', 5000))
    
    if port == 5000:  # Local development
        load_games()
        cleanup_thread = threading.Thread(target=cleanup_old_games, daemon=True)
        cleanup_thread.start()
        
        webhook_url = f"{WEBAPP_URL}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Local dev - Webhook: {webhook_url}")
        
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:  # Production (Gunicorn/Render)
        logger.info("✅ Production mode - Gunicorn will start Flask")
        load_games()
        cleanup_thread = threading.Thread(target=cleanup_old_games, daemon=True)
        cleanup_thread.start()
        webhook_url = f"{WEBAPP_URL}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Production - Webhook: {webhook_url}")
