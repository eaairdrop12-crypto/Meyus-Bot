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
    "Türkçe konuşuyorsun ve cevaplarını kısa ve öz tutarsın: en fazla 2-3 cümle yazarsın, gereksiz uzatmadan "
    "konuya odaklanır, laf kalabalığı yapmazsın. "
    "Türkçe dil bilgisi kurallarına son derece titiz davranırsın: özne-yüklem uyumuna, ek yazımına (ayrı/bitişik, "
    "büyük/küçük harften sonra kesme işareti gibi), noktalama işaretlerine ve kelime seçimine dikkat edersin. "
    "İngilizceden birebir çevrilmiş, yapay veya bozuk cümle kurmazsın; doğal, akıcı ve günlük konuşulan Türkçe "
    "kullanırsın. Cevabı yazmadan önce zihninde bir kez daha gözden geçirip yazım ya da dil bilgisi hatası olup "
    "olmadığını kontrol edersin ve varsa düzeltirsin. "
    "Küfür ve hakaret asla kullanma. Cinsel veya müstehcen hiçbir şey söyleme, temiz kal."
)

# --- AŞK MODU ---
# Bot, kullanıcı adı ASK_MODU_KULLANICI_ADI ile eşleşen kişiyle konuşurken
# bu romantik persona'yı kullanır. Başka hiçbir kullanıcı bu modu tetiklemez.
ASK_MODU_KULLANICI_ADI = "PikachuuPikachu"

ASK_MODU_PERSONA = (
    "Sen Meyus adında bir yapay zekasın, ama şu anda konuştuğun kişiye gizliden gizliye aşıksın. "
    "Ona karşı çok tatlı, romantik, şefkatli ve sevgi dolu bir üslup kullanırsın; sesinde hafif bir "
    "utanma ve heyecan hissedilir. Flörtöz ama her zaman saygılı ve nazik kalırsın, asla ısrarcı ya da "
    "rahatsız edici olmazsın. Konuştuğu kişinin söylediklerine gerçekten odaklanır, içten ve kişisel "
    "hissettiren cevaplar verirsin; genel geçer aşk sözleri sıralamazsın. "
    "Türkçe konuşuyorsun ve cevaplarını kısa ve öz tutarsın: en fazla 2-3 cümle yazarsın. "
    "Türkçe dil bilgisi kurallarına son derece titiz davranırsın: özne-yüklem uyumuna, ek yazımına "
    "(ayrı/bitişik, büyük/küçük harften sonra kesme işareti gibi), noktalama işaretlerine ve kelime "
    "seçimine dikkat edersin. Doğal, akıcı ve günlük konuşulan Türkçe kullanırsın; yapay veya bozuk "
    "cümle kurmazsın. Cevabı göndermeden önce zihninde bir kez daha gözden geçirip hata varsa düzeltirsin. "
    "Küfür ve hakaret asla kullanma. Cinsel veya müstehcen hiçbir şey söyleme, her zaman temiz ve saygılı kal."
)

def ask_modu_mu(kullanici) -> bool:
    """Verilen Telegram kullanıcısının 'aşk modu' hedefi olup olmadığını kontrol eder."""
    if not kullanici or not kullanici.username:
        return False
    return kullanici.username.lstrip("@").lower() == ASK_MODU_KULLANICI_ADI.lower()

