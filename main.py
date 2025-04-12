import os
import logging
import time
import threading
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler
)

# تكوين التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# روابط ثابتة
BOT_USERNAME = "MinQX_Bot"
WELCOME_IMAGE_URL = "https://github.com/minqx543/minqx/blob/main/src/default_avatar.jpg.png?raw=true"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"

class DatabaseManager:
    def __init__(self):
        self.conn = None
    
    def get_connection(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                host=os.getenv('DB_HOST'),
                database=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                port=os.getenv('DB_PORT', '5432')
            )
        return self.conn
    
    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()

db_manager = DatabaseManager()

def init_db():
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(100),
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    score INTEGER DEFAULT 0,
                    ref_code VARCHAR(50) UNIQUE,
                    ref_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("تم تهيئة جدول المستخدمين بنجاح")
    except Exception as e:
        logger.error(f"فشل في تهيئة قاعدة البيانات: {e}")
        raise

def create_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🎉 بدء التفاعل مع البوت", callback_data="main_menu"),
            InlineKeyboardButton("📢 مشاركة البوت", 
                               url=f"https://t.me/share/url?url={BOT_LINK}&text=انضم%20إلى%20@{BOT_USERNAME}%20للحصول%20على%20مزايا%20رائعة!")
        ],
        [
            InlineKeyboardButton("🤑 نقاطك في اللعبة", callback_data="show_score"),
            InlineKeyboardButton("📢 منصاتنا الاجتماعية", callback_data="social_media")
        ],
        [
            InlineKeyboardButton("🥇 أفضل 10 اللاعبين", callback_data="top_players"),
            InlineKeyboardButton("🔥 رابط الإحالات", callback_data="referral_link")
        ],
        [
            InlineKeyboardButton("🥇 أفضل 10 إحالات", callback_data="top_referrals"),
            InlineKeyboardButton("🚀 الانتقال إلى نظام المهام", url=f"https://t.me/{BOT_USERNAME}?start=tasks")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (user_id, username, first_name, last_name) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username",
                (user_id, user.username, user.first_name, user.last_name)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"خطأ في قاعدة البيانات: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء معالجة طلبك.")
        return

    welcome_message = f"🎊 مرحبًا بك {user.first_name} في @{BOT_USERNAME} 🎊"
    await update.message.reply_photo(
        photo=WELCOME_IMAGE_URL,
        caption=welcome_message,
        reply_markup=create_main_menu_keyboard()
    )

def keep_alive():
    while True:
        try:
            conn = db_manager.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            time.sleep(300)
        except Exception as e:
            logger.error(f"خطأ في اتصال قاعدة البيانات: {e}")
            time.sleep(60)

def main():
    required_env_vars = ['TELEGRAM_BOT_TOKEN', 'DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"المتغيرات البيئية المفقودة: {', '.join(missing_vars)}")
    
    init_db()
    
    try:
        application = ApplicationBuilder() \
            .token(os.getenv('TELEGRAM_BOT_TOKEN')) \
            .build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_main_menu))
        
        threading.Thread(target=keep_alive, daemon=True).start()
        application.run_polling()
        
    except Exception as e:
        logger.error(f"خطأ فادح في تشغيل البوت: {e}")
        raise

if __name__ == '__main__':
    main()
