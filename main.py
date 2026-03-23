import asyncio
import logging
import json
import random
import os
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from flask import Flask, request, jsonify, render_template
from threading import Thread

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN required!")

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.onrender.com")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Globals
games: Dict[str, Dict] = {}
called_numbers: set = set()

app = Flask(__name__, template_folder='templates', static_folder='static')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

class BingoGame:
    def __init__(self):
        self.grid = self._generate_grid()
        self.marked = [[False] * 5 for _ in range(5)]
        self.wins = []
    
    def _generate_grid(self) -> List[List[int]]:
        columns = [random.sample(range(1 + i*15, 16 + i*15), 5) for i in range(5)]
        for col in columns: col.sort()
        columns[2][2] = 0  # FREE
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
                if f"Row {i+1}" not in self.wins: self.wins.append(f"Row {i+1}")
        
        # Columns
        for j in range(5):
            if all(self.marked[i][j] for i in range(5)):
                if f"Col {j+1}" not in self.wins: self.wins.append(f"Col {j+1}")
        
        # Diagonals
        if all(self.marked[i][i] for i in range(5)):
            if "Main Diagonal" not in self.wins: self.wins.append("Main Diagonal")
        if all(self.marked[i][4-i] for i in range(5)):
            if "Anti Diagonal" not in self.wins: self.wins.append("Anti Diagonal")
        
        return bool(self.wins)

@router.message(Command("start"))
async def start_cmd(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Play Bingo", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(
        "🎉 **Telegram Bingo Bot**\n\n"
        "👆 Click to open WebApp\n\n"
        "**Commands:**\n"
        "• `/new` - New card\n"
        "• `/call` - Call number\n"
        "• `/reset` - Reset game",
        reply_markup=kb, parse_mode="Markdown"
    )

@router.message(Command("new"))
async def new_game(message: Message):
    user_id = str(message.from_user.id)
    games[user_id] = {"game": BingoGame(), "created": datetime.now(), "wins": []}
    await message.answer("🎫 **New Bingo card created!**\nOpen WebApp to play! 🎮", parse_mode="Markdown")

@router.message(Command("call"))
async def call_number(message: Message):
    global called_numbers
    number = random.randint(1, 75)
    while number in called_numbers: number = random.randint(1, 75)
    called_numbers.add(number)
    
    letter = "BINGO"[number//15]
    await message.answer(f"🔊 **{letter} {number}**", parse_mode="Markdown")

@router.message(Command("reset"))
async def reset_game(message: Message):
    global called_numbers
    user_id = str(message.from_user.id)
    games.pop(user_id, None)
    called_numbers.clear()
    await message.answer("🔄 **Game reset!** Use `/new` to start", parse_mode="Markdown")

# Flask API
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    return jsonify({'status': 'ok'})

@app.route('/api/game/<user_id>')
def api_game(user_id):
    data = games.get(user_id)
    if not data: return jsonify({'error': 'No game'}), 404
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
    if user_id not in games: return jsonify({'error': 'No game'}), 404
    
    game = games[user_id]['game']
    won = game.mark_number(number)
    return jsonify({'success': True, 'won': won, 'wins': game.wins})

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    await asyncio.sleep(2)  # Wait for Flask
    
    logger.info("🚀 Bingo Bot starting...")
    logger.info(f"🌐 WebApp: {WEBAPP_URL}")
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
