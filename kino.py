import os
import sqlite3
import json
import time
import math
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from telegram.error import Forbidden, BadRequest, TelegramError

TOKEN = ""  
ADMIN_ID = 122354            

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bot_bazasi.db")

# --- 💾 MA'LUMOTLAR BAZASI AMALLARI ---

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            title TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_users_count():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_movies_count():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM movies")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def add_movie_to_db(movie_id, title, caption, uz, ru, hin, trailer, mp4s, mp3s, tags):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    m_id_str = str(movie_id)
    cursor.execute("""
        INSERT OR REPLACE INTO movies 
        (id, nomi, caption, uzb_file_id, rus_file_id, hind_file_id, trailer_file_id, mp4_files, mp3_files, actors, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (m_id_str, title, caption, uz, ru, hin, trailer, json.dumps(mp4s), json.dumps(mp3s), tags.lower(), str(time.time())))
    conn.commit()
    conn.close()

def delete_movie_from_db(movie_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE id = ?", (str(movie_id),))
    conn.commit()
    conn.close()

def get_movie(movie_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM movies WHERE id = ?", (str(movie_id),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        try:
            mp4_clips = json.loads(row[9]) if row[9] else []
        except Exception:
            mp4_clips = [row[9]] if row[9] else []
            
        try:
            mp3_clips = json.loads(row[8]) if row[8] else []
        except Exception:
            mp3_clips = [row[8]] if row[8] else []

        return {
            "id": row[0],
            "title": row[1],
            "caption": row[3],
            "uz_video": row[5],
            "ru_video": row[6],
            "hin_video": row[7],
            "trailer": row[4],
            "mp4_clips": mp4_clips,
            "mp3_clips": mp3_clips,
            "tags": row[2],
            "updated_at": row[11]
        }
    return None

def get_all_movies_ordered():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nomi FROM movies ORDER BY CAST(updated_at AS REAL) DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_movies_in_db(query):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    q = f"%{query.lower()}%"
    cursor.execute("""
        SELECT id, nomi FROM movies 
        WHERE LOWER(nomi) LIKE ? OR LOWER(actors) LIKE ? 
        ORDER BY CAST(updated_at AS REAL) DESC
    """, (q, q))
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_channel_to_db(channel_id, title):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO channels (channel_id, title) VALUES (?, ?)", (channel_id, title))
    conn.commit()
    conn.close()

def delete_channel_from_db(channel_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()

def get_channels_from_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, title FROM channels")
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- 🤖 STATE DEFINITIONS FOR CONVERSATION HANDLERS ---
(
    ADD_TITLE, ADD_ID, ADD_CAPTION, ADD_UZ_VIDEO, ADD_RU_VIDEO, 
    ADD_HIN_VIDEO, ADD_TRAILER, ADD_MP4_CLIPS, ADD_MP3_CLIPS, ADD_TAGS
) = range(10)

(EDIT_ID, EDIT_FIELD, EDIT_VALUE) = range(10, 13)

# --- 🔒 MAJBURIY AZOLIK TIZIMI ---

async def is_subscribed(user_id, bot):
    # Agar foydalanuvchi admin (siz) bo'lsa, uni tekshirib o'tirmaymiz
    if user_id == ADMIN_ID:
        return True

    channels = get_channels_from_db()
    if not channels:
        return True # Agar kanallar qo'shilmagan bo'lsa, hammani o'tkazadi

    for ch_id, title in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)[cite: 1]
            # Agar foydalanuvchi guruh/kanaldan chiqqan bo'lsa yoki haydalgan bo'lsa:
            if member.status in ["left", "kicked"]:[cite: 1]
            return False
        except TelegramError as e:
            # Agar bot kanalda admin bo'lmasa yoki kanal topilmasa xatolikni terminalga chiqaradi
            print(f"Xatolik yuz berdi ({ch_id} kanali tekshirilganda): {e}")
            # Xatolik bo'lsa, xavfsizlik yuzasidan foydalanuvchini o'tkazmay turganimiz ma'qul
            return False
    return True

async def show_subscription_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = get_channels_from_db()
    keyboard = []
    for ch_id, title in channels:
        link = f"https://t.me/{ch_id.replace('@', '')}" if ch_id.startswith('@') else f"https://t.me/c/{ch_id.replace('-100', '')}/1"
        keyboard.append([InlineKeyboardButton(text=f"📢 {title}", url=link)])
    
    keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = "🚨 *Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling!*"
    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if await is_subscribed(user_id, context.bot):
        await query.message.delete()
        await query.message.reply_text(
            "🎉 Rahmat! Obuna tasdiqlandi.\n"
            "Endi `/izla [kino yoki aktyor]` orqali qidirishingiz mumkin!"
        )
    else:
        await query.answer("❌ Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

# --- 🚀 START KOMANDASI ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)
    
    if not await is_subscribed(user_id, context.bot):
        await show_subscription_keyboard(update, context)
        return


    movies = get_all_movies_ordered()
    reply_markup = get_pagination_keyboard(movies, page=1)
    
    if reply_markup is None:
        await update.message.reply_text("👋 Botga xush kelibsiz! Hozircha bazada kinolar yo'q.")
        return

    await update.message.reply_text(
        "Quyidagi kinolarni birini tanlang yoki poiskdan aktyor yoki kinoyingizni ism yoki nomini yozing:",
        reply_markup=reply_markup
    )

# --- 🔍 IZLASH KOMANDASI ---
# Faqat "/izla [matn]" yuborilgandagina ishlaydi, argument bo'lmasa javob bermaydi.

async def search_movie_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context.bot):
        await show_subscription_keyboard(update, context)
        return

    text = update.message.text.strip()
    if text == "/izla" or not text.startswith("/izla "):
        return

    query = text.replace("/izla ", "", 1).strip()
    results = search_movies_in_db(query)
    
    if not results:
        await update.message.reply_text("😔 Kechirasiz, qidiruv bo'yicha hech qanday kino topilmadi.")
        return
    
    reply_markup = get_pagination_keyboard(results, page=1, search_query=query)
    await update.message.reply_text(
        f"🔍 *\"{query}\"* bo'yicha topilgan kinolar:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    if not await is_subscribed(user_id, context.bot):
        await show_subscription_keyboard(update, context)
        return


# --- 📄 PAGINATION (8 tadan sahifalash) ---
MOVIES_PER_PAGE = 8

def get_pagination_keyboard(movies, page=1, search_query=None):
    total_movies = len(movies)
    total_pages = math.ceil(total_movies / MOVIES_PER_PAGE)
    
    if total_pages == 0:
        return None
    
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    start_idx = (page - 1) * MOVIES_PER_PAGE
    end_idx = start_idx + MOVIES_PER_PAGE
    page_movies = movies[start_idx:end_idx]
    
    keyboard = []
    for m_id, nomi in page_movies:
        keyboard.append([InlineKeyboardButton(text=nomi, callback_data=f"show_{m_id}_{page}")])
    
    nav_row = []
    q_suffix = f"_{search_query}" if search_query else "_all"
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"page_{page-1}{q_suffix}"))
    
    nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"page_{page+1}{q_suffix}"))
        
    keyboard.append(nav_row)
    return InlineKeyboardMarkup(keyboard)

# --- 🎬 KINO KO'RSATISH VA MULTIPLE PLAYER INTERFEYSI ---

async def show_movie_media(query, movie_id, active_tab, current_page, context: ContextTypes.DEFAULT_TYPE = None):
    movie = get_movie(movie_id)
    if not movie:
        await query.answer("Kino topilmadi.")
        return
    
    media_file_id = None
    caption_prefix = ""

    # Auto rejim tanlovi
    if active_tab == "auto":
        if movie["uz_video"]: active_tab = "uz"
        elif movie["ru_video"]: active_tab = "ru"
        elif movie["hin_video"]: active_tab = "hin"
        elif movie["trailer"]: active_tab = "trailer"

    # Aktiv material va file_id ni aniqlash
    if active_tab == "uz":
        media_file_id = movie["uz_video"]
        caption_prefix = "🇺🇿 *O'zbek tili*"
    elif active_tab == "ru":
        media_file_id = movie["ru_video"]
        caption_prefix = "🇷🇺 *Rus tili*"
    elif active_tab == "hin":
        media_file_id = movie["hin_video"]
        caption_prefix = "🇮🇳 *Hind tili*"
    elif active_tab == "trailer":
        media_file_id = movie["trailer"]
        caption_prefix = "📹 *Trailer*"
    elif active_tab.startswith("mp4_"):
        try:
            clip_idx = int(active_tab.split("_")[1])
            media_file_id = movie["mp4_clips"][clip_idx]
            caption_prefix = f"🎬 *MP4 Klip #{clip_idx + 1}*"
        except Exception:
            media_file_id = None

    caption = f"{caption_prefix}\n\n🎬 *{movie['title']}*\n\n{movie['caption'] or ''}"
    
    keyboard = []
    
    # 1. Tillarning tugmalari qatori
    lang_row = []
    if movie["uz_video"]:
        btn_text = "🇺🇿 Uz ☑️" if active_tab == "uz" else "🇺🇿 Uz"
        lang_row.append(InlineKeyboardButton(btn_text, callback_data=f"play_{movie_id}_uz_{current_page}"))
    if movie["ru_video"]:
        btn_text = "🇷🇺 Ru ☑️" if active_tab == "ru" else "🇷🇺 Ru"
        lang_row.append(InlineKeyboardButton(btn_text, callback_data=f"play_{movie_id}_ru_{current_page}"))
    if movie["hin_video"]:
        btn_text = "🇮🇳 Hindi ☑️" if active_tab == "hin" else "🇮🇳 Hindi"
        lang_row.append(InlineKeyboardButton(btn_text, callback_data=f"play_{movie_id}_hin_{current_page}"))
    if lang_row:
        keyboard.append(lang_row)
        
    # 2. Trailer qatori
    action_row = []
    if movie["trailer"]:
        btn_text = "📹 Trailer ☑️" if active_tab == "trailer" else "📹 Trailer"
        action_row.append(InlineKeyboardButton(btn_text, callback_data=f"play_{movie_id}_trailer_{current_page}"))
    if action_row:
        keyboard.append(action_row)

    # 3. MP4 (Video) kliplar navigatsiyasi
    if movie["mp4_clips"]:
        mp4_nav = []
        current_clip_idx = int(active_tab.split("_")[1]) if active_tab.startswith("mp4_") else -1
        
        if current_clip_idx > 0:
            mp4_nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"play_{movie_id}_mp4_{current_clip_idx-1}_{current_page}"))
        
        if current_clip_idx != -1:
            mp4_nav.append(InlineKeyboardButton(f"🎬 {current_clip_idx+1}/{len(movie['mp4_clips'])}", callback_data="ignore"))
        else:
            mp4_nav.append(InlineKeyboardButton(f"🎬 MP4 Kliplar ({len(movie['mp4_clips'])} ta)", callback_data=f"play_{movie_id}_mp4_0_{current_page}"))
            
        if current_clip_idx != -1 and current_clip_idx < len(movie["mp4_clips"]) - 1:
            mp4_nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"play_{movie_id}_mp4_{current_clip_idx+1}_{current_page}"))
            
        keyboard.append(mp4_nav)

    # 4. MP3 Audio klip tugmasi
    if movie["mp3_clips"]:
        keyboard.append([InlineKeyboardButton("🎵 Barcha MP3 qo'shiqlarni olish", callback_data=f"send_all_mp3_{movie_id}_{current_page}")])
        
    keyboard.append([InlineKeyboardButton("⬅️ Bosh menyuga qaytish", callback_data=f"back_list_{current_page}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    chat_id = query.message.chat_id
    bot_client = context.bot if context else query.bot

    try:
        await query.message.delete()
    except Exception:
        pass

    if media_file_id:
        try:
            await bot_client.send_video(
                chat_id=chat_id, 
                video=media_file_id, 
                caption=caption, 
                reply_markup=reply_markup, 
                parse_mode="Markdown"
            )
        except Exception:
            await bot_client.send_message(
                chat_id=chat_id,
                text=f"{caption}\n\n⚠️ Videoni yuborib bo'lmadi.", 
                reply_markup=reply_markup, 
                parse_mode="Markdown"
            )
    else:
        await bot_client.send_message(
            chat_id=chat_id,
            text=caption, 
            reply_markup=reply_markup, 
            parse_mode="Markdown"
        )
async def show_clips_menu(query, movie_id, current_page):
    movie = get_movie(movie_id)
    keyboard = []
    
    # Mp4 kliplar tugmalari
    for i, file_id in enumerate(movie["mp4_clips"], 1):
        keyboard.append([InlineKeyboardButton(f"🎬 MP4 Klip #{i}", callback_data=f"send_media_{movie_id}_mp4_{i-1}_{current_page}")])
        
    # Mp3 kliplar tugmalari
    for i, file_id in enumerate(movie["mp3_clips"], 1):
        keyboard.append([InlineKeyboardButton(f"🎵 MP3 Klip #{i}", callback_data=f"send_media_{movie_id}_mp3_{i-1}_{current_page}")])
        
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"play_{movie_id}_auto_{current_page}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(f"🎶 *{movie['title']}* kinosining MP4 va MP3 materiallari:", reply_markup=reply_markup, parse_mode="Markdown")

# --- ➕ KINO QO'SHISH BOSQICHMA-BOSQICH (/add_movie) ---

async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text(
        "📝 *Kino qo'shish tizimi boshlandi!*\n\n"
        "Kino *NOMINI* yozing:\n"
        "💡 _Bekor qilish uchun istalgan vaqt /cancel deb yozing._",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data["new_movie"] = {}
    return ADD_TITLE

async def add_movie_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_movie"]["title"] = update.message.text
    await update.message.reply_text("🔢 Kino uchun *ID raqam* kiriting (masalan: `2026`):", parse_mode="Markdown")
    return ADD_ID

async def add_movie_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m_id = update.message.text.strip() # Bo'sh joylarni olib tashlaymiz
    
    # ID bo'sh emasligini tekshiramiz
    if not m_id:
        await update.message.reply_text("⚠️ ID bo'sh bo'lishi mumkin emas. Qaytadan kiriting:")
        return ADD_ID
        
    if get_movie(m_id):
        await update.message.reply_text("⚠️ Bu ID bilan allaqachon kino kiritilgan! Boshqa ID kiriting:")
        return ADD_ID
        
    context.user_data["new_movie"]["id"] = m_id
    await update.message.reply_text("📝 Kino uchun *TAVSIF (Caption)* kiriting:", parse_mode="Markdown")
    return ADD_CAPTION

async def add_movie_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_movie"]["caption"] = update.message.text
    skip_kb = ReplyKeyboardMarkup([["/skip"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("🇺🇿 *O'zbek tilidagi videoni* yuboring (yoki /skip deb yuboring):", parse_mode="Markdown", reply_markup=skip_kb)
    return ADD_UZ_VIDEO

async def add_movie_uz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/skip":
        context.user_data["new_movie"]["uz"] = None
    elif update.message.video:
        context.user_data["new_movie"]["uz"] = update.message.video.file_id
    else:
        await update.message.reply_text("❌ Iltimos, video yuboring yoki /skip ni bosing!")
        return ADD_UZ_VIDEO
        
    skip_kb = ReplyKeyboardMarkup([["/skip"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("🇷🇺 *Rus tilidagi videoni* yuboring (yoki /skip deb yuboring):", parse_mode="Markdown", reply_markup=skip_kb)
    return ADD_RU_VIDEO

async def add_movie_ru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/skip":
        context.user_data["new_movie"]["ru"] = None
    elif update.message.video:
        context.user_data["new_movie"]["ru"] = update.message.video.file_id
    else:
        await update.message.reply_text("❌ Iltimos, video yuboring yoki /skip ni bosing!")
        return ADD_RU_VIDEO
        
    skip_kb = ReplyKeyboardMarkup([["/skip"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("🇮🇳 *Hind tilidagi videoni* yuboring (yoki /skip deb yuboring):", parse_mode="Markdown", reply_markup=skip_kb)
    return ADD_HIN_VIDEO

async def add_movie_hin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/skip":
        context.user_data["new_movie"]["hin"] = None
    elif update.message.video:
        context.user_data["new_movie"]["hin"] = update.message.video.file_id
    else:
        await update.message.reply_text("❌ Iltimos, video yuboring yoki /skip ni bosing!")
        return ADD_HIN_VIDEO
        
    skip_kb = ReplyKeyboardMarkup([["/skip"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("📹 Kino *Trailer* videosini yuboring (yoki /skip deb yuboring):", parse_mode="Markdown", reply_markup=skip_kb)
    return ADD_TRAILER

async def add_movie_trailer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/skip":
        context.user_data["new_movie"]["trailer"] = None
    elif update.message.video:
        context.user_data["new_movie"]["trailer"] = update.message.video.file_id
    else:
        await update.message.reply_text("❌ Iltimos, video yuboring yoki /skip ni bosing!")
        return ADD_TRAILER
        
    context.user_data["new_movie"]["mp4s"] = []
    done_kb = ReplyKeyboardMarkup([["/done", "/skip"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("🎬 *MP4 kliplar* ketma-ketligini yuboring. Tugatgach */done* buyrug'ini bosing (yoki klip bo'lmasa */skip* yuboring):", parse_mode="Markdown", reply_markup=done_kb)
    return ADD_MP4_CLIPS

async def add_movie_mp4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "/skip":
        context.user_data["new_movie"]["mp4s"] = []
    elif text == "/done":
        pass
    elif update.message.video:
        context.user_data["new_movie"]["mp4s"].append(update.message.video.file_id)
        await update.message.reply_text(f"✅ MP4 klip saqlandi. (Jami: {len(context.user_data['new_movie']['mp4s'])} ta). Yana yuborishingiz mumkin yoki /done ni bosing.")
        return ADD_MP4_CLIPS
    else:
        await update.message.reply_text("❌ Iltimos, video yuboring, yoki tugatish uchun /done, o'tkazish uchun /skip yuboring!")
        return ADD_MP4_CLIPS

    context.user_data["new_movie"]["mp3s"] = []
    done_kb = ReplyKeyboardMarkup([["/done", "/skip"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("🎵 *MP3 audio kliplar* ketma-ketligini yuboring. Tugatgach */done* (yoki klip bo'lmasa */skip*) yuboring:", parse_mode="Markdown", reply_markup=done_kb)
    return ADD_MP3_CLIPS

async def add_movie_mp3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "/skip":
        context.user_data["new_movie"]["mp3s"] = []
    elif text == "/done":
        pass
    elif update.message.audio or update.message.voice:
        fid = update.message.audio.file_id if update.message.audio else update.message.voice.file_id
        context.user_data["new_movie"]["mp3s"].append(fid)
        await update.message.reply_text(f"✅ MP3 klip saqlandi. (Jami: {len(context.user_data['new_movie']['mp3s'])} ta). Yana yuborishingiz mumkin yoki /done ni bosing.")
        return ADD_MP3_CLIPS
    else:
        await update.message.reply_text("❌ Iltimos, audio yoki ovozli xabar yuboring!")
        return ADD_MP3_CLIPS

    await update.message.reply_text("🔍 Qidiruv uchun kalit so'zlarni (Aktyorlar va janrlar) kiriting (vergul bilan ajrating, masalan: `Riteish, komediya`):", reply_markup=ReplyKeyboardRemove())
    return ADD_TAGS

async def add_movie_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tags = update.message.text
    m = context.user_data["new_movie"]
    
    add_movie_to_db(
        m["id"], m["title"], m["caption"], 
        m["uz"], m["ru"], m["hin"], m["trailer"], 
        m["mp4s"], m["mp3s"], tags
    )
    
    await update.message.reply_text("🎉 *Kino muvaffaqiyatli qo'shildi va bazaga saqlandi!*", parse_mode="Markdown")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Amaliyot bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- 🔧 KINO TAHRIRLASH (/edit_movie) ---

async def edit_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("🔧 Tahrir qilmoqchi bo'lgan kinongizning *ID raqamini* yuboring:", parse_mode="Markdown")
    return EDIT_ID

async def edit_movie_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m_id = update.message.text.strip()
    movie = get_movie(m_id)
    if not movie:
        await update.message.reply_text("❌ Bunday ID ga ega kino topilmadi! Qaytadan kiriting:")
        return EDIT_ID
        
    context.user_data["edit_movie_id"] = m_id
    
    kb = [
        [KeyboardButton("Nomi"), KeyboardButton("Tavsif (Caption)")],
        [KeyboardButton("Uzb Video"), KeyboardButton("Rus Video")],
        [KeyboardButton("Hind Video"), KeyboardButton("Trailer")],
        [KeyboardButton("MP4 Kliplar (Qayta yuklash)"), KeyboardButton("MP3 Kliplar (Qayta yuklash)")],
        [KeyboardButton("Teglar (Aktyorlar/Janrlar)")],
        [KeyboardButton("❌ Bekor qilish")]
    ]
    reply_markup = ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Qaysi ma'lumotni tahrirlaymiz/yangilaymiz? Tanlang:", reply_markup=reply_markup)
    return EDIT_FIELD

async def edit_movie_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = update.message.text
    if field == "❌ Bekor qilish":
        await update.message.reply_text("Tahrirlash bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
        
    context.user_data["edit_field"] = field
    
    if field in ["Nomi", "Tavsif (Caption)", "Teglar (Aktyorlar/Janrlar)"]:
        await update.message.reply_text(f"📝 Yangi qiymatni (matn shaklida) yozing:", reply_markup=ReplyKeyboardRemove())
    elif field in ["Uzb Video", "Rus Video", "Hind Video", "Trailer"]:
        await update.message.reply_text(f"📹 Yangi videoni yuboring (O'chirish uchun /skip deb yozing):", reply_markup=ReplyKeyboardRemove())
    elif field in ["MP4 Kliplar (Qayta yuklash)", "MP3 Kliplar (Qayta yuklash)"]:
        context.user_data["edit_clips"] = []
        await update.message.reply_text(f"🎶 Yangi fayllarni ketma-ket yuboring. Tugatgach */done* deb yozing. Hamma klip o'chirilsin desangiz shunchaki */skip* yozing.", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("Noma'lum tanlov. Iltimos menyudan foydalaning.")
        return EDIT_FIELD
        
    return EDIT_VALUE

async def edit_movie_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m_id = context.user_data["edit_movie_id"]
    field = context.user_data["edit_field"]
    movie = get_movie(m_id)
    val = update.message.text
    
    if field == "Nomi":
        add_movie_to_db(m_id, val, movie["caption"], movie["uz_video"], movie["ru_video"], movie["hin_video"], movie["trailer"], movie["mp4_clips"], movie["mp3_clips"], movie["tags"])
    elif field == "Tavsif (Caption)":
        add_movie_to_db(m_id, movie["title"], val, movie["uz_video"], movie["ru_video"], movie["hin_video"], movie["trailer"], movie["mp4_clips"], movie["mp3_clips"], movie["tags"])
    elif field == "Teglar (Aktyorlar/Janrlar)":
        add_movie_to_db(m_id, movie["title"], movie["caption"], movie["uz_video"], movie["ru_video"], movie["hin_video"], movie["trailer"], movie["mp4_clips"], movie["mp3_clips"], val)
    
    elif field in ["Uzb Video", "Rus Video", "Hind Video", "Trailer"]:
        file_id = None
        if val != "/skip":
            if update.message.video:
                file_id = update.message.video.file_id
            else:
                await update.message.reply_text("❌ Iltimos, video yozuv yuboring (yoki o'chirish uchun /skip)!")
                return EDIT_VALUE
                
        if field == "Uzb Video":
            add_movie_to_db(m_id, movie["title"], movie["caption"], file_id, movie["ru_video"], movie["hin_video"], movie["trailer"], movie["mp4_clips"], movie["mp3_clips"], movie["tags"])
        elif field == "Rus Video":
            add_movie_to_db(m_id, movie["title"], movie["caption"], movie["uz_video"], file_id, movie["hin_video"], movie["trailer"], movie["mp4_clips"], movie["mp3_clips"], movie["tags"])
        elif field == "Hind Video":
            add_movie_to_db(m_id, movie["title"], movie["caption"], movie["uz_video"], movie["ru_video"], file_id, movie["trailer"], movie["mp4_clips"], movie["mp3_clips"], movie["tags"])
        elif field == "Trailer":
            add_movie_to_db(m_id, movie["title"], movie["caption"], movie["uz_video"], movie["ru_video"], movie["hin_video"], file_id, movie["mp4_clips"], movie["mp3_clips"], movie["tags"])

    elif field == "MP4 Kliplar (Qayta yuklash)":
        if val == "/skip":
            add_movie_to_db(m_id, movie["title"], movie["caption"], movie["uz_video"], movie["ru_video"], movie["hin_video"], movie["trailer"], [], movie["mp3_clips"], movie["tags"])
        elif val == "/done":
            add_movie_to_db(m_id, movie["title"], movie["caption"], movie["uz_video"], movie["ru_video"], movie["hin_video"], movie["trailer"], context.user_data["edit_clips"], movie["mp3_clips"], movie["tags"])
        elif update.message.video:
            context.user_data["edit_clips"].append(update.message.video.file_id)
            await update.message.reply_text(f"✅ Yangi MP4 klip qo'shildi ({len(context.user_data['edit_clips'])}). Davom eting yoki /done yuboring.")
            return EDIT_VALUE
        else:
            await update.message.reply_text("❌ Faqat video yuboring yoki /done bosing.")
            return EDIT_VALUE

    elif field == "MP3 Kliplar (Qayta yuklash)":
        if val == "/skip":
            add_movie_to_db(m_id, movie["title"], movie["caption"], movie["uz_video"], movie["ru_video"], movie["hin_video"], movie["trailer"], movie["mp4_clips"], [], movie["tags"])
        elif val == "/done":
            add_movie_to_db(m_id, movie["title"], movie["caption"], movie["uz_video"], movie["ru_video"], movie["hin_video"], movie["trailer"], movie["mp4_clips"], context.user_data["edit_clips"], movie["tags"])
        elif update.message.audio or update.message.voice:
            fid = update.message.audio.file_id if update.message.audio else update.message.voice.file_id
            context.user_data["edit_clips"].append(fid)
            await update.message.reply_text(f"✅ Yangi MP3 klip qo'shildi ({len(context.user_data['edit_clips'])}). Davom eting yoki /done yuboring.")
            return EDIT_VALUE
        else:
            await update.message.reply_text("❌ Faqat audio/voice yuboring yoki /done bosing.")
            return EDIT_VALUE

    # Har doim edit qilsak Video nomi 1-sahifa 1-qatorga o'tadi (chunki add_movie_to_db() funksiyasida updated_at ni hozirgi vaqtga o'zgartiradi)
    await update.message.reply_text("✨ *Kino tahrirlandi va u sahifada eng birinchi o'ringa ko'tarildi!*", parse_mode="Markdown")
    return ConversationHandler.END

# --- 🗑 KINONI O'CHIRISH (/del_movie) ---

async def delete_movie_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        m_id = context.args[0]
        movie = get_movie(m_id)
        if movie:
            delete_movie_from_db(m_id)
            await update.message.reply_text(f"🗑 *'{movie['title']}'* kinosi bazadan butunlay o'chirildi!", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Bunday ID ga ega kino topilmadi.")
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ To'g'ri foydalaning: `/del_movie [Kino_ID]`")

# --- 📊 STATISTIKA (/stat) ---

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_count = get_users_count()
    movies_count = get_movies_count()
    await update.message.reply_text(
        f"📊 *Bot statistikasi:*\n\n"
        f"👥 *Foydalanuvchilar soni:* `{users_count}` ta\n"
        f"🎬 *Bazadagi kinolar soni:* `{movies_count}` ta",
        parse_mode="Markdown"
    )

# --- 📢 REKLAMA TARQATISH (/reklama) ---

async def reklama_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reklama yuborish uchun biror xabarga reply (javob) qilib `/reklama` deb yozing!")
        return
        
    ref_msg = update.message.reply_to_message
    users = get_all_users()
    
    await update.message.reply_text(f"🚀 {len(users)} ta foydalanuvchiga reklama yuborish boshlandi...")
    
    success, failed = 0, 0
    for u_id in users:
        try:
            await context.bot.copy_message(chat_id=u_id, from_chat_id=ref_msg.chat_id, message_id=ref_msg.message_id)
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1
            
    await update.message.reply_text(f"🏁 *Reklama yakunlandi!*\n\n✅ Muvaffaqiyatli: `{success}` ta\n❌ Bloklaganlar: `{failed}` ta", parse_mode="Markdown")

# --- 📂 ID KINO RO'YXATI (/list_movie) ---

async def list_movies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    movies = get_all_movies_ordered()
    if not movies:
        await update.message.reply_text("Bazada hozircha kinolar mavjud emas.")
        return
        
    text = "📂 *Bazada mavjud kinolar ro'yxati (ID bo'yicha):*\n\n"
    for m_id, nomi in movies:
        text += f"🔑 *ID:* `{m_id}` | 🎬 {nomi}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# --- 📢 MAJBURIY AZOLIK KOMANDALARI ---

async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        channel_id = context.args[0]
        title = " ".join(context.args[1:])
        add_channel_to_db(channel_id, title)
        await update.message.reply_text(f"✅ Kanal majburiy obunaga qo'shildi: {title} ({channel_id})")
    except IndexError:
        await update.message.reply_text("⚠️ To'g'ri foydalaning: `/add_channel [Kanal_ID_Yoki_Username] [Kanal Nomi]`")

async def del_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        channel_id = context.args[0]
        delete_channel_from_db(channel_id)
        await update.message.reply_text(f"🗑 Kanal majburiy obunadan o'chirildi: {channel_id}")
    except IndexError:
        await update.message.reply_text("⚠️ To'g'ri foydalaning: `/del_channel [Kanal_ID_Yoki_Username]`")

async def show_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    channels = get_channels_from_db()
    if not channels:
        await update.message.reply_text("Hozircha majburiy a'zolik kanallari qo'shilmagan.")
        return
    text = "📢 *Majburiy a'zolik kanallari:*\n\n"
    for ch_id, title in channels:
        text += f"🔹 *{title}* — `{ch_id}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# --- 📖 HELP KOMANDASI (/help) ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Kino bot foydalanish qo'llanmasi:*\n\n"
        "🔍 *Foydalanuvchilar uchun:*\n"
        "👉 `/izla [kino yoki aktyor nomi]` — kinolarni qidirish (kattami-kichikmi harflar farqi yo'q)\n\n"
    )
    if update.effective_user.id == ADMIN_ID:
        text += (
            "🛠 *Admin komandalari:*\n"
            "➕ `/add_movie` — yangi kino qo'shish (bosqichma-bosqich)\n"
            "🔧 `/edit_movie` — mavjud kinoni tahrirlash (sahifada birinchi o'ringa ko'tariladi)\n"
            "🗑 `/del_movie [Kino_ID]` — kinoni bazadan o'chirish\n"
            "📂 `/list_movie` — bazadagi barcha kinolar ID va nomlarini ko'rish\n"
            "📊 `/stat` — foydalanuvchilar va kinolar statistikasi\n"
            "📢 `/reklama` — (reply xabar bilan) hammaga reklama yuborish\n"
            "➕ `/add_channel [@username] [Nomi]` — majburiy obuna kanali qo'shish\n"
            "🗑 `/del_channel [@username]` — majburiy obunadan o'chirish\n"
            "📋 `/show_channels` — majburiy kanallarni ko'rish\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")

# --- 🖱 TUGMA CALLBACK QUERY HANDLING ---

async def handle_callback_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if not await is_subscribed(user_id, context.bot):
        await show_subscription_keyboard(update, context)
        return

    data = query.data

    if data == "check_sub":
        await check_sub_callback(update, context)
        return

    # 1. Sahifani almashtirish (Pagination)
    if data.startswith("page_"):
        parts = data.split("_")
        try:
            page = int(parts[1])
        except ValueError:
            page = 1
            
        q_type = "_".join(parts[2:])
        
        if q_type == "all":
            movies = get_all_movies_ordered()
            reply_markup = get_pagination_keyboard(movies, page=page)
            msg_text = "Quyidagi kinolardan birini tanlang yoki poiskdan aktyor yoki kinoyingizning ism yoki nomini yozing:"
            try:
                await query.message.edit_text(text=msg_text, reply_markup=reply_markup)
            except Exception:
                await context.bot.send_message(chat_id=query.message.chat_id, text=msg_text, reply_markup=reply_markup)
        else:
            movies = search_movies_in_db(q_type)
            reply_markup = get_pagination_keyboard(movies, page=page, search_query=q_type)
            msg_text = f"🔍 \"{q_type}\" bo'yicha qidiruv natijalari (Sahifa: {page}):"
            try:
                await query.message.edit_text(text=msg_text, reply_markup=reply_markup)
            except Exception:
                await context.bot.send_message(chat_id=query.message.chat_id, text=msg_text, reply_markup=reply_markup)

    # 2. Kinoni birinchi marta ochish (Auto tanlov)
    elif data.startswith("show_"):
        parts = data.split("_")
        try:
            page = int(parts[-1])
            movie_id = "_".join(parts[1:-1])
        except ValueError:
            page = 1
            movie_id = "_".join(parts[1:])
            
        await show_movie_media(query, movie_id, "auto", page, context)

    # 3. Tanlangan til yoki MP4 klipni pleyer qilish
    elif data.startswith("play_"):
        parts = data.split("_")
        try:
            page = int(parts[-1])
            if len(parts) >= 5 and parts[-3] == "mp4":
                tab = f"mp4_{parts[-2]}"
                movie_id = "_".join(parts[1:-3])
            else:
                tab = parts[-2]
                movie_id = "_".join(parts[1:-2])
        except ValueError:
            page = 1
            tab = "uz"
            movie_id = "_".join(parts[1:])
            
        await show_movie_media(query, movie_id, tab, page, context)

    # 4. Barcha MP3 qo'shiqlarni ketma-ket yuklash va yuborish
    elif data.startswith("send_all_mp3_"):
        parts = data.split("_")
        try:
            page = int(parts[-1])
            movie_id = "_".join(parts[3:-1])
        except ValueError:
            page = 1
            movie_id = "_".join(parts[3:])
            
        movie = get_movie(movie_id)
        if movie and movie["mp3_clips"]:
            try:
                await query.message.delete()
            except Exception:
                pass
            
            for idx, file_id in enumerate(movie["mp3_clips"]):
                try:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=file_id,
                        caption=f"🎵 {movie['title']} — MP3 Qo'shiq #{idx+1}"
                    )
                except Exception:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=f"❌ MP3 #{idx+1} faylini yuborishda xatolik."
                    )
            
            await show_movie_media(query, movie_id, "auto", page, context)
        else:
            await query.answer("Kechirasiz, ushbu kino uchun MP3 fayllar topilmadi.")

    # 5. Bosh menyuga qaytish
    elif data.startswith("back_list_"):
        parts = data.split("_")
        try:
            page = int(parts[-1])
        except ValueError:
            page = 1
            
        movies = get_all_movies_ordered()
        reply_markup = get_pagination_keyboard(movies, page=page)
        try:
            await query.message.delete()
        except Exception:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Quyidagi kinolardan birini tanlang yoki poiskdan aktyor yoki kinoyingizning ism yoki nomini yozing:", 
            reply_markup=reply_markup
        )

# --- 🚀 ASOSIY RUNNER ---

def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # ➕ Kino qo'shish Conversation Handler
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add_movie", add_movie_start)],
        states={
            ADD_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_title)],
            ADD_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_id)], # ID matn bo'lishi uchun
            ADD_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_caption)],
            # Quyidagilardan & ~filters.COMMAND olib tashlandi, endi /skip va /done ishlaydi:
            ADD_UZ_VIDEO: [MessageHandler(filters.VIDEO | filters.TEXT, add_movie_uz)],
            ADD_RU_VIDEO: [MessageHandler(filters.VIDEO | filters.TEXT, add_movie_ru)],
            ADD_HIN_VIDEO: [MessageHandler(filters.VIDEO | filters.TEXT, add_movie_hin)],
            ADD_TRAILER: [MessageHandler(filters.VIDEO | filters.TEXT, add_movie_trailer)],
            ADD_MP4_CLIPS: [MessageHandler(filters.VIDEO | filters.TEXT, add_movie_mp4)],
            ADD_MP3_CLIPS: [MessageHandler(filters.AUDIO | filters.VOICE | filters.TEXT, add_movie_mp3)],
            ADD_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_tags)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^/cancel$"), cancel)],
    )

    # 🔧 Tahrirlash Conversation Handler
    edit_conv = ConversationHandler(
        entry_points=[CommandHandler("edit_movie", edit_movie_start)],
        states={
            EDIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_movie_id)],
            EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_movie_field)],
            # Bu yerda ham /skip va /done ishlashi uchun filters.ALL yetarli:
            EDIT_VALUE: [MessageHandler(filters.ALL, edit_movie_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^/cancel$"), cancel)],
    )
    
    # Qolgan handlerlar o'zgarishsiz qoladi...
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stat", stat_command))
    app.add_handler(CommandHandler("reklama", reklama_command))
    app.add_handler(CommandHandler("list_movie", list_movies_command))
    app.add_handler(CommandHandler("del_movie", delete_movie_command))
    
    app.add_handler(CommandHandler("add_channel", add_channel_command))
    app.add_handler(CommandHandler("del_channel", del_channel_command))
    app.add_handler(CommandHandler("show_channels", show_channels_command))
    
    app.add_handler(MessageHandler(filters.Regex("^/izla"), search_movie_command))
    app.add_handler(add_conv)
    app.add_handler(edit_conv)
    
    app.add_handler(CallbackQueryHandler(handle_callback_queries))
    
    print("🤖 Bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()