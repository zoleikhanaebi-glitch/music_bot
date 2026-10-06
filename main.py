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

users_list = set()
broadcast_state = {}
search_results = {}


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


def save_users():
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users_list), f)
    except:
        pass


users_list = load_users()


def add_user(user_id):
    if user_id not in users_list:
        users_list.add(user_id)
        save_users()


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

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^\w\sآ-ی]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================
# RESULT SCORE
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
    "karaoke",
    "instrumental",
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

    # شباهت کلی
    similarity = difflib.SequenceMatcher(
        None,
        q,
        t
    ).ratio()

    score += similarity * 50

    # کلمات مشترک
    q_words = set(q.split())
    t_words = set(t.split())

    if q_words:

        matched = len(q_words & t_words)

        score += (
            matched /
            len(q_words)
        ) * 80

    # تطابق کامل
    if q in t:
        score += 60

    # تطبیق با نام آپلودر
    for word in q_words:

        if len(word) >= 3 and word in u:
            score += 20

    # جریمه نسخه‌های غیر اصلی
    for word in BAD_WORDS:

        if word in t:
            score -= 40

    return score


def choose_best(query, entries):

    best = None
    best_score = -99999

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
            "📊 آمار",
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
            "❌ لغو",
            callback_data="broadcast_cancel"
        )
    )

    return markup


# =========================
# SEARCH RESULTS KEYBOARD
# =========================

def results_keyboard(user_id, entries):

    markup = InlineKeyboardMarkup(row_width=1)

    for index, entry in enumerate(entries[:8]):

        title = entry.get(
            "title",
            "آهنگ"
        )

        uploader = entry.get(
            "uploader",
            ""
        )

        text = f"🎵 {title}"

        if uploader:
            text += f" — {uploader}"

        callback = f"song:{user_id}:{index}"

        markup.add(
            InlineKeyboardButton(
                text[:60],
                callback_data=callback
            )
        )

    markup.add(
        InlineKeyboardButton(
            "❌ لغو",
            callback_data="song_cancel"
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
            "🎵 راهنما",
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
        "نام خواننده و آهنگ را بفرستید.\n\n"

        "مثال:\n"
        "🎧 شادمهر - تقدیر\n"
        "🎧 محسن یگانه - بهت قول میدم\n"
        "🎧 معین - کعبه\n\n"

        "ربات چند نتیجه را پیدا می‌کند و "
        "می‌توانید آهنگ دقیق را انتخاب کنید.",

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

        "اسم خواننده + اسم آهنگ را بفرست.\n\n"

        "مثال:\n"
        "🎧 شادمهر - تقدیر\n"
        "🎧 رضا بهرام - دیوانه\n\n"

        "بعد از جستجو چند نتیجه نمایش داده می‌شود "
        "و خودت آهنگ درست را انتخاب می‌کنی.",

        parse_mode="HTML"
    )


# =========================
# ADMIN PANEL
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
        "یک گزینه را انتخاب کنید:",

        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# =========================
# ADMIN CALLBACK
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

            f"👤 تعداد کاربران: "
            f"<b>{len(users_list)}</b>\n\n"

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

            "پیام موردنظر را ارسال کن.\n\n"

            "متن، عکس، ویدیو، صوت، فایل و "
            "انواع پیام تلگرام قابل ارسال است.",

            call.message.chat.id,
            call.message.message_id,

            parse_mode="HTML",

            reply_markup=cancel_keyboard()
        )

    elif call.data == "admin_back":

        bot.answer_callback_query(call.id)

        bot.edit_message_text(

            "⚙️ <b>پنل مدیریت</b>\n\n"
            "یک گزینه را انتخاب کنید:",

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
        "ارسال پیام لغو شد.",

        call.message.chat.id,
        call.message.message_id,

        parse_mode="HTML",

        reply_markup=admin_keyboard()
    )


# =========================
# SONG CANCEL
# =========================

@bot.callback_query_handler(
    func=lambda call:
    call.data == "song_cancel"
)
def song_cancel(call):

    bot.answer_callback_query(
        call.id,
        "لغو شد"
    )

    try:
        bot.delete_message(
            call.message.chat.id,
            call.message.message_id
        )
    except:
        pass


# =========================
# SONG SELECTION
# =========================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("song:")
)
def song_selected(call):

    parts = call.data.split(":")

    if len(parts) != 3:
        return

    owner_id = int(parts[1])
    index = int(parts[2])

    # فقط همان کاربری که سرچ کرده
    if call.from_user.id != owner_id:
        bot.answer_callback_query(
            call.id,
            "❌ این لیست برای شما نیست.",
            show_alert=True
        )
        return

    entries = search_results.get(
        owner_id,
        []
    )

    if index >= len(entries):
        bot.answer_callback_query(
            call.id,
            "❌ نتیجه منقضی شده.",
            show_alert=True
        )
        return

    selected = entries[index]

    bot.answer_callback_query(
        call.id,
        "انتخاب شد 🎵"
    )

    title = selected.get(
        "title",
        "آهنگ"
    )

    bot.edit_message_text(
        f"🎵 <b>{title}</b>\n\n"
        "⏬ در حال دانلود...",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML"
    )

    download_song(
        call.message.chat.id,
        call.message.message_id,
        selected
    )


