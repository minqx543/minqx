import logging
import asyncio
import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import RetryAfter

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "MissionxX_bot"  # بدون @
PLATFORM_LINKS = """
يوتيوب: https://www.youtube.com/@MissionX_offici
تويتر (X): https://x.com/MissionX_Offici?t=2a_ntYJ4pOs8FteAPyLnuQ&s=09
انستغرام: https://www.instagram.com/minqx2025/?utm_source=qr&r=nametag
تيليجرام: https://t.me/MissionX_offici
فيسبوك: https://www.facebook.com/share/1F45g9xY8M/
تيك توك: https://www.tiktok.com/@missionx_offici?_t=ZS-8vguTuRcP7y&_r=1
"""

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect('referrals.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            referrals_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

async def handle_flood_control(func, *args, **kwargs):
    while True:
        try:
            return await func(*args, **kwargs)
        except RetryAfter as e:
            logger.warning(f"Flood control exceeded. Waiting for {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('referrals.db')
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM referrals WHERE user_id = ?', (user.id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO referrals (user_id, username, first_name) VALUES (?, ?, ?)',
                       (user.id, user.username, user.first_name))
        conn.commit()

    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        if referrer_id != user.id:
            cursor.execute('SELECT * FROM referrals WHERE user_id = ?', (referrer_id,))
            if cursor.fetchone():
                cursor.execute('UPDATE referrals SET referrals_count = referrals_count + 1 WHERE user_id = ?',
                               (referrer_id,))
                conn.commit()
                logger.info(f"New referral from {user.id} to {referrer_id}")

    conn.close()

    keyboard = [[InlineKeyboardButton("روابط المنصات", url="https://t.me/" + BOT_USERNAME)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = f"مرحباً {user.first_name}!\n\nتابع منصاتنا:\n{PLATFORM_LINKS}\n\nاستخدم /referral_link للحصول على رابط الإحالة الخاص بك.\nواستخدم /top_referrals لرؤية أفضل المحيلين."
    await handle_flood_control(update.message.reply_text, message, reply_markup=reply_markup)

async def referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referral_url = f"http://t.me/{BOT_USERNAME}?start={user.id}"
    await update.message.reply_text(f"رابط الإحالة الخاص بك:\n{referral_url}")

async def top_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('referrals.db')
    cursor = conn.cursor()
    cursor.execute('SELECT first_name, referrals_count FROM referrals ORDER BY referrals_count DESC LIMIT 10')
    top_users = cursor.fetchall()
    conn.close()

    if not top_users:
        await update.message.reply_text("لا يوجد إحالات بعد.")
        return

    message = "أفضل 10 محيلين:\n\n"
    for i, (name, count) in enumerate(top_users, start=1):
        message += f"{i}. {name} — {count} إحالة\n"

    await update.message.reply_text(message)

async def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral_link", referral_link))
    app.add_handler(CommandHandler("top_referrals", top_referrals))
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
