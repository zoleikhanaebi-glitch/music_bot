import os
import json
import re
import urllib.request
import tempfile
import threading

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from radiojavanapi import Client


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

CHANNEL_USERNAME = "meov2ray"

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = telebot.TeleBot(TOKEN)

# Radio Javan client
rj = Client()

USERS_FILE = "users.json"

users_list = set()

# وضعیت پیام همگانی
broadcast_state = {}

# نتایج سرچ هر کاربر
# user_id -> list of song objects
search_results = {}


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
            return set(json.load(f))

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
# TEXT HELPERS
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
# SEARCH RESULT HELPERS
# =========================================================

def get_value(obj, name, default=""):

    try:
        value = getattr(
            obj,
            name,
            default
        )

        if value is None:
            return default

        return value

    except Exception:
        return default


def song_title(song):

    return get_value(
        song,
        "name",
        "آهنگ"
    )


def song_artist(song):

    return get_value(
        song,
        "artist",
        "خواننده"
    )


def song_id(song):

    return get_value(
        song,
        "id",
        None
    )


# =========================================================
# SONG SCORE
# =========================================================

BAD_WORDS = [
    "remix",
    "ریمیکس",
    "cover",
    "کاور",
    "live",
    "لایو",
    "slowed",
    "sped",
    "nightcore",
    "karaoke",
    "instrumental"
]


def score_song(query, song):

    q = normalize(query)

    title = normalize(
        song_title(song)
    )

    artist = normalize(
        song_artist(song)
    )

    score = 0

    if not title:
        return -1000

    # عبارت کامل
    if q in title:
        score += 100

    if q in artist:
        score += 50

    # کلمات
    q_words = set(q.split())

    title_words = set(
        title.split()
    )

    artist_words = set(
        artist.split()
    )

    for word in q_words:

        if word in title_words:
            score += 30

        if word in artist_words:
            score += 25

    # نسخه‌های غیر اصلی
    for bad in BAD_WORDS:

        if bad in title:
            score -= 40

    return score


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():

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

    return markup


def admin_keyboard():

    markup = InlineKeyboardMarkup(
        row_width=2
    )

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
# SEARCH KEYBOARD
# =========================================================

def results_keyboard(
    user_id,
    songs
):

    markup = InlineKeyboardMarkup(
        row_width=1
    )

    for index, song in enumerate(songs):

        title = song_title(song)
        artist = song_artist(song)

        text = f"🎵 {artist} - {title}"

        # Telegram callback محدودیت طول دارد
        callback = (
            f"song:{user_id}:{index}"
        )

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


# =========================================================
# START
# =========================================================

@bot.message_handler(
    commands=["start"]
)
def start(message):

    chat_id = message.chat.id

    add_user(chat_id)

    bot.send_message(

        chat_id,

        "سلام 👋🎵\n\n"

        "به ربات موزیک رادیو جوان خوش آمدید.\n\n"

        "اسم خواننده و آهنگ را بفرستید.\n\n"

        "مثال:\n"
        "🎧 شادمهر - تقدیر\n"
        "🎧 محسن یگانه - بهت قول میدم\n"
        "🎧 معین - کعبه\n\n"

        "بعد از جستجو، چند نتیجه نمایش داده می‌شود "
        "و خودتان آهنگ دقیق را انتخاب می‌کنید.",

        reply_markup=main_keyboard()
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

        "🎵 <b>راهنمای ربات</b>\n\n"

        "نام خواننده و آهنگ را بفرستید.\n\n"

        "مثال:\n"
        "🎧 شادمهر - تقدیر\n"
        "🎧 معین - کعبه\n"
        "🎧 رضا بهرام - دیوانه\n\n"

        "ربات نتایج Radio Javan را پیدا می‌کند "
        "و شما نتیجه دقیق را انتخاب می‌کنید.",

        parse_mode="HTML"
    )


