import html
import os
import random
import re
import asyncio
import sqlite3
from collections import defaultdict, deque
from datetime import time, datetime
from zoneinfo import ZoneInfo

from openai import OpenAI
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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("BOT_TOKEN veya GROQ_API_KEY ortam değişkenleri eksik!")

ai_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
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
    "yardım": "Elbette, neye ihtiyacın var?",
}

# =====================
# SAAT ESPRİLERİ
# =====================

TIME_PATTERN = re.compile(r'(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)')
SAAT_KELIME_PATTERN = re.compile(r'\bsaat\s+([01]?\d|2[0-3])\b')

SAAT_CEVAPLARI = [
    "Saat {saat} mi? Kahve molası tam zamanı ☕😄",
    "{saat}'te herkes hâlâ hayatta, helal olsun 💪😂",
    "Vay be, {saat}! Zaman su gibi akıp gidiyor ⏳✨",
    "{saat} demek, tam bir şeyler atıştırma vakti 🍫😋",
    "Saat {saat}... yatalım mı, uyanık mı kalalım? Karar sizin 😴🤔",
    "{saat} gibi bir saat, tam da espri saati! 😆",
    "Aa {saat} olmuş, ben hâlâ burada dedikodu peşindeyim 🕵️‍♂️😂",
    "{saat}, mükemmel bir sohbet saati! Devam edelim 🥳",
    "{saat}'ü gösteriyor demek ki, bir çay molası şart ☕🍪",
]

def saat_tespit_et(metin):
    eslesme = TIME_PATTERN.search(metin)
    if eslesme:
        return f"{eslesme.group(1)}:{eslesme.group(2)}"
    eslesme2 = SAAT_KELIME_PATTERN.search(tr_lower(metin))
    if eslesme2:
        return f"{eslesme2.group(1)}:00"
    return None

async def saat_cevabi_gonder(update, saat):
    sablon = random.choice(SAAT_CEVAPLARI)
    await update.message.reply_text(sablon.format(saat=saat))

# =====================
# /slap İÇİN VERİLER
# =====================

TOKAT_HAREKETLERI = [
    "kocaman bir balıkla tokatladı 🐟",
    "uçan bir sandalyeyle selamladı 🪑",
    "sopayla nazikçe uyardı 🏒",
    "sanal ama acıtan bir tokat attı 🖐️",
    "sıcak bir pizza dilimiyle tokatladı 🍕",
    "klavyeyle tokatladı ⌨️",
    "bir tokat serveti gibi savurdu 👋",
    "ayakkabısıyla fırlattı 👟",
]

# =====================
# /siir İÇİN VERİLER
# =====================

SIIR_KONULARI = [
    "hayat", "kahve", "pazartesi", "arkadaşlık", "yaz",
    "tembellik", "aşk", "para", "uyku", "grup sohbeti",
]

SIIR_PERSONA = (
    "Sen MeyusBot'sun, Türkçe, esprili ve sıcak şiirler yazan bir yapay "
    "zekasın. Verilen konu hakkında 4-8 dizelik, komik ama akıcı bir şiir "
    "yaz. Sadece şiiri yaz, başka açıklama ekleme."
)

# =====================
# /fal İÇİN VERİLER
# =====================

FAL_METINLERI = [
    "Fincanında büyük bir haber görüyorum ☕ Yakında biri seni tatlıyla şaşırtacak 🍰",
    "Telve şekli bana bir yol gösteriyor 🛣️ Önündeki hafta biraz koşuşturmaca ama sonu güzel 😌",
    "Fal bana diyor ki: bugün gönlünden geçeni söylersen şaşırtıcı bir 'evet' duyabilirsin 💌",
    "Yıldızlar senin adına parlıyor ✨ Bu hafta beklenmedik güzel bir haber gelebilir 🎉",
    "Fincanda küçük bir kuş görüyorum 🐦 Uzaktan bir haber yolda, sabırlı ol",
    "Telvede para şekli var 💰 Cüzdanına iyi bir sürpriz gelebilir, ama abartma 😄",
    "Fal diyor ki bugün biraz dırdırcı olabilirsin, sabırlı biriyle konuş 😅",
    "Fincanının kenarında bir kalp görüyorum ❤️ Aşk ya da dostluk konularında güzel gelişmeler var",
    "Bu fal biraz esrarengiz... uzun lafın kısası: kahveni bitirip biraz dinlen 😴☕",
    "Telvede bir yol ayrımı var 🔀 Yakında bir karar vermen gerekebilir, içgüdülerine güven",
]

# =====================
# /soru İÇİN VERİLER
# =====================

