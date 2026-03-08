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
WAJIB_JOIN = os.getenv("WAJIB_JOIN")

ADMIN_FEE = 2000
AUTO_CANCEL_SECONDS = 1800
QRIS_IMAGE = "qris_dana.jpg"
# ==========================================

logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
conn = sqlite3.connect("enterprise_escrow.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
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
    status TEXT,
    created_at TEXT
)
""")

conn.commit()

# ================= CHECK JOIN =================
async def check_join(user_id, bot):
    try:
        member = await bot.get_chat_member(WAJIB_JOIN, user_id)
        return member.status in ["member","administrator","creator"]
    except:
        return False

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await check_join(user.id, context.bot):
        await update.message.reply_text("⚠️ Wajib join channel terlebih dahulu.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Titip Barang", callback_data="menu_titip")],
        [InlineKeyboardButton("📖 Cara Transaksi", callback_data="cara")]
    ])

    await update.message.reply_text(
        f"🛍️ *Jasa Titip Online*\n\n"
        f"Halo {user.first_name} 👋\n"
        f"Sistem Rekening Bersama Aman 🔒\n\n"
        f"Pilih menu:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ================= MENU TITIP =================
async def menu_titip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    context.user_data["titip"] = {}

    await query.message.reply_text(
        "🛍️ *Format Titip*\n\n"
        "`Nama Produk | Harga`\n\n"
        "Contoh:\n"
        "`Sepatu Adidas | 200000`\n\n"
        "Lalu kirim foto produk 📷",
        parse_mode="Markdown"
    )

# ================= CARA =================
async def cara(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📖 *Alur Transaksi*\n\n"
        "1️⃣ Buyer bayar ke Rekber\n"
        "2️⃣ Admin konfirmasi\n"
        "3️⃣ Seller kirim barang\n"
        "4️⃣ Dana dilepas setelah diterima\n\n"
        "💰 Harga + Rp2.000 biaya admin.",
        parse_mode="Markdown"
    )

# ================= HANDLE TEXT =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "titip" not in context.user_data:
        return

    try:
        name, price = update.message.text.split("|")
        price = int(price.strip())
        context.user_data["titip"]["name"] = name.strip()
        context.user_data["titip"]["price"] = price
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

    cursor.execute(
        "INSERT INTO products (seller_id,name,price,photo) VALUES (?,?,?,?)",
        (user.id, data["name"], data["price"], photo)
    )
    conn.commit()

    pid = cursor.lastrowid

    sent = await context.bot.send_photo(
        CHANNEL_ID,
        photo=photo,
        caption=f"🛍️ {data['name']}\n💰 Rp {data['price']}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Beli", callback_data=f"buy_{pid}")]
        ])
    )

    cursor.execute("UPDATE products SET message_id=? WHERE id=?", (sent.message_id, pid))
    conn.commit()

    await update.message.reply_text("✅ Produk berhasil dipost.")
    context.user_data.clear()

# ================= BELI =================
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = int(query.data.split("_")[1])
    cursor.execute("SELECT seller_id,price,name,status FROM products WHERE id=?", (pid,))
    data = cursor.fetchone()

    if not data or data[3] != "AVAILABLE":
        await query.message.reply_text("❌ Produk tidak tersedia.")
        return

    seller_id, price, name, _ = data
    total = price + ADMIN_FEE

    cursor.execute(
        "INSERT INTO transactions (product_id,buyer_id,seller_id,total,status,created_at) VALUES (?,?,?,?,?,?)",
        (pid, query.from_user.id, seller_id, total, "PENDING", datetime.now().isoformat())
    )
    conn.commit()

    trx_id = cursor.lastrowid
    cursor.execute("UPDATE products SET status='LOCKED' WHERE id=?", (pid,))
    conn.commit()

    context.user_data.clear()
    context.user_data["trx"] = trx_id

    # Kirim QRIS jika ada
    if os.path.exists(QRIS_IMAGE):
        await query.message.reply_photo(
            photo=open(QRIS_IMAGE,"rb"),
            caption=f"🧾 INVOICE\n\n"
                    f"📦 {name}\n"
                    f"💰 Rp {price}\n"
                    f"🏦 Admin Rp {ADMIN_FEE}\n"
                    f"━━━━━━━━━━\n"
                    f"💳 Total Rp {total}\n\n"
                    f"Kirim bukti pembayaran.",
        )
    else:
        await query.message.reply_text(
            f"🧾 Total Bayar: Rp {total}\nKirim bukti pembayaran."
        )

    context.job_queue.run_once(auto_cancel, AUTO_CANCEL_SECONDS, data=trx_id)

# ================= AUTO CANCEL =================
async def auto_cancel(context: ContextTypes.DEFAULT_TYPE):
    trx_id = context.job.data
    cursor.execute("SELECT status,product_id,buyer_id,seller_id FROM transactions WHERE id=?", (trx_id,))
    data = cursor.fetchone()

    if data and data[0] == "PENDING":
        cursor.execute("UPDATE transactions SET status='CANCELLED' WHERE id=?", (trx_id,))
        cursor.execute("UPDATE products SET status='AVAILABLE' WHERE id=?", (data[1],))
        conn.commit()

        await context.bot.send_message(data[2], "❌ Transaksi dibatalkan (timeout).")
        await context.bot.send_message(data[3], "🔓 Produk kembali tersedia.")

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

    await context.bot.send_message(buyer_id, "📦 Klik jika barang sudah diterima.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Barang Diterima", callback_data=f"received_{trx_id}")]
        ])
    )

    await context.bot.send_message(seller_id, "💰 Pembayaran telah dikonfirmasi admin.")

# ================= RECEIVED =================
async def received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    trx_id = int(query.data.split("_")[1])
    cursor.execute("UPDATE transactions SET status='COMPLETED' WHERE id=?", (trx_id,))
    conn.commit()

    cursor.execute("SELECT product_id,seller_id FROM transactions WHERE id=?", (trx_id,))
    pid, seller_id = cursor.fetchone()

    cursor.execute("UPDATE products SET status='SOLD' WHERE id=?", (pid,))
    conn.commit()

    await context.bot.send_message(seller_id, "💸 Dana dilepas. Transaksi selesai.")

# ================= STATS =================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM transactions WHERE status='COMPLETED'")
    success = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM transactions")
    total = cursor.fetchone()[0]

    await update.message.reply_text(
        f"📊 Statistik\n\n"
        f"Total Transaksi: {total}\n"
        f"Sukses: {success}"
    )

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(menu_titip, pattern="menu_titip"))
    app.add_handler(CallbackQueryHandler(cara, pattern="cara"))
    app.add_handler(CallbackQueryHandler(buy, pattern="buy_"))
    app.add_handler(CallbackQueryHandler(confirm, pattern="confirm_"))
    app.add_handler(CallbackQueryHandler(received, pattern="received_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))

    print("🚀 Jasa Titip Online PRO Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
