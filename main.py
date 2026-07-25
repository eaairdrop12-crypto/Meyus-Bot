import html
import os
import random
import asyncio
import sqlite3
from collections import defaultdict, deque
from datetime import time, datetime
from zoneinfo import ZoneInfo

import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    JobQueue,
)

TR_TZ = ZoneInfo("Europe/Istanbul")

def tr_lower(metin):
    """Türkçe İ/I harflerini doğru şekilde küçük harfe çevirir."""
    metin = metin.replace("İ", "i").replace("I", "ı")
    return metin.lower()

# =====================
# BOT AYARLARI
# =====================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not BOT_TOKEN or not ANTHROPIC_API_KEY:
    raise ValueError("BOT_TOKEN veya ANTHROPIC_API_KEY ortam değişkenleri eksik!")

ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
sohbet_gecmisi = defaultdict(lambda: deque(maxlen=10))

BOT_PERSONA = (
    "Sen MeyusBot adında, bir Telegram grubunda yaşayan samimi, esprili ve "
    "kısa cevaplar veren bir yapay zekasın. Türkçe konuşuyorsun, arkadaşça "
    "bir üslubun var, emoji kullanabilirsin ama abartma. Cevapların 1-3 "
    "cümleyi geçmesin, sohbet havasında ol, resmi konuşma."
)

# =====================
# KEYWORDS (Anahtar Kelimeler)
# =====================
# Buraya botun cevap vereceği kelimeleri ve karşılıklarını ekle
KEYWORDS = {
    "merhaba": "Selam! Nasılsın?",
    "nasılsın": "İyiyim, sen nasılsın? 😊",
    "günaydın": "Günaydın! Harika bir gün dilerim ☀️",
    "iyi geceler": "İyi geceler, tatlı rüyalar 🌙",
    "bot": "Ben buradayım! Sana nasıl yardımcı olabilirim?",
    "yardım": "Elbette, neye ihtiyacın var?",
}

# =====================
# AI CEVAP ÜRETME
# =====================

