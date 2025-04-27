from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import psycopg2
import os
from dotenv import load_dotenv

# تحميل المتغيرات البيئية من ملف .env (إذا كنت تستخدمه)
load_dotenv()

# المتغيرات
TOKEN = os.getenv('TELEGRAM_TOKEN')  # استخدام متغير البيئة الخاص بالتوكن
DATABASE_URL = os.getenv('DATABASE_URL')  # استخدام متغير البيئة الخاص بـ Render

# الاتصال بقاعدة البيانات
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# إنشاء جدول إذا لم يكن موجودًا
def create_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    referrals INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

# تسجيل لاعب جديد
def add_user(user_id, username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    if not c.fetchone():
        c.execute('INSERT INTO users (id, username) VALUES (%s, %s)', (user_id, username))
        conn.commit()
    conn.close()

# تحديث عدد الإحالات
def update_referrals(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET referrals = referrals + 1 WHERE id = %s', (user_id,))
    conn.commit()
    conn.close()

# جلب ترتيب اللاعبين
def get_leaderboard():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT username, referrals FROM users ORDER BY referrals DESC LIMIT 10')
    leaderboard = c.fetchall()
    conn.close()
    return leaderboard

# عند بدء البوت
async def start(update: Update, context: CallbackContext) -> None:
    print(f"تم استقبال أمر start من {update.message.from_user.username}")
    add_user(update.message.from_user.id, update.message.from_user.username)
    message = (
        f'مرحبًا {update.message.from_user.username}!\n'
        'أهلاً بك في اللعبة! نتمنى لك حظًا سعيدًا.\n'
        'لتبدأ في إحالة أصدقائك ورفع ترتيبك، استخدم الأمر /referral.\n'
        'إليك رابط البوت: @MissionxX_bot'
    )
    await update.message.reply_text(message)

# أمر referral
async def referral(update: Update, context: CallbackContext) -> None:
    link = f'https://yourwebsite.com/referral/{update.message.from_user.id}'
    await update.message.reply_text(f'رابط إحالتك الخاص هو: {link}')

# أمر leaderboard
async def leaderboard(update: Update, context: CallbackContext) -> None:
    print(f"تم استقبال أمر leaderboard من {update.message.from_user.username}")
    leaderboard_data = get_leaderboard()
    leaderboard_text = "أفضل 10 لاعبين:\n"
    for index, (username, referrals) in enumerate(leaderboard_data, start=1):
        leaderboard_text += f'{index}. {username} - عدد الإحالات: {referrals}\n'
    await update.message.reply_text(leaderboard_text)

def main():
    # إعداد البوت باستخدام Application بدلاً من Updater
    application = Application.builder().token(TOKEN).build()

    # عند بدء البوت
    create_db()

    # إضافة الأوامر للبوت
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("leaderboard", leaderboard))

    # بدء البوت
    application.run_polling()

if __name__ == '__main__':
    main()