# =========================================================
# ADMIN
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
        "یکی از گزینه‌ها را انتخاب کنید:",

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

            "🟢 وضعیت ربات: فعال",

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

            "پیامت را همینجا ارسال کن.\n\n"

            "متن، عکس، ویدیو، فایل، صوت و "
            "پیام‌های تلگرام قابل ارسال است.",

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
            "یکی از گزینه‌ها را انتخاب کنید:",

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

    # فقط صاحب سرچ اجازه انتخاب دارد
    if call.from_user.id != owner_id:

        bot.answer_callback_query(

            call.id,

            "❌ این لیست برای کاربر دیگری است.",

            show_alert=True
        )

        return

    songs = search_results.get(
        owner_id,
        []
    )

    if index >= len(songs):

        bot.answer_callback_query(

            call.id,

            "❌ نتیجه منقضی شده.",

            show_alert=True
        )

        return

    song = songs[index]

    bot.answer_callback_query(
        call.id,
        "🎵 انتخاب شد"
    )

    title = song_title(song)
    artist = song_artist(song)

    bot.edit_message_text(

        f"🎵 <b>{artist} - {title}</b>\n\n"
        "⏬ در حال دریافت آهنگ از Radio Javan...",

        call.message.chat.id,

        call.message.message_id,

        parse_mode="HTML"
    )

    # دانلود در thread
    threading.Thread(
        target=download_song,
        args=(
            call.message.chat.id,
            call.message.message_id,
            song
        ),
        daemon=True
    ).start()


# =========================================================
# DOWNLOAD SONG
# =========================================================

