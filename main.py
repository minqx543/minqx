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
TASK_TYPE, TASK_DETAILS = range(2)

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
                    task_type VARCHAR(50) NOT NULL,
                    details TEXT,
                    points_granted INTEGER DEFAULT 10,
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
WELCOME_IMAGE_URL = "https://github.com/minqx543/minqx/blob/main/src/default_avatar.jpg.png?raw=true"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"

# أنواع المهام المحددة مسبقاً
TASK_TYPES = {
    "watch_video": {
        "name": "شاهد الفيديو",
        "description": "شاهد الفيديو كاملاً وأدخل الكود الظاهر في نهايته",
        "input_prompt": "🎥 الرجاء إدخال كود الفيديو:",
        "points": 10
    },
    "watch_video_comment": {
        "name": "شاهد الفيديو وأضف تعليق",
        "description": "شاهد الفيديو كاملاً وأدخل التعليق الذي أضفته",
        "input_prompt": "💬 الرجاء إدخال نص التعليق الذي أضفته:",
        "points": 15
    },
    "watch_tweet": {
        "name": "شاهد التغريدة",
        "description": "شاهد التغريدة كاملة وأدخل رابط التغريدة",
        "input_prompt": "🐦 الرجاء إدخال رابط التغريدة:",
        "points": 8
    },
    "follow_account": {
        "name": "تابع الحساب",
        "description": "تابع الحساب المطلوب وأدخل اسم المستخدم",
        "input_prompt": "👤 الرجاء إدخال اسم المستخدم الذي تابعته:",
        "points": 20
    }
}

