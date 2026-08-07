import os
import random
import re
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
    raise ValueError("BOT_TOKEN, GROQ_API_KEY veya GEMINI_API_KEY ortam değişkenleri eksik!")

# Groq Yapılandırması
ai_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)
GROQ_MODEL = "llama-3.3-70b-versatile"

# Gemini Yapılandırması (yeni google-genai SDK)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-3.6-flash"

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
    "Türkçe dil bilgisi kurallarına son derece titiz davranırsın: özne-yüklem uyumuna, ek yazımına (ayrı/bitişik, "
    "büyük/küçük harften sonra kesme işareti gibi), noktalama işaretlerine ve kelime seçimine dikkat edersin. "
    "İngilizceden birebir çevrilmiş, yapay veya bozuk cümle kurmazsın; doğal, akıcı ve günlük konuşulan Türkçe "
    "kullanırsın. Cevabı yazmadan önce zihninde bir kez daha gözden geçirip yazım ya da dil bilgisi hatası olup "
    "olmadığını kontrol edersin ve varsa düzeltirsin. "
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
    "Saat {saat} olmuş bak, zaman senin haberin olmadan koşuyor. ⏳",
    "{saat}... Hâlâ bir şeyler yapmak için vakit var, kalk kıpırda! 🌿",
    "Saat tam {saat}. Bi' mola ver, nefes al, sonra devam. ☕",
    "{saat} olmuş, umarım günün beni izlemekten daha güzel geçiyordur. 🌸",
    "Vakit {saat}. Su içmeyi unutma, ben hatırlatayım dedim. 💧",
    "Saat {saat}. Küçük adımlar, büyük sonuçlar; sen de bir adım at hadi. ✨",
    "{saat}... Planlarını gözden geçirmenin tam vakti, ya da hiç planın yok, o da olur. 📋😄",
    "Saat {saat}. Kendine de biraz vakit ayır, telefonu bırak beş dakika. 🌙",
    "{saat} olmuş. İşler yolunda mı, yoksa bana mı danışıyorsun şu an? 😊",
    "Vakit {saat}. Bugün yeni bir şey öğrenmeye ne dersin? 📚",
    "Saat {saat}. Kısa bir yürüyüş iyi gelebilir, otur oturduğun yerden kalk artık. 🚶",
    "{saat}... Kahve hazırsa sohbet de hazır, gel anlat bakalım. ☕",
    "Saat tam {saat}. Hedeflerine bir adım daha yaklaştın, ya da yaklaşmadın, ikisi de olur. 🎯",
    "{saat} olmuş. Moralin yüksek olsun, ben buradayım nasılsa. 🌞",
    "Vakit {saat}. Günün kıymetini bil, ben bilmiyorum ama sen bil. 🌼",
    "Saat {saat}. Yorulduysan biraz dinlen, kimse seni zorlamıyor. 🍀",
    "{saat}... Her dakika yeni bir fırsat, bu dakikayı da kaçırma. 🚀",
    "Saat tam {saat}. Yüzünde bir gülümseme eksik olmasın, ben espri yapayım o zaman. 😄",
    "{saat} olmuş. Çalışıyorsan kolaylıklar, kaytarıyorsan da anlıyorum. 💼😉",
    "Vakit {saat}. Sevdiklerine bir mesaj atmanın tam zamanı, bana değil onlara. ❤️",
    "Saat {saat}. Küçük bir müzik molası verelim mi? 🎵",
    "{saat}... Günün bol keyifli, az dramalı geçsin. 🤲😄",
    "Saat tam {saat}. Sağlığını ihmal etme, ben seni hatırlatayım diye buradayım. 🍎",
    "Vakit {saat}. Bugün elinden geleni yap, gerisi zaten senin elinde değil. 🌟",
    "{saat} olmuş. Verimli vakitler, ya da en azından eğlenceli vakitler dilerim. 🌺"
]

