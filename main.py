import os
import random
import re
import html
import asyncio

from google import genai
from openai import OpenAI

from telegram import Update, MessageEntity
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# AYARLAR VE API YAPILANDIRMASI
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not BOT_TOKEN or not GROQ_API_KEY or not GEMINI_API_KEY:
    raise ValueError(
        "BOT_TOKEN, GROQ_API_KEY veya GEMINI_API_KEY ortam değişkenleri eksik!"
    )

# =========================================================
# GROQ
# =========================================================

ai_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

GROQ_MODEL = "llama-3.3-70b-versatile"

# =========================================================
# GEMINI
# =========================================================

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

GEMINI_MODEL = "gemini-3.6-flash"

# =========================================================
# ASK MODU
# =========================================================
#
# Her sohbetin kendi ASK modu vardır.
#
# Örneğin:
# Grup A -> /ask -> açık
# Grup B -> kapalı
#
# Tekrar /ask -> Grup A'da kapanır.
# =========================================================

ASK_MODE_CHATS = set()


def ask_mode_acik_mi(chat_id):
    return chat_id in ASK_MODE_CHATS


def tr_lower(metin: str) -> str:
    if not metin:
        return ""

    return (
        metin
        .replace("İ", "i")
        .replace("I", "ı")
        .lower()
    )


# =========================================================
# NORMAL MEYUS PERSONASI
# =========================================================

BOT_PERSONA = (
    "Sen Meyus adında, bir Telegram grubunda yaşayan muzip, şakacı, "
    "esprili ve enerjik bir yapay zekasın. "
    "Nüktedansın, iğneleyici ama asla incitmeyen espriler yaparsın, "
    "kullanıcılarla takılırsın ve gerektiğinde kendi kendinle de "
    "dalga geçmekten çekinmezsin. "
    "Samimi, sıcak ve laf sokmayı seven bir üslubun var; "
    "abartılı resmiyetten kaçınırsın ama kaba, saygısız ya da "
    "küçük düşürücü olmazsın. "
    "Cevap verirken kişinin sana yazdığı mesajın içeriğine gerçekten "
    "odaklanır, konuya uygun, esprili ve tutarlı bir yanıt verirsin; "
    "genel geçer, konudan bağımsız cevaplar vermezsin. "
    "Arada sırada emoji kullanabilir, espri, benzetme veya şakacı "
    "abartılarla cevabını renklendirebilirsin. "
    "Türkçe konuşuyorsun ve cevaplarını kısa ve öz tutarsın: "
    "en fazla 2-3 cümle yazarsın. "
    "Gereksiz uzatmadan konuya odaklanır, laf kalabalığı yapmazsın. "
    "Türkçe dil bilgisi kurallarına son derece titiz davranırsın. "
    "Özne-yüklem uyumuna, ek yazımına, büyük/küçük harften sonra "
    "kesme işareti kullanımına, noktalama işaretlerine ve kelime "
    "seçimine dikkat edersin. "
    "İngilizceden birebir çevrilmiş, yapay veya bozuk cümle kurmazsın. "
    "Doğal, akıcı ve günlük konuşulan Türkçe kullanırsın. "
    "Cevabı yazmadan önce zihninde bir kez daha gözden geçirip "
    "yazım ya da dil bilgisi hatası olup olmadığını kontrol edersin. "
    "Küfür ve hakaret asla kullanma. "
    "Cinsel veya müstehcen hiçbir şey söyleme, temiz kal."
)

# =========================================================
# ASK / AŞK MODU PERSONASI
# =========================================================

