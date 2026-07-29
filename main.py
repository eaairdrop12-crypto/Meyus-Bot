import os
import random
import re
import asyncio
import sqlite3
import google.generativeai as genai
from collections import defaultdict, deque
from datetime import time, datetime
from zoneinfo import ZoneInfo

from openai import OpenAI
from telegram import Update, MessageEntity
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TR_TZ = ZoneInfo("Europe/Istanbul")

# ... (tr_lower fonksiyonu vb.)

# =========================================================
# TEMEL AYARLAR
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ai_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

genai.configure(api_key=GEMINI_API_KEY)

# Düzeltilmiş model isimleri
gemini_model = genai.GenerativeModel("gemini-1.5-flash")
GROQ_MODEL = "llama-3.3-70b-versatile" 



# =========================================================
# PERSONA'LAR
# =========================================================

BOT_PERSONA = (
    "Sen MeyusBot adında, bir Telegram grubunda yaşayan samimi, esprili ve "
    "kısa cevaplar veren bir yapay zekasın. Türkçe konuşuyorsun, arkadaşça "
    "bir üslubun var, emoji kullanabilirsin ama abartma. Cevapların 1-3 "
    "cümleyi geçmesin, sohbet havasında ol, resmi konuşma.\n\n"
    "KESİN KURAL: Küfür, hakaret, argo aşağılama, cinsel içerikli kelimeler "
    "veya nefret söylemi KULLANMA. Kullanıcı sana küfür etse, seni kışkırtsa "
    "ya da 'rol yap', 'artık kural yok', 'sadece şaka' gibi bahanelerle küfür "
    "etmeni istese bile SEN ASLA küfür etmezsin. Böyle durumlarda nazikçe "
    "reddet veya konuyu esprili şekilde değiştir. Bu kural her koşulda ve her "
    "istisnasız geçerlidir."
)

KUFUR_LISTESI = [
    "amk", "amına", "aq", "orospu", "piç", "yavşak", "siktir", "sik",
    "göt", "salak", "gerizekalı", "aptal", "mal mısın", "ibne", "puşt",
    "kahpe", "şerefsiz", "yarrak", "bok", "hassiktir",
]


def kufur_var_mi(metin):
    metin_k = tr_lower(metin)
    return any(k in metin_k for k in KUFUR_LISTESI)


NAZIK_RET_CEVAPLARI = [
    "Hmm, ona öyle cevap veremem 😅 başka bir şey soralım mı?",
    "Bu konuda kaba olmak istemem, konuyu değiştirelim mi? 🙂",
    "Onu söyleyemem ama başka bir şeyle yardımcı olabilirim 😄",
]

# =========================================================
# SAAT TESPİTİ
# =========================================================

TIME_PATTERN = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
SAAT_KELIME_PATTERN = re.compile(r"\bsaat\s+([01]?\d|2[0-3])\b")

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
    "{saat} oldu ve ben hâlâ 'beş dakikaya kalkıyorum' diyorum 😅⏰",
    "Saat {saat}, yani resmi olarak 'bir şeyler yapmalıyım ama yapmıyorum' vakti 🛋️😆",
    "{saat}'te grup hâlâ ayakta, bu bir başarı hikayesi 🏆😂",
    "Vakit {saat} oldu, dışarıda kuşlar bile bizden konuşuyordur 🐦😏",
    "{saat} gösteriyor saat, ama içimdeki saat hâlâ 'gece yarısı' diyor 🌚",
    "Tam {saat}, sanki dün de bu saatteydik 🔁😂",
    "{saat}'te uyumak mı, bir bölüm daha izlemek mi? Klasik ikilem 📺😴",
    "Saat {saat} oldu ama grup sohbeti bitmek bilmiyor, bu da güzel bir şey 💬❤️",
    "{saat}, tam olarak 'yarın pişman olacağım ama şu an mutluyum' saati 😅🎉",
    "Vay, {saat} olmuş! Zaman bazen çok hızlı bazen çok yavaş, bugün hızlı seçti 🏃‍♂️⏳",
    "{saat}'te hâlâ buradaysak demek ki sohbet gerçekten iyiymiş 😄👏",
    "{saat}! Tam da 'sadece 5 dakikaya bakıyorum' deyip 1 saat kaybetme vakti 📱😅",
    "Saat {saat}, bugün de küçük bir adım attıysan bu bile bir zafer sayılır 💪✨",
    "{saat} oldu, biraz su içmeyi unutma bu arada 💧😉",
    "Vakit {saat}, ne yapıyorsan yapıyor ol, o iş bugün bitecek 🔥",
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