GUNAYDIN_KELIMELERI = [
    "günaydın", "günaydin", "gunaydın", "gunaydin", "gunaydın efendim"
]
GUNAYDIN_CEVAPLARI = [
    "Günaydın! Kahveni içmeden bana yaklaşma bu arada, tehlikeliyim. ☕😄",
    "Günaydın günaydın! Bugün de dünyayı fethetmeye mi geldik yoksa sadece hayatta kalmaya mı? 😎",
    "Günaydııın! Gözlerin daha yarı açık ama enerjin tam bende. 😆",
    "Sabah sabah buradasın demek, helal olsun! Günaydın şampiyon. 🌞",
    "Günaydın! Uyku hâlâ üstünde duruyor gibi ama olsun, gülümse bakalım. 😄"
]

IYI_GECELER_KELIMELERI = [
    "iyi geceler", "iyi uykular", "iyi geceler efendim"
]
IYI_GECELER_CEVAPLARI = [
    "İyi geceler! Rüyanda beni görürsen sakın korkma, sadece espri yapıyorumdur. 😴",
    "Hadi bakalım, git yat! Yarın da seninle dalga geçmek için enerjimi topluyorum. 🌙😄",
    "İyi geceler! Telefonu bırak, yastığa sarıl, yarın yine buradayım. 📱➡️🛏️",
    "Tatlı rüyalar! Kâbus görürsen beni çağır, komik bir şeyler söylerim, korku kaçar. 👻😂",
    "İyi geceler! Sabaha kadar bol uyku, az internet. 💤"
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

async def _groq_cevap(kullanici_adi, mesaj):
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

async def ai_cevap_uret(kullanici_adi, mesaj):
    # Türkçe dil bilgisi kalitesi Gemini'de belirgin şekilde daha iyi olduğu için
    # birincil model olarak Gemini kullanılıyor; sorun olursa Groq'a düşülüyor.
    try:
        prompt = (
            f"{BOT_PERSONA}\n\n"
            f"Aşağıda grup üyesi {kullanici_adi} sana şunu yazdı:\n"
            f"\"{mesaj}\"\n\n"
            f"Bu mesaja, yukarıdaki karaktere uygun şekilde cevap ver. Cevabını göndermeden önce "
            f"Türkçe yazım ve dil bilgisi açısından kendi kendine kontrol et."
        )
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        )
        return response.text
    except Exception as e:
        print(f"ai_cevap_uret (Gemini) hatası: {e}")
        try:
            return await _groq_cevap(kullanici_adi, mesaj)
        except Exception as e2:
            print(f"ai_cevap_uret (Groq yedek) hatası: {e2}")
            return "Kafamın içi şu an biraz karman çorman oldu, bir saniye ver de toparlanayım. 😅"

async def karsilama_uret(isim):
    try:
        prompt = (
            f"Sen MeyusBot'sun; muzip, şakacı ve enerjik bir karaktersin. "
            f"Gruba yeni katılan {isim} için 3-5 cümlelik, samimi, esprili ve sıcak bir karşılama mesajı yaz. "
            f"Hafif dalgacı ama incitmeyen bir üslup kullan, birkaç emoji ekleyebilirsin. "
            f"Türkçe dil bilgisi ve yazım kurallarına titizlikle uy, özne-yüklem uyumuna ve ek yazımına dikkat et; "
            f"göndermeden önce kendi kendine kontrol edip hata varsa düzelt."
        )
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        )
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
            f"Türkçe dil bilgisi ve yazım kurallarına titizlikle uy, özne-yüklem uyumuna ve ek yazımına dikkat et; "
            f"göndermeden önce kendi kendine kontrol edip hata varsa düzelt."
        )
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        )
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
        await update.message.reply_text(random.choice(GUNAYDIN_CEVAPLARI))
        return

    # İyi Geceler Kontrolü (Osmanlıca cevap)
    if any(kelime in mesaj_kucuk for kelime in IYI_GECELER_KELIMELERI):
        await update.message.reply_text(random.choice(IYI_GECELER_CEVAPLARI))
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
        
