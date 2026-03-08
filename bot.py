import logging
import sqlite3
import os
import io
from datetime import datetime
from telegram import *
from telegram.ext import *
from PIL import Image, ImageDraw, ImageFont

# ================= CONFIG (RAILWAY) =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
WAJIB_JOIN = os.getenv("WAJIB_JOIN")

FEE_PERCENT = 0.4
AUTO_CANCEL_SECONDS = 1800
# ====================================================

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

# ================= DIGITAL ID CARD =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await check_join(user.id, context.bot):
        await update.message.reply_text("⚠️ Anda wajib join channel terlebih dahulu.")
        return

    premium = "🌟 PREMIUM" if user.is_premium else "👤 REGULER"
    username = f"@{user.username}" if user.username else "Tidak tersedia"

    photos = await context.bot.get_user_profile_photos(user.id)

    if photos.total_count > 0:
        file = await context.bot.get_file(photos.photos[0][-1].file_id)
        bio = io.BytesIO()
        await file.download_to_memory(bio)
        bio.seek(0)
        profile = Image.open(bio).convert("RGBA")
    else:
        profile = Image.new("RGBA",(250,250),(150,150,150))

    profile = profile.resize((250,250))

    card = Image.new("RGBA",(900,500),(20,30,60))
    draw = ImageDraw.Draw(card)

    mask = Image.new("L",(250,250),0)
    ImageDraw.Draw(mask).ellipse((0,0,250,250),fill=255)
    card.paste(profile,(50,125),mask)

    font = ImageFont.load_default()

    draw.text((350,50),"KARTU PENDUDUK TELEGRAM",fill="white",font=font)
    draw.text((350,90),"🛍️ Jasa Titip Online",fill="gold",font=font)

    draw.text((350,160),f"👤 Nama      : {user.first_name}",fill="white",font=font)
    draw.text((350,200),f"🔎 Username  : {username}",fill="white",font=font)
    draw.text((350,240),f"🆔 ID        : {user.id}",fill="white",font=font)
    draw.text((350,280),f"⭐ Status    : {premium}",fill="white",font=font)

    output = io.BytesIO()
    card.save(output,"PNG")
    output.seek(0)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Titip Barang",callback_data="menu_titip")],
        [InlineKeyboardButton("📖 Cara Titip",callback_data="cara")],
        [InlineKeyboardButton("📞 Hubungi Admin",url="https://t.me/USERNAMEADMIN")]
    ])

    await update.message.reply_photo(
        photo=output,
        caption="🛍️ Jasa Titip Online\n🔒 Escrow Protection Active\nMarketplace Aman & Profesional.",
        reply_markup=keyboard
    )

# ================= MENU TITIP =================
async def menu_titip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["titip"] = {}

    await query.message.reply_text(
        "🛍️ <b>Menu Jasa Titip Online</b>\n\n"
        "📌 Format:\n<code>Nama Produk | Harga</code>\n\n"
        "📝 Contoh:\n<code>Baju Kemeja | 25000</code>\n\n"
        "📷 Setelah itu kirim foto produk.\n\n"
        "🔒 Transaksi menggunakan Rekening Bersama.\n"
        "❓ Tidak paham? Hubungi admin.",
        parse_mode="HTML"
    )

# ================= CARA =================
async def cara(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "📖 <b>Panduan Jasa Titip Online 🛍️</b>\n\n"
        "1️⃣ Klik Titip Barang\n"
        "2️⃣ Kirim Nama & Harga\n"
        "3️⃣ Kirim Foto\n"
        "4️⃣ Produk otomatis masuk channel\n\n"
        "🔒 Semua transaksi menggunakan Rekening Bersama (Rekber).\n"
        "🛡 Dana diamankan hingga transaksi selesai.",
        parse_mode="HTML"
    )

# ================= HANDLE TEXT =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "titip" not in context.user_data:
        return

    data = update.message.text.split("|")
    if len(data)!=2:
        await update.message.reply_text("Format salah.")
        return

    context.user_data["titip"]["name"]=data[0].strip()
    context.user_data["titip"]["price"]=int(data[1].strip())

    await update.message.reply_text("📷 Kirim foto produk.")

# ================= POST PRODUK =================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "titip" not in context.user_data:
        return

    user=update.effective_user
    data=context.user_data["titip"]
    photo=update.message.photo[-1].file_id

    cursor.execute("INSERT INTO products (seller_id,name,price,photo) VALUES (?,?,?,?)",
                   (user.id,data["name"],data["price"],photo))
    conn.commit()

    pid=cursor.lastrowid

    sent=await context.bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=photo,
        caption=f"🛍️ {data['name']}\n💰 Rp {data['price']}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Beli",callback_data=f"buy_{pid}")]
        ])
    )

    cursor.execute("UPDATE products SET message_id=? WHERE id=?",(sent.message_id,pid))
    conn.commit()

    await update.message.reply_text("✅ Produk berhasil dipost.")
    del context.user_data["titip"]

