import os
import re
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

OWNER_ID = 7777471529  # ganti jika perlu
CHANNEL_USERNAME = "jetrolet"
SUPPORT_USERNAME = "burgaa"

# gunakan 1 email agar tidak dianggap spam
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

approved_users = set()

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
    joined = await check_join(user.id, context)

    if not joined:
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ Saya Sudah Join", callback_data="check_join")]
        ]

        await update.message.reply_text(
            "⚠️ Anda wajib join channel owner terlebih dahulu.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await send_welcome(update, context)

# ==============================
# WELCOME
# ==============================

async def send_welcome(update, context):
    user = update.effective_user
    premium = "Yes" if user.is_premium else "No"

    text = f"""
👋 Selamat datang di Bot Laporan

━━━━━━━━━━━━━━
👤 Nama : {user.full_name}
🔗 Username : @{user.username if user.username else '-'}
🆔 ID : {user.id}
⭐ Premium : {premium}
⚙️ Status : {"Owner" if user.id == OWNER_ID else "Member"}
━━━━━━━━━━━━━━

📌 Cara Pakai:
1️⃣ Minta akses
2️⃣ Tunggu approve
3️⃣ Kirim username target
4️⃣ Kirim laporan via email
"""

    # ambil foto profil
    photos = await context.bot.get_user_profile_photos(user.id)

    keyboard = [
        [InlineKeyboardButton("🛂 Minta Akses", callback_data="request_access")],
        [
            InlineKeyboardButton("📢 Channel Owner", url=f"https://t.me/{CHANNEL_USERNAME}"),
            InlineKeyboardButton("🆘 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")
        ]
    ]

    if user.id in approved_users or user.id == OWNER_ID:
        keyboard.insert(1, [InlineKeyboardButton("🚨 Buat Laporan", callback_data="report_menu")])

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

# ==============================
# BUTTON HANDLER
# ==============================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    await query.answer()

    if data == "check_join":
        joined = await check_join(user.id, context)
        if joined:
            await send_welcome(update, context)
        else:
            await query.message.reply_text("❌ Anda belum join channel.")

    elif data == "request_access":
        text = f"""
🔔 Permintaan Akses

👤 Nama : {user.full_name}
🔗 Username : @{user.username}
🆔 ID : {user.id}
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
        if user.id not in approved_users and user.id != OWNER_ID:
            await query.message.reply_text("⛔ Anda belum di-approve.")
            return

        await query.message.reply_text(
            "📨 Kirim username target\n\nContoh:\n@targetusername"
        )

    elif data.startswith("approve_"):
        uid = int(data.split("_")[1])
        approved_users.add(uid)

        await context.bot.send_message(
            uid,
            "✅ Akses disetujui!\nSekarang Anda bisa membuat laporan."
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

    if user.id not in approved_users and user.id != OWNER_ID:
        return

    text = update.message.text.strip()

    # regex username telegram valid
    if not re.match(r"^@[A-Za-z0-9_]{5,32}$", text):
        await update.message.reply_text(
            "⚠️ Format username tidak valid.\nContoh: @username"
        )
        return

    username = text[1:]

    # tidak pakai get_chat supaya tidak false error
    subject = quote(EMAIL_SUBJECT)
    body = quote(EMAIL_BODY.format(username="@" + username))

    mailto = f"mailto:{REPORT_EMAIL}?subject={subject}&body={body}"

    keyboard = [
        [InlineKeyboardButton("📧 Buka Email & Kirim", url=mailto)]
    ]

    await update.message.reply_text(
        "✅ Username valid.\nKlik tombol dibawah untuk membuka aplikasi email.",
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
