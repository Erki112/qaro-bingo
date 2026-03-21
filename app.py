import os
import random
import threading
from flask import Flask, render_template, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = Flask(__name__)

# --- BINGO LOGIC ---
def generate_card():
    card = []
    ranges = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]
    for r in ranges:
        column = random.sample(range(r[0], r[1] + 1), 5)
        card.append(column)
    card[2][2] = 0
    return card

@app.route('/')
def index():
    return "Bingo Bot is Running!"

@app.route('/get_card')
def get_card():
    return jsonify({"card": generate_card()})

# --- TELEGRAM BOT LOGIC ---
TOKEN = "8487920836:AAFe77nalADov0H7ufj4GWZb0gYiEq5xdBQ"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Linkii Render keetii kooppii godhii as galchi
    web_app_url = "https://qaro-bingo.onrender.com"
    
    keyboard = [[InlineKeyboardButton("🎮 TAPHAA JALQABI", web_app_info=WebAppInfo(url=web_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Baga nagaan dhuftan!\n\nQaro Bingo taphachuuf button gadii tuqaa.",
        reply_markup=reply_markup
    )

def run_bot():
    # Polling akka malee hin baay'anneef drop_pending_updates=True dabalameera
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    # Bot-icha thread addaatiin kaasi
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Flask port Render irraa fudhata
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
