import os
import re
import random
import threading
import logging
import requests
import telebot

from flask import Flask
from telebot import types

logging.basicConfig(level=logging.INFO)

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@Aboemq").lstrip("@").lower()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing required environment variables")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# تخزين نوع الوسائط مؤقتاً أثناء اختيار العدد
pending_types = {}

# الاتصال بقاعدة البيانات
def db_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }


def db_get(table, params=None):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=db_headers(),
        params=params or {},
        timeout=20
    )
    response.raise_for_status()
    return response.json()


def db_upsert(table, data, conflict):
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params={"on_conflict": conflict},
        headers={
            **db_headers(),
            "Prefer": "resolution=merge-duplicates,return=minimal"
        },
        json=data,
        timeout=20
    )
    response.raise_for_status()


# استخراج رابط MEGA من وصف الصورة
def get_mega_link(caption):
    if not caption:
        return ""

    match = re.search(
        r"https?://(?:www\.)?mega\.(?:nz|co\.nz)/\S+",
        caption
    )

    if match:
        return match.group(0).rstrip(".,،)")

    return ""


# حفظ صورة أو فيديو في Supabase
def save_media(media_type, file_id, mega_url=""):
    db_upsert(
        "media",
        {
            "media_type": media_type,
            "file_id": file_id,
            "mega_url": mega_url
        },
        "file_id"
    )


# استقبال الصور والفيديوهات من القناة
@bot.channel_post_handler(content_types=["photo", "video"])
def receive_media(message):
    username = (message.chat.username or "").lower()

    if username != CHANNEL_USERNAME:
        return

    try:
        if message.photo:
            file_id = message.photo[-1].file_id
            mega_url = get_mega_link(message.caption)

            save_media("photo", file_id, mega_url)

        elif message.video:
            file_id = message.video.file_id

            save_media("video", file_id, "")

        logging.info("Media saved successfully")

    except Exception:
        logging.exception("Could not save media")


# لوحة الأزرار الرئيسية
def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    keyboard.row("امم مافي شي 🍌💦🍌")
    keyboard.row("ايش حاب اليوم 👅👄")

    return keyboard


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "أهلاً بك! اختر ماذا تريد:",
        reply_markup=main_keyboard()
    )


# قراءة إعدادات المستخدم
def get_preferences(user_id):
    rows = db_get(
        "user_preferences",
        {
            "user_id": f"eq.{user_id}",
            "select": "media_type,item_count"
        }
    )

    if rows:
        return rows[0]

    return {
        "media_type": "both",
        "item_count": 5
    }


# حفظ إعدادات المستخدم
def save_preferences(user_id, media_type, item_count):
    db_upsert(
        "user_preferences",
        {
            "user_id": user_id,
            "media_type": media_type,
            "item_count": item_count
        },
        "user_id"
    )


# زر الإعدادات
@bot.message_handler(func=lambda m: m.text == "ايش حاب اليوم 👅👄")
def settings(message):
    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "صور فقط 📷",
            callback_data="type_photo"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "فيديو فقط 🎬",
            callback_data="type_video"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "صور وفيديو 🎲",
            callback_data="type_both"
        )
    )

    bot.send_message(
        message.chat.id,
        "اختر نوع الوسائط:",
        reply_markup=keyboard
    )


# اختيار نوع الوسائط
@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def choose_type(call):
    media_type = call.data.replace("type_", "")

    pending_types[call.from_user.id] = media_type

    bot.answer_callback_query(call.id)

    sent = bot.send_message(
        call.message.chat.id,
        "كم صورة أو فيديو تريد؟ اكتب رقماً من 1 إلى 50."
    )

    bot.register_next_step_handler(
        sent,
        save_count,
        call.from_user.id
    )


# حفظ العدد والإعدادات
def save_count(message, user_id):
    if message.text == "/cancel":
        bot.send_message(
            message.chat.id,
            "تم إلغاء الإعدادات.",
            reply_markup=main_keyboard()
        )
        pending_types.pop(user_id, None)
        return

    try:
        count = int(message.text)

        if not 1 <= count <= 50:
            raise ValueError

        media_type = pending_types.pop(user_id)

        save_preferences(user_id, media_type, count)

        bot.send_message(
            message.chat.id,
            f"تم حفظ إعداداتك! ✅\n"
            f"النوع: {media_type}\n"
            f"العدد: {count}",
            reply_markup=main_keyboard()
        )

    except ValueError:
        sent = bot.send_message(
            message.chat.id,
            "اكتب رقماً صحيحاً من 1 إلى 50."
        )

        bot.register_next_step_handler(
            sent,
            save_count,
            user_id
        )

    except Exception:
        logging.exception("Saving preferences failed")
        bot.send_message(
            message.chat.id,
            "حدث خطأ أثناء حفظ الإعدادات. حاول مرة أخرى."
        )


# إرسال الوسائط العشوائية
@bot.message_handler(func=lambda m: m.text == "امم مافي شي 🍌💦🍌")
def send_random_media(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        preferences = get_preferences(user_id)

        media_type = preferences["media_type"]
        count = preferences["item_count"]

        media = db_get(
            "media",
            {"select": "media_type,file_id,mega_url"}
        )

        if media_type != "both":
            media = [
                item for item in media
                if item["media_type"] == media_type
            ]

        if not media:
            bot.send_message(
                chat_id,
                "ما فيه وسائط من النوع الذي اخترته حالياً."
            )
            return

        selected = random.sample(
            media,
            min(count, len(media))
        )

        if len(selected) < count:
            bot.send_message(
                chat_id,
                f"المتوفر حالياً {len(selected)} فقط."
            )

        for item in selected:
            if item["media_type"] == "photo":
                bot.send_photo(
                    chat_id,
                    item["file_id"],
                    caption=item.get("mega_url") or None
                )

            elif item["media_type"] == "video":
                bot.send_video(
                    chat_id,
                    item["file_id"]
                )

    except Exception:
        logging.exception("Sending random media failed")
        bot.send_message(
            chat_id,
            "حدث خطأ أثناء جلب الوسائط. حاول مرة أخرى."
        )


# معرفة عدد الوسائط المحفوظة
@bot.message_handler(commands=["count"])
def count_media(message):
    try:
        media = db_get(
            "media",
            {"select": "media_type"}
        )

        photos = sum(
            1 for item in media
            if item["media_type"] == "photo"
        )

        videos = sum(
            1 for item in media
            if item["media_type"] == "video"
        )

        bot.send_message(
            message.chat.id,
            f"📷 عدد الصور: {photos}\n"
            f"🎬 عدد الفيديوهات: {videos}"
        )

    except Exception:
        logging.exception("Counting media failed")
        bot.send_message(
            message.chat.id,
            "تعذر قراءة عدد الوسائط."
        )


# صفحة Render
@app.route("/")
def home():
    return "Bot is running!"


def run_bot():
    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30
    )


if __name__ == "__main__":
    threading.Thread(
        target=run_bot,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
