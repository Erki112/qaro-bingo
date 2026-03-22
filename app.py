import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# TOKEN KEE ASITTI GALCHI
TOKEN = "8487920836:AAFe77nalADov0H7ufj4GWZb0gYiEq5xdBQ"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Linkii Web App keetii (isa Render duraan siif kenne) asitti galchi
    url = "https://qaro-bingo.onrender.com" 
    kb = [[InlineKeyboardButton("🎮 TAPHAA JALQABI", web_app_info=WebAppInfo(url=url))]]
    await update.message.reply_text(
        "👋 Baga nagaan dhuftan! Bingo taphachuuf gadi tuqaa.", 
        reply_markup=InlineKeyboardMarkup(kb)
    )

if __name__ == '__main__':
    print("Botichi Background irratti hojii jalqabeera...")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling(drop_pending_updates=True)
