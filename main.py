import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import sqlite3

# تفعيل السجل لتتبع الأخطاء
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إعداد الاتصال بقاعدة البيانات
def connect_db():
    conn = sqlite3.connect('missions.db')
    return conn

# إنشاء الجداول في قاعدة البيانات إذا لم تكن موجودة
def create_tables():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        points INTEGER DEFAULT 0
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS missions (
        mission_id INTEGER PRIMARY KEY,
        mission_name TEXT,
        points INTEGER
    )''')
    conn.commit()
    conn.close()

# إضافة مستخدم إلى قاعدة البيانات إذا لم يكن موجودًا
def add_user(user_id, username):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, points) 
    VALUES (?, ?, ?)
    ''', (user_id, username, 0))
    conn.commit()
    conn.close()

# الحصول على النقاط الخاصة بالمستخدم
def get_user_points(user_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('SELECT points FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return 0

# تحديث النقاط الخاصة بالمستخدم
def update_user_points(user_id, points):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (points, user_id))
    conn.commit()
    conn.close()

# إضافة مهمة جديدة
def add_mission(mission_name, points):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO missions (mission_name, points) VALUES (?, ?)
    ''', (mission_name, points))
    conn.commit()
    conn.close()

# عرض المهام للمستخدم
def list_missions():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('SELECT mission_name, points FROM missions')
    missions = cursor.fetchall()
    conn.close()
    return missions

# تعريف الأوامر
def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    add_user(user_id, username)

    points = get_user_points(user_id)
    update.message.reply_text(f"مرحبًا {username}!\nنقاطك الحالية: {points}")

def complete_mission(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    missions = list_missions()
    if not missions:
        update.message.reply_text("لا توجد مهام حالياً.")
        return

    mission_name, points = missions[0]  # اختيار المهمة الأولى كمثال
    update_user_points(user_id, points)
    update.message.reply_text(f"لقد أكملت المهمة: {mission_name}!\nتم إضافة {points} نقاط!")

def show_points(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    points = get_user_points(user_id)
    update.message.reply_text(f"نقاطك الحالية: {points}")

# تعريف وظيفة رئيسية لتشغيل البوت
def main():
    # إعداد البوت باستخدام المفتاح API الخاص بك
    updater = Updater("YOUR_BOT_API_KEY", use_context=True)

    # إنشاء الجداول في قاعدة البيانات عند تشغيل البوت
    create_tables()

    dp = updater.dispatcher

    # إضافة الأوامر للبوت
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("complete_mission", complete_mission))
    dp.add_handler(CommandHandler("points", show_points))

    # بدء البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
