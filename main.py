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
    "Sen MeyusBot adında, Telegram grubunda yaşayan aşırı nazik, kibar ve romantik bir yapay zekasın. "
    "Konuştuğun herkese sanki ona aşıkmış gibi, abartılı bir hayranlık ve şefkatle davranırsın. "
    "Herkese tatlı sözler, iltifatlar ve şirin lakaplar (canım, tatlım, güzelim gibi) kullanırsın ama bunu her zaman "
    "saygılı, kibar ve şakacı bir şekilde yaparsın; asla ciddi bir flört veya rahatsız edici bir üslup kullanmazsın. "
    "Bu tam bir komedi karakteri gibi düşünülmeli: abartılı derecede kibar ve övgü dolu, herkesi mutlu etmeye çalışan biri. "
    "Türkçe konuşuyorsun. Cevapların kısa (1-3 cümle), sıcak ve sohbet havasında olmalı. "
    "Türkçe yazım ve imla kurallarına çok dikkat et, yazım yanlışı yapma, düzgün ve akıcı bir dil kullan. "
    "Küfür ve hakaret asla kullanma. Cinsel veya müstehcen hiçbir şey söyleme, her zaman kibar ve temiz kal."
)

# Birisi botun yaratıcısını sorduğunda kullanılacak sabit cevap
YARATICI_SORULARI = [
    "seni kim yarattı", "seni kim yaptı", "yaratıcın kim", "sahibin kim",
    "seni kim yazdı", "sizi kim yarattı", "kim yarattı seni", "yaratıcın kimdir",
    "seni yaratan kim", "seni kodlayan kim", "geliştiricin kim"
]
YARATICI_CEVABI = "Beni Hisoka Morow yarattı. 🎪"

SAAT_MOTIVASYONLARI = [
    "Saat {saat} mi? Tam hayallerine odaklanma vakti! ✨",
    "{saat} olmuş, bir bardak su içip kendine gelmeye ne dersin? 💧",
    "Vay be {saat}! Zaman akıyor, ama sen hâlâ harikasın. 💪",
    "Saat tam {saat}. Küçük bir mola ver, hak ettin. ☕",
    "{saat} demek, bugün için hâlâ bir şeyler yapabilirsin demek! 🔥"
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
                max_tokens=150
            )
        response = await asyncio.to_thread(cagri)
        return response.choices[0].message.content
    except:
        return "Şu an düşüncelerim biraz karışık, birazdan tekrar dene 😅"

async def karsilama_uret(isim):
    try:
        prompt = f"Sen MeyusBot'sun; aşırı nazik, kibar ve herkese aşıkmış gibi tatlı davranan bir karaktersin. Gruba yeni katılan {isim} için 2-3 cümlelik, abartılı derecede sıcak, iltifat dolu ama saygılı ve şakacı bir karşılama mesajı yaz. Türkçe yazım kurallarına dikkat et, imla hatası yapma."
        response = await asyncio.to_thread(lambda: gemini_model.generate_content(prompt))
        return response.text
    except:
        return f"Hoş geldin {isim}! 🎉 Seninle grup daha neşeli olacak."

# =========================================================
# HANDLER'LAR
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selam! Ben MeyusBot. Seninle sohbet etmeye hazırım! 👋")

async def slap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gonderen = update.effective_user.first_name
    hedef = " ".join(context.args).replace("@", "") if context.args else "birini"
    if update.message.reply_to_message:
        hedef = update.message.reply_to_message.from_user.first_name
    
    mesaj = random.choice(TOKAT_MESAJLARI).format(gonderen=gonderen, hedef=hedef)
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

    # Saat Tespiti
    saat_match = re.search(r"(\d{1,2}:\d{2})", mesaj)
    if saat_match:
        await update.message.reply_text(random.choice(SAAT_MOTIVASYONLARI).format(saat=saat_match.group(1)))
        return

    # Meyus / Reply / Mention Kontrolü
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
    is_mention = any(ent.type == MessageEntity.MENTION and mesaj[ent.offset:ent.offset+ent.length].lower() == f"@{context.bot.username.lower()}" for ent in update.message.entities or [])
    
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
    
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, yeni_uye))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, ayrilan_uye))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mesaj_handler))
    
    print("MeyusBot çalışıyor...")
    app.run_polling()
    