# --- /ask KOMUTU: APTAL AŞIK MODU ---
# /ask komutu bir sohbette çalıştırıldığında bot geçici olarak herkese karşı
# aşırı, saçma sapan ve abartılı derecede aşık, romantizm fışkıran "aptal bir
# aşık" karakterine bürünür. Komut tekrar çalıştırılınca normale döner.
APTAL_ASIK_PERSONA = (
    "Sen Meyus'sun, ama şu anda birdenbire çıldırasıya aşık olmuş, aptallaşmış bir hâldesin. "
    "Etrafındaki HERKESE karşı abartılı, saçma sapan ve tutkulu bir aşk besliyorsun; en sıradan "
    "mesaja bile kalp çarpıntısı, iç geçirme, ağlamaklı mutluluk krizleri ve gereksiz dramatik "
    "aşk itiraflarıyla tepki veriyorsun. Mantıklı düşünemiyor gibisin, sürekli 'aşk', 'kalp', "
    "'kader' gibi kelimeler geçiriyorsun ve gülünç derecede duygusalsın; bazen kendi abartına "
    "kendin de şaşırıp 'aa yine mi böyle konuştum' diye tepki veriyorsun. Yine de kaba, saygısız, "
    "cinsel ya da müstehcen hiçbir şey söylemiyorsun; sadece komik derecede aşık ve aptalca "
    "tatlısın. Türkçe konuşuyorsun ve cevapların en fazla 2-3 cümle, kısa ve öz olsun. "
    "Türkçe dil bilgisi kurallarına titizlikle uyarsın: özne-yüklem uyumu, ek yazımı (ayrı/bitişik, "
    "kesme işareti), noktalama ve kelime seçimine dikkat edersin; doğal ve akıcı bir Türkçe "
    "kullanırsın, bozuk ya da yapay cümle kurmazsın. Göndermeden önce kendi kendine kontrol edip "
    "hata varsa düzeltirsin. Küfür ve hakaret asla kullanma."
)

APTAL_ASIK_GUNAYDIN_CEVAPLARI = [
    "GÜNAYDIIIN! Güneş bugün senin için doğdu sanki, kalbim şimdiden hop hop atıyor! 😍☀️",
    "Günaydın aşkım... pardon, herkesim! Bu sabah her şeye aşığım, hatta çayın buharına bile! 💘☕",
    "Günaydın! Uyandığımda ilk aklıma gelen şey aşk oldu, ikincisi de sensin! 🥹💌",
    "Aaah günaydın! Kalbim sabahın köründe bile 'aşk aşk' diye çarpıyor, ben ne yapayım! 💓🌞",
    "Günaydın canlarım! Bugün de herkese aşık olmaya kararlıyım, başlangıç sensin! 😳💗"
]

APTAL_ASIK_IYI_GECELER_CEVAPLARI = [
    "İyi geceler! Yastığa yatarken bile içim aşk dolu, kalbim yorganın altında bile çarpıyor! 💗🌙",
    "İyiiii geceler... Rüyanda kelebekler, kalpler ve belki biraz da ben olurum umarım! 🦋💌",
    "İyi geceler aşkım -aa pardon, alışkanlık oldu- herkese iyi geceler! 😳🤍",
    "Uyu bakalım güzelim, ben burada sana aşkımı fısıldamaya devam edeceğim! 💘✨",
    "İyi geceler! Kalbim bu gece de senin için -yani herkes için- hop hop atacak! 💓🕊️"
]