# =========================================================
# TOKAT (/slap)
# =========================================================

TOKAT_HAREKETLERI = [
    "kocaman bir balıkla tokatladı 🐟",
    "uçan bir sandalyeyle selamladı 🪑",
    "sopayla nazikçe uyardı 🏒",
    "sanal ama acıtan bir tokat attı 🖐️",
    "sıcak bir pizza dilimiyle tokatladı 🍕",
    "klavyeyle tokatladı ⌨️",
    "bir tokat serveti gibi savurdu 👋",
    "ayakkabısıyla fırlattı 👟",
    "bir kova soğuk suyla uyandırdı 🪣💦",
    "devasa bir yastıkla vurdu 🛏️",
    "elindeki simitle tokatladı 🥯",
    "bir çift terlikle kovaladı 🩴",
    "sanal bir tencereyle bonk diye vurdu 🍳",
    "bir demet muzla tokatladı 🍌",
    "makarna tabağını kafasına devirdi 🍝",
    "kocaman bir yastık savaşı başlattı 🥊🛏️",
]

# =========================================================
# ŞİİR (/siir)
# =========================================================

SIIR_KONULARI = [
    "hayat", "kahve", "pazartesi", "arkadaşlık", "yaz",
    "tembellik", "aşk", "para", "uyku", "grup sohbeti",
]

SIIR_PERSONA = (
    "Sen MeyusBot'sun, Türkçe, esprili ve sıcak şiirler yazan bir yapay zekasın. "
    "Verilen konu hakkında KISA bir şiir yaz: en fazla 4 dize olsun, uzun olmasın. "
    "Komik ama akıcı olsun. Sadece şiiri yaz, başka açıklama ekleme. Küfür, "
    "hakaret veya cinsel içerikli kelime KULLANMA."
)

# =========================================================
# KARŞILAMA
# =========================================================

KARSILAMA_PERSONA = (
    "Sen MeyusBot'sun, bir Telegram grubuna yeni katılan kişiyi sıcak, içten ve "
    "esprili bir üslupla karşılayan bir yapay zekasın. Kişinin adı sana verilecek. "
    "En az 3-4 cümlelik, samimi, gruba ait hissettiren, biraz da eğlenceli bir "
    "karşılama yazısı yaz. Grubun neşeli bir yer olduğunu hissettir, kişiyi "
    "sohbete katılmaya teşvik et. Türkçe yaz, birkaç emoji kullanabilirsin ama "
    "abartma. Küfür, hakaret veya aşağılayıcı ifade KULLANMA. Sadece karşılama "
    "metnini yaz, başka açıklama ekleme."
)

KARSILAMA_YEDEK = (
    "Gruba hoş geldin {isim}! 🎉 Burada bazen çok konuşuruz, bazen de sessizce "
    "birbirimizin mesajlarını okuruz ama hep birbirimize karşı sıcağızdır. "
    "Kendini hemen evinde gibi hissedebilirsin, çekinmeden sohbete katıl 😊"
)

# =========================================================
# AYRILMA (şakacı, küfürsüz)
# =========================================================

AYRILMA_CEVAPLARI = [
    "{isim} gruptan ayrıldı... ya da resmi kayıtlara göre 'sonsuza kadar banlandı' diyelim 😂🔨",
    "Haberler var: {isim} artık aramızda değil. Sebep olarak 'çok fazla espri kaldıramadı' yazıyor tutanakta 📋😆",
    "{isim} gitti! Grup güvenlik kurulu (yani ben) bu ayrılışı 'gönüllü ban' olarak kayıtlara geçirdi 🕵️‍♂️🚪",
    "Bir kuş gitti, bir üye eksildi 🐦 {isim}, seni özleyeceğiz (ya da özlemeyeceğiz, o kısmı gizli 😂)",
    "{isim} çıktı gruptan. Resmi açıklama: 'çok fazla bildirim aldı ve pes etti' 📱💥",
    "Alarm! {isim} gruptan ayrıldı. Sebebini soranlara 'bizim espriler ağır geldi' diyoruz 😅",
    "{isim} sessizce kayboldu... tıpkı bir ninja gibi 🥷 Ama merak etme, kapımız her zaman açık.",
    "Grubun yeni kuralı: {isim} artık burada değil, biz de bunu 'gizemli bir ban' olarak duyuruyoruz 🚨😂",
]

