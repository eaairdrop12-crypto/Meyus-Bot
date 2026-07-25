import random
import sqlite3

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =====================
# BOT AYARLARI
# =====================

BOT_TOKEN = "7692589208:AAFHsNmRMOEbaBB2wqgn_lU-lAthhtGTxW0"

# =====================
# VERİTABANI
# =====================

db = sqlite3.connect("meyus.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    xp INTEGER DEFAULT 0
)
""")

db.commit()

# =====================
# VERİTABANI FONKSİYONLARI
# =====================

def add_xp(user):
    cursor.execute(
        "SELECT xp FROM users WHERE user_id=?",
        (user.id,)
    )

    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO users(user_id, first_name, xp) VALUES(?,?,?)",
            (user.id, user.first_name, 2)
        )
    else:
        cursor.execute(
            "UPDATE users SET xp=xp+2 WHERE user_id=?",
            (user.id,)
        )

    db.commit()

# =====================
# KOMUTLAR
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Merhaba! Ben MeyusBot.\n\n"
        "/help yazarak komutları görebilirsin."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """
📚 Komutlar

/start
/help
/espri
/zar
/coin
/profil
"""
    )

# =====================
# BOTU BAŞLAT
# =====================

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))

print("🤖 MeyusBot çalışıyor...")

app.run_polling()
