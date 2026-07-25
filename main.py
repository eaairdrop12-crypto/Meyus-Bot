import random
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "BOT_TOKEN_BURAYA"

db = sqlite3.connect("meyus.db", check_same_thread=False)
c = db.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
name TEXT,
xp INTEGER DEFAULT 0
)""")
db.commit()

JOKES=[
"Çay koyun da başlayalım. ☕",
"Ben botum ama muhabbeti severim. 🤖",
"Bugün de çalışıyorum. 😄"
]

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merhaba! Ben MeyusBot.\nKomutlar: /espri /zar /coin /profil")

async def espri(update, context):
    await update.message.reply_text(random.choice(JOKES))

async def zar(update, context):
    await update.message.reply_text(f"🎲 {random.randint(1,6)}")

async def coin(update, context):
    await update.message.reply_text(random.choice(["Yazı","Tura"]))

async def profil(update, context):
    uid=update.effective_user.id
    c.execute("SELECT xp FROM users WHERE id=?",(uid,))
    row=c.fetchone()
    if not row:
        c.execute("INSERT INTO users VALUES(?,?,?)",(uid,update.effective_user.first_name,0))
        db.commit()
        row=(0,)
    await update.message.reply_text(f"👤 {update.effective_user.first_name}\nXP: {row[0]}")

async def chat(update, context):
    uid=update.effective_user.id
    c.execute("SELECT xp FROM users WHERE id=?",(uid,))
    row=c.fetchone()
    if not row:
        c.execute("INSERT INTO users VALUES(?,?,?)",(uid,update.effective_user.first_name,2))
    else:
        c.execute("UPDATE users SET xp=xp+2 WHERE id=?",(uid,))
    db.commit()
    text=update.message.text.lower()
    if "selam" in text:
        await update.message.reply_text("Selam! 👋")
    elif "nasılsın" in text:
        await update.message.reply_text("İyiyim, teşekkürler. 😊")
    elif random.randint(1,8)==1:
        await update.message.reply_text(random.choice(JOKES))

app=ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("espri",espri))
app.add_handler(CommandHandler("zar",zar))
app.add_handler(CommandHandler("coin",coin))
app.add_handler(CommandHandler("profil",profil))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

if __name__=="__main__":
    print("MeyusBot çalışıyor...")
    app.run_polling()
