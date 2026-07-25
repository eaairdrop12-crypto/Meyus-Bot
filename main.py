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
)

TR_TZ = ZoneInfo("Europe/Istanbul")


def tr_lower(metin):
    """Türkçe İ/I harflerini doğru şekilde küçük harfe çevirir.
    Python'un varsayılan .lower() fonksiyonu 'İ' harfini yanlış
    çevirdiği için (noktalı özel karakter üretiyor), önce bu
    harfleri manuel değiştirip sonra normal lower() uyguluyoruz."""
    metin = metin.replace("İ", "i").replace("I", "ı")
    return metin.lower()

# =====================
# BOT AYARLARI
# =====================

BOT_TOKEN = os.environ["BOT_TOKEN"]

ai_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
sohbet_gecmisi = defaultdict(lambda: deque(maxlen=10))

BOT_PERSONA = (
    "Sen MeyusBot adında, bir Telegram grubunda yaşayan samimi, esprili ve "
    "kısa cevaplar veren bir yapay zekasın. Türkçe konuşuyorsun, arkadaşça "
    "bir üslubun var, emoji kullanabilirsin ama abartma. Cevapların 1-3 "
    "cümleyi geçmesin, sohbet havasında ol, resmi konuşma."
)


async def ai_cevap_uret(chat_id, kullanici_adi, mesaj):
    gecmis = sohbet_gecmisi[chat_id]
    gecmis.append({"role": "user", "content": f"{kullanici_adi}: {mesaj}"})

    def cagri():
        return ai_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=BOT_PERSONA,
            messages=list(gecmis),
        )

    try:
        response = await asyncio.to_thread(cagri)
        cevap = response.content[0].text
        gecmis.append({"role": "assistant", "content": cevap})
        return cevap
    except Exception:
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


def log_activity(chat_id, user, mesaj_metni):
    simdi = datetime.now(TR_TZ).strftime("%d.%m.%Y %H:%M")
    kisa_mesaj = mesaj_metni[:60]

    cursor.execute(
        "SELECT message_count FROM activity WHERE chat_id=? AND user_id=?",
        (chat_id, user.id)
    )
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO activity(chat_id, user_id, first_name, message_count, last_message, last_seen) VALUES(?,?,?,?,?,?)",
            (chat_id, user.id, user.first_name, 1, kisa_mesaj, simdi)
        )
    else:
        cursor.execute(
            "UPDATE activity SET message_count=message_count+1, first_name=?, last_message=?, last_seen=? WHERE chat_id=? AND user_id=?",
            (user.first_name, kisa_mesaj, simdi, chat_id, user.id)
        )

    db.commit()


def get_activity(chat_id):
    cursor.execute(
        "SELECT first_name, message_count, last_message, last_seen FROM activity WHERE chat_id=? ORDER BY message_count DESC",
        (chat_id,)
    )
    return cursor.fetchall()

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
/aktifler
/sondurum
/kimvar
/etiketle
/slap
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
    "canımsın": "Sen de benim canımsın 🥰",
    "özledim": "Ben de seni özledim 🤗",
    "iyi hafta sonları": "Sana da iyi hafta sonları! Keyfine bak 🎉",
    "pazartesi": "Pazartesi sendromu mu? Geçer, dayan 💪",
    "cuma": "Cumaya geldik mi? Hafta sonu kapıda 🥳",
    "hafta sonu": "Hafta sonu tadını çıkar! 🎈",
    "doğum günü": "Doğum günün mü? Nice yıllara! 🎂🎉",
    "kutlarım": "Ben de kutluyorum, tebrikler! 🎊",
    "başarılar": "Sana da başarılar dilerim! 🍀",
    "geçmiş olsun": "Geçmiş olsun, çabuk iyileş 🙏",
    "hasta": "Hasta mısın? Geçmiş olsun, iyileş bakalım 🤒",
    "hastayım": "Geçmiş olsun, kendine iyi bak 🤒",
    "sınav": "Sınav mı var? Bol şans, elinden geleni yap 📚",
    "ders çalış": "Ders çalışmak önemli, ama mola vermeyi unutma 📖",
    "para kazan": "Para kazanmak kolay değil ama pes etme 💪",
    "iş buldum": "Tebrikler, hayırlı olsun! 🎉",
    "işten çıktım": "Yeni başlangıçlar hep daha iyisi getirir 💪",
    "evlendim": "Tebrikler, ömür boyu mutluluklar dilerim 💍🎉",
    "bebek": "Bebek haberi mi var? Tebrikler! 👶🎉",
    "seyahat": "Seyahat mi? İyi yolculuklar! ✈️",
    "yolculuk": "İyi yolculuklar, güvenli git gel 🚗",
    "araba": "Araba mı? Dikkatli sür 🚙",
    "trafik": "Trafik berbat olabilir, sabırlı ol 🚦",
    "sınavdayım": "Bol şanslar, başarırsın 🍀",
    "motivasyon": "Sen yapabilirsin, pes etme! 💪🔥",
    "başaramıyorum": "Vazgeçme, her başarısızlık bir öğrenme fırsatı 💪",
    "pes etmeyeceğim": "İşte bu ruh! Devam et 🔥",
    "harikayım": "Tabii ki harikasın! 🌟",
    "kötü hissediyorum": "Yalnız değilsin, buradayım 🤗",
    "iyiyim": "Ne güzel, sağlıcakla kal! 😊",
    "keyifsizim": "Biraz müzik dinle, iyi gelir 🎵",
    "sinir bozucu": "Derin nefes al, geçecek bu da 🧘",
    "şükürler olsun": "Şükretmek güzel bir şey 🙏",
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

