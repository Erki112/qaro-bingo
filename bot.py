import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8487920836:AAEBYuO1MCJNRgmMaLk0k70xp6tqKglrnmM"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://qaro-bingo.onrender.com"
    kb = [[InlineKeyboardButton("🎮 TAPHAA JALQABI", web_app_info=WebAppInfo(url=url))]]
    await update.message.reply_text("👋 Baga dhuftan! Bingo taphachuuf gadi tuqaa.", reply_markup=InlineKeyboardMarkup(kb))

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

