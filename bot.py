import os
import re
import asyncio
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS").split(",")]
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
SUPPORT_LINK = os.getenv("SUPPORT_LINK")
REPORT_TEMPLATE = os.getenv("REPORT_TEMPLATE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_seen TEXT,
    approved INTEGER DEFAULT 0,
    total_reports INTEGER DEFAULT 0
)
""")
conn.commit()

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def add_user(user_id):
    if not get_user(user_id):
        cursor.execute(
            "INSERT INTO users (user_id, first_seen) VALUES (?, ?)",
            (user_id, datetime.now().strftime("%d %B %Y %H:%M:%S"))
        )
        conn.commit()

def approve_user(user_id):
    cursor.execute("UPDATE users SET approved=1 WHERE user_id=?", (user_id,))
    conn.commit()

def add_report(user_id):
    cursor.execute("UPDATE users SET total_reports=total_reports+1 WHERE user_id=?", (user_id,))
    conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)

    msg = await update.message.reply_text("⚡ Initializing secure system...")
    await asyncio.sleep(1)

    data = get_user(user.id)
    premium = "💎 Premium" if user.is_premium else "🆓 Standard"
    username = f"@{user.username}" if user.username else "Not Set"
    role = "👑 Owner" if user.id in ADMIN_IDS else "👤 Member"

    text = (
        f"🔐 Secure Access Panel\n\n"
        f"👤 {user.full_name}\n"
        f"🆔 {user.id}\n"
        f"🔗 {username}\n"
        f"{premium}\n"
        f"{role}\n"
        f"📅 First Use: {data[1]}\n"
        f"📊 Reports: {data[3]}\n\n"
        f"⚠️ Request access to create report."
    )

    if data[2] == 0:
        keyboard = [
            [InlineKeyboardButton("📨 Request Access", callback_data="request")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📝 Create Report", callback_data="report")]
        ]

    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    for admin in ADMIN_IDS:
        await context.bot.send_message(
            admin,
            f"Access Request\nUser: {user.full_name}\nID: {user.id}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}")]
            ])
        )

    await query.edit_message_text("⏳ Waiting admin approval.")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[1])
    approve_user(user_id)

    await context.bot.send_message(
        user_id,
        "✅ Access Approved!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Create Report", callback_data="report")]
        ])
    )

    await query.edit_message_text("Approved.")

async def report_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Send username like: @username")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = get_user(user.id)

    if not data or data[2] == 0:
        return

    target = update.message.text.strip()

    if not re.match(r"^@[A-Za-z0-9_]{5,32}$", target):
        await update.message.reply_text("Invalid format.")
        return

    final_report = REPORT_TEMPLATE.replace("{target}", target)
    add_report(user.id)

    for admin in ADMIN_IDS:
        await context.bot.send_message(admin, final_report)

    total = get_user(user.id)[3]

    await update.message.reply_text(
        f"✅ Report sent.\nTotal Reports: {total}"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(request_access, pattern="request"))
    app.add_handler(CallbackQueryHandler(approve, pattern="approve_"))
    app.add_handler(CallbackQueryHandler(report_button, pattern="report"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_report))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
