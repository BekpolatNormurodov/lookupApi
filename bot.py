
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests

# Django APIni URLi (ngrok yoki localhost)
DJANGO_SEARCH_URL = "http://127.0.0.1:8000/search/?q="  # yoki ngrok orqali bo'lsa o'sha URL

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Qidiruv uchun telefon raqam yoki Telegram ID yuboring.")

# Matnli so'rovlar uchun handler
async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    response = requests.get(DJANGO_SEARCH_URL + query)

    if response.status_code == 200:
        data = response.json()
        if data:
            reply = "\n\n".join([
                f"📞 Phone: {u['phone']}\n👤 Name: {u['first_name']} {u['last_name'] or ''}\n🆔 Telegram ID: {u['telegram_id']}\n🔗 Username: @{u['username']}" 
                for u in data
            ])
        else:
            reply = "❌ Hech narsa topilmadi."
    else:
        reply = "❗ Qidiruvda xatolik yuz berdi."

    await update.message.reply_text(reply)

# Botni ishga tushuruvchi asosiy funksiya
def main():
    application = Application.builder().token("7136158913:AAFBYCzwtwLx0x7IQ0JszcwaGxLeBwB2590").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_user))

    application.run_polling()

if __name__ == "__main__":
    main()
