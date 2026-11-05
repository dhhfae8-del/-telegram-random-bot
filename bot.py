import os
import json
import random
import threading
import logging
import telebot
from flask import Flask

# إعدادات البوت
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL_USERNAME", "").replace("@", "").lower()

if not TOKEN:
    raise ValueError("BOT_TOKEN غير موجود في Environment Variables")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ملف حفظ الصور والفيديوهات
MEDIA_FILE = "media.json"
media = []

logging.basicConfig(level=logging.INFO)


# تحميل الوسائط المحفوظة
def load_media():
    global media

    if os.path.exists(MEDIA_FILE):
        try:
            with open(MEDIA_FILE, "r", encoding="utf-8") as file:
                media = json.load(file)
        except Exception as error:
            logging.error("خطأ في تحميل الوسائط: %s", error)


# حفظ الوسائط
def save_to_file():
    with open(MEDIA_FILE, "w", encoding="utf-8") as file:
        json.dump(media, file)


load_media()


# صفحة Render
@app.route("/")
def home():
    return "Bot is running!"


# استقبال الصور والفيديوهات من القناة
@bot.channel_post_handler(content_types=["photo", "video"])
def save_media(message):
    username = message.chat.username or ""

    if CHANNEL and username.lower() != CHANNEL:
        return

    if message.photo:
        file_id = message.photo[-1].file_id
        item = ["photo", file_id]

    elif message.video:
        file_id = message.video.file_id
        item = ["video", file_id]

    else:
        return

    if item not in media:
        media.append(item)
        save_to_file()
        logging.info("تم استقبال وسائط جديدة من القناة")


# أمر البداية
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "أهلاً! استخدم /random لإرسال صورة أو فيديو عشوائي."
    )


# إرسال صورة أو فيديو عشوائي
@bot.message_handler(commands=["random"])
def random_media(message):
    if not media:
        bot.reply_to(
            message,
            "لا توجد صور أو مقاطع محفوظة حتى الآن."
        )
        return

    kind, file_id = random.choice(media)

    if kind == "photo":
        bot.send_photo(message.chat.id, file_id)
    else:
        bot.send_video(message.chat.id, file_id)


# إرسال صورة عشوائية فقط
@bot.message_handler(commands=["photo"])
def random_photo(message):
    items = [x for x in media if x[0] == "photo"]

    if items:
        bot.send_photo(
            message.chat.id,
            random.choice(items)[1]
        )
    else:
        bot.reply_to(message, "لا توجد صور.")


# إرسال فيديو عشوائي فقط
@bot.message_handler(commands=["video"])
def random_video(message):
    items = [x for x in media if x[0] == "video"]

    if items:
        bot.send_video(
            message.chat.id,
            random.choice(items)[1]
        )
    else:
        bot.reply_to(message, "لا توجد مقاطع.")


# عدد الوسائط المحفوظة
@bot.message_handler(commands=["count"])
def count_media(message):
    photos = sum(1 for x in media if x[0] == "photo")
    videos = sum(1 for x in media if x[0] == "video")

    bot.reply_to(
        message,
        f"عدد الصور: {photos}\nعدد الفيديوهات: {videos}\nالمجموع: {len(media)}"
    )


# تشغيل البوت
def run_bot():
    bot.infinity_polling(skip_pending=True)


threading.Thread(
    target=run_bot,
    daemon=True
).start()


# تشغيل الموقع على Render
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
`