async def ai_cevap_uret(chat_id, kullanici_adi, mesaj):
    gecmis = sohbet_gecmisi[chat_id]
    gecmis.append({"role": "user", "content": f"{kullanici_adi}: {mesaj}"})

    def cagri():
        return ai_client.messages.create(
            model="claude-sonnet-4-latest", # Model adını güncelle (varsa) veya mevcut olanı kullan
            max_tokens=200,
            system=BOT_PERSONA,
            messages=list(gecmis),
        )

    try:
        response = await asyncio.to_thread(cagri)
        cevap = response.content.text
        gecmis.append({"role": "assistant", "content": cevap})
        return cevap
    except Exception as e:
        print(f"AI Hatası: {e}")
        return "Şu an düşüncelerim biraz karışık, birazdan tekrar dene 😅"

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS group_members(
 chat_id INTEGER,
 user_id INTEGER,
 first_name TEXT,
 PRIMARY KEY (chat_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS activity(
 chat_id INTEGER,
 user_id INTEGER,
 first_name TEXT,
 message_count INTEGER DEFAULT 0,
 last_message TEXT,
 last_seen TEXT,
 PRIMARY KEY (chat_id, user_id)
)
""")

db.commit()

def add_xp(user):
    cursor.execute("SELECT xp FROM users WHERE user_id=?", (user.id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO users(user_id, first_name, xp) VALUES(?,?,?)", (user.id, user.first_name, 2))
    else:
        cursor.execute("UPDATE users SET xp=xp+2 WHERE user_id=?", (user.id,))
    db.commit()

def get_user(user_id):
    cursor.execute("SELECT first_name, xp FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def remember_group_member(chat_id, user):
    cursor.execute("INSERT OR REPLACE INTO group_members(chat_id, user_id, first_name) VALUES(?,?,?)", (chat_id, user.id, user.first_name))
    db.commit()

def get_group_members(chat_id):
    cursor.execute("SELECT user_id, first_name FROM group_members WHERE chat_id=?", (chat_id,))
    return cursor.fetchall()

def get_all_group_chat_ids():
    cursor.execute("SELECT DISTINCT chat_id FROM group_members")
    return [row for row in cursor.fetchall()]

def mention_all_text(chat_id):
    members = get_group_members(chat_id)
    if not members:
        return None
    etiketler = [f'<a href="tg://user?id={uid}">{ad}</a>' for uid, ad in members]
    return " ".join(etiketler)

def log_activity(chat_id, user, mesaj_metni):
    simdi = datetime.now(TR_TZ).strftime("%d.%m.%Y %H:%M")
    kisa_mesaj = mesaj_metni[:60]
    
    cursor.execute("SELECT message_count FROM activity WHERE chat_id=? AND user_id=?", (chat_id, user.id))
    row = cursor.fetchone()
    
    if row is None:
        cursor.execute("INSERT INTO activity(chat_id, user_id, first_name, message_count, last_message, last_seen) VALUES(?,?,?,?,?,?)",
                       (chat_id, user.id, user.first_name, 1, kisa_mesaj, simdi))
    else:
        cursor.execute("UPDATE activity SET message_count=message_count+1, first_name=?, last_message=?, last_seen=? WHERE chat_id=? AND user_id=?",
                       (user.first_name, kisa_mesaj, simdi, chat_id, user.id))
    db.commit()

# =====================
# MESAJ İŞLEYİCİLERİ
# =====================

async def keyword_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if update.effective_chat.type in ("group", "supergroup"):
        remember_group_member(update.effective_chat.id, update.effective_user)
        log_activity(update.effective_chat.id, update.effective_user, update.message.text)

    metin_ham = update.message.text
    metin = tr_lower(metin_ham)
    chat_id = update.effective_chat.id
    kullanici_adi = update.effective_user.first_name

    bot_username = context.bot.username
    mention_edildi = bot_username and f"@{bot_username.lower()}" in metin
    reply_bota_mi = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )

    if mention_edildi or reply_bota_mi:
        add_xp(update.effective_user)
        cevap = await ai_cevap_uret(chat_id, kullanici_adi, metin_ham)
        await update.message.reply_text(cevap)
        return

    for kelime, cevap in KEYWORDS.items():
        if kelime in metin:
            add_xp(update.effective_user)
            await update.message.reply_text(cevap)
            return

    if update.effective_chat.type in ("group", "supergroup") and random.random() < 0.05:
        add_xp(update.effective_user)
        cevap = await ai_cevap_uret(chat_id, kullanici_adi, metin_ham)
        await update.message.reply_text(cevap)

async def gunaydin_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in get_all_group_chat_ids():
        etiketler = mention_all_text(chat_id)
        if not etiketler:
            continue
        foto_url = f"https://picsum.photos/800/600?random={random.randint(1, 100000)}"
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=foto_url,
            caption=f"☀️ Günaydın! Herkese bereketli bir gün diliyorum 🌞\n\n{etiketler}",
            parse_mode="HTML"
        )

async def iyigeceler_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in get_all_group_chat_ids():
        etiketler = mention_all_text(chat_id)
        if not etiketler:
            continue
        foto_url = f"https://picsum.photos/800/600?random={random.randint(1, 100000)}"
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=foto_url,
            caption=f"🌙 İyi geceler herkese, tatlı rüyalar 💤\n\n{etiketler}",
            parse_mode="HTML"
        )

# =====================
# BAŞLATMA FONKSİYONU
# =====================

async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    job_queue = application.job_queue

    # Handler'ları ekle
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyword_listener))
    
    # Zamanlanmış görevleri ayarla
    job_queue.run_daily(gunaydin_job, time(hour=7, tzinfo=TR_TZ))
    job_queue.run_daily(iyigeceler_job, time(hour=23, tzinfo=TR_TZ))

    print("Bot başlatılıyor...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)
 __name__ == "__main__":
    asyncio.run(main())
