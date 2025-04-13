from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import sqlite3
import json
import os  # مكتبة os للوصول إلى المتغيرات البيئية

# تحميل التوكن من المتغير البيئي
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')  # جلب التوكن من المتغير البيئي

# تحميل المهام من ملف JSON
def load_tasks():
    with open('tasks.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data['tasks']

# دالة لربط قاعدة البيانات
def get_user_data(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT points, referrals FROM users WHERE user_id = ?', (user_id,))
    data = cursor.fetchone()
    if data:
        return data
    else:
        cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        return 0, 0

# دالة لحفظ النقاط
def update_points(user_id, points):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (points, user_id))
    conn.commit()
    conn.close()

# دالة لعرض رسالة الترحيب مع اسم اللاعب
async def start(update: Update, context: CallbackContext) -> None:
    user_name = update.message.from_user.first_name  # الحصول على اسم المستخدم
    welcome_message = f"🎊 مرحبًا بك {user_name} في @MinQX_Bot 🎊\n✨ اختر أحد الخيارات من الأزرار أدناه ✨"
    await update.message.reply_text(welcome_message)

# دالة لإظهار المهام من ملف JSON
async def tasks(update: Update, context: CallbackContext) -> None:
    tasks_list = load_tasks()  # تحميل المهام من ملف JSON
    tasks_message = "مهام اليوم:\n"
    
    for task in tasks_list:
        tasks_message += f"\n{task['type'].replace('_', ' ').capitalize()}: {task['link']} (احصل على {task['reward']} نقاط)"
    
    await update.message.reply_text(tasks_message)

# دالة لمعالجة الإحالات
async def referral(update: Update, context: CallbackContext) -> None:
    referral_code = context.args[0] if context.args else None
    if referral_code:
        # في حالة وجود رابط الإحالة
        user_id = update.message.from_user.id
        update_points(user_id, 10)  # إضافة 10 نقاط للمستخدم
        await update.message.reply_text(f"تم إضافة 10 نقاط لك بسبب الإحالة!")

# دالة لعرض النقاط للمستخدم
async def points(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    points, referrals = get_user_data(user_id)
    await update.message.reply_text(f"نقاطك الحالية: {points}\nالإحالات: {referrals}")

# الدالة الأساسية التي ستقوم بتشغيل البوت
def main():
    # إعداد البوت باستخدام Application
    application = Application.builder().token(TOKEN).build()

    # إضافة معالجات للأوامر
    application.add_handler(CommandHandler("start", start))  # إضافة دالة start لعرض الترحيب
    application.add_handler(CommandHandler("tasks", tasks))  # عرض المهام
    application.add_handler(CommandHandler("points", points))  # عرض النقاط
    application.add_handler(CommandHandler("referral", referral))  # الإحالة

    # تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()
