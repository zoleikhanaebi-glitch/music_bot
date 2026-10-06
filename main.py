import os
import json
import re
import threading
import time

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

CHANNEL_USERNAME = "meov2ray"

USERS_FILE = "users.json"

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = telebot.TeleBot(TOKEN)

# کاربران
users_list = set()

# وضعیت پیام همگانی
broadcast_state = {}

# نتایج سرچ:
# user_id -> {
#     "created": timestamp,
#     "entries": [...]
# }
search_results = {}

# قفل برای جلوگیری از چند دانلود همزمان
download_locks = {}


# =========================================================
# FOLDERS
# =========================================================

os.makedirs("downloads", exist_ok=True)


# =========================================================
# USERS
# =========================================================

def load_users():
    if not os.path.exists(USERS_FILE):
        return set()

    try:
        with open(
            USERS_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        return set(data)

    except Exception:
        return set()


def save_users():
    try:
        with open(
            USERS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                list(users_list),
                f,
                ensure_ascii=False
            )

    except Exception:
        pass


users_list = load_users()


def add_user(user_id):

    if user_id not in users_list:

        users_list.add(user_id)

        save_users()


# =========================================================
# TEXT NORMALIZER
# =========================================================

def normalize(text):

    if not text:
        return ""

    text = str(text).lower()

    replacements = {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ة": "ه",
        "ۀ": "ه",
        "ؤ": "و",
        "إ": "ا",
        "أ": "ا",
        "ـ": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"[^\w\sآ-ی]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# SEARCH SCORING
# =========================================================

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
    "acoustic",
    "8d",
]


def score_result(query, entry):

    query = normalize(query)

    title = normalize(
        entry.get("title", "")
    )

    uploader = normalize(
        entry.get("uploader", "")
    )

    full = f"{uploader} {title}"

    if not title:
        return -1000

    score = 0

    # -----------------------------
    # Exact query
    # -----------------------------

    if query == title:
        score += 200

    if query in title:
        score += 120

    if query in full:
        score += 80

    # -----------------------------
    # Word matching
    # -----------------------------

    query_words = set(
        query.split()
    )

    title_words = set(
        title.split()
    )

    uploader_words = set(
        uploader.split()
    )

    for word in query_words:

        if word in title_words:
            score += 35

        if word in uploader_words:
            score += 45

    # -----------------------------
    # Bad versions
    # -----------------------------

    for bad in BAD_WORDS:

        if bad in title:
            score -= 35

    # -----------------------------
    # Prefer official/audio
    # -----------------------------

    preferred_words = [
        "official",
        "official audio",
        "original",
        "audio",
        "موزیک",
        "آهنگ"
    ]

    for word in preferred_words:

        if word in title:
            score += 5

    return score


# =========================================================
# ADMIN KEYBOARD
# =========================================================

def admin_keyboard():

    markup = InlineKeyboardMarkup(
        row_width=2
    )

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


def cancel_broadcast_keyboard():

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "❌ لغو",
            callback_data="broadcast_cancel"
        )
    )

    return markup


# =========================================================
# SEARCH RESULTS KEYBOARD
# =========================================================

def results_keyboard(
    user_id,
    entries
):

    markup = InlineKeyboardMarkup(
        row_width=1
    )

    for index, entry in enumerate(entries):

        title = entry.get(
            "title",
            "Unknown"
        )

        uploader = entry.get(
            "uploader",
            "Unknown Artist"
        )

        # متن دکمه
        button_text = (
            f"🎵 {uploader} - {title}"
        )

        # محدودیت callback data
        callback_data = (
            f"song:{user_id}:{index}"
        )

        markup.add(

            InlineKeyboardButton(
                button_text[:60],
                callback_data=callback_data
            )
        )

    markup.add(

        InlineKeyboardButton(
            "❌ لغو",
            callback_data="song_cancel"
        )
    )

    return markup


# =========================================================
# START
# =========================================================

@bot.message_handler(
    commands=["start"]
)
def start(message):

    chat_id = message.chat.id

    add_user(chat_id)

    markup = InlineKeyboardMarkup(
        row_width=1
    )

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

        "اسم خواننده و آهنگ را بفرستید.\n\n"

        "مثال:\n"
        "🎧 Shadmehr - Taghdir\n"
        "🎧 The Weeknd - Blinding Lights\n"
        "🎧 محسن یگانه - بهت قول میدم\n\n"

        "ربات چند نتیجه پیدا می‌کند "
        "و می‌توانید آهنگ دقیق را انتخاب کنید.",

        reply_markup=markup
    )


