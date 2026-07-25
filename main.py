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

# ÖNEMLİ: Token'ını BotFather'dan /revoke ile yenile ve
# yeni token'ı buraya yaz (eski token'ı asla paylaşma).
BOT_TOKEN = "BURAYA_YENI_TOKENINI_YAZ"

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


def get_user(user_id):
    cursor.execute(
        "SELECT first_name, xp FROM users WHERE user_id=?",
        (user_id,)
    )
    return cursor.fetchone()

# =====================
# KOMUTLAR
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_xp(update.effective_user)
    await update.message.reply_text(
        "🤖 Merhaba! Ben MeyusBot.\n\n"
        "/help yazarak komutları görebilirsin."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_xp(update.effective_user)
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

ESPRILER = [
    "Matematik öğretmeni neden üzgündü? Çünkü çok fazla problemi vardı.",
    "Bilgisayarım bugün çok üşengeç, sürekli 'cache' istiyor.",
    "İki atom yürüyor, biri diğerine 'elektron kaybettim' diyor. Diğeri: 'emin misin?' Birincisi: 'Eminim!'",
    "Neden programcılar karanlıkta çalışmayı sever? Çünkü 'light' bug'ları çeker.",
    "Bir SQL sorgusu bara girer, iki masaya yaklaşır ve sorar: 'Buraya katılabilir miyim?'",
]

async def espri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_xp(update.effective_user)
    await update.message.reply_text(random.choice(ESPRILER))

async def zar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_xp(update.effective_user)
    sonuc = random.randint(1, 6)
    await update.message.reply_text(f"🎲 Zar atıldı: {sonuc}")

async def coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_xp(update.effective_user)
    sonuc = random.choice(["Yazı 🪙", "Tura 🪙"])
    await update.message.reply_text(f"🪙 Sonuç: {sonuc}")

async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_xp(update.effective_user)
    user = update.effective_user
    row = get_user(user.id)

    if row is None:
        xp = 0
        first_name = user.first_name
    else:
        first_name, xp = row

    await update.message.reply_text(
        f"👤 Profil\n\n"
        f"İsim: {first_name}\n"
        f"XP: {xp}"
    )

# =====================
# BOTU BAŞLAT
# =====================

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("espri", espri))
app.add_handler(CommandHandler("zar", zar))
app.add_handler(CommandHandler("coin", coin))
app.add_handler(CommandHandler("profil", profil))

print("🤖 MeyusBot çalışıyor...")

app.run_polling()