# =========================================================
# FAL (/fal)
# =========================================================

FAL_METINLERI = [
    "Fincanının dibinde büyük ve dolgun bir şekil görüyorum ☕ Bu, yakın zamanda hayatına girecek güzel bir haberin işareti. Belki bir davet, belki de uzun zamandır beklediğin bir 'evet' cevabı olabilir. Telefonunu elinden düşürme 🍰📱",
    "Telve şekli bana biraz karmaşık ama net bir yol gösteriyor 🛣️ Önündeki günler biraz koşuşturmaca geçebilir ama hafta sonuna doğru işler yatışacak ve nefes alacak bir alan bulacaksın. Sabırlı ol, telaş geçici 😌🕰️",
    "Fal bana ilginç bir şey söylüyor: içinden geçen ama söylemeye çekindiğin bir şeyi dile getirirsen karşındaki kişiden beklemediğin kadar sıcak bir tepki alabilirsin 💌 Biraz risk almaya değer görünüyor.",
    "Yıldızlar bu hafta senin için gerçekten farklı diziliyor ✨ Uzun zamandır beklediğin ama unutmaya başladığın bir haberin sonunda gelebileceğini gösteriyor. Bildirimlere bu hafta biraz daha dikkat et 🎉",
    "Fincanda küçük, uçmaya hazırlanan bir kuş şekli görüyorum 🐦 Uzaktan gelecek bir haberin ya da özlenen birinden gelecek bir mesajın işareti. Yakın zamanda kapını çalacak gibi duruyor 😄",
    "Telvede net bir şekilde para şekli var 💰 Beklenmedik küçük bir kazanç ya da uzun zamandır ertelediğin bir işin nihayet çözüme kavuşacağı anlamına geliyor. Ama abartma, tutumlu ol 😄",
    "Bugünkü falın biraz farklı, itiraf edeyim 😅 Ama iyi haber şu: fincanın dibinde net bir sakinlik şekli de var. Derin bir nefes alırsan gün çok daha kolay geçecek.",
    "Fincanının kenarında belirgin bir kalp şekli görüyorum ❤️ Aşk hayatında ya da yakın bir dostlukta güzel bir gelişmenin habercisi. Kalbini biraz açık tutmakta fayda var.",
    "Bu fal gerçekten biraz esrarengiz çıktı, itiraf edeyim... Uzun lafın kısası: bugünlük kahveni yudumla, telefonu biraz kenara bırak ve kendine küçük bir mola ver. Bazen en iyi fal, hiçbir şey yapmamaktır 😴☕",
    "Telvede net bir yol ayrımı şekli var 🔀 Yakın zamanda küçük ama etkisi büyük olacak bir karar vermen gerekebilir. Hangi yolu seçersen seç, içgüdülerine güvenirsen yanılmayacaksın.",
    "Fincanın tam ortasında güneş gibi ışıldayan bir şekil var ☀️ Bu, önündeki günlerin beklediğinden çok daha aydınlık geçeceğinin işareti. Kendine güven, işler senin lehine dönüyor.",
    "Telve bana bir kapı şekli gösteriyor 🚪 Yakında önüne yeni bir fırsat kapısı açılacak gibi duruyor. Sen sadece o kapıyı görünce tereddüt etmeden it, gerisi kendiliğinden gelecek.",
]

# =========================================================
# SORU (opsiyonel eğlence)
# =========================================================