# =========================================================
# HELP
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data == "help"
)
def help_callback(call):

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(

        call.message.chat.id,

        "🎵 <b>راهنمای استفاده</b>\n\n"

        "اسم خواننده و آهنگ را بفرست.\n\n"

        "مثال فارسی:\n"
        "🎧 شادمهر - تقدیر\n\n"

        "مثال انگلیسی:\n"
        "🎧 The Weeknd - Blinding Lights\n\n"

        "ربات چند نتیجه از SoundCloud "
        "نشان می‌دهد و می‌توانی مورد درست را انتخاب کنی.",

        parse_mode="HTML"
    )


# =========================================================
# ADMIN PANEL
# =========================================================

@bot.message_handler(
    commands=["admin"]
)
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


# =========================================================
# ADMIN CALLBACK
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("admin_")
)
def admin_callback(call):

    if not ADMIN_ID:
        return

    if str(call.message.chat.id) != str(ADMIN_ID):
        return

    # -------------------------
    # STATS
    # -------------------------

    if call.data == "admin_stats":

        bot.answer_callback_query(
            call.id
        )

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

    # -------------------------
    # BROADCAST
    # -------------------------

    elif call.data == "admin_broadcast":

        bot.answer_callback_query(
            call.id
        )

        broadcast_state[
            call.message.chat.id
        ] = True

        bot.edit_message_text(

            "📢 <b>پیام همگانی</b>\n\n"

            "پیام موردنظر را ارسال کن.\n\n"

            "متن، عکس، ویدیو، فایل، صوت و "
            "انواع پیام تلگرام قابل ارسال است.",

            call.message.chat.id,

            call.message.message_id,

            parse_mode="HTML",

            reply_markup=
            cancel_broadcast_keyboard()
        )

    # -------------------------
    # BACK
    # -------------------------

    elif call.data == "admin_back":

        bot.answer_callback_query(
            call.id
        )

        bot.edit_message_text(

            "⚙️ <b>پنل مدیریت</b>\n\n"
            "یک گزینه را انتخاب کنید:",

            call.message.chat.id,

            call.message.message_id,

            parse_mode="HTML",

            reply_markup=admin_keyboard()
        )


# =========================================================
# CANCEL BROADCAST
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data == "broadcast_cancel"
)
def broadcast_cancel(call):

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


# =========================================================
# CANCEL SEARCH
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data == "song_cancel"
)
def song_cancel(call):

    bot.answer_callback_query(
        call.id,
        "لغو شد"
    )

    search_results.pop(
        call.from_user.id,
        None
    )

    try:

        bot.delete_message(
            call.message.chat.id,
            call.message.message_id
        )

    except Exception:
        pass


# =========================================================
# DOWNLOAD FUNCTION
# =========================================================

