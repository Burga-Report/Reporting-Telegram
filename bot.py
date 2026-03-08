import logging
import sqlite3
import os
import asyncio
from datetime import datetime
from telegram import *
from telegram.ext import *

# ================= FIX RAILWAY EVENT LOOP =================
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

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
    message_id INTEGER