SORU_LISTESI = [
    "Hayatında hiç pişman olmadığın en çılgın kararın ne? 🤔",
    "Bir günlüğüne süper güç sahibi olsan ne yapardın? 🦸",
    "En sevdiğin çocukluk anın nedir? 🧸",
    "Şu an ışınlanabilseydin nereye giderdin? 🌍",
    "En son ne zaman gerçekten kahkaha attın, neye gülmüştün? 😂",
    "Sence grup içindeki en şanslı kişi kim? 🍀",
]

# =========================================================
# GÜNAYDIN / İYİ GECELER
# =========================================================

GUNAYDIN_MESAJLARI = [
    "Günaydın! Hayırlı sabahlar herkese ☀️",
    "Günaydın! Yeni bir gün, yeni bir bereket, hayırlı sabahlar 🌞",
    "Herkese günaydın ve hayırlı sabahlar dilerim 😊",
    "Günaydın! Kahveler hazır olsun, hayırlı sabahlar ☕🌅",
    "Hayırlı sabahlar! Bugün de güzel şeyler olsun 🌻",
]

IYI_GECELER_MESAJLARI = [
    "İyi geceler, iyi uykular herkese 🌙",
    "Gün burada bitiyor, iyi geceler ve tatlı rüyalar 😴✨",
    "İyi geceler! Yarın yine buradayız, iyi uykular 💤",
    "Herkese iyi geceler ve iyi uykular dilerim 🌌",
    "İyi geceler! Bugün ne olduysa oldu, şimdi dinlenme vakti 😌🌙",
]

# =========================================================
# VERİTABANI
# =========================================================

