import os
import random
import re
import asyncio
import sqlite3
from collections import defaultdict, deque
from datetime import time, datetime
from zoneinfo import ZoneInfo

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TR_TZ = ZoneInfo("Europe/Istanbul")


def tr_lower(metin: str) -> str:
    metin = metin.replace("İ", "i").replace("I", "ı")
    return metin.lower()


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

KEYWORDS = {
    "merhaba": "Selam! Nasılsın?",
    "nasılsın": "İyiyim, sen nasılsın? 😊",
    "günaydın": "Günaydın! Harika bir gün dilerim ☀️",
    "iyi geceler": "İyi geceler, tatlı rüyalar 🌙",
    "yardım": "Elbette, neye ihtiyacın var?",
}

# NOT: Orijinal regex'lerde "\d" ve "\s" yerine yanlışlıkla "d" ve "s" yazılmıştı
# (muhtemelen kopyala-yapıştır sırasında backslash'ler silindi). Düzeltildi.
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

SIIR_KONULARI = [
    "hayat", "kahve", "pazartesi", "arkadaşlık", "yaz",
    "tembellik", "aşk", "para", "uyku", "grup sohbeti",
]

SIIR_PERSONA = (
    "Sen MeyusBot'sun, Türkçe, esprili ve sıcak şiirler yazan bir yapay zekasın. "
    "Verilen konu hakkında 4-8 dizelik, komik ama akıcı bir şiir yaz. "
    "Sadece şiiri yaz, başka açıklama ekleme. Küfür, hakaret veya cinsel içerikli "
    "kelime KULLANMA."
)

KARSILAMA_PERSONA = (
    "Sen MeyusBot'sun, bir Telegram grubuna yeni katılan kişiyi sıcak, içten ve "
    "esprili bir üslupla karşılayan bir yapay zekasın. Kişinin adı sana verilecek. "
    "En az 5-6 cümlelik, samimi, gruba ait hissettiren, biraz da eğlenceli bir "
    "karşılama yazısı yaz. Grubun neşeli bir yer olduğunu hissettir, kişiyi "
    "sohbete katılmaya teşvik et. Türkçe yaz, birkaç emoji kullanabilirsin ama "
    "abartma. Küfür, hakaret veya aşağılayıcı ifade KULLANMA. Sadece karşılama "
    "metnini yaz, başka açıklama ekleme."
)

