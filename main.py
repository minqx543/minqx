from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import sqlite3
import json

# إعدادات البوت
TOKEN = 'YOUR_BOT_TOKEN'  # ضع هنا التوكن الخاص بك

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
def start(update: Update, context: CallbackContext) -> None:
    user_name = update.message.from_user.first_name  # الحصول على اسم المستخدم
    welcome_message = f"🎊 مرحبًا بك {user_name} في @MinQX_Bot 🎊\n✨ اختر أحد الخيارات من الأزرار أدناه ✨"
    update.message.reply_text(welcome_message)

# دالة لإظهار المهام من ملف JSON
def tasks(update: Update, context: CallbackContext) -> None:
    tasks_list = load_tasks()  # تحميل المهام من ملف JSON
    tasks_message = "مهام اليوم:\n"
    
    for task in tasks_list:
        tasks_message += f"\n{task['type'].replace('_', ' ').capitalize()}: {task['link']} (احصل على {task['reward']} نقاط)"
    
    update.message.reply_text(tasks_message)

# دالة لمعالجة الإحالات
def referral(update: Update, context: CallbackContext) -> None:
    referral_code = context.args[0] if context.args else None
    if referral_code:
        # في حالة وجود رابط الإحالة
        user_id = update.message.from_user.id
        update_points(user_id, 10)  # إضافة 10 نقاط للمستخدم
        update.message.reply_text(f"تم إضافة 10 نقاط لك بسبب الإحالة!")

# دالة لعرض النقاط للمستخدم
def points(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    points, referrals = get_user_data(user_id)
    update.message.reply_text(f"نقاطك الحالية: {points}\nالإحالات: {referrals}")

# الدالة الأساسية التي ستقوم بتشغيل البوت
def main():
    # إعداد البوت
    updater = Updater(TOKEN)

    # الحصول على المحول الخاص بالبوت
    dispatcher = updater.dispatcher

    # إضافة معالجات للمهام المختلفة
    dispatcher.add_handler(CommandHandler("start", start))  # إضافة دالة start لعرض الترحيب
    dispatcher.add_handler(CommandHandler("tasks", tasks))  # عرض المهام
    dispatcher.add_handler(CommandHandler("points", points))  # عرض النقاط
    dispatcher.add_handler(CommandHandler("referral", referral))  # الإحالة

    # تشغيل البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
