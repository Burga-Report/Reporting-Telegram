import os
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
REPORT_EMAIL = os.getenv("REPORT_EMAIL")
REPORT_SUBJECT = os.getenv("REPORT_SUBJECT")
REPORT_TEMPLATE = os.getenv("REPORT_TEMPLATE")

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 Buat Laporan", callback_data="report")]
    ])

    await update.message.reply_text(
        "🤖 Bot Laporan Email Manual\n\n"
        "Klik tombol untuk membuat laporan.",
        reply_markup=keyboard
    )

# ================= BUTTON =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "report":
        context.user_data["waiting"] = True
        await query.message.reply_text("Kirim username target.\nContoh: @username")

# ================= HANDLE USERNAME =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting"):
        return

    text = update.message.text.strip()

    if not text.startswith("@"):
        await update.message.reply_text("Format salah. Gunakan @username")
        return

    username = text
    link = f"https://t.me/{username[1:]}"

    body = REPORT_TEMPLATE.replace("{username}", username).replace("{link}", link)

    mailto_link = f"mailto:{REPORT_EMAIL}?subject={urllib.parse.quote(REPORT_SUBJECT)}&body={body}"

    await update.message.reply_text(
    f"Klik link berikut untuk membuka email:\n\n{mailto_link}"
    )

    await update.message.reply_text(
        "Klik tombol di bawah untuk membuka aplikasi email.",
        reply_markup=keyboard
    )

    context.user_data.clear()

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
