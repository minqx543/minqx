import logging
import asyncio
import os
import sqlite3
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import RetryAfter

# قراءة المتغيرات من Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
PLATFORM_LINKS = os.getenv("PLATFORM_LINKS", "لا توجد روابط حالياً.")

# إعداد سجل الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# قاعدة البيانات
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

# دالة الحماية من Flood Control
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

# /start
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
            cursor.execute('UPDATE referrals SET referrals_count = referrals_count + 1 WHERE user_id = ?',
                           (referrer_id,))
            conn.commit()

    conn.close()

    reply_text = f"""مرحباً {user.first_name}!

روابط منصاتي:
{PLATFORM_LINKS}
"""
    keyboard = [
        [InlineKeyboardButton("احصل على رابط إحالتك", callback_data="get_referral")],
    ]
    await handle_flood_control(
        update.message.reply_text,
        reply_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# أمر للحصول على رابط الإحالة
async def referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    link = f"https://t.me/{BOT_USERNAME}?start={user.id}"
    await handle_flood_control(
        update.message.reply_text,
        f"رابط الإحالة الخاص بك:\n{link}"
    )

# عرض أفضل 10 محيلين
async def top_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('referrals.db')
    cursor = conn.cursor()
    cursor.execute('SELECT first_name, referrals_count FROM referrals ORDER BY referrals_count DESC LIMIT 10')
    top_users = cursor.fetchall()
    conn.close()

    if not top_users:
        await update.message.reply_text("لا يوجد إحالات حتى الآن.")
        return

    msg = "**أفضل 10 محيلين:**\n\n"
    for i, (name, count) in enumerate(top_users, 1):
        msg += f"{i}. {name} - {count} إحالة\n"

    await handle_flood_control(update.message.reply_text, msg)

# الرد على ضغط زر الإحالة
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    link = f"https://t.me/{BOT_USERNAME}?start={user.id}"
    await handle_flood_control(
        query.message.reply_text,
        f"رابط الإحالة الخاص بك:\n{link}"
    )

# تشغيل البوت
if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral_link", referral_link))
    app.add_handler(CommandHandler("top_referrals", top_referrals))
    app.add_handler(CommandHandler("top", top_referrals))  # اختصار

    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is running...")
    app.run_polling()