def download_song(
    chat_id,
    status_message_id,
    song
):

    temp_path = None

    try:

        # -------------------------------------------------
        # گرفتن ID
        # -------------------------------------------------

        sid = song_id(song)

        if not sid:

            raise Exception(
                "Song ID not found"
            )

        # -------------------------------------------------
        # دریافت اطلاعات کامل آهنگ
        # -------------------------------------------------

        full_song = rj.get_song_by_id(
            sid
        )

        # -------------------------------------------------
        # HQ LINK
        # -------------------------------------------------

        hq_link = get_value(
            full_song,
            "hq_link",
            ""
        )

        if not hq_link:

            # بعضی نسخه‌ها ممکن است link داشته باشند
            hq_link = get_value(
                full_song,
                "link",
                ""
            )

        if not hq_link:

            raise Exception(
                "Radio Javan did not return an audio link"
            )

        title = song_title(
            full_song
        )

        artist = song_artist(
            full_song
        )

        # -------------------------------------------------
        # Download
        # -------------------------------------------------

        bot.edit_message_text(

            f"🎵 <b>{artist} - {title}</b>\n\n"
            "⬇️ در حال دانلود...",

            chat_id,

            status_message_id,

            parse_mode="HTML"
        )

        # فایل موقت m4a
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".m4a"
        )

        temp_path = temp_file.name

        temp_file.close()

        request = urllib.request.Request(

            hq_link,

            headers={
                "User-Agent":
                "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=60
        ) as response:

            with open(
                temp_path,
                "wb"
            ) as output:

                while True:

                    chunk = response.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    output.write(
                        chunk
                    )

        # -------------------------------------------------
        # Send directly as audio
        # -------------------------------------------------

        bot.edit_message_text(

            "⬆️ در حال ارسال آهنگ...",

            chat_id,

            status_message_id
        )

        caption = (

            f"🎵 <b>{title}</b>\n\n"

            f"👤 {artist}\n\n"

            f"🆔 @{CHANNEL_USERNAME}"
        )

        with open(
            temp_path,
            "rb"
        ) as audio:

            bot.send_audio(

                chat_id=chat_id,

                audio=audio,

                title=title,

                performer=artist,

                caption=caption,

                parse_mode="HTML"
            )

        # پاک کردن پیام وضعیت
        try:

            bot.delete_message(
                chat_id,
                status_message_id
            )

        except Exception:
            pass

    except Exception as e:

        error = str(e)

        try:

            bot.edit_message_text(

                "❌ <b>خطا در دریافت آهنگ</b>\n\n"

                f"<code>{error[:500]}</code>",

                chat_id,

                status_message_id,

                parse_mode="HTML"
            )

        except Exception:
            pass

    finally:

        if temp_path:

            try:
                os.remove(
                    temp_path
                )
            except Exception:
                pass


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

            "✅ <b>ارسال پایان یافت</b>\n\n"

            f"🟢 موفق: <b>{success}</b>\n"

            f"🔴 ناموفق: <b>{failed}</b>",

            chat_id,

            status.message_id,

            parse_mode="HTML",

            reply_markup=admin_keyboard()
        )

        return

    # =====================================================
    # REGISTER USER
    # =====================================================

    add_user(chat_id)

    # =====================================================
    # ONLY TEXT
    # =====================================================

    if message.content_type != "text":
        return

    if message.text.startswith("/"):
        return

    query = message.text.strip()

    if not query:
        return

    status = bot.send_message(

        chat_id,

        "🔍 در حال جستجو در Radio Javan..."
    )

    # =====================================================
    # DIRECT RADIO JAVAN LINK
    # =====================================================

    if (
        "radiojavan.com" in query
        or "play.radiojavan.com" in query
    ):

        try:

            song = rj.get_song_by_url(
                query
            )

            search_results[
                chat_id
            ] = [song]

            markup = results_keyboard(
                chat_id,
                [song]
            )

            bot.edit_message_text(

                "🎵 <b>آهنگ پیدا شد</b>\n\n"
                "برای دریافت، دکمه زیر را بزن:",

                chat_id,

                status.message_id,

                parse_mode="HTML",

                reply_markup=markup
            )

        except Exception as e:

            bot.edit_message_text(

                "❌ لینک Radio Javan معتبر نیست.\n\n"
                f"<code>{str(e)[:300]}</code>",

                chat_id,

                status.message_id,

                parse_mode="HTML"
            )

        return

    # =====================================================
    # RADIO JAVAN SEARCH
    # =====================================================

    try:

        result = rj.search(
            query
        )

        # songs_id طبق مستندات radiojavanapi
        song_ids = get_value(
            result,
            "songs_id",
            []
        )

        if not song_ids:

            bot.edit_message_text(

                "❌ آهنگی پیدا نشد.\n\n"
                "مثلاً این‌طور جستجو کن:\n"
                "شادمهر - تقدیر",

                chat_id,

                status.message_id
            )

            return

        songs = []

        # حداکثر 10 نتیجه
        for sid in song_ids[:10]:

            try:

                song = rj.get_song_by_id(
                    sid
                )

                songs.append(
                    song
                )

            except Exception:
                continue

        if not songs:

            bot.edit_message_text(

                "❌ اطلاعات آهنگ‌ها دریافت نشد.",

                chat_id,

                status.message_id
            )

            return

        # مرتب‌سازی بر اساس تطابق
        songs.sort(

            key=lambda song:
            score_song(
                query,
                song
            ),

            reverse=True
        )

        songs = songs[:8]

        # ذخیره نتایج
        search_results[
            chat_id
        ] = songs

        # ساخت متن
        text = (
            "🎵 <b>نتایج Radio Javan</b>\n\n"
            "آهنگ موردنظرت را انتخاب کن:"
        )

        bot.edit_message_text(

            text,

            chat_id,

            status.message_id,

            parse_mode="HTML",

            reply_markup=
            results_keyboard(
                chat_id,
                songs
            )
        )

    except Exception as e:

        bot.edit_message_text(

            "❌ <b>خطا در جستجوی Radio Javan</b>\n\n"

            f"<code>{str(e)[:500]}</code>",

            chat_id,

            status.message_id,

            parse_mode="HTML"
        )


# =========================================================
# START BOT
# =========================================================

print(
    "🎵 Radio Javan Music Bot Started..."
)

bot.infinity_polling(
    skip_pending=True
)
