from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import psycopg2
import os

# المتغيرات
TOKEN = 'توكن_البوت_هنا'
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
def start(update: Update, context: CallbackContext) -> None:
    add_user(update.message.from_user.id, update.message.from_user.username)
    update.message.reply_text(f'مرحبًا {update.message.from_user.username}! أهلاً بك في اللعبة. نتمنى لك حظًا سعيدًا!')

# أمر referral
def referral(update: Update, context: CallbackContext) -> None:
    link = f'https://yourwebsite.com/referral/{update.message.from_user.id}'
    update.message.reply_text(f'رابط إحالتك الخاص هو: {link}')

# أمر leaderboard
def leaderboard(update: Update, context: CallbackContext) -> None:
    leaderboard_data = get_leaderboard()
    leaderboard_text = "أفضل 10 لاعبين:\n"
    for index, (username, referrals) in enumerate(leaderboard_data, start=1):
        leaderboard_text += f'{index}. {username} - عدد الإحالات: {referrals}\n'
    update.message.reply_text(leaderboard_text)

def main():
    # إعداد البوت
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # عند بدء البوت
    create_db()

    # إضافة الأوامر للبوت
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("referral", referral))
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard))

    # بدء البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
