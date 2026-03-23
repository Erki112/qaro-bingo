import asyncio
import logging
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from flask import Flask, request, jsonify, render_template
from threading import Thread

# Config
from config import BOT_TOKEN, WEBAPP_URL

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
games: Dict[str, Dict] = {}  # user_id -> game_data
called_numbers: set = set()

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

class BingoGame:
    def __init__(self):
        self.grid = self._generate_grid()
        self.marked = [[False for _ in range(5)] for _ in range(5)]
        self.wins = []
    
    def _generate_grid(self) -> List[List[int]]:
        """Generate unique 5x5 bingo grid (B=1-15, I=16-30, N=31-45, G=46-60, O=61-75)"""
        columns = [
            random.sample(range(1 + i*15, 16 + i*15), 5) for i in range(5)
        ]
        # Sort each column
        for col in columns:
            col.sort()
        # Free space in center
        columns[2][2] = 0
        return [row[:] for row in zip(*columns)]
    
    def mark_number(self, number: int) -> bool:
        """Mark number and check for win"""
        for i in range(5):
            for j in range(5):
                if self.grid[i][j] == number:
                    self.marked[i][j] = True
                    return self._check_win()
        return False
    
    def _check_win(self) -> bool:
        # Check rows
        for i in range(5):
            if all(self.marked[i][j] for j in range(5)):
                if i not in self.wins:
                    self.wins.append(f"Row {i+1}")
        
        # Check columns
        for j in range(5):
            if all(self.marked[i][j] for i in range(5)):
                if f"Col {j+1}" not in self.wins:
                    self.wins.append(f"Col {j+1}")
        
        # Check diagonals
        if all(self.marked[i][i] for i in range(5)):
            if "Main Diagonal" not in self.wins:
                self.wins.append("Main Diagonal")
        if all(self.marked[i][4-i] for i in range(5)):
            if "Anti Diagonal" not in self.wins:
                self.wins.append("Anti Diagonal")
        
        return bool(self.wins)

@router.message(Command("start"))
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Play Bingo", web_app=WebAppInfo(url=f"{WEBAPP_URL}"))]
    ])
    await message.answer(
        "🎉 Welcome to **Telegram Bingo Bot**!\n\n"
        "Click the button below to open the interactive Bingo Web App:\n\n"
        "✨ Generate your 5x5 Bingo card\n"
        "✅ Mark numbers as they're called\n"
        "🏆 Win with 5 in a row/column/diagonal!\n\n"
        "**Commands:**\n"
        "/new - Generate new card\n"
        "/call - Call random number\n"
        "/reset - Reset game",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@router.message(Command("new"))
async def new_game(message: Message):
    user_id = str(message.from_user.id)
    games[user_id] = {
        "game": BingoGame(),
        "created": datetime.now(),
        "wins": []
    }
    await message.answer("🎫 **New Bingo card generated!**\nOpen the Web App to view it!", parse_mode="Markdown")

@router.message(Command("call"))
async def call_number(message: Message):
    global called_numbers
    # Generate random number 1-75
    number = random.randint(1, 75)
    while number in called_numbers:
        number = random.randint(1, 75)
    
    called_numbers.add(number)
    
    # Check wins for all players
    winners = []
    for user_id, data in games.items():
        if data["game"].mark_number(number):
            winners.append(user_id)
    
    letter = "BINGO"[number//15]
    response = f"🔊 **{letter} {number}**\n\n"
    
    if winners:
        response += f"🎉 **WINNERS!** {len(winners)} players got BINGO!\n"
    
    await message.answer(response, parse_mode="Markdown")

@router.message(Command("reset"))
async def reset_game(message: Message):
    global called_numbers
    user_id = str(message.from_user.id)
    if user_id in games:
        del games[user_id]
    called_numbers.clear()
    await message.answer("🔄 **Game reset!** Called numbers cleared.\nUse /new to start fresh!", parse_mode="Markdown")

# Flask Webhook & WebApp routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data and 'query_id':
        asyncio.create_task(bot.answer_web_app_query(data['query_id'], {
            'type': 'article',
            'id': data['query_id'],
            'input_message_content': {
                'message_text': '✅ Data received!'
            }
        }))
    return jsonify({'status': 'ok'})

@app.route('/api/game/<user_id>')
def get_game(user_id):
    game_data = games.get(user_id, {})
    if not game_data:
        return jsonify({'error': 'No active game'}), 404
    
    return jsonify({
        'grid': game_data['game'].grid,
        'marked': game_data['game'].marked,
        'wins': game_data['game'].wins,
        'called_numbers': list(called_numbers)
    })

@app.route('/api/game/<user_id>/mark', methods=['POST'])
def mark_number_endpoint(user_id):
    data = request.get_json()
    number = data.get('number')
    
    if user_id not in games:
        return jsonify({'error': 'No active game'}), 404
    
    game = games[user_id]['game']
    won = game.mark_number(number)
    
    return jsonify({
        'success': True,
        'won': won,
        'wins': game.wins
    })

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

async def main():
    # Start Flask in background thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Set webhook
    webhook_url = f"{WEBHOOK_URL}/webhook"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
