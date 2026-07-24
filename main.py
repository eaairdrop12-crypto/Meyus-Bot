from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

BOT_TOKEN = "7692589208:AAFHsNmRMOEbaBB2wqgn_lU-lAthhtGTxW0"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Merhaba! Ben MeyusBot.\nÇalışıyorum. 🎉"
    )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    print("MeyusBot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
