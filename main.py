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
    filters,
    CallbackQueryHandler
)

# تكوين التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# حالات المحادثة
TASK_NAME, TASK_DUE_DATE, TASK_DESCRIPTION, TASK_COMPLETE = range(4)

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
                    reward_points INTEGER DEFAULT 10,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS social_media_rewards (
                    user_id BIGINT NOT NULL REFERENCES users(user_id),
                    platform VARCHAR(50) NOT NULL,
                    rewarded BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (user_id, platform)
                )
            """)
            conn.commit()
            logger.info("تم تهيئة جداول قاعدة البيانات بنجاح")
    except Exception as e:
        logger.error(f"فشل في تهيئة قاعدة البيانات: {e}")
        raise

# روابط ثابتة
BOT_USERNAME = "MinQX_Bot"
WELCOME_IMAGE_URL = "https://github.com/minqx543/minqx/blob/main/src/default_avatar.jpg.png?raw=true"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"

# روابط المنصات الاجتماعية
SOCIAL_MEDIA_LINKS = {
    "تويتر": {
        "url": "https://x.com/MinQX_Official?t=xQGqqJLnypq5TKP4jmDm2A&s=09",
        "icon": "🐦",
        "reward": 10
    },
    "تيك توك": {
        "url": "https://www.tiktok.com/@minqx2?_t=ZS-8u9g1d9GPLe&_r=1",
        "icon": "🎵",
        "reward": 10
    },
    "إنستجرام": {
        "url": "https://www.instagram.com/minqx2025?igsh=MTRhNmJtNm1wYWxqYw==",
        "icon": "📷",
        "reward": 10
    },
    "يوتيوب": {
        "url": "https://www.youtube.com/@MinQX_Official",
        "icon": "▶️",
        "reward": 10
    },
    "فيسبوك": {
        "url": "https://www.facebook.com/share/1BmovBrBn4/",
        "icon": "👍",
        "reward": 10
    },
    "تيليجرام": {
        "url": "https://t.me/minqx1official",
        "icon": "✈️",
        "reward": 10
    }
}

def generate_ref_code(user_id: int) -> str:
    return f"REF{user_id % 10000:04d}"

def create_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🎉 بدء التفاعل مع البوت", callback_data="main_menu"),
            InlineKeyboardButton("📢 مشاركة البوت", 
                               url=f"https://t.me/share/url?url={BOT_LINK}&text=انضم%20إلى%20@{BOT_USERNAME}%20للحصول%20على%20مزايا%20رائعة!")
        ],
        [
            InlineKeyboardButton("🤑 نقاطك في اللعبة", callback_data="show_score"),
            InlineKeyboardButton("✅️ المهام المتاحة", callback_data="list_tasks")
        ],
        [
            InlineKeyboardButton("🥇 أفضل 10 اللاعبين", callback_data="top_players"),
            InlineKeyboardButton("🔥 رابط الإحالات", callback_data="referral_link")
        ],
        [
            InlineKeyboardButton("🥇 أفضل 10 إحالات", callback_data="top_referrals"),
            InlineKeyboardButton("📢 منصاتنا الاجتماعية", callback_data="social_media")
        ],
        [
            InlineKeyboardButton("➕ إضافة مهمة جديدة", callback_data="add_task"),
            InlineKeyboardButton("✅ إكمال مهمة", callback_data="complete_task")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_back_button():
    keyboard = [
        [InlineKeyboardButton("🔙 الرجوع إلى القائمة الرئيسية", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

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

    welcome_message = f"🎊 مرحبًا بك {user.first_name} في @{BOT_USERNAME} 🎊"
    await update.message.reply_photo(
        photo=WELCOME_IMAGE_URL,
        caption=welcome_message,
        reply_markup=create_main_menu_keyboard())

async def show_score(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT score FROM users WHERE user_id = %s", (user_id,))
            result = cur.fetchone()
            
            if result:
                score = result[0]
                response = f"🎯 نقاطك الحالية: {score}"
            else:
                response = "⚠️ لم يتم العثور على حسابك. يرجى استخدام /start أولاً."
                
        await update.message.reply_text(response, reply_markup=create_back_button())
    except Exception as e:
        logger.error(f"خطأ في عرض النقاط: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء جلب بياناتك.", reply_markup=create_back_button())

async def list_tasks(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT task_id, name, due_date, description, completed, reward_points "
                "FROM tasks WHERE user_id = %s ORDER BY due_date",
                (user_id,))
            tasks = cur.fetchall()
            
            if tasks:
                message = "📋 مهامك:\n\n"
                for task in tasks:
                    task_id, name, due_date, description, completed, reward = task
                    status = "✅" if completed else "⏳"
                    message += f"{status} {name} - {due_date} (نقاط المكافأة: {reward})\n"
                    if description:
                        message += f"وصف: {description}\n"
                    message += f"ID: {task_id}\n\n"
                
                await update.message.reply_text(message, reply_markup=create_back_button())
            else:
                await update.message.reply_text("📭 ليس لديك أي مهام حالياً.", reply_markup=create_back_button())
    except Exception as e:
        logger.error(f"خطأ في عرض المهام: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء جلب المهام.", reply_markup=create_back_button())

async def complete_task_start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("📝 أدخل ID المهمة التي أكملتها (يمكنك الحصول على ID من قائمة المهام):")
    return TASK_COMPLETE

async def complete_task_finish(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    task_id = update.message.text
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            # تحقق من أن المهمة موجودة ولم تكتمل بعد
            cur.execute(
                """SELECT reward_points FROM tasks 
                WHERE task_id = %s AND user_id = %s AND completed = FALSE""",
                (task_id, user_id))
            result = cur.fetchone()
            
            if result:
                reward_points = result[0]
                
                # تحديث حالة المهمة وإضافة النقاط
                cur.execute(
                    """UPDATE tasks SET completed = TRUE 
                    WHERE task_id = %s AND user_id = %s""",
                    (task_id, user_id))
                
                cur.execute(
                    "UPDATE users SET score = score + %s WHERE user_id = %s",
                    (reward_points, user_id))
                
                conn.commit()
                await update.message.reply_text(
                    f"🎉 تم إكمال المهمة بنجاح! حصلت على {reward_points} نقطة!",
                    reply_markup=create_back_button())
            else:
                await update.message.reply_text(
                    "⚠️ لم يتم العثور على المهمة أو أنها مكتملة بالفعل.",
                    reply_markup=create_back_button())
    except Exception as e:
        logger.error(f"خطأ في إكمال المهمة: {e}")
        await update.message.reply_text(
            "⚠️ حدث خطأ أثناء إكمال المهمة. تأكد من إدخال ID صحيح.",
            reply_markup=create_back_button())
    
    return ConversationHandler.END

async def show_social_media(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    message = "📢 تابعنا على منصاتنا الاجتماعية واحصل على 10 نقاط لكل منصة:\n\n"
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            keyboard = []
            for platform, data in SOCIAL_MEDIA_LINKS.items():
                # تحقق إذا كان المستخدم قد حصل على النقاط مسبقاً
                cur.execute(
                    "SELECT rewarded FROM social_media_rewards WHERE user_id = %s AND platform = %s",
                    (user_id, platform))
                result = cur.fetchone()
                
                if result and result[0]:
                    message += f"{data['icon']} {platform}: {data['url']} (تم المكافأة ✅)\n"
                    keyboard.append([InlineKeyboardButton(
                        f"{data['icon']} {platform} (مكتمل)",
                        url=data['url']))
                else:
                    message += f"{data['icon']} {platform}: {data['url']} (10 نقاط)\n"
                    keyboard.append([InlineKeyboardButton(
                        f"{data['icon']} {platform} (احصل على 10 نقاط)",
                        url=data['url']))
            
            keyboard.append([InlineKeyboardButton(
                "✅ تأكيد المتابعة والحصول على النقاط",
                callback_data="confirm_social_rewards")])
            
            keyboard.append([InlineKeyboardButton(
                "🔙 الرجوع إلى القائمة الرئيسية",
                callback_data="main_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"خطأ في عرض روابط السوشيال ميديا: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء جلب البيانات.", reply_markup=create_back_button())

async def handle_social_rewards(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == "confirm_social_rewards":
        try:
            conn = db_manager.get_connection()
            with conn.cursor() as cur:
                total_rewards = 0
                
                for platform, data in SOCIAL_MEDIA_LINKS.items():
                    # تحقق إذا كان المستخدم قد حصل على النقاط مسبقاً
                    cur.execute(
                        "SELECT rewarded FROM social_media_rewards WHERE user_id = %s AND platform = %s",
                        (user_id, platform))
                    result = cur.fetchone()
                    
                    if not result or not result[0]:
                        # منح النقاط وتسجيل المكافأة
                        cur.execute(
                            "INSERT INTO social_media_rewards (user_id, platform, rewarded) "
                            "VALUES (%s, %s, TRUE) "
                            "ON CONFLICT (user_id, platform) DO UPDATE SET rewarded = TRUE",
                            (user_id, platform))
                        
                        cur.execute(
                            "UPDATE users SET score = score + %s WHERE user_id = %s",
                            (data['reward'], user_id))
                        
                        total_rewards += data['reward']
                
                conn.commit()
                
                if total_rewards > 0:
                    await query.answer(f"🎉 تم منحك {total_rewards} نقاط للمتابعة!")
                    await query.edit_message_text(
                        query.message.text + f"\n\n✅ تم تأكيد متابعتك وحصولك على {total_rewards} نقاط!",
                        reply_markup=create_back_button())
                else:
                    await query.answer("⚠️ لم يتم العثور على منصات جديدة لمتابعتها.")
        except Exception as e:
            logger.error(f"خطأ في تحديث نقاط السوشيال ميديا: {e}")
            await query.answer("⚠️ حدث خطأ أثناء تحديث نقاطك.")

async def handle_main_menu(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "show_score":
        await show_score(update, context)
    elif data == "list_tasks":
        await list_tasks(update, context)
    elif data == "top_players":
        await show_top_players(update, context)
    elif data == "referral_link":
        await show_referral_link(update, context)
    elif data == "top_referrals":
        await show_top_referrals(update, context)
    elif data == "social_media":
        await show_social_media(update, context)
    elif data == "main_menu":
        await start(update, context)
    elif data == "add_task":
        await add_task(update, context)
    elif data == "complete_task":
        await complete_task_start(update, context)

# باقي الدوال (add_task, task_name_handler, task_due_date_handler, task_description_handler) 
# تبقى كما هي بدون تغيير

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
        
        # معالجات الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("score", show_score))
        application.add_handler(CommandHandler("tasks", list_tasks))
        application.add_handler(CommandHandler("social", show_social_media))
        
        # معالجات المحادثة
        task_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('addtask', add_task),
                CallbackQueryHandler(add_task, pattern="^add_task$")
            ],
            states={
                TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_name_handler)],
                TASK_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_due_date_handler)],
                TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_description_handler)],
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        complete_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('complete', complete_task_start),
                CallbackQueryHandler(complete_task_start, pattern="^complete_task$")
            ],
            states={
                TASK_COMPLETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, complete_task_finish)],
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        # معالجات الاستجابة للأزرار
        application.add_handler(CallbackQueryHandler(handle_main_menu))
        application.add_handler(CallbackQueryHandler(handle_social_rewards, pattern="^confirm_social_rewards$"))
        
        application.add_handler(task_conv_handler)
        application.add_handler(complete_conv_handler)
        
        application.run_polling()
        
    except Exception as e:
        logger.error(f"خطأ فادح في تشغيل البوت: {e}")
        raise

if __name__ == '__main__':
    main()
