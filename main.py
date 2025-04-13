from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import sqlite3
import json
import os

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def load_tasks():
    with open('tasks.json', 'r', encoding='utf-8') as file:
        return json.load(file)['tasks']

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT points, referrals FROM users WHERE user_id = ?', (user_id,))
    data = cursor.fetchone()
    conn.close()
    return data if data else (0, 0)

def update_user(user_id, points=0, referrals=0):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id) VALUES (?)
    ''', (user_id,))
    cursor.execute('''
        UPDATE users SET points = points + ?, referrals = referrals + ? WHERE user_id = ?
    ''', (points, referrals, user_id))
    conn.commit()
    conn.close()

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update_user(user.id)  # تسجيل المستخدم الجديد
    await update.message.reply_text(f"مرحباً {user.first_name}!")

async def tasks(update: Update, context: CallbackContext):
    tasks_msg = "📋 المهام المتاحة:\n"
    for task in load_tasks():
        tasks_msg += f"\n- {task['type']}: {task['reward']} نقاط ({task['link']})"
    await update.message.reply_text(tasks_msg)

async def points(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    points, referrals = get_user_data(user_id)
    await update.message.reply_text(f"نقاطك: {points}\nإحالاتك: {referrals}")

def main():
    init_db()  # تهيئة قاعدة البيانات
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("points", points))
    
    app.run_polling()

if __name__ == '__main__':
    main()