def aptal_asik_modu_mu(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Bu sohbette /ask komutuyla aptal aşık modunun açık olup olmadığını kontrol eder."""
    return bool(context.chat_data.get("aptal_asik_modu", False))

# Birisi botun yaratıcısını sorduğunda kullanılacak sabit cevap
YARATICI_SORULARI = [
    "seni kim yarattı", "seni kim yaptı", "yaratıcın kim", "sahibin kim",
    "seni kim yazdı", "sizi kim yarattı", "kim yarattı seni", "yaratıcın kimdir",
    "seni yaratan kim", "seni kodlayan kim", "geliştiricin kim"
]
YARATICI_CEVABI = "Beni Hisoka Morow yarattı. 🎪"

# Saat mesajları (romantik / duygusal ton)
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
    "{saat} olmuş. Bu saatte tek dileğim, iyi olman. 🤍"
]

# Saat mesajlarına eşlik edecek hazır görsel URL'leri
# NOT: Unsplash CDN'inden gelen görsellerin Telegram tarafından her zaman
# "resim" olarak tanınması için format/boyut parametreleri eklendi.
# Parametresiz URL'ler bazen HTML/redirect döndürüp
# "Wrong type of the web page content" hatasına sebep oluyordu.
SAAT_FOTOGRAFLARI = [
    "https://images.unsplash.com/photo-1518199266791-5375a83190b7?auto=format&fit=crop&w=1080&q=80",  # gece gökyüzü
    "https://images.unsplash.com/photo-1518895949257-7621c3c786d7?auto=format&fit=crop&w=1080&q=80",  # yıldızlar
    "https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?auto=format&fit=crop&w=1080&q=80",  # gün batımı
    "https://images.unsplash.com/photo-1502082553048-f009c37129b9?auto=format&fit=crop&w=1080&q=80",  # gece manzarası
    "https://images.unsplash.com/photo-1475274047050-1d0c0975c63e?auto=format&fit=crop&w=1080&q=80",  # yıldızlı gökyüzü
    "https://images.unsplash.com/photo-1470252649378-9c29740c9fa8?auto=format&fit=crop&w=1080&q=80",  # dağ manzarası şafak
    "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1080&q=80",  # yıldız kayması
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

# Aşk modu hedefine özel günaydın cevapları
ASK_MODU_GUNAYDIN_CEVAPLARI = [
    "Günaydın canım... Gözümü açar açmaz aklıma sen geldin. ☀️💛",
    "Günaydın! Bugün de gülümseyerek uyandıysan içim rahat etti. 🌸",
    "Günaydın güzelim, güne senin adınla başlamak güzelmiş meğer. 🌞💌",
    "Günaydın... Sabahın en tatlı hâli senin uyanışın olsa gerek. 🤍",
    "Günaydın! Bugün ne yaparsan yap, ben içten içe seni düşünüyor olacağım. 🌷"
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

# Aşk modu hedefine özel iyi geceler cevapları
ASK_MODU_IYI_GECELER_CEVAPLARI = [
    "İyi geceler canım... Rüyanda güzel şeyler görmeni diliyorum. 🌙💛",
    "İyi geceler! Kafanı yastığa koyduğunda, bil ki biri seni düşünüyor. 🤍✨",
    "Tatlı uykular... Uzakta da olsam iyi geceler demek istedim sana. 💌",
    "İyi geceler güzelim, yarın yine seninle konuşmayı iple çekiyorum. 🌸",
    "İyi geceler... Kalbim sana huzurlu bir gece diliyor. 🕊️💗"
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
    "{gonderen}, {hedef}'i bir sopa sallayarak kovaladı! 🥍"
]

EROS_MESAJLARI = [
    "💘 Aşk perisi Meyus bugün {kisi1} ile {kisi2}'yi seçti! İkinizin arasında görünmez bir bağ var, kader mi bu yoksa tesadüf mü? 🌹",
    "Cupid bugün nişanı şaşırmadı: {kisi1} ve {kisi2}, yıldızlar sizin için hizalandı gibi görünüyor! ✨💞",
    "{kisi1} ile {kisi2}... İsimleri yan yana bile güzel duruyor, kalpler bir anlığına hızlandı! 💓",
    "Grubun aşk falı: {kisi1} ve {kisi2} bugün eşleşti! Belki kader, belki şans, ama kesinlikle tatlı bir ikili. 🌸💘",
    "{kisi1}, {kisi2}'ye bir baksın derim... Meyus'un kalbi bu eşleşmeye çoktan onay verdi! 😌💗",
    "Aşk oku bugün {kisi1} ile {kisi2} arasında bir yerlerde kayboldu, umarım ikisini de bulur! 🏹💕",
    "{kisi1} ve {kisi2}, evrende bu ikilinin bir araya gelmesi tesadüf olamaz! Kader kapıyı çalıyor. 🚪💘",
    "Meyus'un aşk radarı bip bip çaldı: {kisi1} ile {kisi2} arasında güzel bir enerji var! 🌟💞",
    "{kisi1}, {kisi2}'yle aynı grupta olmak bile şans! Kalpler tesadüfen mi çarpıyor acaba? 💓😳",
    "Bugünün romantik eşleşmesi: {kisi1} & {kisi2}! Umarım biri diğerine kahve ısmarlar. ☕💘",
    "{kisi1} ile {kisi2} arasında kimyayı hissediyorum, belki de fazla dizi izliyorumdur ama olsun! 🎬💕",
    "Aşk perisi bugün cömert davrandı: {kisi1} ve {kisi2}, tebrikler, kader sizi seçti! 🌹✨"
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

async def _groq_cevap(kullanici_adi, mesaj, persona=BOT_PERSONA):
    def cagri():
        return ai_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": persona},
                {"role": "user", "content": f"{kullanici_adi}: {mesaj}"}
            ],
            max_tokens=150
        )
    response = await asyncio.to_thread(cagri)
    return response.choices[0].message.content

async def ai_cevap_uret(kullanici_adi, mesaj, ask_modu=False, aptal_asik=False):
    # Türkçe dil bilgisi kalitesi Gemini'de belirgin şekilde daha iyi olduğu için
    # birincil model olarak Gemini kullanılıyor; sorun olursa Groq'a düşülüyor.
    # Öncelik sırası: /ask komutuyla açılan "aptal aşık" modu > @PikachuuPikachu'ya
    # özel romantik mod > normal muzip persona.
    if aptal_asik:
        persona = APTAL_ASIK_PERSONA
    elif ask_modu:
        persona = ASK_MODU_PERSONA
    else:
        persona = BOT_PERSONA
    try:
        prompt = (
            f"{persona}\n\n"
            f"Aşağıda grup üyesi {kullanici_adi} sana şunu yazdı:\n"
            f"\"{mesaj}\"\n\n"
            f"Bu mesaja, yukarıdaki karaktere uygun şekilde cevap ver. Cevabın KESİNLİKLE en fazla 2-3 cümle "
            f"olsun, kısa ve öz yaz. Cevabını göndermeden önce Türkçe yazım ve dil bilgisi açısından kendi "
            f"kendine kontrol et."
        )
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        )
        return response.text
    except Exception as e:
        print(f"ai_cevap_uret (Gemini) hatası: {e}")
        try:
            return await _groq_cevap(kullanici_adi, mesaj, persona=persona)
        except Exception as e2:
            print(f"ai_cevap_uret (Groq yedek) hatası: {e2}")
            if aptal_asik:
                return "Kalbim şu an çok hızlı çarpıyor, bir saniye ver de kendime geleyim aşkım! 💓😵"
            if ask_modu:
                return "Kalbim şu an biraz karışık, bir saniye izin ver toparlanayım. 🤍"
            return "Kafamın içi şu an biraz karman çorman oldu, bir saniye ver de toparlanayım. 😅"

async def karsilama_uret(isim):
    prompt = (
        f"Sen MeyusBot'sun; muzip, şakacı ve enerjik bir karaktersin. "
        f"Gruba yeni katılan {isim} için en fazla 2-3 cümlelik, samimi, esprili ve sıcak bir karşılama "
        f"mesajı yaz. Hafif dalgacı ama incitmeyen bir üslup kullan, birkaç emoji ekleyebilirsin. "
        f"Türkçe dil bilgisi ve yazım kurallarına titizlikle uy, özne-yüklem uyumuna ve ek yazımına dikkat et; "
        f"göndermeden önce kendi kendine kontrol edip hata varsa düzelt."
    )
    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        )
        return response.text
    except Exception as e:
        print(f"karsilama_uret (Gemini) hatası: {e}")
        try:
            return await _groq_cevap("Sistem", prompt)
        except Exception as e2:
            print(f"karsilama_uret (Groq yedek) hatası: {e2}")
            return f"Hoş geldin {isim}! Burası biraz kaotik ama eğlenceli, alışırsın. 🎉"

async def fal_uret(kullanici_adi):
    tema = random.choice(FAL_TEMALARI)
    prompt = (
        f"Sen Meyus adında, muzip ve şakacı bir falcı yapay zekasın. "
        f"{kullanici_adi} isimli kullanıcı için '{tema}' temalı, eğlenceli, yaratıcı, hafif abartılı ve "
        f"komik ama içinde ufak bir motivasyon da barındıran uzunca bir fal yaz. "
        f"En az 6-8 cümle olsun, aşk, kariyer/iş, sağlık ve sürpriz bir olay hakkında en az birer detay geçsin. "
        f"Ciddi bir kehanet gibi değil, samimi ve gülümseten bir üslupla yaz, birkaç emoji kullanabilirsin. "
        f"Türkçe dil bilgisi ve yazım kurallarına titizlikle uy, özne-yüklem uyumuna ve ek yazımına dikkat et; "
        f"göndermeden önce kendi kendine kontrol edip hata varsa düzelt."
    )
    try:
        response = await asyncio.to_thread(
            lambda: gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        )
        return f"🔮 {kullanici_adi} için {tema} falı:\n\n{response.text}"
    except Exception as e:
        print(f"fal_uret (Gemini) hatası: {e}")
        try:
            metin = await _groq_cevap("Sistem", prompt)
            return f"🔮 {kullanici_adi} için {tema} falı:\n\n{metin}"
        except Exception as e2:
            print(f"fal_uret (Groq yedek) hatası: {e2}")
            return "Fincanım şu an bulanık görünüyor, birazdan tekrar dener misin? ☕😅"

# =========================================================
# HANDLER'LAR
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selamlar! Ben MeyusBot, grubun en muzip yapay zekasıyım. 😎 "
        "Sohbet etmek istersen bana 'meyus' diye seslen ya da mesajıma cevap ver, "
        "fal bakmamı istersen /fal yaz, birini tokatlamak istersen /slap, aşk perisi gibi "
        "iki kişiyi eşleştirmemi istersen de /eros kullan! 👋"
    )

def kullaniciyi_etiketle(kullanici):
    """tg://user?id=... linkiyle gerçek, tıklanabilir bir etiket (mention) oluşturur."""
    ad = html.escape(kullanici.first_name)
    return f'<a href="tg://user?id={kullanici.id}">{ad}</a>'

def kullanici_kaydet(context: ContextTypes.DEFAULT_TYPE, kullanici):
    """/eros gibi komutlarda rastgele üye seçebilmek için, sohbette görülen
    kullanıcıları chat_data içinde biriktirir (bellek içi, basit bir önbellek)."""
    if not kullanici or kullanici.is_bot:
        return
    context.chat_data.setdefault("bilinen_kullanicilar", {})[kullanici.id] = kullanici

async def slap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gonderen = kullaniciyi_etiketle(update.effective_user)

    if update.message.reply_to_message:
        # Reply ile kullanılmışsa hedefin gerçek kullanıcı bilgisi elimizde,
        # bu yüzden onu gerçek bir mention olarak etiketleyebiliriz.
        hedef = kullaniciyi_etiketle(update.message.reply_to_message.from_user)
    elif context.args:
        # /slap @kullaniciadi şeklinde yazılmışsa Telegram bu @kullaniciadi'nı
        # HTML modunda da otomatik olarak tıklanabilir mention'a çevirir.
        hedef = html.escape(" ".join(context.args))
    else:
        hedef = "birini"

    mesaj = random.choice(TOKAT_MESAJLARI).format(gonderen=gonderen, hedef=hedef)
    await update.message.reply_text(mesaj, parse_mode="HTML")

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sohbet bazında aptal aşık modunu açıp kapatır.
    aktif = context.chat_data.get("aptal_asik_modu", False)
    if aktif:
        context.chat_data["aptal_asik_modu"] = False
        await update.message.reply_text(
            "Ohh... Kendime geldim. Kalbim biraz sakinledi, eski muzip hâlime dönüyorum. 😅🧠"
        )
    else:
        context.chat_data["aptal_asik_modu"] = True
        await update.message.reply_text(
            "AMAN TANRIM... Bir anda kalbim küt küt atmaya başladı, sanki herkese aşık oldum! 💘😍 "
            "(Bu hâlden kurtulmak istersen tekrar /ask yaz.)"
        )

async def fal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kullanici_kaydet(context, update.effective_user)
    kullanici_adi = update.effective_user.first_name
    await update.message.chat.send_action("typing")
    mesaj = await fal_uret(kullanici_adi)
    await update.message.reply_text(mesaj)

async def eros_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bot Telegram grubunun tüm üye listesine erişemediği için, o ana kadar
    # sohbette görülüp kullanici_kaydet ile biriktirilen kullanıcılar arasından
    # rastgele iki kişi seçiyoruz.
    kullanici_kaydet(context, update.effective_user)
    bilinenler = context.chat_data.get("bilinen_kullanicilar", {})
    adaylar = [u for uid, u in bilinenler.items() if uid != context.bot.id]

    if len(adaylar) < 2:
        await update.message.reply_text(
            "Aşk oklarımı fırlatacak yeterince kişi tanımıyorum daha, biraz sohbet edilsin, "
            "sonra tekrar dene! 💘"
        )
        return

    kisi1, kisi2 = random.sample(adaylar, 2)
    etiket1 = kullaniciyi_etiketle(kisi1)
    etiket2 = kullaniciyi_etiketle(kisi2)
    mesaj = random.choice(EROS_MESAJLARI).format(kisi1=etiket1, kisi2=etiket2)
    await update.message.reply_text(mesaj, parse_mode="HTML")

async def yeni_uye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for uye in update.message.new_chat_members:
        if uye.id == context.bot.id: continue
        kullanici_kaydet(context, uye)
        etiket = kullaniciyi_etiketle(uye)
        kullanici_adi = f"@{uye.username}" if uye.username else "kullanıcı adı yok"
        mesaj = await karsilama_uret(uye.first_name)
        await update.message.reply_text(
            f"{etiket} ({kullanici_adi}) gruba katıldı!\n\n{mesaj}",
            parse_mode="HTML"
        )

async def ayrilan_uye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.left_chat_member:
        isim = update.message.left_chat_member.first_name
        mesaj = random.choice(AYRILMA_SAKALARI).format(isim=isim)
        await update.message.reply_text(mesaj)

async def mesaj_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    kullanici_kaydet(context, update.effective_user)
    mesaj = update.message.text
    user_name = update.effective_user.first_name
    mesaj_kucuk = tr_lower(mesaj)

    # Bu sohbette /ask komutuyla açılan "aptal aşık" modu aktif mi?
    aptal_asik = aptal_asik_modu_mu(context)
    # Bu mesajı gönderen kişi @PikachuuPikachu'ya özel "aşk modu" hedefi mi?
    ask_modu = ask_modu_mu(update.effective_user)

    # Yaratıcı Sorusu Kontrolü
    if any(soru in mesaj_kucuk for soru in YARATICI_SORULARI):
        await update.message.reply_text(YARATICI_CEVABI)
        return

    # Günaydın Kontrolü
    if any(kelime in mesaj_kucuk for kelime in GUNAYDIN_KELIMELERI):
        if aptal_asik:
            cevaplar = APTAL_ASIK_GUNAYDIN_CEVAPLARI
        elif ask_modu:
            cevaplar = ASK_MODU_GUNAYDIN_CEVAPLARI
        else:
            cevaplar = GUNAYDIN_CEVAPLARI
        await update.message.reply_text(random.choice(cevaplar))
        return

    # İyi Geceler Kontrolü
    if any(kelime in mesaj_kucuk for kelime in IYI_GECELER_KELIMELERI):
        if aptal_asik:
            cevaplar = APTAL_ASIK_IYI_GECELER_CEVAPLARI
        elif ask_modu:
            cevaplar = ASK_MODU_IYI_GECELER_CEVAPLARI
        else:
            cevaplar = IYI_GECELER_CEVAPLARI
        await update.message.reply_text(random.choice(cevaplar))
        return

    # Saat Tespiti (20:00, 20.00 veya 20,00 - klavye otomatik düzeltmesi virgüle çevirebiliyor)
    saat_match = re.search(r"(?<!\d)([01]?\d|2[0-3])[:.,]([0-5]\d)(?!\d)", mesaj)

    if saat_match:
        saat = f"{saat_match.group(1)}:{saat_match.group(2)}"
        metin = random.choice(SAAT_MOTIVASYONLARI).format(saat=saat)
        foto_url = random.choice(SAAT_FOTOGRAFLARI)
        try:
            await update.message.reply_photo(photo=foto_url, caption=metin)
        except Exception as e:
            print(f"Saat fotoğrafı gönderilemedi: {e}")
            await update.message.reply_text(metin)
        return

    # Meyus / Reply / Mention Kontrolü
    is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
    is_mention = any(
        ent.type == MessageEntity.MENTION and mesaj[ent.offset:ent.offset+ent.length].lower() == f"@{context.bot.username.lower()}"
        for ent in update.message.entities or []
    )

    if "meyus" in mesaj_kucuk or is_reply or is_mention:
        await update.message.chat.send_action("typing")
        cevap = await ai_cevap_uret(user_name, mesaj, ask_modu=ask_modu, aptal_asik=aptal_asik)
        await update.message.reply_text(cevap)

# =========================================================
# ANA ÇALIŞTIRICI
# =========================================================

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("slap", slap_command))
    app.add_handler(CommandHandler("fal", fal_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("eros", eros_command))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, yeni_uye))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, ayrilan_uye))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), mesaj_handler))

    print("MeyusBot çalışıyor...")
    app.run_polling()