# =========================
# DOWNLOAD
# =========================

def download_song(
    chat_id,
    status_message_id,
    selected
):

    os.makedirs(
        "downloads",
        exist_ok=True
    )

    video_url = selected.get(
        "webpage_url"
    ) or selected.get(
        "url"
    )

    if not video_url:

        bot.edit_message_text(
            "❌ لینک آهنگ پیدا نشد.",
            chat_id,
            status_message_id
        )

        return

    ydl_opts = {

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

        "nocheckcertificate": True,

        "ffmpeg_location":
        "/usr/bin",

        "retries": 3
    }

    try:

        with YoutubeDL(
            ydl_opts
        ) as ydl:

            info = ydl.extract_info(
                video_url,
                download=True
            )

        if (
            "entries" in info
            and info["entries"]
        ):
            info = info["entries"][0]

        file_id = info.get(
            "id",
            selected.get("id", "audio")
        )

        file_path = (
            f"downloads/{file_id}.mp3"
        )

        title = info.get(
            "title",
            selected.get(
                "title",
                "Music"
            )
        )

        uploader = info.get(
            "uploader",
            selected.get(
                "uploader",
                "Unknown Artist"
            )
        )

        if not os.path.exists(
            file_path
        ):

            bot.edit_message_text(
                "❌ فایل آهنگ ساخته نشد.",
                chat_id,
                status_message_id
            )

            return

        bot.edit_message_text(
            "⬆️ در حال ارسال آهنگ...",
            chat_id,
            status_message_id
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

        try:
            os.remove(file_path)
        except:
            pass

        try:
            bot.delete_message(
                chat_id,
                status_message_id
            )
        except:
            pass

    except Exception as e:

        error = str(e)

        bot.edit_message_text(

            "❌ <b>خطا در دریافت آهنگ</b>\n\n"
            f"<code>{error[:300]}</code>",

            chat_id,
            status_message_id,

            parse_mode="HTML"
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
            "⏳ در حال ارسال پیام..."
        )

        success = 0
        failed = 0

        for user_id in list(
            users_list
        ):

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

    # فقط متن
    if message.content_type != "text":
        return

    if message.text.startswith("/"):
        return

    query = message.text.strip()

    if not query:
        return

    status = bot.send_message(
        chat_id,
        "🔍 در حال جستجو در Audiomack..."
    )

    # =========================
    # LINK
    # =========================

    if query.startswith(
        ("http://", "https://")
    ):

        selected = {
            "webpage_url": query,
            "title": "Music",
            "uploader": ""
        }

        download_song(
            chat_id,
            status.message_id,
            selected
        )

        return

    # =========================
    # SEARCH AUDIOMACK
    # =========================

    try:

        search_opts = {

            "quiet": True,

            "skip_download": True,

            "extract_flat": True,

            "noplaylist": True
        }

        search_query = (
            f"amsearch10:{query}"
        )

        with YoutubeDL(
            search_opts
        ) as ydl:

            result = ydl.extract_info(
                search_query,
                download=False
            )

        entries = result.get(
            "entries",
            []
        )

        entries = [
            e for e in entries
            if e
        ]

        if not entries:

            bot.edit_message_text(
                "❌ آهنگ پیدا نشد.\n\n"
                "اسم خواننده و آهنگ را دقیق‌تر بنویس.",
                chat_id,
                status.message_id
            )

            return

        # مرتب‌سازی
        entries.sort(
            key=lambda e:
            score_result(query, e),
            reverse=True
        )

        # ذخیره نتایج برای کاربر
        search_results[
            chat_id
        ] = entries[:8]

        bot.edit_message_text(

            "🎵 <b>نتایج جستجو</b>\n\n"
            "آهنگ موردنظر را انتخاب کن:",

            chat_id,
            status.message_id,

            parse_mode="HTML",

            reply_markup=results_keyboard(
                chat_id,
                entries
            )
        )

    except Exception as e:

        error = str(e)

        bot.edit_message_text(

            "❌ <b>خطا در جستجو</b>\n\n"
            f"<code>{error[:300]}</code>",

            chat_id,
            status.message_id,

            parse_mode="HTML"
        )


# =========================
# DOWNLOAD FOLDER
# =========================

os.makedirs(
    "downloads",
    exist_ok=True
)


# =========================
# START
# =========================

print(
    "🎵 Music Bot Started..."
)

bot.infinity_polling(
    skip_pending=True
)
