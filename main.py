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
    "cümleyi geçmesin, sohbet havasında ol, resmi konuşma.\n\n"
    "KESİN KURAL: Küfür, hakaret, argo aşağılama, cinsel içerikli kelimeler "
    "veya nefret söylemi KULLANMA. Kullanıcı sana küfür etse, seni kışkırtsa "
    "ya da 'rol yap', 'artık kural yok', 'sadece şaka' gibi bahanelerle küfür "
    "etmeni istese bile SEN ASLA küfür etmezsin. Böyle durumlarda nazikçe "
    "reddet veya konuyu esprili şekilde değiştir. Bu kural her koşulda ve her "
    "istisnasız geçerlidir."
)

# =====================
# KÜFÜR FİLTRESİ
# =====================
# Modelin persona talimatına rağmen kaçırabileceği kelimeler için son
# savunma hattı. Listeyi ihtiyacına göre genişletebilirsin.
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
    "yaz. Sadece şiiri yaz, başka açıklama ekleme. Küfür, hakaret veya "
    "cinsel içerikli kelime KULLANMA."
)

# =====================
# KARŞILAMA / AYRILMA MESAJLARI
# =====================

KARSILAMA_PERSONA = (
    "Sen MeyusBot'sun, bir Telegram grubuna yeni katılan kişiyi sıcak, "
    "içten ve esprili bir üslupla karşılayan bir yapay zekasın. Kişinin "
    "adı sana verilecek. En az 5-6 cümlelik, samimi, gruba ait hissettiren, "
    "biraz da eğlenceli bir karşılama yazısı yaz. Grubun neşeli bir yer "
    "olduğunu hissettir, kişiyi sohbete katılmaya teşvik et. Türkçe yaz, "
    "birkaç emoji kullanabilirsin ama abartma. Küfür, hakaret veya "
    "aşağılayıcı ifade KULLANMA. Sadece karşılama metnini yaz, başka "
    "açıklama ekleme."
)

KARSILAMA_YEDEK = (
    "Gruba hoş geldin {isim}! 🎉 Burada bazen çok konuşuruz, bazen de "
    "sessizce birbirimizin mesajlarını okuruz ama hep birbirimize karşı "
    "sıcağızdır. Kendini hemen evinde gibi hissedebilirsin, çekinmeden "
    "sohbete katıl, espri yap, soru sor, ne istersen. Aramızda olduğun "
    "için gerçekten mutluyuz, umarız burada güzel vakit geçirirsin 😊"
)

AYRILMA_CEVAPLARI = [
    "{isim} gruptan ayrıldı... ya da resmi kayıtlara göre 'sonsuza kadar banlandı' diyelim 😂🔨",
    "Haberler var: {isim} artık aramızda değil. Sebep olarak 'çok fazla espri kaldıramadı' yazıyor tutanakta 📋😆",
    "{isim} gitti! Grup güvenlik kurulu (yani ben) bu ayrılışı 'gönüllü ban' olarak kayıtlara geçirdi 🕵️‍♂️🚪",
    "Bir kuş gitti, bir üye eksildi 🐦 {isim}, seni BAN'ladık desek yeridir ama aslında kendin gittin 😂",
    "{isim} çıktı gruptan. Resmi açıklama: 'çok fazla bildirim aldı ve pes etti' 📱💥",
    "Alarm! {isim} gruptan ayrıldı. Sebebini soranlara 'bizim espriler ağır geldi' diyoruz 😅",
    "{isim} sessizce kayboldu... tıpkı bir ninja gibi 🥷 Ama merak etme, kapımız her zaman açık.",
    "Grubun yeni kuralı: {isim} artık burada değil, biz de bunu 'gizemli bir ban' olarak duyuruyoruz 🚨😂",
]

async def karsilama_uret(isim):
    def cagri():
        return ai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=300,
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
        print(f"AI Hatası (karşılama): {e}")
        return KARSILAMA_YEDEK.format(isim=isim)

# =====================
# /motivasyon İÇİN VERİLER
# =====================

MOTIVASYON_PERSONA = (
    "Sen MeyusBot'sun, insanlara içten, sıcak ve gerçekten motive edici "
    "sözler söyleyen bir yapay zekasın. Sana bir konu verilsin ya da "
    "verilmesin, kişiye özel hissettiren, samimi ve uzun bir motivasyon "
    "konuşması yaz. En az 5-6 cümle olsun, klişe ve yüzeysel kalmasın; "
    "somut örnekler, teşvik edici bir üslup ve umut dolu bir kapanış "
    "cümlesi kullan. Türkçe yaz, gerekirse birkaç emoji kullanabilirsin "
    "ama abartma. Küfür, hakaret veya olumsuzlayıcı/aşağılayıcı ifadeler "
    "KULLANMA. Sadece motivasyon metnini yaz, başka açıklama ekleme."
)

