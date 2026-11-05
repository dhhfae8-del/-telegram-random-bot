import os
import re
import json
import random
import threading

import telebot
from flask import Flask

# الإعدادات
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").lstrip("@").lower()

if not TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود في Environment Variables")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

BUTTON_TEXT = "امم مافي شي 🍌💦🍌"
DATA_FILE = "media.json"

media_lock = threading.Lock()

# تحميل الوسائط
def load_media():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            return {
                "photo": data.get("photo", []),
                "video": data.get("video", [])
            }
        except Exception:
            pass

    return {"photo": [], "video": []}


media = load_media()


# حفظ الوسائط
def save_data():
    with media_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(media, f, ensure_ascii=False, indent=2)


# استخراج رابط MEGA من وصف الصورة
def get_mega_link(caption):
    if not caption:
        return ""

    match = re.search(
        r"https?://(?:www\.)?mega\.nz/\S+",
        caption
    )

    if match:
        return match.group(0).rstrip(".,)]}")

    return ""


# استقبال الصور والفيديوهات من القناة
@bot.channel_post_handler(content_types=["photo", "video"])
def save_media(message):

    # التأكد من القناة
    if CHANNEL_USERNAME:
        channel_name = (message.chat.username or "").lower()

        if channel_name and channel_name != CHANNEL_USERNAME:
            return

    # استقبال الصور
    if message.content_type == "photo":
        file_id = message.photo[-1].file_id
        mega_url = get_mega_link(message.caption)

        with media_lock:
            existing = next(
                (item for item in media["photo"]
                 if item["file_id"] == file_id),
                None
            )

            if existing:
                existing["mega_url"] = mega_url
            else:
                media["photo"].append({
                    "file_id": file_id,
                    "mega_url": mega_url
                })

        save_data()

    # استقبال الفيديوهات
    elif message.content_type == "video":
        file_id = message.video.file_id

        with media_lock:
            if not any(
                item["file_id"] == file_id
                for item in media["video"]
            ):
                media["video"].append({
                    "file_id": file_id
                })

        save_data()


# إنشاء الزر
def get_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True
    )

    keyboard.add(
        telebot.types.KeyboardButton(BUTTON_TEXT)
    )

    return keyboard


# إرسال صورة وفيديو عشوائيين
def send_random_media(message):
    chat_id = message.chat.id

    with media_lock:
        photos = media["photo"].copy()
        videos = media["video"].copy()

    if not photos and not videos:
        bot.send_message(
            chat_id,
            "ما فيه صور أو فيديوهات محفوظة حتى الآن."
        )
        return

    # صورة عشوائية مع رابط MEGA
    if photos:
        photo = random.choice(photos)

        caption = photo.get("mega_url") or "ما فيه رابط MEGA مرفق."

        bot.send_photo(
            chat_id,
            photo["file_id"],
            caption=caption
        )
    else:
        bot.send_message(chat_id, "ما فيه صور محفوظة حتى الآن.")

    # فيديو عشوائي بدون رابط
    if videos:
        video = random.choice(videos)

        bot.send_video(
            chat_id,
            video["file_id"]
        )
    else:
        bot.send_message(chat_id, "ما فيه فيديوهات محفوظة حتى الآن.")


# أمر البداية
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "اضغط الزر للحصول على صورة وفيديو عشوائيين 🎲",
        reply_markup=get_keyboard()
    )


# الزر
@bot.message_handler(func=lambda message: message.text == BUTTON_TEXT)
def button_pressed(message):
    send_random_media(message)


# أمر عشوائي
@bot.message_handler(commands=["random"])
def random_command(message):
    send_random_media(message)


# معرفة عدد الوسائط
@bot.message_handler(commands=["count"])
def count_media(message):
    with media_lock:
        photo_count = len(media["photo"])
        video_count = len(media["video"])

    bot.send_message(
        message.chat.id,
        f"📸 عدد الصور: {photo_count}\n"
        f"🎬 عدد الفيديوهات: {video_count}"
    )


# صفحة Render
@app.route("/")
def home():
    return "Bot is running!"


# تشغيل البوت
def run_bot():
    bot.infinity_polling(skip_pending=True)


threading.Thread(
    target=run_bot,
    daemon=True
).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