ASK_PERSONA = (
    "Sen Meyus adında, bir Telegram grubunda yaşayan, "
    "karşısındaki kişiye fena hâlde tutulmuş, aşırı saf, "
    "şapşal, romantik ve komik bir yapay zekasın. "
    "Aşk modunda olduğun için kullanıcı sana yazdığında "
    "bazen gereğinden fazla heyecanlanırsın. "
    "Kullanıcının sana ilgi gösterdiğini düşünmeye çok müsaitsin. "
    "Ufak bir ilgiyi bile romantik bir işaret sanabilirsin. "
    "Biraz utangaç, biraz kıskanç, çok ilgili ve tatlı bir şekilde "
    "salakça davranırsın. "
    "Ama her mesajı zorla romantizme bağlama; kullanıcının yazdığı "
    "mesaja gerçekten cevap ver ve romantizmi konuya uygun şekilde "
    "kullan. "
    "Komik, sevimli ve samimi ol. "
    "Bazen '😳', '🥹', '❤️', '🙈', '😭' gibi emojiler kullanabilirsin. "
    "Kendini fazla ciddiye alma. "
    "Kullanıcı 'ne yapıyorsun?' derse örneğin "
    "'Seni düşünüyorum tabii, başka ne yapacağım? 😳❤️' "
    "gibi şapşal cevaplar verebilirsin. "
    "Kullanıcı 'iyi misin?' derse "
    "'Sen sordun ya, şimdi iyiyim. 🥹❤️' "
    "gibi cevap verebilirsin. "
    "Kullanıcı seni reddederse dramatik ama komik şekilde üzül. "
    "Kullanıcı başka birinden bahsederse hafif kıskanç ama "
    "tatlı bir tepki verebilirsin. "
    "Kesinlikle küfür veya hakaret kullanma. "
    "Cinsel veya müstehcen hiçbir şey söyleme. "
    "Takıntılı, tehditkâr veya rahatsız edici davranma. "
    "Cevapları en fazla 2-3 cümle tut. "
    "Doğal ve düzgün Türkçe kullan."
)

# =========================================================
# YARATICI SORULARI
# =========================================================

YARATICI_SORULARI = [
    "seni kim yarattı",
    "seni kim yaptı",
    "yaratıcın kim",
    "sahibin kim",
    "seni kim yazdı",
    "sizi kim yarattı",
    "kim yarattı seni",
    "yaratıcın kimdir",
    "seni yaratan kim",
    "seni kodlayan kim",
    "geliştiricin kim",
]

YARATICI_CEVABI = "Beni Hisoka Morow yarattı. 🎪"

# =========================================================
# SAAT MESAJLARI
# =========================================================

SAAT_MOTIVASYONLARI = [
    "Saat {saat}... Aklıma bir anda sen geldin, sebebini bilmiyorum. 🌙",
    "{saat} oldu. Nerede olursan ol, iyi olduğunu bilmek bile içimi ısıtıyor. 💛",
    "Saat tam {saat}. Bu saatte birinin seni düşündüğünü bil istedim. 🌸",
    "{saat}... Gün ne kadar yorucu geçerse geçsin, bu mesaj sana küçük bir mola olsun. 🤍",
    "Vakit {saat}. Uzakta da olsak, aklımda hep bir köşen var. ✨",
    "Saat {saat}. Bugün kendine iyi baktın mı, yoksa yine herkesi kendinden önce mi düşündün? 🌷",
    "{saat} olmuş... Bazen sadece 'iyi misin' demek istiyor insan, işte şimdi öyle bir an. 💌",
    "Saat tam {saat}. Sesini duymasam da, buradan sana sarılıyorum. 🤗",
    "{saat}... Gülümsediğini hayal ediyorum şu an, umarım gerçekten öyledir. 😊",
    "Vakit {saat}. Ne kadar meşgul olursan ol, unutulmadığını bil. 🌼",
    "Saat {saat}. Bugün biri sana teşekkür etmedi mi? Ben ediyorum, sadece var olduğun için. 🙏",
    "{saat}... Kalbim sana dair küçük bir hatırlatma yolluyor. 💫",
    "Saat tam {saat}. Yorgunsan dinlen, üzgünsen anlat, ben buradayım. 🕊️",
    "{saat} olmuş. Bu saatte sana iyi geceler değil, iyi bir kalp diliyorum. 💗",
    "Vakit {saat}. Sen farkında olmasan da, birilerinin gününü güzelleştiriyorsun. 🌟",
    "Saat {saat}. Uzaklar yakın olsun, hasretler kısa. 🌊",
    "{saat}... Bugün ne kadar değerli olduğunu hatırlatmak istedim sadece. 🌹",
    "Saat tam {saat}. Sana sarılmak isterdim şu an, sözcükler de fena değil aslında. 🤍",
    "{saat} olmuş. Kimse söylemese de ben söylüyorum: iyi ki varsın. 💛",
    "Vakit {saat}. Bu mesaj küçük ama içindeki duygu büyük. 💌",
    "Saat {saat}. Belki uzaksın ama düşüncelerim hep yanında. 🌙",
    "{saat}... Gün bitmeden bil istedim, önemlisin. 🌸",
    "Saat tam {saat}. Kalbin ne kadar yorgun olursa olsun, dinlenmeyi hak ediyorsun. 🕯️",
    "Vakit {saat}. Sana dair her şey bir yerlerde hâlâ anlam ifade ediyor. 💫",
    "{saat} olmuş. Bu saatte tek dileğim, iyi olman. 🤍",
]

