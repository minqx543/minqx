import json
import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or 'YOUR_BOT_TOKEN_HERE'

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
            referrals INTEGER DEFAULT 0,
            last_login TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT points, referrals, last_login FROM users WHERE user_id = ?', (user_id,))
    data = cursor.fetchone()
    conn.close()
    return data if data else (0, 0, None)

def update_user(user_id, points=0, referrals=0, last_login=None):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    cursor.execute('''
        UPDATE users SET points = points + ?, referrals = referrals + ?, last_login = ?
        WHERE user_id = ?
    ''', (points, referrals, last_login, user_id))
    conn.commit()
    conn.close()

def get_top_users(column, limit=10):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(f'SELECT user_id, {column} FROM users ORDER BY {column} DESC LIMIT ?', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    args = context.args
    inviter_id = int(args[0]) if args and args[0].isdigit() else None

    is_new = get_user_data(user.id) == (0, 0, None)
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
        f"🎊 مرحبًا بك {user.full_name} في @MissionxX_bot 🎊\n"
        f"✨ اختر أحد الخيارات من الأزرار أدناه ✨",
        reply_markup=reply_markup
    )

async def handle_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if query.data == "score":
        points, referrals, _ = get_user_data(user.id)
        await query.edit_message_text(f"🤑 نقاطك الحالية: {points} نقطة\n🔗 عدد الإحالات: {referrals}")
    
    elif query.data == "referrals":
        await query.edit_message_text(
            f"🔥 رابط الإحالة الخاص بك:\n"
            f"http://t.me/MissionxX_bot?start={user.id}"
        )

    elif query.data == "top":
        top = get_top_users('points')
        msg = "🥇 أفضل 10 اللاعبين حسب النقاط:\n\n"
        for i, (user_id, points) in enumerate(top, 1):
            msg += f"{i}. ID: {user_id} - {points} نقطة\n"
        await query.edit_message_text(msg)

    elif query.data == "topreferrals":
        top = get_top_users('referrals')
        msg = "🥇 أفضل 10 بالإحالات:\n\n"
        for i, (user_id, refs) in enumerate(top, 1):
            msg += f"{i}. ID: {user_id} - {refs} إحالة\n"
        await query.edit_message_text(msg)

    elif query.data == "tasks":
        tasks = load_tasks()
        msg = "✅️ المهام المتاحة:\n\n"
        for task in tasks:
            msg += f"• {task['type'].replace('_', ' ').title()} - [اضغط هنا]({task['link']}) للحصول على {task['reward']} نقطة\n"
        await query.edit_message_text(msg, disable_web_page_preview=True, parse_mode="Markdown")

    elif query.data == "start":
        await start(update, context)

    elif query.data == "daily_login":
        points, referrals, last_login = get_user_data(user.id)
        today = datetime.today().strftime('%Y-%m-%d')

        if last_login != today:
            update_user(user.id, points=points + 5, last_login=today)
            await query.edit_message_text(f"🎉 تم تسجيل دخولك اليوم! حصلت على 5 نقاط. اجعلها عادة يومية!")
        else:
            await query.edit_message_text("🚫 لقد قمت بتسجيل الدخول اليوم بالفعل.")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
