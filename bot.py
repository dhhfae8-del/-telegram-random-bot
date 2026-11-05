import os
import re
import json
import random
import threading

import telebot
from flask import Flask

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").lstrip("@").lower()

if not TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

BUTTON_RANDOM = "امم مافي شي 🍌💦🍌"
BUTTON_SETTINGS = "ايش حاب اليوم 👅👄"

MEDIA_FILE = "media.json"
PREFS_FILE = "preferences.json"

lock = threading.Lock()


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


media = load_json(MEDIA_FILE, {"photo": [], "video": []})
preferences = load_json(PREFS_FILE, {})


def save_json(filename, data):
    with lock:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def get_mega_link(caption):
    if not caption:
        return ""

    match = re.search(r"https?://(?:www\.)?mega\.nz/\S+", caption)

    if match:
        return match.group(0).rstrip(".,)]}")

    return ""


def get_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True
    )
    keyboard.row(
        telebot.types.KeyboardButton(BUTTON_RANDOM)
    )
    keyboard.row(
        telebot.types.KeyboardButton(BUTTON_SETTINGS)
    )
    return keyboard


# استقبال الصور والفيديوهات من القناة
@bot.channel_post_handler(content_types=["photo", "video"])
def save_media(message):

    if CHANNEL_USERNAME:
        channel_name = (message.chat.username or "").lower()
        if channel_name != CHANNEL_USERNAME:
            return

    if message.content_type == "photo":
        item = {
            "file_id": message.photo[-1].file_id,
            "mega_url": get_mega_link(message.caption)
        }
        category = "photo"

    else:
        item = {
            "file_id": message.video.file_id
        }
        category = "video"

    with lock:
        if not any(
            x["file_id"] == item["file_id"]
            for x in media[category]
        ):
            media[category].append(item)
            updated = True
        else:
            updated = False

    if updated:
        save_json(MEDIA_FILE, media)


# بداية البوت
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "أهلًا بك 🎲\nاختر الزر الذي تريده:",
        reply_markup=get_keyboard()
    )


# فتح إعدادات العشوائية
@bot.message_handler(func=lambda m: m.text == BUTTON_SETTINGS)
def settings(message):

    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)

    keyboard.add(
        telebot.types.InlineKeyboardButton(
            "📸 صور فقط", callback_data="type_photo"
        ),
        telebot.types.InlineKeyboardButton(
            "🎬 فيديوهات فقط", callback_data="type_video"
        ),
        telebot.types.InlineKeyboardButton(
            "🎲 صور وفيديوهات مع بعض", callback_data="type_both"
        )
    )

    bot.send_message(
        message.chat.id,
        "ايش تحب يجيك؟ اختر نوع العشوائية:",
        reply_markup=keyboard
    )


# اختيار النوع
@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def choose_type(call):

    user_id = str(call.from_user.id)
    selected = call.data.replace("type_", "")

    preferences[user_id] = {
        "type": selected,
        "count": preferences.get(user_id, {}).get("count", 5)
    }

    save_json(PREFS_FILE, preferences)

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "كم ملف عشوائي تبي يجيك كل مرة؟\n"
        "اكتب الرقم الذي تريده، مثل 5 أو 10 أو 20."
    )

    bot.register_next_step_handler(
        call.message,
        receive_count,
        user_id
    )


# استقبال العدد
def receive_count(message, user_id):

    if not message.text or not message.text.isdigit():
        bot.send_message(
            message.chat.id,
            "اكتب رقمًا صحيحًا من 1 إلى 50."
        )
        bot.register_next_step_handler(
            message,
            receive_count,
            user_id
        )
        return

    count = int(message.text)

    if count < 1 or count > 50:
        bot.send_message(
            message.chat.id,
            "اختر عددًا من 1 إلى 50."
        )
        bot.register_next_step_handler(
            message,
            receive_count,
            user_id
        )
        return

    if user_id not in preferences:
        preferences[user_id] = {"type": "both", "count": count}
    else:
        preferences[user_id]["count"] = count

    save_json(PREFS_FILE, preferences)

    bot.send_message(
        message.chat.id,
        f"✅ تم حفظ إعداداتك!\n"
        f"العدد: {count}\n"
        f"النوع: {preferences[user_id]['type']}\n\n"
        f"اضغط زر «{BUTTON_RANDOM}» وقت ما تحب.",
        reply_markup=get_keyboard()
    )


# إرسال الوسائط حسب إعدادات المستخدم
def send_random(message):

    user_id = str(message.from_user.id)

    if user_id not in preferences:
        bot.send_message(
            message.chat.id,
            f"حدد إعداداتك أولًا من زر «{BUTTON_SETTINGS}».",
            reply_markup=get_keyboard()
        )
        return

    settings = preferences[user_id]
    selected_type = settings["type"]
    count = settings["count"]

    with lock:
        photos = media["photo"].copy()
        videos = media["video"].copy()

    if selected_type == "photo":
        pool = [("photo", x) for x in photos]

    elif selected_type == "video":
        pool = [("video", x) for x in videos]

    else:
        pool = (
            [("photo", x) for x in photos]
            + [("video", x) for x in videos]
        )

    if not pool:
        bot.send_message(
            message.chat.id,
            "ما فيه ملفات من النوع الذي اخترته حتى الآن."
        )
        return

    # اختيار عشوائي، مع السماح بالتكرار إذا كان العدد أكبر من المتوفر
    if count <= len(pool):
        chosen = random.sample(pool, count)
    else:
        chosen = random.choices(pool, k=count)

    for kind, item in chosen:
        try:
            if kind == "photo":
                caption = item.get("mega_url", "")
                bot.send_photo(
                    message.chat.id,
                    item["file_id"],
                    caption=caption if caption else None
                )

            else:
                bot.send_video(
                    message.chat.id,
                    item["file_id"]
                )

        except Exception as e:
            print("Send error:", e)


# زر العشوائية
@bot.message_handler(func=lambda m: m.text == BUTTON_RANDOM)
def random_button(message):
    send_random(message)


# عدد الوسائط المحفوظة
@bot.message_handler(commands=["count"])
def count_command(message):

    with lock:
        photo_count = len(media["photo"])
        video_count = len(media["video"])

    bot.send_message(
        message.chat.id,
        f"📸 الصور: {photo_count}\n"
        f"🎬 الفيديوهات: {video_count}"
    )


@app.route("/")
def home():
    return "Bot is running!"


def run_bot():
    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=20
    )


threading.Thread(
    target=run_bot,
    daemon=True
).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
