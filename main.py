import os
import json
import re
import difflib
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL

# =========================
# SETTINGS
# =========================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_USERNAME = "meov2ray"

bot = telebot.TeleBot(TOKEN)

USERS_FILE = "users.json"
broadcast_state = {}

# =========================
# USERS
# =========================

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            pass
    return set()


def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users), f)
    except:
        pass


users_list = load_users()


def add_user(user_id):
    if user_id not in users_list:
        users_list.add(user_id)
        save_users(users_list)


# =========================
# TEXT NORMALIZER
# =========================

def normalize(text):
    if not text:
        return ""

    text = text.lower()

    replacements = {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ة": "ه",
        "ۀ": "ه",
        "ؤ": "و",
        "إ": "ا",
        "أ": "ا",
    }

    for a, b in replacements.items():
        text = text.replace(a, b)

    text = re.sub(r"[^\w\sآ-ی]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================
# SEARCH SCORE
# =========================

BAD_WORDS = [
    "remix",
    "ریمیکس",
    "cover",
    "کاور",
    "live",
    "لایو",
    "slowed",
    "slow",
    "sped up",
    "speed up",
    "nightcore",
    "instrumental",
    "karaoke",
    "اجرای زنده",
    "ریمیکس",
]


def score_result(query, entry):

    title = entry.get("title", "")
    uploader = entry.get("uploader", "")

    q = normalize(query)
    t = normalize(title)
    u = normalize(uploader)

    if not t:
        return -1000

    score = 0

    # شباهت کل عبارت
    similarity = difflib.SequenceMatcher(
        None,
        q,
        t
    ).ratio()

    score += similarity * 50

    # کلمات جستجو
    query_words = set(q.split())
    title_words = set(t.split())

    if query_words:

        matched = len(query_words & title_words)

        score += (
            matched /
            len(query_words)
        ) * 70

    # اگر کل سرچ داخل عنوان باشد
    if q in t:
        score += 50

    # تطبیق کلمات با نام خواننده / کانال
    for word in query_words:

        if len(word) >= 3 and word in u:
            score += 25

    # نتایج نامطلوب
    for bad in BAD_WORDS:

        if bad in t:
            score -= 35

    # امتیاز برای موزیک‌های معمولی
    music_words = [
        "official",
        "official audio",
        "music",
        "audio",
        "موزیک",
        "آهنگ"
    ]

    for word in music_words:

        if word in t:
            score += 5

    return score


def best_result(query, entries):

    if not entries:
        return None

    best = None
    best_score = -9999

    for entry in entries:

        if not entry:
            continue

        score = score_result(
            query,
            entry
        )

        if score > best_score:

            best_score = score
            best = entry

    return best


# =========================
# ADMIN KEYBOARD
# =========================

def admin_keyboard():

    markup = InlineKeyboardMarkup(row_width=2)

    markup.add(
        InlineKeyboardButton(
            "📊 آمار ربات",
            callback_data="admin_stats"
        ),
        InlineKeyboardButton(
            "📢 پیام همگانی",
            callback_data="admin_broadcast"
        )
    )

    return markup


def back_keyboard():

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="admin_back"
        )
    )

    return markup


def cancel_keyboard():

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "❌ لغو ارسال",
            callback_data="broadcast_cancel"
        )
    )

    return markup


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    chat_id = message.chat.id

    add_user(chat_id)

    markup = InlineKeyboardMarkup(row_width=1)

    markup.add(
        InlineKeyboardButton(
            "🎵 راهنمای استفاده",
            callback_data="help"
        )
    )

    markup.add(
        InlineKeyboardButton(
            "📢 کانال ما",
            url=f"https://t.me/{CHANNEL_USERNAME}"
        )
    )

    bot.send_message(
        chat_id,

        "سلام 👋🎵\n\n"
        "به ربات دانلود موزیک خوش آمدید.\n\n"

        "برای دریافت آهنگ، اسم خواننده و آهنگ را بفرستید.\n\n"

        "مثال:\n"
        "🎧 شادمهر - تقدیر\n"
        "🎧 محسن یگانه - بهت قول میدم\n"
        "🎧 رضا بهرام - دیوانه\n\n"

        "یا لینک آهنگ را ارسال کنید.",

        reply_markup=markup
    )


