import json
import os
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or 'YOUR_BOT_TOKEN_HERE'

# تحميل المهام من ملف JSON
def load_tasks():
    with open('tasks.json', 'r', encoding='utf-8') as file:
        return json.load(file)['tasks']

# إنشاء قاعدة البيانات
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrals INTEGER DEFAULT 0,
            last_login TEXT,
            invited_by INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# جلب بيانات مستخدم
def get_user_data(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT referrals, last_login, invited_by FROM users WHERE user_id = ?', (user_id,))
    data = cursor.fetchone()
    conn.close()
    return data if data else (None, None, None)

# تحديث بيانات مستخدم
def update_user(user_id, referrals=0, last_login=None, invited_by=None):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    if invited_by is not None:
        cursor.execute('''
            UPDATE users
            SET referrals = referrals + ?, last_login = ?, invited_by = ?
            WHERE user_id = ?
        ''', (referrals, last_login, invited_by, user_id))
    else:
        cursor.execute('''
            UPDATE users
            SET referrals = referrals + ?, last_login = ?
            WHERE user_id = ?
        ''', (referrals, last_login, user_id))
    conn.commit()
    conn.close()

# أمر /start
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    args = context.args
    inviter_id = int(args[0]) if args and args[0].isdigit() else None

    referrals, _, invited_by = get_user_data(user.id)
    is_new = referrals is None

    if is_new and inviter_id and inviter_id != user.id:
        update_user(user.id, last_login=str(datetime.now()), invited_by=inviter_id)
        update_user(inviter_id, referrals=1)
        await context.bot.send_message(
            chat_id=inviter_id,
            text=f"لقد حصلت على إحالة جديدة من {user.full_name}!"
        )
    else:
        update_user(user.id, last_login=str(datetime.now()))

    # إرسال المهام
    tasks = load_tasks()
    task_text = "✅ *مهام اليوم:*\n"
    for task in tasks:
        task_text += f"\n- {task['type'].replace('_', ' ').capitalize()}: [اضغط هنا]({task['link']}) - مكافأة: {task['reward']} نقاط"

    # إرسال رابط الإحالة
    referral_link = f"https://t.me/{context.bot.username}?start={user.id}"
    task_text += f"\n\n🎯 رابط الإحالة الخاص بك:\n{referral_link}"
    task_text += "\n\nارسل هذا الرابط لأصدقائك وكل من يسجل عن طريقك يحسب لك إحالة!"

    await context.bot.send_message(
        chat_id=user.id,
        text=task_text,
        parse_mode='Markdown'
    )

# أمر /myrefs
async def myrefs(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    referrals, _, _ = get_user_data(user_id)
    referrals = referrals or 0
    await update.message.reply_text(f"لديك {referrals} إحالة.")

# تشغيل البوت
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myrefs", myrefs))
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
