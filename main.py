from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    cursor.execute('UPDATE users SET points = points + ?, referrals = referrals + ? WHERE user_id = ?', (points, referrals, user_id))
    conn.commit()
    conn.close()

def get_top_users(column, limit=10):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(f'SELECT user_id, {column} FROM users ORDER BY {column} DESC LIMIT ?', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    inviter_id = int(args[0]) if args and args[0].isdigit() else None

    is_new = get_user_data(user.id) == (0, 0)
    update_user(user.id)

    if inviter_id and inviter_id != user.id and is_new:
        update_user(inviter_id, points=10, referrals=1)
        await context.bot.send_message(chat_id=inviter_id, text=f"🎉 لقد حصلت على 10 نقاط لأن {user.first_name} اشترك عبر رابطك!")

    keyboard = [
        [InlineKeyboardButton("🎉 بدء التفاعل", callback_data="start")],
        [InlineKeyboardButton("🤑 نقاطك في اللعبة", callback_data="score")],
        [InlineKeyboardButton("✅️ المهام المتاحة", callback_data="tasks")],
        [InlineKeyboardButton("🥇 أفضل 10 اللاعبين", callback_data="top")],
        [InlineKeyboardButton("🔥 رابط الإحالات", callback_data="referrals")],
        [InlineKeyboardButton("🥇 افضل 10 إحالات", callback_data="topreferrals")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎊 مرحبًا بك {user.first_name} في @MinQX_Bot 🎊\n"
        f"✨ اختر أحد الخيارات من الأزرار أدناه ✨",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == "score":
        points, _ = get_user_data(user.id)
        await query.edit_message_text(f"🤑 نقاطك الحالية: {points}")
    elif data == "referrals":
        await query.edit_message_text(f"🔥 رابط الإحالة الخاص بك:\nhttps://t.me/MinQX_Bot?start={user.id}")
    elif data == "top":
        top = get_top_users("points")
        msg = "🥇 أفضل 10 اللاعبين:\n"
        for i, (uid, pts) in enumerate(top, start=1):
            msg += f"{i}. ID: {uid} - نقاط: {pts}\n"
        await query.edit_message_text(msg)
    elif data == "topreferrals":
        top = get_top_users("referrals")
        msg = "🥇 أفضل 10 من جلبوا إحالات:\n"
        for i, (uid, ref) in enumerate(top, start=1):
            msg += f"{i}. ID: {uid} - إحالات: {ref}\n"
        await query.edit_message_text(msg)
    elif data == "tasks":
        tasks = load_tasks()
        msg = "✅️ المهام المتاحة:\n"
        for task in tasks:
            msg += f"- {task['title']}: {task['description']} (نقاط: {task['points']})\n"
        await query.edit_message_text(msg)
    elif data == "start":
        await start(update, context)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