# =========================
# HELP
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data == "help"
)
def help_callback(call):

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,

        "🎵 <b>راهنمای استفاده</b>\n\n"

        "نام خواننده + نام آهنگ را ارسال کنید.\n\n"

        "مثال:\n"
        "🎧 شادمهر - تقدیر\n"
        "🎧 معین - کعبه\n"
        "🎧 محسن یگانه - نشکن دلمو\n\n"

        "همچنین می‌توانید لینک YouTube یا سایت‌های پشتیبانی‌شده را ارسال کنید.",

        parse_mode="HTML"
    )


# =========================
# ADMIN
# =========================

@bot.message_handler(commands=["admin"])
def admin_panel(message):

    if not ADMIN_ID:
        return

    if str(message.chat.id) != str(ADMIN_ID):
        return

    bot.send_message(
        message.chat.id,

        "⚙️ <b>پنل مدیریت</b>\n\n"
        "یکی از گزینه‌ها را انتخاب کنید:",

        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# =========================
# ADMIN CALLBACKS
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("admin_")
)
def admin_callback(call):

    if not ADMIN_ID:
        return

    if str(call.message.chat.id) != str(ADMIN_ID):
        return

    if call.data == "admin_stats":

        bot.answer_callback_query(call.id)

        bot.edit_message_text(

            "📊 <b>آمار ربات</b>\n\n"

            f"👤 تعداد کاربران: <b>{len(users_list)}</b>\n"
            "🟢 وضعیت: فعال",

            call.message.chat.id,
            call.message.message_id,

            parse_mode="HTML",

            reply_markup=back_keyboard()
        )

    elif call.data == "admin_broadcast":

        bot.answer_callback_query(call.id)

        broadcast_state[
            call.message.chat.id
        ] = True

        bot.edit_message_text(

            "📢 <b>پیام همگانی</b>\n\n"

            "حالا پیام موردنظر را ارسال کن.\n\n"

            "می‌توانی متن، عکس، ویدیو، فایل، صوت و "
            "انواع پیام‌های تلگرام را بفرستی.",

            call.message.chat.id,
            call.message.message_id,

            parse_mode="HTML",

            reply_markup=cancel_keyboard()
        )

    elif call.data == "admin_back":

        bot.answer_callback_query(call.id)

        bot.edit_message_text(

            "⚙️ <b>پنل مدیریت</b>\n\n"
            "یکی از گزینه‌ها را انتخاب کنید:",

            call.message.chat.id,
            call.message.message_id,

            parse_mode="HTML",

            reply_markup=admin_keyboard()
        )


# =========================
# CANCEL BROADCAST
# =========================

@bot.callback_query_handler(
    func=lambda call:
    call.data == "broadcast_cancel"
)
def cancel_broadcast(call):

    if not ADMIN_ID:
        return

    if str(call.message.chat.id) != str(ADMIN_ID):
        return

    broadcast_state[
        call.message.chat.id
    ] = False

    bot.answer_callback_query(
        call.id,
        "لغو شد ❌"
    )

    bot.edit_message_text(

        "⚙️ <b>پنل مدیریت</b>\n\n"
        "ارسال پیام همگانی لغو شد.",

        call.message.chat.id,
        call.message.message_id,

        parse_mode="HTML",

        reply_markup=admin_keyboard()
    )


# =========================
# ALL MESSAGES
# =========================

