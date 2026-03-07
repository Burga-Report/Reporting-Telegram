import os
import re
import sqlite3
import logging
from urllib.parse import quote

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

# ==============================
# CONFIG
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 7777471529
CHANNEL_USERNAME = "jetrolet"
SUPPORT_USERNAME = "burgaa"

REPORT_EMAIL = "abuse@telegram.org"

EMAIL_SUBJECT = "Impersonation and Fraudulent Activity Using the Name of Group-IB"

EMAIL_BODY = """
Hello Telegram Support,
I would like to report a Telegram account that appears to be impersonating and misusing the name of Group-IB, a well-known cybersecurity company. The reported account is using the company’s name and identity in a misleading manner that strongly suggests an attempt to deceive Telegram users.

Target Username : {username}

This account appears to be engaging in suspicious and potentially fraudulent activity by presenting itself as affiliated with or representing Group-IB, which may mislead users into believing the account is legitimate. Such impersonation creates a serious risk of scams, financial fraud, and abuse of trust among Telegram users.
Impersonating a recognized cybersecurity company is a significant concern, as it can damage the reputation of the organization and may lead unsuspecting users to disclose personal information, send money, or interact with a fraudulent service under false pretenses.
For the safety of the Telegram community, this account should be carefully reviewed by the moderation team. If the violation is confirmed, appropriate action should be taken in accordance with Telegram policies. At minimum, it would be helpful if the account could be clearly marked with a warning label (such as a fake account / scam account indicator) on the profile or username, so that users are aware of the potential risk.
This report is submitted in good faith to help protect Telegram users from impersonation and possible fraud.
Thank you for reviewing this matter and for helping maintain the safety and integrity of the Telegram platform.
"""

# ==============================
# DATABASE
# ==============================

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

conn.commit()

# ==============================
# DATABASE FUNCTIONS
# ==============================

def is_approved(user_id):
    cursor.execute("SELECT 1 FROM approved_users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def approve_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO approved_users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def set_state(user_id, state):
    cursor.execute("INSERT OR REPLACE INTO user_state (user_id, state) VALUES (?,?)", (user_id, state))
    conn.commit()

def get_state(user_id):
    cursor.execute("SELECT state FROM user_state WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def clear_state(user_id):
    cursor.execute("DELETE FROM user_state WHERE user_id=?", (user_id,))
    conn.commit()

# ==============================
# CHECK JOIN
# ==============================

async def check_join(user_id, context):
    try:
        member = await context.bot.get_chat_member(
            chat_id=f"@{CHANNEL_USERNAME}",
            user_id=user_id
        )
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ==============================
# START
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await check_join(user.id, context):
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ Saya Sudah Join", callback_data="check_join")]
        ]

        await update.message.reply_text(
            "⚠️ Anda wajib join channel terlebih dahulu.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await send_welcome(update, context)

# ==============================
# WELCOME
# ==============================

async def send_welcome(update, context):
    user = update.effective_user

    text = f"""
👋 Selamat datang

👤 Nama : {user.full_name}
🔗 Username : @{user.username if user.username else '-'}
🆔 ID : {user.id}

📌 Cara Pakai:
1️⃣ Minta akses
2️⃣ Tunggu approve
3️⃣ Klik Buat Laporan
4️⃣ Kirim username target
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

    await context.bot.send_message(
        chat_id=user.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==============================
# BUTTON HANDLER
# ==============================

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

        await context.bot.send_message(
            OWNER_ID,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        await query.message.reply_text("📨 Permintaan dikirim ke owner.")

    elif data == "report_menu":
        if not is_approved(user.id) and user.id != OWNER_ID:
            await query.message.reply_text("⛔ Anda belum di-approve.")
            return

        set_state(user.id, "WAIT_USERNAME")

        await query.message.reply_text(
            "📨 Kirim username target.\nContoh:\n@username"
        )

    elif data.startswith("approve_"):
        uid = int(data.split("_")[1])
        approve_user(uid)

        await context.bot.send_message(
            uid,
            "✅ Akses disetujui. Sekarang Anda bisa membuat laporan."
        )

        await query.message.edit_text("User berhasil di-approve.")

    elif data.startswith("deny_"):
        uid = int(data.split("_")[1])

        await context.bot.send_message(
            uid,
            "❌ Permintaan akses ditolak."
        )

        await query.message.edit_text("User ditolak.")

# ==============================
# USERNAME HANDLER
# ==============================

async def username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = get_state(user.id)

    if state != "WAIT_USERNAME":
        return

    text = update.message.text.strip()

    if not re.match(r"^@[A-Za-z0-9_]{5,32}$", text):
        await update.message.reply_text("⚠️ Format username tidak valid.")
        return

    if user.username and text.lower() == f"@{user.username}".lower():
        await update.message.reply_text("❌ Tidak bisa melaporkan diri sendiri.")
        return

    clear_state(user.id)

    subject = quote(EMAIL_SUBJECT)
    body = quote(EMAIL_BODY.format(username=text))

    mailto = f"mailto:{REPORT_EMAIL}?subject={subject}&body={body}"

    keyboard = [[InlineKeyboardButton("📧 Buka Email & Kirim", url=mailto)]]

    await update.message.reply_text(
        "✅ Username diterima.\nKlik tombol dibawah untuk membuka aplikasi email.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==============================
# MAIN
# ==============================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, username_handler))

    print("BOT RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