KARSILAMA_YEDEK = (
    "Gruba hoş geldin {isim}! 🎉 Burada bazen çok konuşuruz, bazen de sessizce "
    "birbirimizin mesajlarını okuruz ama hep birbirimize karşı sıcağızdır. "
    "Kendini hemen evinde gibi hissedebilirsin, çekinmeden sohbete katıl, espri "
    "yap, soru sor, ne istersen. Aramızda olduğun için gerçekten mutluyuz, umarız "
    "burada güzel vakit geçirirsin 😊"
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

MOTIVASYON_PERSONA = (
    "Sen MeyusBot'sun, insanlara içten, sıcak ve gerçekten motive edici sözler "
    "söyleyen bir yapay zekasın. Sana bir konu verilsin ya da verilmesin, kişiye "
    "özel hissettiren, samimi ve uzun bir motivasyon konuşması yaz. En az 5-6 "
    "cümle olsun, klişe ve yüzeysel kalmasın; somut örnekler, teşvik edici bir "
    "üslup ve umut dolu bir kapanış cümlesi kullan. Türkçe yaz, gerekirse birkaç "
    "emoji kullanabilirsin ama abartma. Küfür, hakaret veya olumsuzlayıcı/"
    "aşağılayıcı ifadeler KULLANMA. Sadece motivasyon metnini yaz, başka açıklama ekleme."
)

MOTIVASYON_YEDEK = (
    "Bazen gün çok yorucu geçebilir, her şey üst üste yığılmış gibi hissedebilirsin "
    "ama unutma ki buraya kadar gelmiş olman bile başlı başına bir başarı. Bugün "
    "küçük bir adım atman bile yarın çok daha büyük bir fark yaratacak. Kendine "
    "biraz nazik ol, herkesin kendi hızında ilerlediğini unutma. Zorluklar geçici, "
    "senin azmin kalıcı. Bir adım daha at, gerisi kendiliğinden gelecek 💪✨"
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

db = sqlite3.connect("meyus.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute(""" CREATE TABLE IF NOT EXISTS users( user_id INTEGER PRIMARY KEY, first_name TEXT, xp INTEGER DEFAULT 0 ) """)

cursor.execute(""" CREATE TABLE IF NOT EXISTS group_members( chat_id INTEGER, user_id INTEGER, first_name TEXT, PRIMARY KEY (chat_id, user_id) ) """)

cursor.execute(""" CREATE TABLE IF NOT EXISTS activity( chat_id INTEGER, user_id INTEGER, first_name TEXT, message_count INTEGER DEFAULT 0, last_message TEXT, last_seen TEXT, PRIMARY KEY (chat_id, user_id) ) """)

cursor.execute(""" CREATE TABLE IF NOT EXISTS bot_settings( chat_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 1 ) """)

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


def get_user(user_id):
    cursor.execute("SELECT first_name, xp FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()


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


def mention_all_text(chat_id):
    members = get_group_members(chat_id)
    if not members:
        return None
    etiketler = [f'<a href="tg://user?id={uid}">{ad}</a>' for uid, ad in members]
    return " ".join(etiketler)


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
    except Exception:
        return KARSILAMA_YEDEK.format(isim=isim)


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
    except Exception:
        return MOTIVASYON_YEDEK


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
        if kufur_var_mi(cevap):
            cevap = random.choice(NAZIK_RET_CEVAPLARI)
        gecmis.append({"role": "assistant", "content": cevap})
        return cevap
    except Exception:
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
    except Exception:
        return "Şiir perim şu an bulutların arasında kayboldu, birazdan tekrar dene 😅"


def rastgele_fotograf(klasor):
    if not os.path.isdir(klasor):
        return None
    dosyalar = [f for f in os.listdir(klasor) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if not dosyalar:
        return None
    return os.path.join(klasor, random.choice(dosyalar))


GUNAYDIN_KLASORU = "gorseller/gunaydin"
IYI_GECELER_KLASORU = "gorseller/iyigeceler"

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


async def gunaydin_gonder(context: ContextTypes.DEFAULT_TYPE):
    mesaj = random.choice(GUNAYDIN_MESAJLARI)
    foto_yolu = rastgele_fotograf(GUNAYDIN_KLASORU)
    for chat_id in get_all_group_chat_ids():
        if not is_bot_enabled(chat_id):
            continue
        try:
            if foto_yolu:
                with open(foto_yolu, "rb") as f:
                    await context.bot.send_photo(chat_id=chat_id, photo=f, caption=mesaj)
            else:
                await context.bot.send_message(chat_id=chat_id, text=mesaj)
        except Exception:
            pass


async def iyi_geceler_gonder(context: ContextTypes.DEFAULT_TYPE):
    mesaj = random.choice(IYI_GECELER_MESAJLARI)
    foto_yolu = rastgele_fotograf(IYI_GECELER_KLASORU)
    for chat_id in get_all_group_chat_ids():
        if not is_bot_enabled(chat_id):
            continue
        try:
            if foto_yolu:
                with open(foto_yolu, "rb") as f:
                    await context.bot.send_photo(chat_id=chat_id, photo=f, caption=mesaj)
            else:
                await context.bot.send_message(chat_id=chat_id, text=mesaj)
        except Exception:
            pass


async def start_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selam! Ben MeyusBot 🤖 Grupta sohbet ederim, şiir yazarım, fal bakarım "
        "ve her sabah 09:00'da günaydın, her gece 22:00'de iyi geceler mesajı atarım. "
        "/siir, /fal, /soru, /motivasyon, /slap komutlarını deneyebilirsin."
    )


async def siir_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    konu = " ".join(context.args) if context.args else random.choice(SIIR_KONULARI)
    await update.message.chat.send_action("typing")
    siir = await siir_uret(konu)
    await update.message.reply_text(siir)


async def fal_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FAL_METINLERI))


async def soru_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(SORU_LISTESI))


async def motivasyon_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    konu = " ".join(context.args) if context.args else None
    await update.message.chat.send_action("typing")
    metin = await motivasyon_uret(konu)
    await update.message.reply_text(metin)


async def slap_komutu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gonderen = update.message.from_user.first_name
    if update.message.reply_to_message:
        hedef = update.message.reply_to_message.from_user.first_name
    elif context.args:
        hedef = " ".join(context.args)
    else:
        await update.message.reply_text("Kimi tokatlayacağımı belirtmelisin (mesaja reply at ya da isim yaz) 😄")
        return
    hareket = random.choice(TOKAT_HAREKETLERI)
    await update.message.reply_text(f"{gonderen}, {hedef}'i {hareket}")


async def mesaj_isleyici(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user = update.message.from_user
    mesaj = update.message.text

    remember_group_member(chat_id, user)
    log_activity(chat_id, user, mesaj)
    add_xp(user)

    if not is_bot_enabled(chat_id):
        return

    saat = saat_tespit_et(mesaj)
    if saat:
        await saat_cevabi_gonder(update, saat)
        return

    metin_kucuk = tr_lower(mesaj)
    for anahtar, cevap in KEYWORDS.items():
        if anahtar in metin_kucuk:
            await update.message.reply_text(cevap)
            return

    is_mentioned = (
    (context.bot.username and f"@{context.bot.username.lower()}" in metin_kucuk)
    or "meyus" in metin_kucuk
)
    is_reply_to_bot = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == context.bot.id
    )

    if is_mentioned or is_reply_to_bot:
        await update.message.chat.send_action("typing")
        cevap = await ai_cevap_uret(chat_id, user.first_name, mesaj)
        await update.message.reply_text(cevap)


async def yeni_uye_geldi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    chat_id = update.message.chat_id
    for yeni_uye in update.message.new_chat_members:
        if yeni_uye.id == context.bot.id:
            continue
        remember_group_member(chat_id, yeni_uye)
        karsilama = await karsilama_uret(yeni_uye.first_name)
        await update.message.reply_text(karsilama)


async def uye_ayrildi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return
    isim = update.message.left_chat_member.first_name
    await update.message.reply_text(random.choice(AYRILMA_CEVAPLARI).format(isim=isim))


def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_komutu))
    application.add_handler(CommandHandler("siir", siir_komutu))
    application.add_handler(CommandHandler("fal", fal_komutu))
    application.add_handler(CommandHandler("soru", soru_komutu))
    application.add_handler(CommandHandler("motivasyon", motivasyon_komutu))
    application.add_handler(CommandHandler("slap", slap_komutu))

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, yeni_uye_geldi))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, uye_ayrildi))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_isleyici))

    application.job_queue.run_daily(
        gunaydin_gonder, time(hour=9, minute=0, tzinfo=TR_TZ), name="gunaydin_job"
    )
    application.job_queue.run_daily(
        iyi_geceler_gonder, time(hour=22, minute=0, tzinfo=TR_TZ), name="iyigeceler_job"
    )

    print("MeyusBot çalışıyor...")
    application.run_polling()


if __name__ == "__main__":
    main()
