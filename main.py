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

# إنشاء قاعدة البيانات إذا لم تكن موجودة
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrals INTEGER DEFAULT 0,
            last_login TEXT
        )
    ''')
    conn.commit()
    conn.close()

# جلب بيانات مستخدم
def get_user_data(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT referrals, last_login FROM users WHERE user_id = ?', (user_id,))
    data = cursor.fetchone()
    conn.close()
    return data if data else (None, None)

# تحديث بيانات مستخدم
def update_user(user_id, referrals=0, last_login=None):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    cursor.execute('''
        UPDATE users
        SET referrals = referrals + ?, last_login = ?
        WHERE user_id = ?
    ''', (referrals, last_login, user_id))
    conn.commit()
    conn.close()

# الأمر /start
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    args = context.args
    inviter_id = int(args[0]) if args and args[0].isdigit() else None

    is_new = get_user_data(user.id)[0] is None
    update_user(user.id, last_login=str(datetime.now()))

    # إضافة إحالة
    if inviter_id and inviter_id != user.id and is_new:
        update_user(inviter_id, referrals=1)
        await context.bot.send_message(
            chat_id=inviter_id,
            text=f"لقد حصلت على إحالة جديدة من المستخدم {user.full_name}!"
        )

    tasks = load_tasks()
    emoji_map = {
        "join_telegram": "📢",
        "follow_instagram": "📸",
        "like_facebook": "📘",
        "follow_twitter": "🐦",
        "follow_tiktok": "🎵",
        "subscribe_youtube": "▶️",
        "referral": "👥",
        "daily_login": "⏰"
    }

    message = f"مرحبًا {user.first_name}!\n\nقم بإكمال المهام التالية:\n\n"

    for task in tasks:
        icon = emoji_map.get(task['type'], "✅")
        if task['type'] == "referral":
            referral_link = f"https://t.me/MissionX_offici?start={user.id}"
            message += f"{icon} رابط الإحالة الخاص بك:\n{referral_link}\n\n"
        elif task['link']:
            message += f"{icon} {task['link']}\n\n"

    await update.message.reply_text(message)

# تشغيل البوت
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