# روابط المنصات الاجتماعية
SOCIAL_MEDIA = {
    "تويتر 🐦": "https://twitter.com/YourPage",
    "إنستجرام 📸": "https://instagram.com/YourPage",
    "تيليجرام 📢": "https://t.me/YourChannel",
    "يوتيوب ▶️": "https://youtube.com/YourChannel",
    "تيك توك 🎵": "https://tiktok.com/@YourPage"
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
            InlineKeyboardButton("➕ إضافة مهمة جديدة", callback_data="add_task")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_back_button():
    keyboard = [
        [InlineKeyboardButton("🔙 الرجوع إلى القائمة الرئيسية", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_task_types_keyboard():
    keyboard = []
    for task_id, task_data in TASK_TYPES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{task_data['name']} - {task_data['points']} نقاط",
                callback_data=f"tasktype_{task_id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def create_social_media_keyboard():
    keyboard = []
    for platform, url in SOCIAL_MEDIA.items():
        keyboard.append([InlineKeyboardButton(platform, url=url)])
    keyboard.append([InlineKeyboardButton("🔙 الرجوع", callback_data="main_menu")])
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
            )
            
            if context.args:
                referrer_code = context.args[0]
                if referrer_code != generate_ref_code(user_id):
                    cur.execute(
                        "UPDATE users SET score = score + 10, ref_count = ref_count + 1 "
                        "WHERE ref_code = %s AND user_id != %s RETURNING user_id",
                        (referrer_code, user_id)
                    )
                    if cur.fetchone():
                        if update.callback_query:
                            await update.callback_query.answer("🎉 تمت إحالتك بنجاح! حصلت على 10 نقاط إضافية!")
                        else:
                            await update.message.reply_text("🎉 تمت إحالتك بنجاح! حصلت على 10 نقاط إضافية!")
            
            conn.commit()
    except Exception as e:
        logger.error(f"خطأ في قاعدة البيانات: {e}")
        if update.callback_query:
            await update.callback_query.answer("⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقاً.")
        else:
            await update.message.reply_text("⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقاً.")
        return

    welcome_message = (
        f"🎊 مرحبًا بك {user.first_name} في @{BOT_USERNAME} 🎊\n"
        "✨ اختر أحد الخيارات من الأزرار أدناه ✨"
    )
    
    reply_markup = create_main_menu_keyboard()
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=welcome_message,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_photo(
                photo=WELCOME_IMAGE_URL,
                caption=welcome_message,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسالة الترحيبية: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=welcome_message,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def show_score(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT score FROM users WHERE user_id = %s",
                (user_id,)
            )
            result = cur.fetchone()
            
            if result:
                score = result[0]
                response = f"🎯 نقاطك الحالية: {score}"
            else:
                response = "⚠️ لم يتم العثور على حسابك. يرجى استخدام /start أولاً."
                
        if query:
            await query.edit_message_text(
                text=response,
                reply_markup=create_back_button()
            )
        else:
            await update.message.reply_text(
                text=response,
                reply_markup=create_back_button()
            )
    except Exception as e:
        logger.error(f"خطأ في عرض النقاط: {e}")
        response = "⚠️ حدث خطأ أثناء جلب بياناتك. يرجى المحاولة لاحقاً."
        if query:
            await query.edit_message_text(
                text=response,
                reply_markup=create_back_button()
            )
        else:
            await update.message.reply_text(response, reply_markup=create_back_button())

async def list_tasks(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT task_type, details, created_at FROM tasks WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            tasks = cur.fetchall()
            
            if tasks:
                message = "📋 مهامك السابقة:\n\n"
                for task in tasks:
                    task_type, details, created_at = task
                    task_name = TASK_TYPES.get(task_type, {}).get('name', task_type)
                    message += f"🔹 {task_name}\n"
                    if details:
                        message += f"التفاصيل: {details}\n"
                    message += f"التاريخ: {created_at.date()}\n\n"
            else:
                message = "📭 ليس لديك أي مهام مسجلة حالياً."
                
        if query:
            await query.edit_message_text(
                text=message,
                reply_markup=create_back_button()
            )
        else:
            await update.message.reply_text(
                text=message,
                reply_markup=create_back_button()
            )
    except Exception as e:
        logger.error(f"خطأ في عرض المهام: {e}")
        response = "⚠️ حدث خطأ أثناء جلب المهام. يرجى المحاولة لاحقاً."
        if query:
            await query.edit_message_text(
                text=response,
                reply_markup=create_back_button()
            )
        else:
            await update.message.reply_text(response, reply_markup=create_back_button())

async def show_social_media(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    message = "🌍 **منصاتنا الاجتماعية**\n\nيمكنك متابعتنا على المنصات التالية:"
    reply_markup = create_social_media_keyboard()
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup
    )

async def add_task(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "📝 اختر نوع المهمة التي تريد إضافتها:",
            reply_markup=create_task_types_keyboard()
        )
    else:
        await update.message.reply_text(
            "📝 اختر نوع المهمة التي تريد إضافتها:",
            reply_markup=create_task_types_keyboard()
        )
    return TASK_TYPE

async def task_type_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    
    task_type = query.data.replace("tasktype_", "")
    context.user_data['task_type'] = task_type
    
    task_data = TASK_TYPES.get(task_type)
    if task_data:
        await query.edit_message_text(
            f"{task_data['name']}\n{task_data['description']}\n\n{task_data['input_prompt']}"
        )
        return TASK_DETAILS
    else:
        await query.edit_message_text("⚠️ نوع المهمة غير صحيح!")
        return ConversationHandler.END

async def task_details_handler(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    task_details = update.message.text
    task_type = context.user_data['task_type']
    points = TASK_TYPES.get(task_type, {}).get('points', 10)
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            # إضافة المهمة
            cur.execute(
                "INSERT INTO tasks (user_id, task_type, details, points_granted) VALUES (%s, %s, %s, %s)",
                (user_id, task_type, task_details, points)
            )
            
            # منح النقاط
            cur.execute(
                "UPDATE users SET score = score + %s WHERE user_id = %s",
                (points, user_id)
            )
            
            conn.commit()
            
            task_name = TASK_TYPES.get(task_type, {}).get('name', task_type)
            await update.message.reply_text(
                f"✅ تم تسجيل مهمة {task_name} بنجاح وحصلت على {points} نقاط!\n"
                f"التفاصيل: {task_details}",
                reply_markup=create_back_button()
            )
    except Exception as e:
        logger.error(f"خطأ في تسجيل المهمة: {e}")
        await update.message.reply_text(
            "⚠️ حدث خطأ أثناء تسجيل المهمة. يرجى المحاولة لاحقاً.",
            reply_markup=create_back_button()
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("تم الإلغاء.", reply_markup=create_back_button())
    else:
        await update.message.reply_text("تم الإلغاء.", reply_markup=create_back_button())
    
    context.user_data.clear()
    return ConversationHandler.END

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

async def show_top_players(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, score 
                FROM users 
                ORDER BY score DESC 
                LIMIT 10
            """)
            top_players = cur.fetchall()
            
            if top_players:
                message = "🏆 أفضل 10 لاعبين:\n\n"
                for i, (username, score) in enumerate(top_players, 1):
                    message += f"{i}. @{username} - {score} نقطة\n"
            else:
                message = "لا يوجد لاعبين مسجلين بعد."
                
        await query.edit_message_text(
            text=message,
            reply_markup=create_back_button()
        )
    except Exception as e:
        logger.error(f"خطأ في جلب أفضل اللاعبين: {e}")
        await query.edit_message_text(
            text="⚠️ حدث خطأ أثناء جلب البيانات.",
            reply_markup=create_back_button()
        )

async def show_referral_link(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ref_code FROM users WHERE user_id = %s",
                (user_id,)
            )
            result = cur.fetchone()
            
            if result:
                ref_code = result[0]
                ref_link = f"https://t.me/{BOT_USERNAME}?start={ref_code}"
                message = (
                    f"🔗 رابط الإحالة الخاص بك:\n\n"
                    f"{ref_link}\n\n"
                    f"شارك هذا الرابط مع أصدقائك واحصل على 10 نقاط لكل شخص ينضم عبره!"
                )
            else:
                message = "⚠️ لم يتم العثور على حسابك."
                
        await query.edit_message_text(
            text=message,
            reply_markup=create_back_button()
        )
    except Exception as e:
        logger.error(f"خطأ في جلب رابط الإحالة: {e}")
        await query.edit_message_text(
            text="⚠️ حدث خطأ أثناء جلب رابط الإحالة.",
            reply_markup=create_back_button()
        )

async def show_top_referrals(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, ref_count 
                FROM users 
                ORDER BY ref_count DESC 
                LIMIT 10
            """)
            top_referrals = cur.fetchall()
            
            if top_referrals:
                message = "🏅 أفضل 10 أحالات:\n\n"
                for i, (username, ref_count) in enumerate(top_referrals, 1):
                    message += f"{i}. @{username} - {ref_count} إحالة\n"
            else:
                message = "لا يوجد إحالات مسجلة بعد."
                
        await query.edit_message_text(
            text=message,
            reply_markup=create_back_button()
        )
    except Exception as e:
        logger.error(f"خطأ في جلب أفضل الأحالات: {e}")
        await query.edit_message_text(
            text="⚠️ حدث خطأ أثناء جلب البيانات.",
            reply_markup=create_back_button()
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
        
        # إضافة المعالجات
        application.add_handler(CommandHandler("start", start))
        
        # معالج المحادثة لإضافة المهام
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('addtask', add_task),
                CallbackQueryHandler(add_task, pattern="^add_task$")
            ],
            states={
                TASK_TYPE: [CallbackQueryHandler(task_type_handler, pattern="^tasktype_")],
                TASK_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_details_handler)],
            },
            fallbacks=[
                CallbackQueryHandler(cancel, pattern="^cancel$"),
                CommandHandler('cancel', cancel)
            ]
        )
        application.add_handler(conv_handler)
        
        # معالج القائمة الرئيسية
        application.add_handler(CallbackQueryHandler(handle_main_menu))
        
        # بدء البوت
        application.run_polling()
        
    except Exception as e:
        logger.error(f"خطأ فادح في تشغيل البوت: {e}")
        raise

if __name__ == '__main__':
    main()