SORU_LISTESI = [
    "Hayatında hiç pişman olmadığın en çılgın kararın ne? 🤔",
    "Bir günlüğüne süper güç sahibi olsan ne yapardın? 🦸",
    "En sevdiğin çocukluk anın nedir? 🧸",
    "Bir kitabın veya filmin dünyasında yaşasaydın hangisini seçerdin? 📖",
    "Şu an ışınlanabilseydin nereye giderdin? 🌍",
    "Ömür boyu tek bir yemek yiyecek olsan ne olurdu? 🍝",
    "En son ne zaman gerçekten kahkaha attın, neye gülmüştün? 😂",
    "Bir günlüğüne başka birinin hayatını yaşasaydın kim olurdu? 🎭",
    "Hangi alışkanlığından vazgeçmek istiyorsun ama vazgeçemiyorsun? 😅",
    "Sence grup içindeki en şanslı kişi kim? 🍀",
]

# =====================
# AI CEVAP ÜRETME
# =====================

async def ai_cevap_uret(chat_id, kullanici_adi, mesaj):
    gecmis = sohbet_gecmisi[chat_id]
    gecmis.append({"role": "user", "content": f"{kullanici_adi}: {mesaj}"})

    def cagri():
        mesajlar = [{"role": "system", "content": BOT_PERSONA}] + list(gecmis)
        return ai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=200,
            messages=mesajlar,
        )

    try:
        response = await asyncio.to_thread(cagri)
        cevap = response.choices[0].message.content
        gecmis.append({"role": "assistant", "content": cevap})
        return cevap
    except Exception as e:
        print(f"AI Hatası: {e}")
        return "Şu an düşüncelerim biraz karışık, birazdan tekrar dene 😅"