# ================= BELI =================
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()

    pid=int(query.data.split("_")[1])
    cursor.execute("SELECT seller_id,price,name,status FROM products WHERE id=?",(pid,))
    data=cursor.fetchone()

    if not data or data[3]!="AVAILABLE":
        await query.message.reply_text("❌ Produk tidak tersedia.")
        return

    seller_id,price,name,status=data
    fee=int(price*FEE_PERCENT/100)
    total=price+fee

    cursor.execute("INSERT INTO transactions (product_id,buyer_id,seller_id,total,status,created_at) VALUES (?,?,?,?,?,?)",
                   (pid,query.from_user.id,seller_id,total,"PENDING",datetime.now().isoformat()))
    conn.commit()

    trx_id=cursor.lastrowid

    cursor.execute("UPDATE products SET status='LOCKED' WHERE id=?",(pid,))
    conn.commit()

    await query.message.reply_photo(
        photo=open("qris_dana.jpg","rb"),
        caption=f"🧾 INVOICE - Jasa Titip Online 🛍️\n\n📦 {name}\n💰 Harga: Rp {price}\n🏦 Biaya Rekber: Rp {fee}\n━━━━━━━━━━\n💳 Total: Rp {total}\n\nBayar lalu kirim bukti."
    )

    context.user_data["trx"]=trx_id
    context.job_queue.run_once(auto_cancel,AUTO_CANCEL_SECONDS,data=trx_id)

# ================= AUTO CANCEL =================
async def auto_cancel(context: ContextTypes.DEFAULT_TYPE):
    trx_id=context.job.data
    cursor.execute("SELECT status,product_id FROM transactions WHERE id=?",(trx_id,))
    data=cursor.fetchone()

    if data and data[0]=="PENDING":
        cursor.execute("UPDATE transactions SET status='CANCELLED' WHERE id=?",(trx_id,))
        cursor.execute("UPDATE products SET status='AVAILABLE' WHERE id=?",(data[1],))
        conn.commit()

# ================= BUKTI =================
async def bukti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "trx" not in context.user_data:
        return

    trx_id=context.user_data["trx"]
    photo=update.message.photo[-1].file_id

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo,
        caption=f"🛍️ BUKTI PEMBAYARAN\nTRX{trx_id}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Konfirmasi",callback_data=f"confirm_{trx_id}")]
        ])
    )

# ================= KONFIRMASI =================
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()

    trx_id=int(query.data.split("_")[1])
    cursor.execute("UPDATE transactions SET status='PAID' WHERE id=?",(trx_id,))
    conn.commit()

    cursor.execute("SELECT buyer_id FROM transactions WHERE id=?",(trx_id,))
    buyer_id=cursor.fetchone()[0]

    await context.bot.send_message(
        buyer_id,
        "📦 Klik jika barang sudah diterima.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Barang Diterima",callback_data=f"received_{trx_id}")]
        ])
    )

# ================= RECEIVED =================
async def received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()

    trx_id=int(query.data.split("_")[1])
    cursor.execute("UPDATE transactions SET status='WAIT_RELEASE' WHERE id=?",(trx_id,))
    conn.commit()

    await context.bot.send_message(
        ADMIN_ID,
        f"💸 TRX{trx_id} siap dilepas.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Lepas Dana",callback_data=f"release_{trx_id}")]
        ])
    )

# ================= RELEASE =================
async def release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query
    await query.answer()

    trx_id=int(query.data.split("_")[1])
    cursor.execute("SELECT product_id,seller_id FROM transactions WHERE id=?",(trx_id,))
    pid,seller_id=cursor.fetchone()

    cursor.execute("SELECT message_id FROM products WHERE id=?",(pid,))
    message_id=cursor.fetchone()[0]

    await context.bot.delete_message(CHANNEL_ID,message_id)

    cursor.execute("UPDATE transactions SET status='COMPLETED' WHERE id=?",(trx_id,))
    cursor.execute("UPDATE products SET status='SOLD' WHERE id=?",(pid,))
    conn.commit()

    await context.bot.send_message(seller_id,"💰 Dana telah dilepas. Transaksi selesai.")

# ================= MAIN =================
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(menu_titip,pattern="menu_titip"))
    app.add_handler(CallbackQueryHandler(cara,pattern="cara"))
    app.add_handler(CallbackQueryHandler(buy,pattern="buy_"))
    app.add_handler(CallbackQueryHandler(confirm,pattern="confirm_"))
    app.add_handler(CallbackQueryHandler(received,pattern="received_"))
    app.add_handler(CallbackQueryHandler(release,pattern="release_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_text))
    app.add_handler(MessageHandler(filters.PHOTO,bukti))

    print("🚀 Jasa Titip Online Running on Railway...")
    app.run_polling()

if __name__=="__main__":
    main()