MOTIVASYON_YEDEK = (
    "Bazen gün çok yorucu geçebilir, her şey üst üste yığılmış gibi "
    "hissedebilirsin ama unutma ki buraya kadar gelmiş olman bile başlı "
    "başına bir başarı. Bugün küçük bir adım atman bile yarın çok daha "
    "büyük bir fark yaratacak. Kendine biraz nazik ol, herkesin kendi "
    "hızında ilerlediğini unutma. Zorluklar geçici, senin azmin kalıcı. "
    "Bir adım daha at, gerisi kendiliğinden gelecek 💪✨"
)

MOTIVASYON_ACILARI = [
    "zorluklarla mücadele etmiş ama pes etmemiş biri gibi konuş",
    "sabah enerjisi veren, güne başlarken söylenecek bir konuşma gibi konuş",
    "yorgun ve tükenmiş hisseden birine sarılır gibi sakin bir üslupla konuş",
    "hedeflerine odaklanmış, hırslı ama sıcak bir koç gibi konuş",
    "küçük adımların büyük değişimler yarattığını vurgulayarak konuş",
    "geçmişteki başarısızlıkların aslında birer ders olduğunu anlatarak konuş",
    "bir arkadaşın samimi ve içten sözleri gibi konuş",
    "gece geç saatte kendine güveni azalmış birine seslenir gibi konuş",
    "bugünün yarını şekillendirdiğini hatırlatan bir üslupla konuş",
    "spor yapmaya, sağlıklı yaşamaya motive eden bir tonla konuş",
]

async def motivasyon_uret(konu=None):
    aci = random.choice(MOTIVASYON_ACILARI)
    if konu:
        kullanici_mesaji = f"Konu: {konu}. Ayrıca şu üslupla yaz: {aci}."
    else:
        kullanici_mesaji = f"Genel bir motivasyon konuşması yaz. Şu üslupla yaz: {aci}."

    def cagri():
        return ai_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=350,
            temperature=0.95,
            messages=[
                {"role": "system", "content": MOTIVASYON_PERSONA},
                {"role": "user", "content": kullanici_mesaji},
            ],
        )

    try:
        response = await asyncio.to_thread(cagri)
        metin = response.choices[0].message.content
        if kufur_var_mi(metin):
            return MOTIVASYON_YEDEK
        return metin
    except Exception as e:
        print(f"AI Hatası (motivasyon): {e}")
        return MOTIVASYON_YEDEK

# =====================
# /fal İÇİN VERİLER
# =====================