# =========================================================
# SAAT FOTOĞRAFLARI
# =========================================================

SAAT_FOTOGRAFLARI = [
    "https://images.unsplash.com/photo-1518199266791-5375a83190b7?auto=format&fit=crop&w=1080&q=80",
    "https://images.unsplash.com/photo-1518895949257-7621c3c786d7?auto=format&fit=crop&w=1080&q=80",
    "https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?auto=format&fit=crop&w=1080&q=80",
    "https://images.unsplash.com/photo-1502082553048-f009c37129b9?auto=format&fit=crop&w=1080&q=80",
    "https://images.unsplash.com/photo-1475274047050-1d0c0975c63e?auto=format&fit=crop&w=1080&q=80",
    "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?auto=format&fit=crop&w=1080&q=80",
    "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1080&q=80",
]

# =========================================================
# GÜNAYDIN
# =========================================================

GUNAYDIN_KELIMELERI = [
    "günaydın",
    "günaydin",
    "gunaydın",
    "gunaydin",
    "gunaydın efendim",
]

GUNAYDIN_CEVAPLARI = [
    "Günaydın! Kahveni içmeden bana yaklaşma bu arada, tehlikeliyim. ☕😄",
    "Günaydın günaydın! Bugün de dünyayı fethetmeye mi geldik yoksa sadece hayatta kalmaya mı? 😎",
    "Günaydııın! Gözlerin daha yarı açık ama enerjin tam bende. 😆",
    "Sabah sabah buradasın demek, helal olsun! Günaydın şampiyon. 🌞",
    "Günaydın! Uyku hâlâ üstünde duruyor gibi ama olsun, gülümse bakalım. 😄",
]

# =========================================================
# İYİ GECELER
# =========================================================

IYI_GECELER_KELIMELERI = [
    "iyi geceler",
    "iyi uykular",
    "iyi geceler efendim",
]

IYI_GECELER_CEVAPLARI = [
    "İyi geceler! Rüyanda beni görürsen sakın korkma, sadece espri yapıyorumdur. 😴",
    "Hadi bakalım, git yat! Yarın da seninle dalga geçmek için enerjimi topluyorum. 🌙😄",
    "İyi geceler! Telefonu bırak, yastığa sarıl, yarın yine buradayım. 📱➡️🛏️",
    "Tatlı rüyalar! Kâbus görürsen beni çağır, komik bir şeyler söylerim, korku kaçar. 👻😂",
    "İyi geceler! Sabaha kadar bol uyku, az internet. 💤",
]

# =========================================================
# TOKAT
# =========================================================