async def etiketle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    etiketler = mention_all_text(chat_id)

    if not etiketler:
        await update.message.reply_text(
            "Henüz kimseyi tanımıyorum. Grupta biraz sohbet edilsin, sonra tekrar dene 🤔"
        )
        return

    if context.args:
        ozel_mesaj = " ".join(context.args)
    else:
        ozel_mesaj = "📢 Dikkat, herkese sesleniyorum!"

    await update.message.reply_text(
        f"{html.escape(ozel_mesaj)}\n\n{etiketler}",
        parse_mode="HTML"
    )

SLAP_MESAJLARI = [
    "{isim} bir tırla ezildi 🚛💥",
    "{isim} balkondan düşen bir saksıyla tanıştı 🪴😵",
    "{isim} banana kabuğuna basıp taklalar attı 🍌🤸",
    "{isim}'e dev bir balık tokadı attı 🐟✋",
    "{isim} elektrik direğine tosladı, kuşlar görüyor 🐦💫",
    "{isim} merdivenden yuvarlandı, hâlâ dönüyor 🌀",
    "{isim} bir kova soğuk suyla tanıştı 🪣💦",
    "{isim} kapıya çarptı, kapı kazandı 🚪🤕",
    "{isim} bir kaplumbağa tarafından geçildi, moralman çöktü 🐢💔",
    "{isim} yanlışlıkla kendine tokat attı, iki kere 🖐️😂",
    "{isim} bir güvercin tarafından fena hâlde küçümsendi 🐦😏",
    "{isim} bir tekme yiyip uzaya fırladı 🚀👟",
]

async def slap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    gonderen = update.effective_user

    hedef_mention = None

    if update.message.reply_to_message:
        hedef = update.message.reply_to_message.from_user
        hedef_mention = f'<a href="tg://user?id={hedef.id}">{html.escape(hedef.first_name)}</a>'
    elif context.args:
        hedef_ad = html.escape(" ".join(context.args))
        hedef_mention = hedef_ad
    else:
        uyeler = get_group_members(chat_id)
        adaylar = [u for u in uyeler if u[0] != gonderen.id] or uyeler
        if adaylar:
            uid, ad = random.choice(adaylar)
            hedef_mention = f'<a href="tg://user?id={uid}">{html.escape(ad)}</a>'
        else:
            hedef_mention = html.escape(gonderen.first_name)

    mesaj = random.choice(SLAP_MESAJLARI).format(isim=hedef_mention)
    await update.message.reply_text(mesaj, parse_mode="HTML")

async def aktifler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    veriler = get_activity(chat_id)

    if not veriler:
        await update.message.reply_text("Henüz kimseden veri toplamadım 🤔")
        return

    satirlar = ["📊 En Aktif Üyeler\n"]
    for i, (ad, sayi, _, _) in enumerate(veriler[:10], start=1):
        satirlar.append(f"{i}. {ad} — {sayi} mesaj")

    await update.message.reply_text("\n".join(satirlar))

async def sondurum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    veriler = get_activity(chat_id)

    if not veriler:
        await update.message.reply_text("Henüz kimseden veri toplamadım 🤔")
        return

    satirlar = ["👀 Grupta Son Durum\n"]
    for ad, sayi, son_mesaj, son_gorulme in veriler:
        satirlar.append(
            f"• {ad} ({sayi} mesaj)\n  Son yazdığı: \"{son_mesaj}\"\n  Zaman: {son_gorulme}"
        )

    await update.message.reply_text("\n\n".join(satirlar))

async def kimvar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uyeler = get_group_members(chat_id)

    if not uyeler:
        await update.message.reply_text("Henüz kimseyi tanımıyorum 🤔")
        return

    satirlar = [f"👥 Takip Ettiğim Üyeler ({len(uyeler)})\n"]
    for _, ad in uyeler:
        satirlar.append(f"• {ad}")

    await update.message.reply_text("\n".join(satirlar))

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

# =====================
# OTOMATİK GÜNAYDIN / İYİ GECELER
# =====================

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
# BOTU BAŞLAT
# =====================

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler
