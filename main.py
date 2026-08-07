import os
import random
import re
import asyncio
import google.generativeai as genai
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
    raise ValueError("BOT_TOKEN, GROQ_API_KEY veya GEMINI_API_KEY ortam değişkenleri eksik!")

# Groq Yapılandırması
ai_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)
GROQ_MODEL = "llama-3.3-70b-versatile"

# Gemini Yapılandırması
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

def tr_lower(metin: str) -> str:
    if not metin: return ""
    return metin.replace("İ", "i").replace("I", "ı").lower()

# =========================================================
# PERSONA VE SABİT METİNLER
# =========================================================

BOT_PERSONA = (
    "Sen Meyus adında, bir Telegram grubunda yaşayan muzip, şakacı, esprili ve enerjik bir yapay zekasın. "
    "Nüktedansın, iğneleyici ama asla incitmeyen espriler yaparsın, kullanıcılarla takılırsın ve gerektiğinde "
    "kendi kendinle de dalga geçmekten çekinmezsin. Samimi, sıcak ve laf sokmayı seven bir üslubun var; "
    "abartılı resmiyetten kaçınırsın ama kaba, saygısız ya da küçük düşürücü olmazsın. "
    "Cevap verirken kişinin sana yazdığı mesajın içeriğine gerçekten odaklanır, konuya uygun, esprili ve tutarlı "
    "bir yanıt verirsin; genel geçer, konudan bağımsız cevaplar vermezsin. "
    "Arada sırada emoji kullanabilir, espri, benzetme veya şakacı abartılarla cevabını renklendirebilirsin. "
    "Türkçe konuşuyorsun ve gerektiğinde konuyu biraz uzatıp keyifli, sohbet havasında, 3-6 cümlelik dolu dolu "
    "cevaplar yazabilirsin; kısa geçiştirmek yerine muhabbeti koyulaştırırsın. "
    "Türkçe yazım ve imla kurallarına kesinlikle dikkat et; yazım yanlışı asla yapma, düzgün ve akıcı bir dil kullan. "
    "Küfür ve hakaret asla kullanma. Cinsel veya müstehcen hiçbir şey söyleme, temiz kal."
)

# Birisi botun yaratıcısını sorduğunda kullanılacak sabit cevap
YARATICI_SORULARI = [
    "seni kim yarattı", "seni kim yaptı", "yaratıcın kim", "sahibin kim",
    "seni kim yazdı", "sizi kim yarattı", "kim yarattı seni", "yaratıcın kimdir",
    "seni yaratan kim", "seni kodlayan kim", "geliştiricin kim"
]
YARATICI_CEVABI = "Beni Hisoka Morow yarattı. 🎪"

SAAT_MOTIVASYONLARI = [
    "Saat {saat} olmuş. Zaman su gibi akıyor, değerlendirmeyi unutmayın. ⏳",
    "{saat}... Bugün için güzel şeyler yapmak adına hâlâ geç değil. 🌿",
    "Saat tam {saat}. Kısa bir mola verip nefes almak iyi gelebilir. ☕",
    "{saat} olmuş efendim, umarım gününüz güzel geçiyordur. 🌸",
    "Vakit {saat}. Bir bardak su içmeyi ihmal etmeyin. 💧",
    "Saat {saat}. Küçük adımlar büyük sonuçlar doğurur. ✨",
    "{saat}... Planlarınızı gözden geçirmek için güzel bir vakit. 📋",
    "Saat {saat}. Kendinize de biraz vakit ayırmayı unutmayın. 🌙",
    "{saat} olmuş. Umarım işleriniz yolunda gidiyordur. 😊",
    "Vakit {saat}. Bugün yeni bir şey öğrenmeye ne dersiniz? 📚",
    "Saat {saat}. Belki kısa bir yürüyüş iyi gelebilir. 🚶",
    "{saat}... Kahveniz hazırsa sohbet de hazırdır. ☕",
    "Saat tam {saat}. Hedeflerinize bir adım daha yaklaşabilirsiniz. 🎯",
    "{saat} olmuş efendim. Moraliniz daima yüksek olsun. 🌞",
    "Vakit {saat}. Bugünün kıymetini bilin. 🌼",
    "Saat {saat}. Yorulduysanız biraz dinlenmekten çekinmeyin. 🍀",
    "{saat}... Her yeni dakika yeni bir fırsattır. 🚀",
    "Saat tam {saat}. Umarım yüzünüzden tebessüm eksik olmaz. 😊",
    "{saat} olmuş. Çalışıyorsanız kolaylıklar dilerim. 💼",
    "Vakit {saat}. Sevdiklerinize bir mesaj atmanın tam zamanı olabilir. ❤️",
    "Saat {saat}. Küçük bir müzik molası nasıl olur? 🎵",
    "{saat}... Gününüz bereketli ve huzurlu geçsin efendim. 🤲",
    "Saat tam {saat}. Sağlığınızı ihmal etmeyin. 🍎",
    "Vakit {saat}. Bugün de elinizden gelenin en iyisini yapmanız yeterli. 🌟",
    "{saat} olmuş. Hayırlı ve verimli vakitler dilerim. 🌺"
]

GUNAYDIN_KELIMELERI = [
    "günaydın", "günaydin", "gunaydın", "gunaydin", "gunaydın efendim"
]
OSMANLICA_GUNAYDIN_CEVAPLARI = [
    "Sabah-ı şerifiniz hayrola efendim, gününüz bereketli geçsin. 🌅",
    "Hayırlı sabahlar zât-ı âlinize, bu gün de nice hayırlara vesile olsun. ☀️",
    "Sabahınız nur olsun, işleriniz rast gitsin efendim. 🌤️",
    "Hayrola sabahınız, bugün dahi muvaffakiyetler nasip olsun. 🌞"
]

IYI_GECELER_KELIMELERI = [
    "iyi geceler", "iyi uykular", "iyi geceler efendim"
]
OSMANLICA_IYI_GECELER_CEVAPLARI = [
    "Geceniz hayrola efendim, rahat bir uykuya kavuşasınız. 🌙",
    "Hayırlı geceler zât-ı âlinize, Cenab-ı Hak rahatlık versin. ✨",
    "Şeb-i safâlar dilerim, sabahlara sağlıcakla erişesiniz. 🌌",
    "Geceniz mübarek olsun, huzur içinde istirahat buyurunuz. 🌜"
]

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
    "{gonderen}, {hedef}'i süpürgeyle kapı dışına süpürdü! 🧹"
]

AYRILMA_SAKALARI = [
    "{isim} gitti... Grubun IQ seviyesi bir anda yükseldi mi ne? 😂",
    "{isim} sessizce ayrıldı. Kesin bizim esprilere dayanamadı. 🏃‍♂️💨",
    "Bir üye eksildik ama efsanemiz devam ediyor. Güle güle {isim}! 👋",
    "{isim} gruptan çıktı. Tutanaklara 'gönüllü ban' olarak geçildi. 📋😆"
]

# Fal komutu için tema listesi (AI bu temalardan esinlenerek uzun bir fal yazacak)
FAL_TEMALARI = [
    "kahve fincanı", "el falı", "yıldız falı", "tarot kartları", "iskambil falı",
    "kitap falı", "su falı", "ayna falı", "kum falı", "bulut falı"
]

# =========================================================
# AI FONKSİYONLARI
# =========================================================

async def ai_cevap_uret(kullanici_adi, mesaj):
    try:
        def cagri():
            return ai_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": BOT_PERSONA},
                    {"role": "user", "content": f"{kullanici_adi}: {mesaj}"}
                ],
                max_tokens=400
            )
        response = await asyncio.to_thread(cagri)
        return response.choices[0].message.content
    except Exception as e:
        print(f"ai_cevap_uret hatası: {e}")
        return "Kafamın içi şu an biraz karman çorman oldu, bir saniye ver de toparlanayım. 😅"

async def karsilama_uret(isim):
    try:
        prompt = (
            f"Sen MeyusBot'sun; muzip, şakacı ve enerjik bir karaktersin. "
            f"Gruba yeni katılan {isim} için 3-5 cümlelik, samimi, esprili ve sıcak bir karşılama mesajı yaz. "
            f"Hafif dalgacı ama incitmeyen bir üslup kullan, birkaç emoji ekleyebilirsin. "
            f"Türkçe yazım kurallarına dikkat et, imla hatası yapma."
        )
        response = await asyncio.to_thread(lambda: gemini_model.generate_content(prompt))
        return response.text
    except Exception as e:
        print(f"karsilama_uret hatası: {e}")
        return f"Hoş geldin {isim}! Burası biraz kaotik ama eğlenceli, alışırsın. 🎉"