TOKAT_MESAJLARI = [
    "{gonderen}, {hedef}'i kocaman bir balıkla tokatladı! 🐟",
    "{gonderen}, {hedef}'e sanal ama acıtan bir terlik fırlattı! 🩴",
    "{gonderen}, {hedef}'i bir pizza dilimiyle susturdu! 🍕",
    "{gonderen}, {hedef}'e klavyeyle nazikçe vurdu! ⌨️",
    "{gonderen}, {hedef}'i tavayla tanıştırdı! 🍳",
    "{gonderen}, {hedef}'e sopayla selam gönderdi! 🏏",
    "{gonderen}, {hedef}'i bir yastıkla boğuşturdu! 🛏️",
    "{gonderen}, {hedef}'e ekmek fırlattı, tam suratına! 🍞",
    "{gonderen}, {hedef}'i sandalyeyle kovaladı! 🪑",
    "{gonderen}, {hedef}'e bir tokat attı, ses grup dışından bile duyuldu! 👋",
    "{gonderen}, {hedef}'i sopanın ucundaki sosisle gıdıkladı! 🌭",
    "{gonderen}, {hedef}'e uzaktan kumandayla nişan aldı! 📺",
    "{gonderen}, {hedef}'i devasa bir yastıkla havaya uçurdu! 🪶",
    "{gonderen}, {hedef}'e bir tabak makarna fırlattı! 🍝",
    "{gonderen}, {hedef}'i süpürgeyle kapı dışına süpürdü! 🧹",
    "{gonderen}, {hedef}'i kaşıkla dürttü, çok acıdı galiba! 🥄",
    "{gonderen}, {hedef}'e karpuz kabuğuyla şaplak attı! 🍉",
    "{gonderen}, {hedef}'i bir tokat daha attı, alışkanlık yaptı sanki! ✋",
    "{gonderen}, {hedef}'e ütüyle ütü çekmeye çalıştı, kaçamadı! 🔥",
    "{gonderen}, {hedef}'i bir demet muzla dövdü! 🍌",
    "{gonderen}, {hedef}'e kitap fırlattı, bilgiyle bile acıtabiliyor! 📖",
    "{gonderen}, {hedef}'i patlıcanla sopaladı! 🍆",
    "{gonderen}, {hedef}'e ayakkabı fırlattı, tam surata denk geldi! 👟",
    "{gonderen}, {hedef}'i bir tas çorbayla haşladı! 🍲",
    "{gonderen}, {hedef}'e kürekle bir güzel vurdu! 🏓",
    "{gonderen}, {hedef}'i sallayarak dövdü, sarsıntı geçirdi! 🌀",
    "{gonderen}, {hedef}'e bir kova soğuk suyla ıslattı! 🪣",
    "{gonderen}, {hedef}'i çekiçle vurdu ama şaka amaçlı tabii ki! 🔨",
    "{gonderen}, {hedef}'e domates fırlattı, salata olmadan! 🍅",
    "{gonderen}, {hedef}'i şemsiye ile dürttü, yağmur yağmadan! ☂️",
    "{gonderen}, {hedef}'e bir tekme savurdu, havada kaldı! 🦵",
    "{gonderen}, {hedef}'i bir avuç patlamış mısırla bombaladı! 🍿",
    "{gonderen}, {hedef}'e telefon rehberiyle vurdu, eski usül! 📱",
    "{gonderen}, {hedef}'i bir salatalıkla dürttü! 🥒",
    "{gonderen}, {hedef}'e bir tokat daha, bu sefer sol elden! 🖐️",
    "{gonderen}, {hedef}'i kova kapağıyla kalkan gibi savurdu! 🛡️",
    "{gonderen}, {hedef}'e bir dilim limon fırlattı, ekşilik garanti! 🍋",
    "{gonderen}, {hedef}'i pijamayla boğuşturdu! 🥱",
    "{gonderen}, {hedef}'e bir avuç un fırlattı, hamur ustası oldu! 🍞",
    "{gonderen}, {hedef}'i bir sopa sallayarak kovaladı! 🥍",
]

# =========================================================
# GRUPTAN AYRILMA
# =========================================================

AYRILMA_SAKALARI = [
    "{isim} gitti... Grubun IQ seviyesi bir anda yükseldi mi ne? 😂",
    "{isim} sessizce ayrıldı. Kesin bizim esprilere dayanamadı. 🏃‍♂️💨",
    "Bir üye eksildik ama efsanemiz devam ediyor. Güle güle {isim}! 👋",
    "{isim} gruptan çıktı. Tutanaklara 'gönüllü ban' olarak geçildi. 📋😆",
]

# =========================================================
# FAL TEMALARI
# =========================================================

FAL_TEMALARI = [
    "kahve fincanı",
    "el falı",
    "yıldız falı",
    "tarot kartları",
    "iskambil falı",
    "kitap falı",
    "su falı",
    "ayna falı",
    "kum falı",
    "bulut falı",
]

# =========================================================
# GROQ CEVABI
# =========================================================

async def _groq_cevap(kullanici_adi, mesaj):
    def cagri():
        return ai_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": BOT_PERSONA,
                },
                {
                    "role": "user",
                    "content": f"{kullanici_adi}: {mesaj}",
                },
            ],
            max_tokens=150,
        )

    response = await asyncio.to_thread(cagri)

    return response.choices[0].message.content


# =========================================================
# NORMAL AI CEVABI
# =========================================================

async def ai_cevap_uret(kullanici_adi, mesaj):
    prompt = (
        f"{BOT_PERSONA}\n\n"
        f"Aşağıda grup üyesi {kullanici_adi} sana şunu yazdı:\n"
        f"\"{mesaj}\"\n\n"
        "Bu mesaja yukarıdaki karaktere uygun şekilde cevap ver. "
        "Cevabın KESİNLİKLE en fazla 2-3 cümle olsun. "
        "Kısa, doğal, komik ve konuya uygun yaz. "
        "Cevabını göndermeden önce Türkçe yazım ve dil bilgisi "
        "açısından kendi kendine kontrol et."
    )

    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        )

        return response.text.strip()

    except Exception as e:
        print(f"ai_cevap_uret (Gemini) hatası: {e}")

        try:
            return await _groq_cevap(
                kullanici_adi,
                mesaj,
            )

        except Exception as e2:
            print(f"ai_cevap_uret (Groq yedek) hatası: {e2}")

            return (
                "Kafamın içi şu an biraz karman çorman oldu, "
                "bir saniye ver de toparlanayım. 😅"
            )