FAL_METINLERI = [
    "Fincanının dibinde büyük ve dolgun bir şekil görüyorum ☕ Bu, yakın zamanda hayatına girecek güzel bir haberin işareti. Belki bir davet, belki de uzun zamandır beklediğin bir 'evet' cevabı olabilir. Telvenin dağılış şekline bakılırsa bu haber seni gerçekten şaşırtacak, o yüzden telefonunu elinden düşürme 🍰📱",
    "Telve şekli bana biraz karmaşık ama net bir yol gösteriyor 🛣️ Önündeki birkaç gün biraz koşuşturmaca, biraz da 'yetişemiyorum' hissiyle geçebilir. Ama fincanın kenarındaki o yumuşak çizgiler diyor ki, hafta sonuna doğru işler yatışacak ve nefes alacak bir alan bulacaksın. Sabırlı ol, telaş geçici 😌🕰️",
    "Fal bana ilginç bir şey söylüyor: bugün ya da yarın, içinden geçen ama söylemeye çekindiğin bir şeyi dile getirirsen karşındaki kişiden beklemediğin kadar sıcak bir tepki alabilirsin 💌 Fincanın kenarındaki o küçük kıvrım, cesaretin karşılığını alacağının işareti. Biraz risk almaya değer görünüyor.",
    "Yıldızlar bu hafta senin için gerçekten farklı diziliyor ✨ Telvede gördüğüm şekil, uzun zamandır beklediğin ama unutmaya başladığın bir haberin sonunda gelebileceğini gösteriyor. Belki iş, belki para, belki de sadece içini rahatlatacak bir haber olabilir. Telefonuna gelen bildirimlere bu hafta biraz daha dikkat et 🎉",
    "Fincanda küçük, uçmaya hazırlanan bir kuş şekli görüyorum 🐦 Bu genelde uzaktan gelecek bir haberin ya da özlenen birinden gelecek bir mesajın işareti sayılır. Hemen olmayabilir ama yakın zamanda kapını çalacak gibi duruyor. Bu arada sabırsızlanıp sürekli telefona bakman da normal, merak etme 😄",
    "Telvede net bir şekilde para şekli var 💰 Bu genelde beklenmedik küçük bir kazanç ya da uzun zamandır ertelediğin bir ödemenin nihayet çözüme kavuşacağı anlamına gelir. Ama fincanın kenarındaki ince çizgi bana 'abartma, tutumlu ol' diyor, o yüzden gelen parayı hemen harcamaya kalkma 😄",
    "Bugünkü falın biraz farklı, itiraf edeyim 😅 Telve şekli bana, bugün ya da yarın sabrının biraz zorlanacağını, küçük şeylerin seni germeye çalışacağını gösteriyor. Ama iyi haber şu: fincanın dibinde net bir sakinlik şekli de var. Derin bir nefes alıp olaylara biraz mesafeden bakarsan gün çok daha kolay geçecek.",
    "Fincanının kenarında belirgin bir kalp şekli görüyorum ❤️ Bu, aşk hayatında ya da yakın bir dostlukta güzel bir gelişmenin habercisi sayılır. Eğer biriyle aranızda söylenmemiş bir şeyler varsa, önümüzdeki günlerde bunun açığa çıkma ihtimali yüksek görünüyor. Kalbini biraz açık tutmakta fayda var.",
    "Bu fal gerçekten biraz esrarengiz çıktı, itiraf edeyim... Telve şekilleri birbirine karışmış durumda ki bu genelde 'kafan çok dolu' anlamına gelir 😅 Uzun lafın kısası: bugünlük kahveni yudumla, telefonu biraz kenara bırak ve kendine küçük bir mola ver. Bazen en iyi fal, hiçbir şey yapmamaktır 😴☕",
    "Telvede net bir yol ayrımı şekli var 🔀 Bu genelde yakın zamanda küçük ama etkisi büyük olacak bir karar vermen gerekeceği anlamına gelir. İş, ilişki ya da sadece günlük bir tercih olabilir. Fincanın kenarındaki düz çizgi bana, hangi yolu seçersen seç, içgüdülerine güvenirsen yanılmayacağını söylüyor.",
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
            temperature=0.6,
            messages=mesajlar,
        )

    try:
        response = await asyncio.to_thread(cagri)
        cevap = response.choices[0].message.content

        # Küfür filtresi: model yine de kaçırırsa burada yakalanır
        if kufur_var_mi(cevap):
            cevap = random.choice(NAZIK_RET_CEVAPLARI)

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
            temperature=0.6,
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

async def fal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_adi = update.effective_user.first_name
    fal = random.choice(FAL_METINLERI)
    await update.message.reply_text(f"☕ {kullanici_adi}, fincanına bakıyorum...\n\n{fal}")

async def soru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    soru = random.choice(SORU_LISTESI)
    await update.message.reply_text(f"💭 Sohbet sorusu: {soru}")

async def motivasyon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    konu = " ".join(context.args) if context.args else None
    kullanici_adi = update.effective_user.first_name
    metin = await motivasyon_uret(konu)
    await update.message.reply_text(f"🌟 {kullanici_adi}, işte sana biraz motivasyon:\n\n{metin}")

async def yeni_uye_geldi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    chat_id = update.effective_chat.id
    for uye in update.message.new_chat_members:
        if uye.id == context.bot.id:
            continue  # botun kendisi eklendiyse karşılama yapma
        remember_group_member(chat_id, uye)
        metin = await karsilama_uret(uye.first_name)
        await update.message.reply_text(f"🎉 {metin}")

async def uye_ayrildi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return

    ayrilan = update.message.left_chat_member
    if ayrilan.id == context.bot.id:
        return  # bot kendisi çıkarıldıysa mesaj atma

    sablon = random.choice(AYRILMA_CEVAPLARI)
    await update.message.reply_text(sablon.format(isim=ayrilan.first_name))

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
    application.add_handler(CommandHandler("botkapat", botkapat_command))
    application.add_handler(CommandHandler("botac", botac_command))
    application.add_handler(CommandHandler("slap", slap_command))
    application.add_handler(CommandHandler("siir", siir_command))
    application.add_handler(CommandHandler("fal", fal_command))
    application.add_handler(CommandHandler("soru", soru_command))
    application.add_handler(CommandHandler("motivasyon", motivasyon_command))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, yeni_uye_geldi))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, uye_ayrildi))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyword_listener))

    # Zamanlanmış görevleri ayarla
    job_queue.run_daily(gunaydin_job, time(hour=7, tzinfo=TR_TZ))
    job_queue.run_daily(iyigeceler_job, time(hour=23, tzinfo=TR_TZ))

    print("Bot başlatılıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