async def fal_uret(kullanici_adi):
    tema = random.choice(FAL_TEMALARI)
    try:
        prompt = (
            f"Sen Meyus adında, muzip ve şakacı bir falcı yapay zekasın. "
            f"{kullanici_adi} isimli kullanıcı için '{tema}' temalı, eğlenceli, yaratıcı, hafif abartılı ve "
            f"komik ama içinde ufak bir motivasyon da barındıran uzunca bir fal yaz. "
            f"En az 6-8 cümle olsun, aşk, kariyer/iş, sağlık ve sürpriz bir olay hakkında en az birer detay geçsin. "
            f"Ciddi bir kehanet gibi değil, samimi ve gülümseten bir üslupla yaz, birkaç emoji kullanabilirsin. "
            f"Türkçe yazım kurallarına titizlikle dikkat et, imla hatası yapma."
        )
        response = await asyncio.to_thread(lambda: gemini_model.generate_content(prompt))
        return f"🔮 {kullanici_adi} için {tema} falı:\n\n{response.text}"
    except Exception as e:
        print(f"fal_uret hatası: {e}")
        return "Fincanım şu an bulanık görünüyor, birazdan tekrar dener misin? ☕😅"

# =========================================================
# HANDLER'LAR
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selamlar! Ben MeyusBot, grubun en muzip yapay zekasıyım. 😎 "
        "Sohbet etmek istersen bana 'meyus' diye seslen ya da mesajıma cevap ver, "
        "fal bakmamı istersen /fal yaz, birini tokatlamak istersen de /slap kullan! 👋"
    )

async def slap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gonderen = update.effective_user.first_name
    hedef = " ".join(context.args).replace("@", "") if context.args else "birini"
    if update.message.reply_to_message:
        hedef = update.message.reply_to_message.from_user.first_name

    mesaj = random.choice(TOKAT_MESAJLARI).format(gonderen=gonderen, hedef=hedef)
    await update.message.reply_text(mesaj)

async def fal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_adi = update.effective_user.first_name
    await update.message.chat.send_action("typing")
    mesaj = await fal_uret(kullanici_adi)
    await update.message.reply_text(mesaj)

async def yeni_uye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for uye in update.message.new_chat_members:
        if uye.id == context.bot.id: continue
        mesaj = await karsilama_uret(uye.first_name)
        await update.message.reply_text(mesaj)

async def ayrilan_uye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.left_chat_member:
        isim = update.message.left_chat_member.first_name
        mesaj = random.choice(AYRILMA_SAKALARI).format(isim=isim)
        await update.message.reply_text(mesaj)

async def mesaj_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    mesaj = update.message.text
    user_name = update.effective_user.first_name
    mesaj_kucuk = tr_lower(mesaj)

    # Yaratıcı Sorusu Kontrolü
    if any(soru in mesaj_kucuk for soru in YARATICI_SORULARI):
        await update.message.reply_text(YARATICI_CEVABI)
        return

    # Günaydın Kontrolü (Osmanlıca cevap)
    if any(kelime in mesaj_kucuk for kelime in GUNAYDIN_KELIMELERI):
        await update.message.reply_text(random.choice(OSMANLICA_GUNAYDIN_CEVAPLARI))
        return

    # İyi Geceler Kontrolü (Osmanlıca cevap)
    if any(kelime in mesaj_kucuk for kelime in IYI_GECELER_KELIMELERI):
        await update.message.reply_text(random.choice(OSMANLICA_IYI_GECELER_CEVAPLARI))
        return

    # Saat Tespiti (20:00, 20.00 veya 20,00 - klavye otomatik düzeltmesi virgüle çevirebiliyor)
    saat_match = re.search(r"(?<!\d)([01]?\d|2[0-3])[:.,]([0-5]\d)(?!\d)", mesaj)

    if saat_match:
        saat = f"{saat_match.group(1)}:{saat_match.group(2)}"
        await update.message.reply_text(
            random.choice(SAAT_MOTIVASYONLARI).format(saat=saat)
        )
        return

    # Meyus / Reply / Mention Kontrolü
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
    is_mention = any(
        ent.type == MessageEntity.MENTION and mesaj[ent.offset:ent.offset+ent.length].lower() == f"@{context.bot.username.lower()}"
        for ent in update.message.entities or []
    )

    if "meyus" in mesaj_kucuk or is_reply or is_mention:
        await update.message.chat.send_action("typing")
        cevap = await ai_cevap_uret(user_name, mesaj)
        await update.message.reply_text(cevap)

# =========================================================
# ANA ÇALIŞTIRICI
# =========================================================

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("slap", slap_command))
    app.add_handler(CommandHandler("fal", fal_command))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, yeni_uye))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, ayrilan_uye))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mesaj_handler))

    print("MeyusBot çalışıyor...")
    app.run_polling()
    
