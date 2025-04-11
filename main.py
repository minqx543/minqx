import os
import logging
import psycopg2
from typing import Dict, List
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    CallbackContext,
    ConversationHandler,
    filters
)

# تكوين التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# حالات المحادثة
TASK_NAME, TASK_DUE_DATE, TASK_DESCRIPTION = range(3)

# اتصال قاعدة البيانات
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', 5432)
    )

# تهيئة الجداول
def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(100),
                    score INTEGER DEFAULT 0,
                    ref_code VARCHAR(50),
                    ref_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    name VARCHAR(100),
                    due_date DATE,
                    description TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"فشل في تهيئة قاعدة البيانات: {e}")
    finally:
        if conn:
            conn.close()

# روابط ثابتة
BOT_USERNAME = "MinQX_Bot"
WELCOME_IMAGE_URL = "https://github.com/minqx543/minqx/blob/main/src/default_avatar.jpg.png?raw=true"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"

def start(update: Update, context: CallbackContext) -> None:
    """إرسال رسالة ترحيبية عند استخدام الأمر /start"""
    user = update.effective_user
    user_id = user.id
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # التحقق من وجود المستخدم أو إنشائه
            cur.execute(
                "INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING",
                (user_id, user.username or user.first_name)
            )
            
            # التحقق من وجود رابط إحالة
            if context.args:
                referrer_code = context.args[0]
                cur.execute(
                    "UPDATE users SET score = score + 10, ref_count = ref_count + 1 WHERE ref_code = %s AND user_id != %s RETURNING user_id",
                    (referrer_code, user_id)
                )
                if cur.fetchone():
                    update.message.reply_text("🎉 تمت إحالتك بنجاح! 🎉\nYou have been successfully referred!")
            
            conn.commit()
    except Exception as e:
        logger.error(f"خطأ في قاعدة البيانات: {e}")
    finally:
        if conn:
            conn.close()

    # رسالة الترحيب
    welcome_message = (
        f"🎊 مرحبًا بك {user.first_name} في @{BOT_USERNAME} 🎊\n"
        f"✨ Welcome {user.first_name} to @{BOT_USERNAME} ✨\n\n"
        "📌 الأوامر المتاحة / Available Commands:\n"
        "/start - 🎉 بدء/Start 🎉\n"
        "/score - 🤑 النقاط/Points 🤑\n"
        "/tasks - ✅️ المهام/Tasks ✅️\n"
        "/top - 🥇 المتصدرين/Top Players 🥇\n"
        "/referrals - 🔥 الإحالات/Referrals 🔥\n"
        "/topreferrals - 🥇 أفضل المحيلين/Top Referrals 🥇"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🚀 بدء الاستخدام", callback_data="get_started"),
            InlineKeyboardButton("📢 مشاركة البوت", url=f"https://t.me/share/url?url={BOT_LINK}&text=انضم%20إلى%20@{BOT_USERNAME}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_photo(
        photo=WELCOME_IMAGE_URL,
        caption=welcome_message,
        reply_markup=reply_markup
    )

# ... (بقية الدوال المعدلة لاستخدام قاعدة البيانات)

def main() -> None:
    """تشغيل البوت"""
    # تهيئة قاعدة البيانات
    init_db()
    
    # الحصول على توكن البوت
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("لم يتم تعيين TELEGRAM_BOT_TOKEN")
    
    # إنشاء Updater
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher

    # تسجيل المعالجات
    dispatcher.add_handler(CommandHandler("start", start))
    # ... (بقية المعالجات)

    # بدء البوت في وضع Polling
    updater.start_polling()
    logger.info("البوت يعمل في وضع Polling")
    
    # إبقاء الخدمة نشطة
    import threading
    def keep_alive():
        while True:
            try:
                conn = get_db_connection()
                conn.close()
            except:
                pass
            time.sleep(300)
    
    threading.Thread(target=keep_alive, daemon=True).start()
    
    updater.idle()

if __name__ == '__main__':
    main()
