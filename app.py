import os
import random
import threading
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- FLASK (WEB SERVER) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Running!", 200

@app.route('/get_card')
def get_card():
    card = []
    ranges = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]
    for r in ranges:
        column = random.sample(range(r[0], r[1] + 1), 5)
        card.append(column)
    card[2][2] = 0
    return jsonify({"card": card})

# --- TELEGRAM BOT ---
TOKEN = "8487920836:AAFe77nalADov0H7ufj4GWZb0gYiEq5xdBQ"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Linkii Render keetii asitti sirreessi
    url = "https://qaro-bingo.onrender.com"
    kb = [[InlineKeyboardButton("🎮 TAPHAA JALQABI", web_app_info=WebAppInfo(url=url))]]
    await update.message.reply_text(
        "👋 Baga dhuftan! Bingo taphachuuf gadi tuqaa.", 
        reply_markup=InlineKeyboardMarkup(kb)
    )

def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    # 1. Bot-icha Background irratti kaasi
    threading.Thread(target=run_bot, daemon=True).start()
    
    # 2. Flask Render irratti jalqabi (Port 10000)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
