import os
import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_USERNAME = "meov2ray"  # 📢 آیدی کانال خود را بدون @ قرار دهید

bot = telebot.TeleBot(TOKEN)

# فایل ذخیره آمار کاربران
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_users(users):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(list(users), f)
    except Exception:
        pass

users_list = load_users()
broadcast_state = {}

# کیبورد شیشه‌ای پنل مدیریت
def get_admin_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    btn_stats = InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats")
    btn_broadcast = InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")
    markup.add(btn_stats, btn_broadcast)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if user_id not in users_list:
        users_list.add(user_id)
        save_users(users_list)

    bot.send_message(
        user_id,
        f"سلام! 🎵\nبه ربات دانلود موزیک خوش آمدید.\n\n"
        f"نام آهنگ یا لینک یوتیوب مورد نظرتان را بفرستید تا فایل صوتی آن را دریافت کنید.\n\n"
        f"📢 عضویت در کانال ما: @{CHANNEL_USERNAME}"
    )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = str(message.chat.id)
    if ADMIN_ID and user_id == str(ADMIN_ID):
        bot.send_message(
            message.chat.id,
            "⚙️ **به پنل مدیریت خوش آمدید:**\nیکی از گزینه‌های زیر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    user_id = str(call.message.chat.id)
    if not (ADMIN_ID and user_id == str(ADMIN_ID)):
        return

    if call.data == "admin_stats":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"📊 **آمار ربات:**\n\nتعداد کل کاربران: `{len(users_list)}` نفر",
            parse_mode="Markdown"
        )
    elif call.data == "admin_broadcast":
        bot.answer_callback_query(call.id)
        broadcast_state[call.message.chat.id] = True
        bot.send_message(
            call.message.chat.id,
            "📢 لطفاً پیامی که می‌خواهید به تمام کاربران ارسال شود را بفرستید (متن، عکس، ویدیو و...):"
        )

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'audio', 'voice', 'document', 'video'])
def handle_all_messages(message):
    chat_id = message.chat.id
    user_id_str = str(chat_id)

    # ارسال همگانی توسط مدیریت
    if ADMIN_ID and user_id_str == str(ADMIN_ID) and broadcast_state.get(chat_id):
        broadcast_state[chat_id] = False
        status_msg = bot.send_message(chat_id, "⏳ در حال ارسال پیام به تمام کاربران...")
        success, failed = 0, 0
        for uid in list(users_list):
            try:
                bot.copy_message(chat_id=uid, from_chat_id=chat_id, message_id=message.message_id)
                success += 1
            except Exception:
                failed += 1
        bot.edit_message_text(
            f"✅ **ارسال همگانی پایان یافت.**\n\nموفق: `{success}`\nناموفق (بلاک شده): `{failed}`",
            chat_id,
            status_msg.message_id,
            parse_mode="Markdown"
        )
        return

    # ثبت آیدی کاربر
    if chat_id not in users_list:
        users_list.add(chat_id)
        save_users(users_list)

    if message.content_type != 'text' or message.text.startswith('/'):
        return

    query = message.text.strip()
    status_msg = bot.send_message(chat_id, "🔍 در حال جستجو و دریافت آهنگ... لطفاً کمی شکیبا باشید.")

    # 🛡️ کانفیگ ضدسد جدید با کلاینت اندروید VR و وب کریئیتور
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
        'user_agent': 'Mozilla/5.0 (Android 14; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0',
        'extractor_args': {
            'youtube': {
                'player_client': ['android_vr', 'web_creator', 'ios'],
                'skip': ['hls', 'dash']
            }
        },
        'nocheckcertificate': True,
    }

    # اگر فایل cookies.txt در ریپازیتوری وجود داشت، آن را هم خوانده و اعمال می‌کند
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

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
                caption_text = f"🎵 {title}\n\n🆔 @{CHANNEL_USERNAME}"
                with open(file_path, 'rb') as audio:
                    bot.send_audio(
                        chat_id=chat_id, 
                        audio=audio, 
                        title=title, 
                        performer=uploader,
                        caption=caption_text
                    )
                os.remove(file_path)
                bot.delete_message(chat_id, status_msg.message_id)
            else:
                bot.edit_message_text("❌ متأسفانه فایل دریافت نشد.", chat_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ خطایی رخ داد:\n`{str(e)[:100]}`", chat_id, status_msg.message_id, parse_mode="Markdown")

if not os.path.exists('downloads'):
    os.makedirs('downloads')

bot.infinity_polling()