async def siir_uret(konu):
    def cagri():
        return ai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=250,
            messages=[
                {"role": "system", "content": SIIR_PERSONA},
                {"role": "user", "content": f"Konu: {konu}"},
            ],
        )

    try:
        response = await asyncio.to_thread(cagri)
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI Hatası (şiir): {e}")
        return "Şiir perim şu an bulutların arasında kayboldu, birazdan tekrar dene 😅"

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_settings(
 chat_id INTEGER PRIMARY KEY,
 enabled INTEGER DEFAULT 1
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

def is_bot_enabled(chat_id):
    cursor.execute("SELECT enabled FROM bot_settings WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        return True
    return bool(row[0])

def set_bot_enabled(chat_id, enabled):
    cursor.execute("INSERT OR REPLACE INTO bot_settings(chat_id, enabled) VALUES(?,?)", (chat_id, int(enabled)))
    db.commit()

async def is_admin(update, context):
    if update.effective_chat.type not in ("group", "supergroup"):
        return False
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        print(f"Admin kontrol hatası: {e}")
        return False

# =====================
# KOMUTLAR
# =====================

async def herkes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Bu komut sadece gruplarda çalışır.")
        return

    chat_id = update.effective_chat.id
    etiketler = mention_all_text(chat_id)

    if not etiketler:
        await update.message.reply_text("Henüz kayıtlı kimse yok, biraz konuşma olsun önce 😄")
        return

    await update.message.reply_text(f"📢 {etiketler}", parse_mode="HTML")

async def botkapat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Bu komut sadece gruplarda çalışır.")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("Bu komutu sadece grup yöneticileri kullanabilir 🙅")
        return
    set_bot_enabled(update.effective_chat.id, False)
    await update.message.reply_text("Tamam, sustum 🤐 Tekrar konuşmamı istersen /botac yazman yeterli.")

async def botac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Bu komut sadece gruplarda çalışır.")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("Bu komutu sadece grup yöneticileri kullanabilir 🙅")
        return
    set_bot_enabled(update.effective_chat.id, True)
    await update.message.reply_text("Ben döndüm! Kaldığım yerden devam 🥳")

async def slap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Bu komut sadece gruplarda çalışır 😄")
        return

    gonderen = update.effective_user
    hareket = random.choice(TOKAT_HAREKETLERI)

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        hedef = update.message.reply_to_message.from_user
        if hedef.id == gonderen.id:
            await update.message.reply_text(f"{gonderen.first_name} kendi kendini {hareket} 😂")
        else:
            await update.message.reply_text(f"{gonderen.first_name}, {hedef.first_name}'i {hareket}")
        return

    uyeler = [u for u in get_group_members(update.effective_chat.id) if u[0] != gonderen.id]
    if not uyeler:
        await update.message.reply_text("Tokatlayacak kimse yok, biraz daha kalabalık olalım 😅")
        return

    hedef_id, hedef_ad = random.choice(uyeler)
    await update.message.reply_text(f"{gonderen.first_name}, {hedef_ad}'i {hareket}")

async def siir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    konu = " ".join(context.args) if context.args else random.choice(SIIR_KONULARI)
    siir = await siir_uret(konu)
    await update.message.reply_text(f"📜 {konu.capitalize()} üzerine bir şiir:\n\n{siir}")

async def aktivite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Bu komut sadece gruplarda çalışır.")
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    cursor.execute(
        "SELECT message_count, last_message, last_seen FROM activity WHERE chat_id=? AND user_id=?",
        (chat_id, user.id),
    )
    row = cursor.fetchone()

    if row is None:
        await update.message.reply_text("Henüz senden bir kayıt yok, biraz konuş bakalım 😄")
        return

    mesaj_sayisi, son_mesaj, son_gorulme = row
    await update.message.reply_text(
        f"📊 {user.first_name} için aktivite:\n"
        f"• Toplam mesaj: {mesaj_sayisi}\n"
        f"• Son görülme: {son_gorulme}\n"
        f"• Son mesaj: {html.escape(son_mesaj)}"
    )

async def siralama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Bu komut sadece gruplarda çalışır.")
        return

    chat_id = update.effective_chat.id
    cursor.execute(
        "SELECT first_name, message_count FROM activity WHERE chat_id=? ORDER BY message_count DESC LIMIT 10",
        (chat_id,),
    )
    satirlar = cursor.fetchall()

    if not satirlar:
        await update.message.reply_text("Henüz sıralama için yeterli veri yok 😄")
        return

    madalyalar = ["🥇", "🥈", "🥉"]
    metin = "🏆 Grubun en aktifleri:\n\n"
    for i, (ad, sayi) in enumerate(satirlar):
        rozet = madalyalar[i] if i < 3 else f"{i + 1}."
        metin += f"{rozet} {ad} — {sayi} mesaj\n"

    await update.message.reply_text(metin)

async def fal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_adi = update.effective_user.first_name
    fal = random.choice(FAL_METINLERI)
    await update.message.reply_text(f"☕ {kullanici_adi}, fincanına bakıyorum...\n\n{fal}")

async def soru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    soru = random.choice(SORU_LISTESI)
    await update.message.reply_text(f"💭 Sohbet sorusu: {soru}")

# =====================
# MESAJ İŞLEYİCİLERİ
# =====================

async def keyword_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if update.effective_chat.type in ("group", "supergroup"):
        remember_group_member(update.effective_chat.id, update.effective_user)
        log_activity(update.effective_chat.id, update.effective_user, update.message.text)

        if not is_bot_enabled(update.effective_chat.id):
            return

    metin_ham = update.message.text
    metin = tr_lower(metin_ham)
    chat_id = update.effective_chat.id
    kullanici_adi = update.effective_user.first_name

    bot_username = context.bot.username
    mention_edildi = bot_username and f"@{bot_username.lower()}" in metin
    meyus_cagrildi = "meyus" in metin
    reply_bota_mi = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )

    if mention_edildi or reply_bota_mi or meyus_cagrildi:
        add_xp(update.effective_user)
        cevap = await ai_cevap_uret(chat_id, kullanici_adi, metin_ham)
        await update.message.reply_text(cevap)
        return

    for kelime, cevap in KEYWORDS.items():
        if kelime in metin:
            add_xp(update.effective_user)
            await update.message.reply_text(cevap)
            return

    saat = saat_tespit_et(metin_ham)
    if saat:
        add_xp(update.effective_user)
        await saat_cevabi_gonder(update, saat)
        return

    if update.effective_chat.type in ("group", "supergroup") and random.random() < 0.05:
        add_xp(update.effective_user)
        cevap = await ai_cevap_uret(chat_id, kullanici_adi, metin_ham)
        await update.message.reply_text(cevap)
        return

    if update.effective_chat.type == "private":
        add_xp(update.effective_user)
        cevap = await ai_cevap_uret(chat_id, kullanici_adi, metin_ham)
        await update.message.reply_text(cevap)

async def gunaydin_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in get_all_group_chat_ids():
        if not is_bot_enabled(chat_id):
            continue
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
        if not is_bot_enabled(chat_id):
            continue
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

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    job_queue = application.job_queue

    # Handler'ları ekle
    application.add_handler(CommandHandler("herkes", herkes_command))
    application.add_handler(CommandHandler("botkapat", botkapat_command))
    application.add_handler(CommandHandler("botac", botac_command))
    application.add_handler(CommandHandler("slap", slap_command))
    application.add_handler(CommandHandler("siir", siir_command))
    application.add_handler(CommandHandler("aktivite", aktivite_command))
    application.add_handler(CommandHandler("siralama", siralama_command))
    application.add_handler(CommandHandler("fal", fal_command))
    application.add_handler(CommandHandler("soru", soru_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyword_listener))

    # Zamanlanmış görevleri ayarla
    job_queue.run_daily(gunaydin_job, time(hour=7, tzinfo=TR_TZ))
    job_queue.run_daily(iyigeceler_job, time(hour=23, tzinfo=TR_TZ))

    print("Bot başlatılıyor...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