def download_song(
    chat_id,
    status_message_id,
    selected
):

    lock_key = chat_id

    if lock_key in download_locks:

        bot.edit_message_text(

            "⏳ یک آهنگ دیگر در حال دانلود است.\n"
            "لطفاً چند لحظه صبر کن.",

            chat_id,

            status_message_id
        )

        return

    download_locks[
        lock_key
    ] = True

    try:

        os.makedirs(
            "downloads",
            exist_ok=True
        )

        # ------------------------------------------
        # URL
        # ------------------------------------------

        url = (
            selected.get("webpage_url")
            or selected.get("original_url")
            or selected.get("url")
        )

        if not url:

            raise Exception(
                "SoundCloud URL not found"
            )

        # ------------------------------------------
        # Download options
        # ------------------------------------------

        ydl_opts = {

            "format":
                "bestaudio/best",

            "noplaylist":
                True,

            "outtmpl":
                "downloads/%(id)s.%(ext)s",

            "quiet":
                True,

            "no_warnings":
                True,

            "retries":
                3,

            "fragment_retries":
                3,

            "socket_timeout":
                30,

            "nocheckcertificate":
                True,

            "postprocessors": [

                {
                    "key":
                        "FFmpegExtractAudio",

                    "preferredcodec":
                        "mp3",

                    "preferredquality":
                        "192"
                }
            ],

            # Railway Dockerfile باید ffmpeg داشته باشد
            "ffmpeg_location":
                "/usr/bin"
        }

        # ------------------------------------------
        # Download
        # ------------------------------------------

        bot.edit_message_text(

            "⏬ <b>در حال دریافت آهنگ...</b>",

            chat_id,

            status_message_id,

            parse_mode="HTML"
        )

        with YoutubeDL(
            ydl_opts
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

        # ------------------------------------------
        # Information
        # ------------------------------------------

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

        file_id = info.get(
            "id",
            selected.get(
                "id",
                "audio"
            )
        )

        file_path = (
            f"downloads/{file_id}.mp3"
        )

        # ------------------------------------------
        # Check file
        # ------------------------------------------

        if not os.path.exists(
            file_path
        ):

            raise Exception(
                "MP3 file was not created"
            )

        # ------------------------------------------
        # Telegram
        # ------------------------------------------

        bot.edit_message_text(

            "⬆️ <b>در حال ارسال آهنگ...</b>",

            chat_id,

            status_message_id,

            parse_mode="HTML"
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

        # ------------------------------------------
        # Delete temporary file
        # ------------------------------------------

        try:

            os.remove(
                file_path
            )

        except Exception:
            pass

        # ------------------------------------------
        # Delete status
        # ------------------------------------------

        try:

            bot.delete_message(
                chat_id,
                status_message_id
            )

        except Exception:
            pass

    except Exception as e:

        error = str(e)

        print(
            "DOWNLOAD ERROR:",
            error
        )

        try:

            bot.edit_message_text(

                "❌ <b>خطا در دریافت آهنگ</b>\n\n"

                f"<code>{error[:700]}</code>",

                chat_id,

                status_message_id,

                parse_mode="HTML"
            )

        except Exception:
            pass

    finally:

        download_locks.pop(
            lock_key,
            None
        )


# =========================================================
# SONG SELECTION
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("song:")
)
def song_selected(call):

    try:

        parts = call.data.split(":")

        owner_id = int(
            parts[1]
        )

        index = int(
            parts[2]
        )

    except Exception:

        bot.answer_callback_query(

            call.id,

            "❌ اطلاعات نامعتبر است.",

            show_alert=True
        )

        return

    # ------------------------------------------
    # Security
    # ------------------------------------------

    if call.from_user.id != owner_id:

        bot.answer_callback_query(

            call.id,

            "❌ این لیست برای کاربر دیگری است.",

            show_alert=True
        )

        return

    # ------------------------------------------
    # Get results
    # ------------------------------------------

    data = search_results.get(
        owner_id
    )

    if not data:

        bot.answer_callback_query(

            call.id,

            "❌ نتایج منقضی شده‌اند. دوباره جستجو کن.",

            show_alert=True
        )

        return

    # ------------------------------------------
    # Expiration
    # ------------------------------------------

    if time.time() - data["created"] > 600:

        search_results.pop(
            owner_id,
            None
        )

        bot.answer_callback_query(

            call.id,

            "❌ نتایج منقضی شده‌اند.",

            show_alert=True
        )

        return

    entries = data["entries"]

    if index < 0 or index >= len(entries):

        bot.answer_callback_query(

            call.id,

            "❌ نتیجه پیدا نشد.",

            show_alert=True
        )

        return

    selected = entries[index]

    bot.answer_callback_query(
        call.id,
        "🎵 انتخاب شد"
    )

    title = selected.get(
        "title",
        "Music"
    )

    uploader = selected.get(
        "uploader",
        "Unknown Artist"
    )

    bot.edit_message_text(

        f"🎵 <b>{uploader} - {title}</b>\n\n"
        "⏬ در حال آماده‌سازی...",

        call.message.chat.id,

        call.message.message_id,

        parse_mode="HTML"
    )

    # دانلود جداگانه
    threading.Thread(

        target=download_song,

        args=(

            call.message.chat.id,

            call.message.message_id,

            selected
        ),

        daemon=True

    ).start()


# =========================================================
# SEARCH SOUNDCLOUD
# =========================================================

def search_soundcloud(
    query
):

    search_opts = {

        "quiet":
            True,

        "no_warnings":
            True,

        "skip_download":
            True,

        "extract_flat":
            True,

        "noplaylist":
            True
    }

    search_url = (
        f"scsearch10:{query}"
    )

    with YoutubeDL(
        search_opts
    ) as ydl:

        result = ydl.extract_info(
            search_url,
            download=False
        )

    entries = result.get(
        "entries",
        []
    )

    entries = [
        entry
        for entry in entries
        if entry
    ]

    return entries


# =========================================================
# ALL MESSAGES
# =========================================================

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

    # =====================================================
    # BROADCAST
    # =====================================================

    if (
        ADMIN_ID
        and str(chat_id) == str(ADMIN_ID)
        and broadcast_state.get(chat_id)
    ):

        broadcast_state[
            chat_id
        ] = False

        status = bot.send_message(

            chat_id,

            "⏳ در حال ارسال پیام همگانی..."
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

                    message_id=
                    message.message_id
                )

                success += 1

            except Exception:

                failed += 1

        bot.edit_message_text(

            "✅ <b>ارسال همگانی پایان یافت</b>\n\n"

            f"🟢 موفق: <b>{success}</b>\n"

            f"🔴 ناموفق: <b>{failed}</b>",

            chat_id,

            status.message_id,

            parse_mode="HTML",

            reply_markup=admin_keyboard()
        )

        return

    # =====================================================
    # REGISTER
    # =====================================================

    add_user(chat_id)

    # =====================================================
    # ONLY TEXT
    # =====================================================

    if message.content_type != "text":
        return

    query = message.text.strip()

    if not query:
        return

    if query.startswith("/"):
        return

    # =====================================================
    # STATUS
    # =====================================================

    status = bot.send_message(

        chat_id,

        "🔍 در حال جستجو در SoundCloud..."
    )

    # =====================================================
    # DIRECT SOUNDCLOUD URL
    # =====================================================

    if (
        "soundcloud.com/" in query
    ):

        selected = {

            "webpage_url":
                query,

            "title":
                "SoundCloud Track",

            "uploader":
                ""
        }

        threading.Thread(

            target=download_song,

            args=(

                chat_id,

                status.message_id,

                selected
            ),

            daemon=True

        ).start()

        return

    # =====================================================
    # SEARCH
    # =====================================================

    try:

        entries = search_soundcloud(
            query
        )

        if not entries:

            bot.edit_message_text(

                "❌ نتیجه‌ای پیدا نشد.\n\n"

                "مثلاً:\n"
                "شادمهر - تقدیر\n"
                "The Weeknd - Blinding Lights",

                chat_id,

                status.message_id
            )

            return

        # =================================================
        # SORT
        # =================================================

        entries.sort(

            key=lambda entry:
            score_result(
                query,
                entry
            ),

            reverse=True
        )

        # حداکثر 8 نتیجه
        entries = entries[:8]

        # =================================================
        # Save
        # =================================================

        search_results[
            chat_id
        ] = {

            "created":
                time.time(),

            "entries":
                entries
        }

        # =================================================
        # Keyboard
        # =================================================

        bot.edit_message_text(

            "🎵 <b>نتایج جستجو</b>\n\n"

            "آهنگ موردنظرت را انتخاب کن:",

            chat_id,

            status.message_id,

            parse_mode="HTML",

            reply_markup=
            results_keyboard(
                chat_id,
                entries
            )
        )

    except Exception as e:

        error = str(e)

        print(
            "SEARCH ERROR:",
            error
        )

        bot.edit_message_text(

            "❌ <b>خطا در جستجو</b>\n\n"

            f"<code>{error[:700]}</code>",

            chat_id,

            status.message_id,

            parse_mode="HTML"
        )


# =========================================================
# CLEAN OLD SEARCHES
# =========================================================

def cleanup_searches():

    while True:

        try:

            now = time.time()

            expired = []

            for user_id, data in list(
                search_results.items()
            ):

                if (
                    now - data["created"]
                    > 600
                ):

                    expired.append(
                        user_id
                    )

            for user_id in expired:

                search_results.pop(
                    user_id,
                    None
                )

        except Exception:
            pass

        time.sleep(300)


threading.Thread(
    target=cleanup_searches,
    daemon=True
).start()


# =========================================================
# START
# =========================================================

print(
    "🎵 Music Bot Started"
)

print(
    f"👤 Users: {len(users_list)}"
)

bot.infinity_polling(
    skip_pending=True
)
