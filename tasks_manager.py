import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    ConversationHandler,
    filters
)
from datetime import datetime

# تكوين التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

def init_tasks_db():
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
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
            logger.info("تم تهيئة جدول المهام بنجاح")
    except Exception as e:
        logger.error(f"فشل في تهيئة جدول المهام: {e}")
        raise

def create_tasks_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مهمة جديدة", callback_data="add_task")],
        [InlineKeyboardButton("📋 عرض المهام", callback_data="list_tasks")],
        [InlineKeyboardButton("🔙 الرجوع للقائمة الرئيسية", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_tasks(update: Update, context: CallbackContext):
    init_tasks_db()
    await update.message.reply_text(
        "🎯 نظام إدارة المهام\nاختر أحد الخيارات:",
        reply_markup=create_tasks_keyboard()
    )

async def add_task(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("📝 ما هي المهمة التي تريد إضافتها؟")
    else:
        await update.message.reply_text("📝 ما هي المهمة التي تريد إضافتها؟")
    return TASK_NAME

async def task_name_handler(update: Update, context: CallbackContext) -> int:
    context.user_data['task_name'] = update.message.text
    await update.message.reply_text("📅 متى يجب إكمال هذه المهمة؟ (YYYY-MM-DD)")
    return TASK_DUE_DATE

async def task_due_date_handler(update: Update, context: CallbackContext) -> int:
    try:
        due_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['due_date'] = due_date
        await update.message.reply_text("📄 هل تريد إضافة وصف للمهمة؟ (اختياري)")
        return TASK_DESCRIPTION
    except ValueError:
        await update.message.reply_text("⚠️ تنسيق التاريخ غير صحيح. يرجى إدخال التاريخ بالصيغة YYYY-MM-DD")
        return TASK_DUE_DATE

async def task_description_handler(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    description = update.message.text
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (user_id, name, due_date, description) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, 
                 context.user_data['task_name'], 
                 context.user_data['due_date'], 
                 description)
            )
            conn.commit()
            
            await update.message.reply_text("✅ تمت إضافة المهمة بنجاح!", 
                                          reply_markup=create_tasks_keyboard())
    except Exception as e:
        logger.error(f"خطأ في إضافة المهمة: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء إضافة المهمة. يرجى المحاولة لاحقاً.", 
                                      reply_markup=create_tasks_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END

async def list_tasks(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    try:
        conn = db_manager.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, due_date, description, completed "
                "FROM tasks WHERE user_id = %s ORDER BY due_date",
                (user_id,)
            )
            tasks = cur.fetchall()
            
            if tasks:
                message = "📋 مهامك:\n\n"
                for task in tasks:
                    name, due_date, description, completed = task
                    status = "✅" if completed else "⏳"
                    message += f"{status} {name} - {due_date}\n"
                    if description:
                        message += f"وصف: {description}\n"
                    message += "\n"
                await update.message.reply_text(message, reply_markup=create_tasks_keyboard())
            else:
                await update.message.reply_text("📭 ليس لديك أي مهام حالياً.", 
                                             reply_markup=create_tasks_keyboard())
    except Exception as e:
        logger.error(f"خطأ في عرض المهام: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء جلب المهام.", 
                                      reply_markup=create_tasks_keyboard())

def main():
    required_env_vars = ['TELEGRAM_BOT_TOKEN', 'DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"المتغيرات البيئية المفقودة: {', '.join(missing_vars)}")
    
    try:
        application = ApplicationBuilder() \
            .token(os.getenv('TELEGRAM_BOT_TOKEN')) \
            .build()
        
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('tasks', start_tasks),
                CallbackQueryHandler(add_task, pattern="^add_task$")
            ],
            states={
                TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_name_handler)],
                TASK_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_due_date_handler)],
                TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_description_handler)],
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        application.add_handler(conv_handler)
        application.add_handler(CallbackQueryHandler(list_tasks, pattern="^list_tasks$"))
        
        application.run_polling()
        
    except Exception as e:
        logger.error(f"خطأ فادح في تشغيل مدير المهام: {e}")
        raise

if __name__ == '__main__':
    main()
