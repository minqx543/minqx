import logging
import asyncio
import os
import sqlite3
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import RetryAfter

# إعداد سجل الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# إعداد قاعدة البيانات
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

# دالة مساعدة للتعامل مع Flood Control
async def handle_flood_control(func, *args, **kwargs):
    while True:
        try:
            return await func(*args, **kwargs)
        except RetryAfter as e:
            wait_time = e.retry_after
            logger.warning(f"Flood control exceeded. Waiting for {wait_time} seconds")
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Error in handle_flood_control: {e}")
            raise

# دوال الأوامر المعدلة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('referrals.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM referrals WHERE user_id = ?', (user.id,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO referrals (user_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (user.id, user.username, user.first_name))
            conn.commit()
        
        if context.args and context.args[0].isdigit():
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                await handle_flood_control(
                    cursor.execute,
                    'UPDATE referrals SET referrals_count = referrals_count + 1 WHERE user_id = ?',
                    (referrer_id,)
                )
                conn.commit()
                logger.info(f"New referral from {user.id} to {referrer_id}")
        
        welcome_msg = f"مرحباً بك {user.first_name} في البوت! 🎉"
        await handle_flood_control(
            update.message.reply_text,
            welcome_msg
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
    finally:
        conn.close()

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('referrals.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT referrals_count FROM referrals WHERE user_id = ?', (user.id,))
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        referral_link = f"https://t.me/{context.bot.username}?start={user.id}"
        message = (
            f"رابط الإحالة الخاص بك:\n{referral_link}\n\n"
            f"عدد الإحالات حتى الآن: {count}"
        )
        await handle_flood_control(
            update.message.reply_text,
            message
        )
    except Exception as e:
        logger.error(f"Error in referral command: {e}")
    finally:
        conn.close()

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('referrals.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT first_name, username, referrals_count
            FROM referrals
            ORDER BY referrals_count DESC
            LIMIT 10
        ''')
        top_referrals = cursor.fetchall()
        
        message = "🏆 أفضل 10 محيلين:\n"
        for i, (name, username, count) in enumerate(top_referrals, 1):
            display_name = name or username or f"مستخدم {i}"
            message += f"{i}. {display_name} - {count} إحالة\n"
        
        if not top_referrals:
            message = "لا توجد بيانات عن الإحالات بعد."
        
        await handle_flood_control(
            update.message.reply_text,
            message
        )
    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}")
    finally:
        conn.close()

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "📎 روابط المنصات:\n"
        "🔗 منصة 1: https://example.com/1\n"
        "🔗 منصة 2: https://example.com/2\n"
        "\nيمكنك مشاركة هذه الروابط مع الأصدقاء!"
    )
    await handle_flood_control(
        update.message.reply_text,
        message
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("حدث خطأ أثناء معالجة الأمر:", exc_info=context.error)

# الدالة الرئيسية المعدلة
async def run_bot():
    # تهيئة قاعدة البيانات
    init_db()
    
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("لم يتم تعيين BOT_TOKEN في متغيرات البيئة")
    
    try:
        application = ApplicationBuilder().token(token).build()

        # إضافة معالجات الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("referral", referral))
        application.add_handler(CommandHandler("leaderboard", leaderboard))
        application.add_handler(CommandHandler("links", links))
        
        # إضافة معالج الأخطاء
        application.add_error_handler(error_handler)

        # تعيين أوامر القائمة مع التعامل مع Flood Control
        commands = [
            BotCommand("start", "بدء استخدام البوت"),
            BotCommand("referral", "الحصول على رابط الإحالة"),
            BotCommand("leaderboard", "أفضل 10 محيلين"),
            BotCommand("links", "روابط المنصات الرسمية")
        ]
        
        await handle_flood_control(
            application.bot.set_my_commands,
            commands
        )

        logger.info("بدأ البوت في الاستماع للتحديثات...")
        await application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"تعطل البوت: {e}")
        raise

if __name__ == '__main__':
    # نظام إعادة التشغيل التلقائي في حالة حدوث خطأ
    while True:
        try:
            asyncio.run(run_bot())
        except KeyboardInterrupt:
            logger.info("إيقاف البوت...")
            break
        except Exception as e:
            logger.error(f"تعطل البوت وسيتم إعادة التشغيل: {e}")
            asyncio.run(asyncio.sleep(5))  # انتظر 5 ثواني قبل إعادة المحاولة