@bot.message_handler(
    func=lambda message: True,
    content_types=[
        "text",
        "photo",
        "audio",
        "voice",
        "document",
        "video",
        "animation"
    ]
)
def handle_messages(message):

    chat_id = message.chat.id

    # =========================
    # BROADCAST
    # =========================

    if (
        ADMIN_ID
        and str(chat_id) == str(ADMIN_ID)
        and broadcast_state.get(chat_id)
    ):

        broadcast_state[chat_id] = False

        status = bot.send_message(
            chat_id,
            "⏳ در حال ارسال..."
        )

        success = 0
        failed = 0

        for user_id in list(users_list):

            try:

                bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=chat_id,
                    message_id=message.message_id
                )

                success += 1

            except:

                failed += 1

        bot.edit_message_text(

            "✅ <b>ارسال پایان یافت</b>\n\n"

            f"🟢 موفق: <b>{success}</b>\n"
            f"🔴 ناموفق: <b>{failed}</b>",

            chat_id,
            status.message_id,

            parse_mode="HTML",

            reply_markup=admin_keyboard()
        )

        return

    # =========================
    # ADD USER
    # =========================

    add_user(chat_id)

    # فقط متن برای سرچ آهنگ
    if message.content_type != "text":
        return

    if message.text.startswith("/"):
        return

    query = message.text.strip()

    if not query:
        return

    status = bot.send_message(
        chat_id,
        "🔍 در حال جستجوی آهنگ..."
    )

    # =========================
    # YT-DLP OPTIONS
    # =========================

    download_opts = {

        "format": "bestaudio/best",

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }
        ],

        "outtmpl":
        "downloads/%(id)s.%(ext)s",

        "quiet": True,

        "noplaylist": True,

        "max_filesize":
        50 * 1024 * 1024,

        "nocheckcertificate": True,

        "ffmpeg_location": "/usr/bin",

        "retries": 3,

        "fragment_retries": 3
    }

    try:

        # =========================
        # DIRECT LINK
        # =========================

        if query.startswith(
            ("http://", "https://")
        ):

            with YoutubeDL(
                download_opts
            ) as ydl:

                info = ydl.extract_info(
                    query,
                    download=True
                )

        # =========================
        # TEXT SEARCH
        # =========================

        else:

            search_opts = {
                "quiet": True,
                "skip_download": True,
                "extract_flat": True,
                "noplaylist": True
            }

            # جستجوی 10 نتیجه YouTube
            search_query = (
                f"ytsearch10:{query}"
            )

            with YoutubeDL(
                search_opts
            ) as ydl:

                results = ydl.extract_info(
                    search_query,
                    download=False
                )

            entries = results.get(
                "entries",
                []
            )

            if not entries:

                bot.edit_message_text(
                    "❌ آهنگ پیدا نشد.",
                    chat_id,
                    status.message_id
                )

                return

            # بهترین نتیجه
            selected = best_result(
                query,
                entries
            )

            if not selected:

                bot.edit_message_text(
                    "❌ نتیجه مناسبی پیدا نشد.",
                    chat_id,
                    status.message_id
                )

                return

            title_preview = selected.get(
                "title",
                "آهنگ"
            )

            bot.edit_message_text(

                f"🎵 <b>{title_preview}</b>\n\n"
                "⏬ در حال دانلود...",

                chat_id,
                status.message_id,

                parse_mode="HTML"
            )

            # دانلود نتیجه انتخاب شده
            with YoutubeDL(
                download_opts
            ) as ydl:

                info = ydl.extract_info(
                    selected["url"],
                    download=True
                )

        # =========================
        # INFO
        # =========================

        if (
            "entries" in info
            and info["entries"]
        ):
            info = info["entries"][0]

        file_id = info.get(
            "id",
            "audio"
        )

        file_path = (
            f"downloads/{file_id}.mp3"
        )

        title = info.get(
            "title",
            "Music"
        )

        uploader = info.get(
            "uploader",
            "Unknown Artist"
        )

        # =========================
        # SEND AUDIO
        # =========================

        if os.path.exists(file_path):

            bot.edit_message_text(

                "⬆️ در حال ارسال آهنگ...",

                chat_id,
                status.message_id
            )

            caption = (
                f"🎵 <b>{title}</b>\n\n"
                f"👤 {uploader}\n\n"
                f"🆔 @{CHANNEL_USERNAME}"
            )

            with open(
                file_path,
                "rb"
            ) as audio:

                bot.send_audio(

                    chat_id=chat_id,

                    audio=audio,

                    title=title,

                    performer=uploader,

                    caption=caption,

                    parse_mode="HTML"
                )

            # پاک کردن فایل
            try:
                os.remove(file_path)
            except:
                pass

            # پاک کردن پیام وضعیت
            try:
                bot.delete_message(
                    chat_id,
                    status.message_id
                )
            except:
                pass

        else:

            bot.edit_message_text(

                "❌ فایل آهنگ ساخته نشد.",

                chat_id,
                status.message_id
            )

    except Exception as e:

        error = str(e)

        bot.edit_message_text(

            "❌ <b>خطا در دریافت آهنگ</b>\n\n"
            f"<code>{error[:300]}</code>",

            chat_id,
            status.message_id,

            parse_mode="HTML"
        )


# =========================
# DOWNLOAD FOLDER
# =========================

if not os.path.exists("downloads"):
    os.makedirs("downloads")


# =========================
# START BOT
# =========================

print("🎵 Music Bot Started!")

bot.infinity_polling(
    skip_pending=True
)
