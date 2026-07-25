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
import random
import sqlite3

from telegram import (
    Update,
    ChatMemberUpdated,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = "BURAYA_BOT_TOKEN"

conn = sqlite3.connect("meyus.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    messages INTEGER DEFAULT 0,
    commands INTEGER DEFAULT 0
)
""")

conn.commit()

ESPIRILER = [
    "Çay koyun da muhabbete başlayalım. ☕",
    "Bugün de maaş almadan çalışıyorum. 😂",
    "Wi-Fi varsa umut vardır. 📶",
    "Ben sustuysam internet gitmiştir.",
    "Grup çok sessiz. 😄",
    "Ben botum ama dedikoduyu severim. 👀",
    "Bugün kim çay ısmarlıyor? ☕",
    "Sohbet ücretsizdir. 😎",
    "Klavyesi hızlı olan kazansın.",
    "Haydi biraz sohbet edin. 🤖"
]

KELIMELER = {
    "selam": [
        "Selam 👋",
        "Merhaba 😄",
        "Hoş geldin."
    ],
    "merhaba": [
        "Merhaba 😊"
    ],
    "nasılsın": [
        "Harikayım. Sen nasılsın? 🤖",
        "Kodlarım çalışıyor. 😄"
    ],
    "çay": [
        "Çaysız sohbet olmaz. ☕"
    ],
    "kahve": [
        "Kahve de güzel gider. ☕"
    ],
    "galatasaray": [
        "💛❤️ Cimbom konuşuluyorsa ben de buradayım."
    ],
    "fener": [
        "Rekabet güzeldir. ⚽"
        
    ]def get_user(user):
    cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user.id,)
    )
    veri = cursor.fetchone()

    if veri is None:
        cursor.execute("""
        INSERT INTO users(
            user_id,
            username,
            first_name,
            xp,
            level,
            messages,
            commands
        )
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            user.id,
            user.username,
            user.first_name,
            0,
            1,
            0,
            0
        ))

        conn.commit()


def add_xp(user):
    get_user(user)

    cursor.execute("""
    
   # =========================
# KOMUTLAR
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_command(update.effective_user)

    await update.message.reply_text(
        """
🤖 Merhaba!

Ben MeyusBot.

Komutlar:

/help
/espri
/zar
/coin
/şans
/profil
/top10
"""
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_command(update.effective_user)

    await update.message.reply_text(
        """
📚 Kullanılabilir Komutlar

🤖 Genel
/start
/help

😂 Eğlence
/espri
/zar
/coin
/şans

👤 Profil
/profil
/top10
"""
    )


async def espri(update: Update, context: ContextTypes.DEFAULT_TYPE):

   # =========================
# SOHBET SİSTEMİ
# =========================

async def sohbet(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    mesaj = update.message.text.lower()

    yeni_level = add_xp(user)

    if yeni_level:
        await update.message.reply_text(
            f"🎉 Tebrikler {user.first_name}!\n"
            f"⭐ Seviye {yeni_level} oldun."
        )

    # Kelime algılama
    for kelime, cevaplar in KELIMELER.items():
        if kelime in mesaj:
            await update.message.reply_text(
                random.choice(cevaplar)
            )
            return

    # %8 ihtimalle espri
    if random
    # =========================
# EK KOMUTLAR
# =========================

BILMECELER = [
    {
        "soru": "Kanadı var uçamaz, ayağı var kaçamaz. Nedir?",
        "cevap": "masa"
    },
    {
        "soru": "Dışı var içi yok, kapısı var eşiği yok. Nedir?",
        "cevap": "gömlek"
    },
    {
        "soru": "Suyu sever ama suda yaşayamaz. Nedir?",
        "cevap": "balıkçı"
    }
]

MOTIVASYON = [
    "💪 Bugün dünden daha iyi ol.",
    "🌟 Vazgeçme,
    # =========================
# ROZET SİSTEMİ
# =========================

ROZETLER = {
    100: "🥉 Aktif Üye",
    500: "🥈 Müdavim",
    1000: "🥇 Efsane Üye",
    2500: "👑 Meyus Ustası"
}


def rozet_bul(xp):
    rozet = "🎈 Yeni Üye"

    for gerekli_xp, ad in ROZETLER.items():
        if xp >= gerekli_xp:
            rozet = ad

    return rozet


async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE):

    add_command(update.effective_user)

    cursor.execute
    # =========================
# ADAM ASMACA
# =========================

KELIMELER_OYUN = [
    "telegram",
    "python",
    "galatasaray",
    "meyus",
    "bilgisayar",
    "ankara",
    "yapayzeka",
    "futbol"
]

oyunlar = {}


async def adamasmaca(update: Update, context: ContextTypes.DEFAULT_TYPE):

    add_command(update.effective_user)

    kelime = random.choice(KELIMELER_OYUN)

    oyunlar[update.effective_user.id] = {
        "kelime": kelime,
        "hak
        # =========================
# YÖNETİCİ KONTROLÜ
# =========================

from telegram.constants import ChatMemberStatus

async def admin_mi(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uye = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )

    return uye.status in (
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER
    )


# =========================
# SP
# =========================
# ANKET
# =========================

async def anket(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if len(context.args) == 0:
        await update.message.reply_text(
            "Kullanım:\n/anket Soru"
        )
        return

    soru = " ".join(context.args)

    mesaj = await update.message.reply_text(
        f"📊 ANKET\n\n{soru}"
    )

    await mesaj.reply_markup

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👍 = Evet\n👎 = Hayır"
    )


# =========================
# DUYURU
# =========================

async def duyuru(update: Update, context: ContextTypes

}# =========================
# HATA YAKALAMA
# =========================

async def error_handler(update, context):
    print("HATA:", context.error)

app.add_error_handler(error_handler)

print("=" * 40)
print("🤖 MeyusBot v1.0")
print("Durum : Aktif")
print("SQLite : Bağlandı")
print("XP Sistemi : Aktif")
print("Komutlar : Yüklendi")
print("=" * 40)
