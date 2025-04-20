import os
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# الحصول على التوكن من متغير البيئة
bot_token = os.getenv('BOT_TOKEN')

# التحقق من وجود التوكن
if not bot_token:
    raise ValueError("بوت توكن غير موجود في متغير البيئة")

# إنشاء قاعدة بيانات SQLite لتخزين المهام
conn = sqlite3.connect('tasks.db')
cursor = conn.cursor()

# إذا لم تكن الجداول موجودة، قم بإنشائها
cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task_name TEXT,
    completed INTEGER
)
''')

# دالة لعرض المهام
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    cursor.execute("SELECT * FROM tasks WHERE user_id=?", (user_id,))
    tasks = cursor.fetchall()

    if not tasks:
        await update.message.reply_text("لا توجد مهام لديك.")
        return

    task_list = "\n".join([f"{task[2]} - {'تم إتمامها' if task[3] else 'لم تتم'}" for task in tasks])
    await update.message.reply_text(f"مهامك:\n{task_list}")

# دالة لإضافة مهمة جديدة
async def add_task(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    task_name = " ".join(context.args)
    
    if not task_name:
        await update.message.reply_text("يرجى إدخال اسم المهمة.")
        return
    
    cursor.execute("INSERT INTO tasks (user_id, task_name, completed) VALUES (?, ?, ?)", 
                   (user_id, task_name, 0))
    conn.commit()
    
    await update.message.reply_text(f"تم إضافة المهمة: {task_name}")

# دالة لتغيير حالة إتمام المهمة
async def complete_task(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    task_id = int(context.args[0]) if context.args else None
    
    if not task_id:
        await update.message.reply_text("يرجى إدخال معرف المهمة.")
        return
    
    cursor.execute("UPDATE tasks SET completed = 1 WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    
    await update.message.reply_text(f"تم إتمام المهمة برقم: {task_id}")

# دالة رئيسية لتشغيل البوت
def main():
    # استبدال التوكن باستخدام متغير البيئة
    application = Application.builder().token(bot_token).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_task))
    application.add_handler(CommandHandler("complete", complete_task))

    # بدء البوت
    application.run_polling()

if __name__ == '__main__':
    main()
