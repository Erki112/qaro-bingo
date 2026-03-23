import os
import uuid
import json
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import telebot
from telebot import types
import redis
from dotenv import load_dotenv
import threading

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
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)
bot = telebot.TeleBot(BOT_TOKEN)
rdb = redis.from_url(REDIS_URL)

# Game state
games: Dict[str, Dict] = {}
BINGO_NUMBERS = list(range(1, 76))

class BingoGame:
    def __init__(self, host_id: int):
        self.host_id = host_id
        self.game_id = str(uuid.uuid4())
        self.players: List[Dict] = []
        self.grid: List[List[int]] = self._generate_grid()
        self.called_numbers: List[int] = []
        self.status = "waiting"  # waiting, active, finished
        self.winner = None
        self.start_time = datetime.now()
    
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
    
    def mark_number(self, number: int) -> bool:
        if number in self.called_numbers:
            return False
        self.called_numbers.append(number)
        
        # Check winners
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

# === TELEGRAM BOT HANDLERS ===
@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = types.InlineKeyboardMarkup()
    webapp_btn = types.InlineKeyboardButton("🎮 Play Bingo", web_app=types.WebAppInfo(url=f"{WEBAPP_URL}/webapp"))
    markup.add(webapp_btn)
    
    bot.send_message(
        message.chat.id,
        "🎉 <b>Welcome to Telegram Bingo Bot!</b>\n\n"
        "Click below to play with your 5x5 bingo card! 👇",
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = """
🎰 <b>Bingo Commands:</b>
/start - Start playing
/call 42 - Call number (admin)
/help - Show this help

Create a game in WebApp and share the Game ID!
    """
    bot.reply_to(message, help_text, parse_mode='HTML')

@bot.message_handler(commands=['call'])
def call_number_cmd(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "Usage: /call 42")
            return
        
        number = int(parts[1])
        if 1 <= number <= 75:
            user_game = rdb.get(f"user_game:{message.from_user.id}")
            if user_game:
                game_id = user_game.decode()
                game = games.get(game_id)
                if game and game.status == "active":
                    if game.mark_number(number):
                        bot.reply_to(message, f"🎉 <b>BINGO!</b>\nWinner: ID {game.winner}")
                        socketio.emit('game_won', {
                            'winner': game.winner,
                            'number': number
                        }, room=f"game_{game_id}")
                    else:
                        bot.reply_to(message, f"✅ <b>{number}</b> called!")
                        socketio.emit('number_called', {'number': number}, room=f"game_{game_id}")
                else:
                    bot.reply_to(message, "❌ No active game found")
            else:
                bot.reply_to(message, "❌ Join a game first!")
        else:
            bot.reply_to(message, "❌ Number must be 1-75")
    except ValueError:
        bot.reply_to(message, "❌ Invalid number!")

@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.reply_to(message, "Use /start to play or /help for commands!")

# === FLASK ROUTES ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webapp')
def webapp():
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
    rdb.setex(f"user_game:{user_id}", 3600, game.game_id)
    
    return jsonify({
        'game_id': game.game_id,
        'grid': game.grid,
        'status': game.status,
        'host': True
    })

@app.route('/api/game/<game_id>')
def get_game(game_id: str):
    game = games.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
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
    game.players.append({
        'user_id': user_id,
        'username': username,
        'grid': player_grid
    })
    
    rdb.setex(f"user_game:{user_id}", 3600, game_id)
    
    socketio.emit('player_joined', {
        'username': username,
        'total_players': len(game.players)
    }, room=f"game_{game_id}")
    
    return jsonify({
        'success': True,
        'grid': player_grid,
        'players': len(game.players)
    })

@app.route('/api/game/<game_id>/call/<int:number>', methods=['POST'])
def call_number_api(game_id: str, number: int):
    game = games.get(game_id)
    if not game or game.status != "active":
        return jsonify({'error': 'Game not active'}), 400
    
    if game.mark_number(number):
        socketio.emit('game_won', {
            'winner': game.winner,
            'number': number
        }, room=f"game_{game_id}")
        return jsonify({'bingo': True, 'winner': game.winner})
    
    socketio.emit('number_called', {'number': number}, room=f"game_{game_id}")
    return jsonify({'success': True, 'bingo': False})

# === SOCKET.IO EVENTS ===
@socketio.on('join_game')
def on_join(data):
    game_id = data.get('game_id')
    if game_id:
        join_room(f"game_{game_id}")
        game = games.get(game_id)
        if game:
            emit('game_state', {
                'status': game.status,
                'called_numbers': game.called_numbers,
                'players': len(game.players),
                'winner': game.winner
            })

@socketio.on('leave_game')
def on_leave(data):
    game_id = data.get('game_id')
    if game_id:
        leave_room(f"game_{game_id}")

# === MAIN ===
def run_bot():
    """Run bot with webhook"""
    webhook_url = f"{WEBAPP_URL}/webhook"
    
    # Delete any existing webhook and set new one
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    
    # Start polling as backup (webhook primary)
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram Webhook endpoint"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'OK', 200

if __name__ == '__main__':
    # Start bot in thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask + SocketIO
    socketio.run(app, host=HOST, port=PORT, debug=False)