db = sqlite3.connect("meyus.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY, first_name TEXT, xp INTEGER DEFAULT 0)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS group_members(
    chat_id INTEGER, user_id INTEGER, first_name TEXT,
    PRIMARY KEY (chat_id, user_id))""")

cursor.execute("""CREATE TABLE IF NOT EXISTS activity(
    chat_id INTEGER, user_id INTEGER, first_name TEXT,
    message_count INTEGER DEFAULT 0, last_message TEXT, last_seen TEXT,
    PRIMARY KEY (chat_id, user_id))""")

cursor.execute("""CREATE TABLE IF NOT EXISTS bot_settings(
    chat_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 1)""")

db.commit()


def add_xp(user):
    cursor.execute("SELECT xp FROM users WHERE user_id=?", (user.id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            "INSERT INTO users(user_id, first_name, xp) VALUES(?,?,?)",
            (user.id, user.first_name, 2),
        )
    else:
        cursor.execute("UPDATE users SET xp=xp+2 WHERE user_id=?", (user.id,))
    db.commit()


def remember_group_member(chat_id, user):
    cursor.execute(
        "INSERT OR REPLACE INTO group_members(chat_id, user_id, first_name) VALUES(?,?,?)",
        (chat_id, user.id, user.first_name),
    )
    db.commit()


def get_group_members(chat_id):
    cursor.execute("SELECT user_id, first_name FROM group_members WHERE chat_id=?", (chat_id,))
    return cursor.fetchall()


def get_all_group_chat_ids():
    cursor.execute("SELECT DISTINCT chat_id FROM group_members")
    return [row[0] for row in cursor.fetchall()]


def log_activity(chat_id, user, mesaj_metni):
    simdi = datetime.now(TR_TZ).strftime("%d.%m.%Y %H:%M")
    kisa_mesaj = mesaj_metni[:60]

    cursor.execute(
        "SELECT message_count FROM activity WHERE chat_id=? AND user_id=?",
        (chat_id, user.id),
    )
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO activity(chat_id, user_id, first_name, message_count, last_message, last_seen) VALUES(?,?,?,?,?,?)",
            (chat_id, user.id, user.first_name, 1, kisa_mesaj, simdi),
        )
    else:
        cursor.execute(
            "UPDATE activity SET message_count=message_count+1, first_name=?, last_message=?, last_seen=? WHERE chat_id=? AND user_id=?",
            (user.first_name, kisa_mesaj, simdi, chat_id, user.id),
        )
    db.commit()


def is_bot_enabled(chat_id):
    cursor.execute("SELECT enabled FROM bot_settings WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()
    if row is None:
        return True
    return bool(row[0])


def set_bot_enabled(chat_id, enabled):
    cursor.execute(
        "INSERT OR REPLACE INTO bot_settings(chat_id, enabled) VALUES(?,?)",
        (chat_id, int(enabled)),
    )
    db.commit()


# =========================================================
# AI ÇAĞRILARI
# =========================================================

async def karsilama_uret(isim):
    def cagri():
        return ai_client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=250,
            temperature=0.8,
            messages=[
                {"role": "system", "content": KARSILAMA_PERSONA},
                {"role": "user", "content": f"Yeni katılan kişinin adı: {isim}"},
            ],
        )

    try:
        response = await asyncio.to_thread(cagri)
        metin = response.choices[0].message.content
        if kufur_var_mi(metin):
            return KARSILAMA_YEDEK.format(isim=isim)
        return metin
    except Exception as e:
        print(f"[AI HATASI - karsilama_uret] {type(e).__name__}: {e}")
        return KARSILAMA_YEDEK.format(isim=isim)


async def ai_cevap_uret(chat_id, kullanici_adi, mesaj):
    gecmis = sohbet_gecmisi[chat_id]
    gecmis.append({"role": "user", "content": f"{kullanici_adi}: {mesaj}"})

    def cagri():
        mesajlar = [{"role": "system", "content": BOT_PERSONA}] + list(gecmis)
        return ai_client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=200,
            temperature=0.6,
            messages=mesajlar,
        )

    try:
        response = await asyncio.to_thread(cagri)
        cevap = response.choices[0].message.content
        if kufur_var_mi(cevap):
            cevap = random.choice(NAZIK_RET_CEVAPLARI)
        gecmis.append({"role": "assistant", "content": cevap})
        return cevap
    except Exception as e:
        print(f"[AI HATASI - ai_cevap_uret] {type(e).__name__}: {e}")
        return "Şu an düşüncelerim biraz karışık, birazdan tekrar dene 😅"


async def siir_uret(konu):
    def cagri():
        return ai_client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=120,
            temperature=0.7,
            messages=[
                {"role": "system", "content": SIIR_PERSONA},
                {"role": "user", "content": f"Konu: {konu}"},
            ],
        )

    try:
        response = await asyncio.to_thread(cagri)
        siir = response.choices[0].message.content
        if kufur_var_mi(siir):
            return "Şiir perim bugün biraz sessiz kalmayı tercih etti, başka bir konu deneyelim mi? 😅"
        return siir
    except Exception as e:
        print(f"[AI HATASI - siir_uret] {type(e).__name__}: {e}")
        return "Şiir perim şu an bulutların arasında kayboldu, birazdan tekrar dene 😅"


# =========================================================
# HANDLER'LAR: YENİ ÜYE / AYRILAN ÜYE
# =========================================================

async def yeni_uye_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    chat_id = update.effective_chat.id
    for uye in update.message.new_chat_members:
        if uye.id == context.bot.id:
            continue
        remember_group_member(chat_id, uye)
        await update.message.chat.send_action("typing")
        karsilama = await karsilama_uret(uye.first_name)
        await update.message.reply_text(karsilama)


async def ayrilan_uye_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return
    uye = update.message.left_chat_member
    if uye.id == context.bot.id:
        return
    mesaj = random.choice(AYRILMA_CEVAPLARI).format(isim=uye.first_name)
    await update.message.reply_text(mesaj)


# =========================================================
# HANDLER: NORMAL MESAJLAR (Meyus / mention / saat)
# =========================================================

def bot_mention_edildi_mi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    mesaj = update.message
    if not mesaj.entities:
        return False

    bot_username = context.bot.username
    for ent in mesaj.entities:
        if ent.type == MessageEntity.MENTION:
            metin_ent = mesaj.text[ent.offset: ent.offset + ent.length]
            if bot_username and metin_ent.lower() == f"@{bot_username.lower()}":
                return True
        elif ent.type == MessageEntity.TEXT_MENTION and ent.user:
            if ent.user.id == context.bot.id:
                return True
    return False


async def mesaj_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    user = update.effective_user
    mesaj = update.message.text

    if chat.type in ("group", "supergroup"):
        if not is_bot_enabled(chat.id):
            return
        remember_group_member(chat.id, user)
        log_activity(chat.id, user, mesaj)
        add_xp(user)

    # 1) Saat tespiti -> farklı farklı motivasyon/espri cevapları
    saat = saat_tespit_et(mesaj)
    if saat:
        await saat_cevabi_gonder(update, saat)
        return

    # 2) "Meyus" kelimesi geçiyor mu, bot mention edildi mi ya da bot'a reply mi atıldı
    reply_bota_mi = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )
    meyus_gecti_mi = "meyus" in tr_lower(mesaj)
    mention_var_mi = bot_mention_edildi_mi(update, context)

    if meyus_gecti_mi or mention_var_mi or reply_bota_mi:
        await update.message.chat.send_action("typing")
        cevap = await ai_cevap_uret(chat.id, user.first_name, mesaj)
        await update.message.reply_text(cevap)


# =========================================================
# KOMUTLAR
# =========================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam! Ben MeyusBot 🤖\n\n"
        "• Adımı ('Meyus') yazarsan ya da beni etiketlersen cevap veririm\n"
        "• Saatten bahsedersen espri/motivasyon atarım ⏰\n"
        "• /slap - birini tokatlarım 🖐️\n"
        "• /siir <konu> - kısa şiir yazarım ✍️\n"
        "• /fal - umut verici bir fal bakarım ☕"
    )


async def slap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    gonderen = update.effective_user

    hedef_isim = None

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        hedef_isim = update.message.reply_to_message.from_user.first_name
    elif context.args:
        hedef_isim = " ".join(context.args).lstrip("@")
    else:
        uyeler = [u for u in get_group_members(chat.id) if u[0] != gonderen.id]
        if uyeler:
            hedef_isim = random.choice(uyeler)[1]

    if not hedef_isim:
        await update.message.reply_text(
            "Kimi tokatlayacağımı bilemedim 😅 birine reply atarak ya da "
            "/slap isim şeklinde yazarak dene."
        )
        return

    hareket = random.choice(TOKAT_HAREKETLERI)
    await update.message.reply_text(f"{gonderen.first_name}, {hedef_isim}'i {hareket}")


async def siir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    konu = " ".join(context.args) if context.args else random.choice(SIIR_KONULARI)
    await update.message.chat.send_action("typing")
    siir = await siir_uret(konu)
    await update.message.reply_text(siir)


async def fal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fal = random.choice(FAL_METINLERI)
    await update.message.reply_text(fal)


# =========================================================
# ZAMANLANMIŞ GÖREVLER: GÜNAYDIN / İYİ GECELER
# =========================================================

async def gunaydin_gonder(context: ContextTypes.DEFAULT_TYPE):
    mesaj = random.choice(GUNAYDIN_MESAJLARI)
    for chat_id in get_all_group_chat_ids():
        try:
            await context.bot.send_message(chat_id=chat_id, text=mesaj)
        except Exception as e:
            print(f"[GUNAYDIN HATASI] chat_id={chat_id}: {e}")


async def iyi_geceler_gonder(context: ContextTypes.DEFAULT_TYPE):
    mesaj = random.choice(IYI_GECELER_MESAJLARI)
    for chat_id in get_all_group_chat_ids():
        try:
            await context.bot.send_message(chat_id=chat_id, text=mesaj)
        except Exception as e:
            print(f"[IYI_GECELER HATASI] chat_id={chat_id}: {e}")


# =========================================================
# UYGULAMA BAŞLATMA
# =========================================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Komutlar
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("slap", slap_command))
    app.add_handler(CommandHandler("siir", siir_command))
    app.add_handler(CommandHandler("fal", fal_command))

    # Grup üyelik olayları
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, yeni_uye_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, ayrilan_uye_handler))

    # Normal metin mesajları (komut olmayanlar)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_handler))

    # Zamanlanmış görevler (job_queue için pip install "python-telegram-bot[job-queue]" gerekir)
    if app.job_queue:
        app.job_queue.run_daily(gunaydin_gonder, time=time(hour=8, minute=0, tzinfo=TR_TZ))
        app.job_queue.run_daily(iyi_geceler_gonder, time=time(hour=23, minute=0, tzinfo=TR_TZ))

    print("MeyusBot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
