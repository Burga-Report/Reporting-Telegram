import logging
import sqlite3
import os
from datetime import datetime
from telegram import *
from telegram.ext import *

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

ADMIN_FEE = 2000
AUTO_CANCEL_SECONDS = 1800
QRIS_IMAGE = "qris_dana.jpg"
# ==========================================

logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
conn = sqlite3.connect("ultimate_stable.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
    seller_username TEXT,
    name TEXT,
    price INTEGER,
    photo TEXT,
    message_id INTEGER,
    status TEXT DEFAULT 'AVAILABLE'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    buyer_id INTEGER,
    seller_id INTEGER,
    total INTEGER,
    method TEXT,
    status TEXT,
    created_at TEXT
)
""")

conn.commit()

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Titip Barang", callback_data="menu_titip")]
    ])

    await update.message.reply_text(
        "🛍️ *Jasa Titip Online*\n"
        "Ultimate Stable Escrow System 🔒",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ================= TITIP =================
async def menu_titip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    context.user_data["titip"] = {}

    await query.message.reply_text(
        "Format:\n`Nama Produk | Harga`\n\n"
        "Contoh:\n`Sepatu Nike | 150000`\n\n"
        "Setelah itu kirim foto produk 📷",
        parse_mode="Markdown"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "titip" not in context.user_data:
        return

    try:
        name, price = update.message.text.split("|")
        context.user_data["titip"]["name"] = name.strip()
        context.user_data["titip"]["price"] = int(price.strip())
    except:
        await update.message.reply_text("❌ Format salah.")
        return

    await update.message.reply_text("📷 Kirim foto produk.")

# ================= POST PRODUK =================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Jika kirim bukti pembayaran
    if "trx" in context.user_data:
        await bukti(update, context)
        return

    if "titip" not in context.user_data:
        return

    user = update.effective_user
    data = context.user_data["titip"]
    photo = update.message.photo[-1].file_id
    username = f"@{user.username}" if user.username else "Tidak ada"

    cursor.execute(
        "INSERT INTO products (seller_id,seller_username,name,price,photo) VALUES (?,?,?,?,?)",
        (user.id, username, data["name"], data["price"], photo)
    )
    conn.commit()

    pid = cursor.lastrowid

    sent = await context.bot.send_photo(
        CHANNEL_ID,
        photo=photo,
        caption=f"🛍️ {data['name']}\n"
                f"💰 Rp {data['price']}\n"
                f"👤 Seller: {username}\n"
                f"🔒 Rekber Optional",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Beli", callback_data=f"buy_{pid}")]
        ])
    )

    cursor.execute("UPDATE products SET message_id=? WHERE id=?", (sent.message_id, pid))
    conn.commit()

    await update.message.reply_text("✅ Produk berhasil dipost ke channel.")
    context.user_data.clear()

# ================= BELI =================
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = int(query.data.split("_")[1])

    cursor.execute("SELECT seller_id,price,status FROM products WHERE id=?", (pid,))
    data = cursor.fetchone()

    if not data or data[2] != "AVAILABLE":
        await query.message.reply_text("❌ Produk tidak tersedia.")
        return

    context.user_data["pid"] = pid

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔒 Via Rekber Admin (+2000)", callback_data="rekber")],
        [InlineKeyboardButton("🤝 Langsung ke Seller", callback_data="direct")]
    ])

    await query.message.reply_text("Pilih metode transaksi:", reply_markup=keyboard)

# ================= DIRECT =================
async def direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = context.user_data.get("pid")

    cursor.execute("SELECT seller_username FROM products WHERE id=?", (pid,))
    seller_username = cursor.fetchone()[0]

    await query.message.reply_text(
        f"🤝 Hubungi seller langsung:\n{seller_username}\n\n"
        "⚠️ Transaksi ini tanpa admin."
    )

# ================= REKBER =================
async def rekber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = context.user_data.get("pid")

    cursor.execute("SELECT seller_id,price,name FROM products WHERE id=?", (pid,))
    seller_id, price, name = cursor.fetchone()

    total = price + ADMIN_FEE

    cursor.execute(
        "INSERT INTO transactions (product_id,buyer_id,seller_id,total,method,status,created_at) VALUES (?,?,?,?,?,?,?)",
        (pid, query.from_user.id, seller_id, total,
         "REKBER", "PENDING", datetime.now().isoformat())
    )
    conn.commit()

    trx_id = cursor.lastrowid
    context.user_data.clear()
    context.user_data["trx"] = trx_id

    cursor.execute("UPDATE products SET status='LOCKED' WHERE id=?", (pid,))
    conn.commit()

    if os.path.exists(QRIS_IMAGE):
        await query.message.reply_photo(
            photo=open(QRIS_IMAGE,"rb"),
            caption=f"🧾 REKBER INVOICE\n\n"
                    f"📦 {name}\n"
                    f"💳 Total: Rp {total}\n\n"
                    f"Silakan bayar lalu kirim bukti."
        )
    else:
        await query.message.reply_text(f"Total bayar: Rp {total}")

    context.job_queue.run_once(auto_cancel, AUTO_CANCEL_SECONDS, data=trx_id)

# ================= BUKTI =================
async def bukti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "trx" not in context.user_data:
        return

    trx_id = context.user_data["trx"]
    photo = update.message.photo[-1].file_id

    await context.bot.send_photo(
        ADMIN_ID,
        photo=photo,
        caption=f"📥 Bukti Pembayaran TRX{trx_id}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Konfirmasi", callback_data=f"confirm_{trx_id}")]
        ])
    )

    await update.message.reply_text("✅ Bukti terkirim ke admin.")

# ================= KONFIRMASI =================
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    trx_id = int(query.data.split("_")[1])

    cursor.execute("UPDATE transactions SET status='PAID' WHERE id=?", (trx_id,))
    conn.commit()

    cursor.execute("SELECT buyer_id,seller_id FROM transactions WHERE id=?", (trx_id,))
    buyer_id, seller_id = cursor.fetchone()

    await context.bot.send_message(buyer_id,
        "📦 Barang sudah diterima?\nKlik tombol di bawah.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Barang Diterima", callback_data=f"received_{trx_id}")]
        ])
    )

    await context.bot.send_message(seller_id,
        "💰 Pembayaran sudah dikonfirmasi admin.")

# ================= RECEIVED =================
async def received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    trx_id = int(query.data.split("_")[1])

    cursor.execute("SELECT seller_id,product_id FROM transactions WHERE id=?", (trx_id,))
    seller_id, pid = cursor.fetchone()

    cursor.execute("UPDATE transactions SET status='COMPLETED' WHERE id=?", (trx_id,))
    cursor.execute("UPDATE products SET status='SOLD' WHERE id=?", (pid,))
    conn.commit()

    await context.bot.send_message(seller_id,
        "💸 Dana dilepas. Transaksi selesai.")

# ================= AUTO CANCEL =================
async def auto_cancel(context: ContextTypes.DEFAULT_TYPE):
    trx_id = context.job.data

    cursor.execute("SELECT status,product_id,buyer_id FROM transactions WHERE id=?", (trx_id,))
    data = cursor.fetchone()

    if data and data[0] == "PENDING":
        cursor.execute("UPDATE transactions SET status='CANCELLED' WHERE id=?", (trx_id,))
        cursor.execute("UPDATE products SET status='AVAILABLE' WHERE id=?", (data[1],))
        conn.commit()

        await context.bot.send_message(data[2], "❌ Transaksi dibatalkan (timeout).")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_titip, pattern="menu_titip"))
    app.add_handler(CallbackQueryHandler(buy, pattern="buy_"))
    app.add_handler(CallbackQueryHandler(rekber, pattern="rekber"))
    app.add_handler(CallbackQueryHandler(direct, pattern="direct"))
    app.add_handler(CallbackQueryHandler(confirm, pattern="confirm_"))
    app.add_handler(CallbackQueryHandler(received, pattern="received_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))

    print("🚀 Ultimate Stable Escrow Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
