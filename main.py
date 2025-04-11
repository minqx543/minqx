import os
import logging
import time
import threading
import psycopg2
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
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
            cur.execute("DROP TABLE IF EXISTS tasks CASCADE")
            cur.execute("DROP TABLE IF EXISTS users CASCADE")
            
            cur.execute("""
                CREATE TABLE users (
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
            
            cur.execute("""
                CREATE TABLE tasks (
                    task_id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    due_date DATE,
                    description TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("تم تهيئة جداول قاعدة البيانات بنجاح")
    except Exception as e:
        logger.error(f"فشل في تهيئة قاعدة البيانات: {e}")
        raise

# روابط ثابتة
BOT_USERNAME = "MinQX_Bot"
WELCOME_IMAGE_URL = "https://raw.githubusercontent.com/minqx543/minqx/main/src/default_avatar.jpg.png"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"

def generate_ref_code(user_id: int) -> str:
    return f"REF{user_id % 10000:04d}"

async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (user_id, username, first_name, last_name, ref_code) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username",
                (user_id, username, user.first_name, user.last_name, generate_ref_code(user_id))
            
            if context.args:
                referrer_code = context.args[0]
                if referrer_code != generate_ref_code(user_id):
                    cur.execute(
                        "UPDATE users SET score = score + 10, ref_count = ref_count + 1 "
                        "WHERE ref_code = %s AND user_id != %s RETURNING user_id",
                        (referrer_code, user_id))
                    if cur.fetchone():
                        await update.message.reply_text("🎉 تمت إحالتك بنجاح! حصلت على 10 نقاط إضافية!")
            
            conn.commit()
    except Exception as e:
        logger.error(f"خطأ في قاعدة البيانات: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقاً.")
        return

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
            InlineKeyboardButton("📢 مشاركة البوت", 
                               url=f"https://t.me/share/url?url={BOT_LINK}&text=انضم%20إلى%20@{BOT_USERNAME}%20للحصول%20على%20مزايا%20رائعة!")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_photo(
            photo=WELCOME_IMAGE_URL,
            caption=welcome_message,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال الصورة الترحيبية: {e}")
        try:
            # حل بديل إذا فشل إرسال الصورة
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)
            
            # يمكنك إضافة محاولة ثانية باستخدام requests إذا لزم الأمر
            import requests
            from io import BytesIO
            response = requests.get(WELCOME_IMAGE_URL)
            if response.status_code == 200:
                photo_file = BytesIO(response.content)
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=welcome_message,
                    reply_markup=reply_markup
                )
        except Exception as backup_error:
            logger.error(f"خطأ في الحل البديل: {backup_error}")
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

# ... (بقية الدوال تبقى كما هي بدون تغيير)

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

async def post_init(application):
    threading.Thread(target=keep_alive, daemon=True).start()

def main():
    # التحقق من المتغيرات البيئية
    required_env_vars = [
        'TELEGRAM_BOT_TOKEN',
        'DB_HOST',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        error_msg = f"المتغيرات البيئية المفقودة: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # تهيئة قاعدة البيانات
    init_db()
    
    try:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        logger.info(f"تم الحصول على توكن البوت، الطول: {len(token)} أحرف")
        
        application = ApplicationBuilder() \
            .token(token) \
            .post_init(post_init) \
            .build()
        
        # تسجيل المعالجات
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("score", show_score))
        application.add_handler(CommandHandler("tasks", list_tasks))
        
        # معالج المحادثة
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('addtask', add_task)],
            states={
                TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_name_handler)],
                TASK_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_due_date_handler)],
                TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_description_handler)],
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        application.add_handler(conv_handler)
        
        # بدء البوت
        application.run_polling()
        
    except Exception as e:
        logger.error(f"خطأ فادح في تشغيل البوت: {e}")
        raise

if __name__ == '__main__':
    main()
