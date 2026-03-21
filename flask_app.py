import os
import random
from flask import Flask, render_template, jsonify
# Library telegram ol-fe'uu (requirements.txt keessatti waan jiruuf)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
import threading

app = Flask(__name__)

# --- BINGO LOGIC ---
def generate_card():
    card = []
    ranges = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]
    for r in ranges:
        column = random.sample(range(r[0], r[1] + 1), 5)
        card.append(column)
    card[2][2] = 0  # Free space
    return card

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_card/<user_id>')
def get_card(user_id):
    card = generate_card()
    return jsonify({"card": card})

# --- TELEGRAM BOT LOGIC ---
TOKEN = "8487920836:AAFe77nalADov0H7ufj4GWZb0gYiEq5xdBQ"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Hubachiisa: Linkii Koyeb siif kennu asirratti jijjiiri (Tarkaanfii itti aanu)
    web_app_url = "https://qaro-bingo-erki112.koyeb.app" 
    
    keyboard = [[InlineKeyboardButton("🎮 TAPHAA JALQABI", web_app_info=WebAppInfo(url=web_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Baga nagaan dhuftan!\n\nQaro Bingo taphachuuf button gadii tuqaa.",
        reply_markup=reply_markup
    )

def run_bot():
    # Koyeb irratti Proxy hin barbaachisu!
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling(drop_pending_updates=True)

# Bot-ichi duuba (background) akka hojjetuuf
if __name__ == '__main__':
    # Flask fi Bot walfaana akka ka'an gochuuf
    threading.Thread(target=run_bot, daemon=True).start()
    # Koyeb port 8000 fayyadama
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

