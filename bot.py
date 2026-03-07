import os
import re
import sqlite3
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

logging.basicConfig(level=logging.INFO)

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 7777471529  # GANTI DENGAN ID OWNER
CHANNEL_USERNAME = "jetrolet"  # tanpa @
SUPPORT_USERNAME = "burgaa"    # tanpa @

REPORT_EMAIL = "abuse@telegram.org"

COOLDOWN_MINUTES = 5

EMAIL_SUBJECT = "Impersonation and Fraudulent Activity Using the Name of Group-IB"
EMAIL_BODY = "{username}:Impersonation and Fraudulent Activity Using the Name of Group-IB"
EMAIL_BODY = "I am reporting a Telegram account that is impersonating Group-IB and using the company name for suspected scam activities.
This is "

# ================= DATABASE =================

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS approved_users (
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_state (
    user_id INTEGER PRIMARY KEY,
    state TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cooldown (
    user_id INTEGER PRIMARY KEY,
    last_report TEXT
)
""")

conn.commit()

# ================= DATABASE FUNCTIONS =================

def is_approved(user_id):
    cursor.execute("SELECT 1 FROM approved_users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def approve_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO approved_users VALUES (?)", (user_id,))
    conn.commit()

def set_state(user_id, state):
    cursor.execute("INSERT OR REPLACE INTO user_state VALUES (?,?)", (user_id, state))
    conn.commit()

def get_state(user_id):
    cursor.execute("SELECT state FROM user_state WHERE user_id=?", (user_id,))
    r = cursor.fetchone()
    return r[0] if r else None

def clear_state(user_id):
    cursor.execute("DELETE FROM user_state WHERE user_id=?", (user_id,))
    conn.commit()

def check_cooldown(user_id):
    cursor.execute("SELECT last_report FROM cooldown WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return True
    last_time = datetime.fromisoformat(row[0])
    if datetime.now() - last_time >= timedelta(minutes=COOLDOWN_MINUTES):
        return True
    return False

def update_cooldown(user_id):
    cursor.execute("INSERT OR REPLACE INTO cooldown VALUES (?,?)",
                   (user_id, datetime.now().isoformat()))
    conn.commit()

# ================= CHECK JOIN =================

async def check_join(user_id, context):
    try:
        member = await context.bot.get_chat_member(
            chat_id=f"@{CHANNEL_USERNAME}",
            user_id=user_id
        )
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await check_join(user.id, context):
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel Owner", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ Saya Sudah Join", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ Anda wajib join saluran owner terlebih dahulu.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await send_welcome(update, context)

# ================= WELCOME =================

async def send_welcome(update, context):
    user = update.effective_user
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    premium = "🌟 Premium" if user.is_premium else "👤 Non Premium"
    role = "👑 Owner" if user.id == OWNER_ID else "👤 Member"

    text = f"""
👋 Selamat Datang di Helpdesk Bot

━━━━━━━━━━━━━━
👤 Nama : {user.full_name}
🔗 Username : @{user.username if user.username else '-'}
🆔 ID : {user.id}
💎 Status : {premium}
🎖 Role : {role}
🕒 Waktu : {now}
━━━━━━━━━━━━━━

📌 Wajib minta akses terlebih dahulu sebelum membuat laporan.
"""

    keyboard = [
        [InlineKeyboardButton("🛂 Minta Akses", callback_data="request_access")]
    ]

    if is_approved(user.id) or user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🚨 Buat Laporan", callback_data="report_menu")])

    keyboard.append([
        InlineKeyboardButton("📢 Channel Owner", url=f"https://t.me/{CHANNEL_USERNAME}"),
        InlineKeyboardButton("🆘 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")
    ])

    photos = await context.bot.get_user_profile_photos(user.id)

    if photos.total_count > 0:
        await context.bot.send_photo(
            chat_id=user.id,
            photo=photos.photos[0][-1].file_id,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await context.bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ================= BUTTON =================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    await query.answer()

    if data == "check_join":
        if await check_join(user.id, context):
            await send_welcome(update, context)
        else:
            await query.message.reply_text("❌ Anda belum join.")

    elif data == "request_access":
        text = f"""
🔔 Permintaan Akses

👤 {user.full_name}
🔗 @{user.username}
🆔 {user.id}
"""
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Deny", callback_data=f"deny_{user.id}")
        ]]
        await context.bot.send_message(OWNER_ID, text, reply_markup=InlineKeyboardMarkup(keyboard))
        await query.message.reply_text("📨 Permintaan dikirim ke owner.")

    elif data.startswith("approve_"):
        uid = int(data.split("_")[1])
        approve_user(uid)
        await context.bot.send_message(uid, "✅ Akses disetujui! Klik /start lagi.")
        await query.message.edit_text("User berhasil di-approve.")

    elif data.startswith("deny_"):
        uid = int(data.split("_")[1])
        await context.bot.send_message(uid, "❌ Permintaan ditolak.")
        await query.message.edit_text("User ditolak.")

    elif data == "report_menu":
        if not is_approved(user.id) and user.id != OWNER_ID:
            await query.message.reply_text("⛔ Anda belum di-approve.")
            return

        if not check_cooldown(user.id):
            await query.message.reply_text("⏳ Tunggu 5 menit sebelum laporan berikutnya.")
            return

        set_state(user.id, "WAIT_USERNAME")
        await query.message.reply_text("✍️ Kirim username target.\nContoh: @username")

# ================= USERNAME =================

async def username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if get_state(user.id) != "WAIT_USERNAME":
        return

    text = update.message.text.strip()

    if not re.match(r"^@[A-Za-z0-9_]{5,32}$", text):
        await update.message.reply_text("⚠️ Format username tidak valid.")
        return

    clear_state(user.id)
    update_cooldown(user.id)

    email_data = {
        "subject": EMAIL_SUBJECT,
        "body": EMAIL_BODY.format(username=text)
    }

    mailto = f"mailto:{REPORT_EMAIL}?" + urlencode(email_data)

    keyboard = [[InlineKeyboardButton("📧 Buka Email & Kirim", url=mailto)]]

    await update.message.reply_text(
        "✅ Username diterima.\nKlik tombol dibawah untuk membuka email.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, username_handler))

    print("HELPDESK BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