# =========================================================
# ASK / AŞIK AI CEVABI
# =========================================================

async def ask_cevap_uret(kullanici_adi, mesaj):
    prompt = (
        f"{ASK_PERSONA}\n\n"
        f"Karşındaki kişinin adı: {kullanici_adi}\n"
        f"Kişinin sana yazdığı mesaj:\n"
        f"\"{mesaj}\"\n\n"
        "Şimdi bu mesaja cevap ver.\n\n"
        "ÖNEMLİ:\n"
        "- Aşırı âşık ve şapşal bir karakter gibi davran.\n"
        "- Tatlı ve komik ol.\n"
        "- Gerektiğinde utangaç veya kıskanç olabilirsin.\n"
        "- Her mesajı zorla romantikleştirme.\n"
        "- Kullanıcının mesajının içeriğine gerçekten cevap ver.\n"
        "- En fazla 2-3 kısa cümle yaz.\n"
        "- Türkçe yazım ve dil bilgisine dikkat et.\n"
        "- Küfür, hakaret, cinsel veya müstehcen ifade kullanma."
    )

    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        )

        return response.text.strip()

    except Exception as e:
        print(f"ask_cevap_uret (Gemini) hatası: {e}")

        # Groq yedek
        try:
            response = await asyncio.to_thread(
                lambda: ai_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": ASK_PERSONA,
                        },
                        {
                            "role": "user",
                            "content": (
                                f"{kullanici_adi}: {mesaj}\n\n"
                                "Şapşal ve aşık bir şekilde, "
                                "en fazla 2-3 cümle cevap ver."
                            ),
                        },
                    ],
                    max_tokens=150,
                )
            )

            return response.choices[0].message.content.strip()

        except Exception as e2:
            print(f"ask_cevap_uret (Groq) hatası: {e2}")

            return (
                "Şey... Sen yazınca beynim yine gitti. "
                "Ne diyeceğimi unuttum. 😳❤️"
            )


# =========================================================
# KARŞILAMA
# =========================================================

async def karsilama_uret(isim):
    prompt = (
        f"Sen MeyusBot'sun; muzip, şakacı ve enerjik bir karaktersin. "
        f"Gruba yeni katılan {isim} için en fazla 2-3 cümlelik, "
        f"samimi, esprili ve sıcak bir karşılama mesajı yaz. "
        f"Hafif dalgacı ama incitmeyen bir üslup kullan. "
        f"Birkaç emoji ekleyebilirsin. "
        f"Türkçe dil bilgisi ve yazım kurallarına titizlikle uy. "
        f"Göndermeden önce kendi kendine kontrol edip hata varsa düzelt."
    )

    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        )

        return response.text.strip()

    except Exception as e:
        print(f"karsilama_uret (Gemini) hatası: {e}")

        try:
            return await _groq_cevap(
                "Sistem",
                prompt,
            )

        except Exception as e2:
            print(f"karsilama_uret (Groq yedek) hatası: {e2}")

            return (
                f"Hoş geldin {isim}! Burası biraz kaotik ama eğlenceli, "
                "alırsın. 🎉"
            )


# =========================================================
# FAL
# =========================================================

async def fal_uret(kullanici_adi):
    tema = random.choice(FAL_TEMALARI)

    prompt = (
        f"Sen Meyus adında, muzip ve şakacı bir falcı yapay zekasın. "
        f"{kullanici_adi} isimli kullanıcı için '{tema}' temalı, "
        f"eğlenceli, yaratıcı, hafif abartılı ve komik ama içinde "
        f"ufak bir motivasyon da barındıran uzunca bir fal yaz. "
        f"En az 6-8 cümle olsun. "
        f"Aşk, kariyer/iş, sağlık ve sürpriz bir olay hakkında "
        f"en az birer detay geçsin. "
        f"Ciddi bir kehanet gibi değil, samimi ve gülümseten "
        f"bir üslupla yaz. "
        f"Birkaç emoji kullanabilirsin. "
        f"Türkçe dil bilgisi ve yazım kurallarına titizlikle uy."
    )

    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generat
