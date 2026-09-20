import os
import telebot
from yt_dlp import YoutubeDL

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "سلام! 🎵\nنام آهنگ یا لینک یوتیوب مورد نظرتان را بفرستید تا فایل صوتی آن را دریافت کنید."
    )

@bot.message_handler(func=lambda message: True)
def download_music(message):
    query = message.text.strip()
    chat_id = message.chat.id

    if query.startswith('/'):
        return

    status_msg = bot.send_message(chat_id, "🔍 در حال جستجو و دریافت آهنگ... لطفاً کمی شکیبا باشید.")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'default_search': 'ytsearch1:',
        'max_filesize': 50 * 1024 * 1024,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            file_id = info['id']
            file_path = f"downloads/{file_id}.mp3"
            title = info.get('title', 'Audio')
            uploader = info.get('uploader', 'Music Bot')

            if os.path.exists(file_path):
                bot.edit_message_text("⬆️ در حال ارسال به تلگرام...", chat_id, status_msg.message_id)
                with open(file_path, 'rb') as audio:
                    bot.send_audio(chat_id, audio=audio, title=title, performer=uploader)
                os.remove(file_path)
                bot.delete_message(chat_id, status_msg.message_id)
            else:
                bot.edit_message_text("❌ متأسفانه فایل دریافت نشد.", chat_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ خطایی رخ داد:\n`{str(e)[:100]}`", chat_id, status_msg.message_id, parse_mode="Markdown")

if not os.path.exists('downloads'):
    os.makedirs('downloads')

bot.infinity_polling()
