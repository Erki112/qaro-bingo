import asyncio
import logging
import json
import random
import os
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from threading import Thread

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

# Environment
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable is required!")

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.onrender.com")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
games: Dict[str, Dict] = {}
called_numbers: set = set()

# Flask & Aiogram setup
app = Flask(__name__, template_folder='templates', static_folder='static')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

class BingoGame:
    """5x5 Bingo Game Logic"""
    def __init__(self):
        self.grid = self._generate_grid()
        self.marked = [[False] * 5 for _ in range(5)]
        self.wins = []
    
    def _generate_grid(self) -> List[List[int]]:
        """B=1-15, I=16-30, N=31-45, G=46-60, O=61-75"""
        columns = [random.sample(range(1 + i*15, 16 + i*15), 5) for i in range(5)]
        for col in columns: col.sort()
        columns[2][2] = 0  # FREE space
        return list(map(list, zip(*columns)))
    
    def mark_number(self, number: int) -> bool:
        for i in range(5):
            for j in range(5):
                if self.grid[i][j] == number:
                    self.marked[i][j] = True
                    return self._check_win()
        return False
    
    def _check_win(self) -> bool:
        # Rows
        for i in range(5):
            if all(self.marked[i][j] for j in range(5)):
                win_name = f"Row {i+1}"
                if win_name not in self.wins: self.wins.append(win_name)
        
        # Columns
        for j in range(5):
            if all(self.marked[i][j] for i in range(5)):
                win_name = f"Col {j+1}"
                if win_name not in self.wins: self.wins.append(win_name)
        
        # Diagonals
        if all(self.marked[i][i] for i in range(5)):
            if "Main Diagonal" not in self.wins: self.wins.append("Main Diagonal")
        if all(self.marked[i][4-i] for i in range(5)):
            if "Anti Diagonal" not in self.wins: self.wins.append("Anti Diagonal")
        
        return bool(self.wins)

# ========== BOT COMMANDS ==========
@router.message(Command("start"))
async def start_cmd(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Play Bingo", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(
        "🎉 **Telegram Bingo Bot**\n\n"
        "👆 Fakkii hojjechuun WebApp furma\n\n"
        "**Commands:**\n"
        "• `/new` - Kaardii haaraa\n"
        "• `/call` - Numara dhiyeessuu\n"
        "• `/reset` - Reset\n"
        "• `/status` - Status",
        reply_markup=kb, parse_mode="Markdown"
    )

@router.message(Command("new"))
async def new_game_cmd(message: Message):
    user_id = str(message.from_user.id)
    games[user_id] = {"game": BingoGame(), "created": datetime.now().isoformat(), "wins": []}
    await message.answer("🎫 **Kaardii haaraa barame!**\nWebApp furadhu!", parse_mode="Markdown")

@router.message(Command("call"))
async def call_number(message: Message):
    global called_numbers
    number = random.randint(1, 75)
    while number in called_numbers:
        number = random.randint(1, 75)
    called_numbers.add(number)
    
    letter = "BINGO"[number//15]
    await message.answer(f"🔊 **{letter} {number}**", parse_mode="Markdown")

@router.message(Command("reset"))
async def reset_game(message: Message):
    global called_numbers
    user_id = str(message.from_user.id)
    games.pop(user_id, None)
    if message.from_user.id == 1:  # Admin reset all
        global games, called_numbers
        games.clear()
        called_numbers.clear()
        await message.answer("🔄 **Game reset (all)!**", parse_mode="Markdown")
    else:
        await message.answer("🔄 **Game reset!** `/new` gamadhu", parse_mode="Markdown")

@router.message(Command("status"))
async def status_cmd(message: Message):
    user_id = str(message.from_user.id)
    game = games.get(user_id)
    total_games = len(games)
    total_called = len(called_numbers)
    
    status = f"📊 **Status**\n"
    status += f"• Games active: {total_games}\n"
    status += f"• Numbers called: {total_called}\n"
    
    if game:
        wins = len(game['wins'])
        status += f"• Your wins: {wins}"
    
    await message.answer(status, parse_mode="Markdown")

# ========== FLASK WEB API ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    return jsonify({'status': 'ok'})

@app.route('/api/new/<user_id>', methods=['POST'])
def api_new_game(user_id):
    """Create new game from WebApp"""
    games[user_id] = {
        "game": BingoGame(),
        "created": datetime.now().isoformat(),
        "wins": []
    }
    logger.info(f"🎮 New WebApp game for {user_id}")
    return jsonify({'success': True, 'message': 'Kaardii haaraa barame!'})

@app.route('/api/game/<user_id>')
def api_game(user_id):
    """Get game data (auto-create if missing)"""
    if user_id not in games:
        games[user_id] = {"game": BingoGame(), "created": datetime.now().isoformat(), "wins": []}
    
    data = games[user_id]
    return jsonify({
        'grid': data['game'].grid,
        'marked': data['game'].marked,
        'wins': data['game'].wins,
        'called_numbers': list(called_numbers),
        'user_id': user_id
    })

@app.route('/api/game/<user_id>/mark', methods=['POST'])
def api_mark_number(user_id):
    """Mark a number"""
    data = request.get_json()
    number = data.get('number')
    
    if user_id not in games:
        return jsonify({'error': 'No game found'}), 404
    
    game = games[user_id]['game']
    won = game.mark_number(number)
    
    return jsonify({
        'success': True,
        'won': won,
        'wins': game.wins
    })

def run_flask():
    """Run Flask server"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

async def main():
    """Start bot + flask"""
    # Start Flask first
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    await asyncio.sleep(3)  # Wait for Flask
    
    logger.info("🚀 Bingo Bot Started!")
    logger.info(f"🌐 WebApp: {WEBAPP_URL}")
    logger.info(f"🤖 Bot ID: {bot.id}")
    
    # LONG POLLING (no webhook issues)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
# Add at bottom of main.py
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
