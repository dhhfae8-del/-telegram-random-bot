random
import threading
import telebot
from flask import Flask

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL = os.getenv("CHANNEL_USERNAME", "").replace("@", "").lower()

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

media = []

@app.route("/")
def home():
    return "Bot is running!"

@bot.channel_post_handler(
    content_types=["photo", "video"]
)
def save_media(message):
    username = message.chat.username or ""

    if CHANNEL and username.lower() != CHANNEL:
        return

    if message.photo:
        file_id = message.photo[-1].file_id
        media.append(("photo", file_id))

    elif message.video:
        media.append(("video", message.video.file_id))

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "أهلاً! استخدم /random لإرسال صورة أو فيديو عشوائي."
    )

@bot.message_handler(commands=["random"])
def random_media(message):
    if not media:
        bot.reply_to(message, "لا توجد صور أو مقاطع محفوظة حتى الآن.")
        return

    kind, file_id = random.choice(media)

    if kind == "photo":
        bot.send_photo(message.chat.id, file_id)
    else:
        bot.send_video(message.chat.id, file_id)

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

def run_bot():
    bot.infinity_polling(skip_pending=True)

threading.Thread(
    target=run_bot,
    daemon=True
).start()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
