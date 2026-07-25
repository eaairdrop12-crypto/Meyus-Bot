import random
import sqlite3
from datetime import time
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TR_TZ = ZoneInfo("Europe/Istanbul")

# =====================
# BOT AYARLARI
# =====================

# ÖNEMLİ: Token'ını BotFather'dan /revoke ile yenile ve
# yeni token'ı buraya yaz (eski token'ı asla paylaşma).
BOT_TOKEN = "7692589208:AAF6RRIaelarag9XN9J_NKhU_igJZ6yXtak"

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


def remember_group_member(chat_id, user):
    cursor.execute(
        "INSERT OR REPLACE INTO group_members(chat_id, user_id, first_name) VALUES(?,?,?)",
        (chat_id, user.id, user.first_name)
    )
    db.commit()


def get_group_members(chat_id):
    cursor.execute(
        "SELECT user_id, first_name FROM group_members WHERE chat_id=?",
        (chat_id,)
    )
    return cursor.fetchall()


def get_all_group_chat_ids():
    cursor.execute("SELECT DISTINCT chat_id FROM group_members")
    return [row[0] for row in cursor.fetchall()]


def mention_all_text(chat_id):
    members = get_group_members(chat_id)
    if not members:
        return None

    etiketler = [
        f'<a href="tg://user?id={uid}">{ad}</a>'
        for uid, ad in members
    ]
    return " ".join(etiketler)

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
/siir
"""
    )

KEYWORDS = {
    "selam": "Selam! 👋",
    "merhaba": "Merhaba! 🤖",
    "meyusbot": "Beni mi çağırdınız? 😄",
    "meyus": "Beni mi çağırdınız? Ben buradayım! 😄🤖",
    "günaydın": "Günaydın! Bugün harika bir gün olacak ☀️",
    "iyi geceler": "İyi geceler, tatlı rüyalar 🌙💤",
    "nasılsın": "Ben bir botum, hep iyiyim! Sen nasılsın? 😎",
    "napıyorsun": "Sizi dinliyorum, espri patlatmaya hazırım 😄",
    "aç": "Karnın mı acıktı? Bence pizza zamanı 🍕",
    "acıktım": "Ben de espri yiyorum, doyurucu değil ama komik 😂",
    "yorgunum": "Biraz dinlen, ben burada nöbetteyim 🛌",
    "sıkıldım": "/espri yaz, seni güldüreyim 😏",
    "kahve": "Kahve molası zamanı mı? ☕",
    "hava nasıl": "Ben botum, dışarı çıkamıyorum ama umarım güneşlidir ☀️",
    "teşekkürler": "Rica ederim! 🤗",
    "sağol": "Ne demek, her zaman! 🙌",
    "iyi akşamlar": "İyi akşamlar! Keyifli bir akşam olsun 🌆",
    "günler": "Güzel günler dilerim! ✨",
    "aşk": "Aşk mı? Ben sadece kod ve espriden anlarım 💔😂",
    "para": "Para mı? Keşke bende de olsaydı, ben bedavayım 💸",
    "okul": "Okul mu? Ben hep tatildeyim 😄",
    "iş": "İş güç, hep aynı telaş 😅",
    "bot": "Evet, ben buradayım! 🤖",
    "robot": "Robot değilim, ben MeyusBot'um! 🤖✨",
    "şaka": "/espri yazarsan sana bir tane patlatayım 😄",
    "canım sıkıldı": "O zaman /zar at, biraz eğlenelim 🎲",
    "n'aber": "İyidir, sen n'aber? 😄",
    "kanka": "Kanka burada! 🤝",
    "dostum": "Ne var dostum? 😎",
    "iyi misin": "Ben botum, hep formdayım! Sen nasılsın? 💪",
    "napalım": "Bilmem, /espri yazalım mı? 😄",
    "canım": "Canım benim, ben de seni severim 🥰",
    "üzgünüm": "Üzülme, /espri seni güldürür 🤗",
    "mutluyum": "Ne güzel! Mutluluk bulaşıcıdır 😄🎉",
    "hadi": "Hadi bakalım, ne yapıyoruz? 😄",
    "gel": "Geldim bile! 👀",
    "git": "Nereye? Ben burada kalıyorum 😄",
    "yemek": "Yemek zamanı mı? Afiyet olsun! 🍽️",
    "pizza": "Pizza dediysen ben de geliyorum 🍕",
    "uyku": "Uyku mu geldi? İyi geceler o zaman 😴",
    "uykum var": "Git yat o zaman, ben nöbetteyim 🛏️",
    "sinirliyim": "Sakin ol, derin bir nefes al 🧘",
    "kızgınım": "Sakin, sakin... /zar at rahatlarsın belki 🎲",
    "bilmiyorum": "Kimse bilmiyor zaten, merak etme 😄",
    "haklısın": "Tabii ki haklıyım, ben botum 😏",
    "yalan": "Ben hiç yalan söylemem, ben botum 🤖",
    "doğru": "Doğru bildin! 👍",
    "gülüyorum": "Gülmek bulaşıcıdır, ben de gülüyorum 😂",
    "ağlıyorum": "Üzülme, buradayım 🤗",
    "korkuyorum": "Korkma, ben yanındayım 💪",
    "tembel": "Tembellik iyi bir şeydir bazen 😴",
    "çalışkan": "Aferin sana, örnek olsun herkese 👏",
    "spor": "Spor mu? Ben sadece kod koşturuyorum 🏃‍♂️",
    "futbol": "Futbol izlemeye bayılırım... aslında botum ama 😄⚽",
    "müzik": "Müzik ruhun gıdasıdır 🎵",
    "film": "İyi bir film önerisi ister misin? 🍿",
    "dizi": "Bu akşam dizi mi izliyoruz? 📺",
    "hava soğuk": "Üşüme, kalın giyin! 🧥",
    "hava sıcak": "Serin bir yerde otur, su iç 💧",
    "yağmur": "Yağmur güzel bir şeydir, dinlenmeye bahane ☔",
    "kar": "Kar yağıyor mu? Kartopu zamanı ❄️",
    "tatil": "Tatil dedin de içim gitti 🏖️",
}

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

SIIRLER = [
    "Sabah rüzgarı eser yavaşça,\nGüneş doğar, gökyüzü aydınlanır.\nBu grup da bir aile gibi,\nHer gün biraz daha canlanır. 🌅",
    "Gece iner, yıldızlar parlar,\nHerkes biraz dinlenmeyi hak eder.\nYarın yeni bir gün başlar,\nBu dostluk hep böyle sürer. 🌙",
    "Kahve kokusu yayılır odaya,\nGülüşmeler karışır sohbete.\nBu grupta herkes bir tada,\nBirlik olmak yeter bize elbette. ☕",
    "Zaman akar durmadan,\nAma dostluklar kalıcıdır.\nHer mesajda bir gülümseme,\nBu grup hepimize armağandır. 💫",
    "Bulutlar gökte süzülür,\nRüzgar hafifçe eser.\nBirlikte geçen her an,\nBize güzel anılar getirir. 🌤️",
]

async def siir_gonder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Şiir Gönder", callback_data="siir_gonder")]
    ])
    await update.message.reply_text(
        "Herkese bir şiir göndermek için butona bas 👇",
        reply_markup=keyboard
    )

async def siir_buton_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    etiketler = mention_all_text(chat_id)
    siir = random.choice(SIIRLER)

    if etiketler:
        mesaj = f"{siir}\n\n{etiketler}"
    else:
        mesaj = siir

    await context.bot.send_message(
        chat_id=chat_id,
        text=mesaj,
        parse_mode="HTML"
    )

async def keyword_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if update.effective_chat.type in ("group", "supergroup"):
        remember_group_member(update.effective_chat.id, update.effective_user)

    metin = update.message.text.lower()

    for kelime, cevap in KEYWORDS.items():
        if kelime in metin:
            add_xp(update.effective_user)
            await update.message.reply_text(cevap)
            break

# =====================
# OTOMATİK GÜNAYDIN / İYİ GECELER
# =====================

async def gunaydin_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in get_all_group_chat_ids():
        etiketler = mention_all_text(chat_id)
        if not etiketler:
            continue
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"☀️ Günaydın! Herkese bereketli bir gün diliyorum 🌞\n\n{etiketler}",
            parse_mode="HTML"
        )

async def iyigeceler_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in get_all_group_chat_ids():
        etiketler = mention_all_text(chat_id)
        if not etiketler:
            continue
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🌙 İyi geceler herkese, tatlı rüyalar 💤\n\n{etiketler}",
            parse_mode="HTML"
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
app.add_handler(CommandHandler("siir", siir_gonder))
app.add_handler(CallbackQueryHandler(siir_buton_callback, pattern="^siir_gonder$"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyword_listener))

app.job_queue.run_daily(gunaydin_job, time=time(hour=8, minute=0, tzinfo=TR_TZ))
app.job_queue.run_daily(iyigeceler_job, time=time(hour=23, minute=0, tzinfo=TR_TZ))

print("🤖 MeyusBot çalışıyor...")

app.run_polling()
  
