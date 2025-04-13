from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

def get_top_users(column, limit=10):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(f'''
        SELECT user_id, {column} FROM users ORDER BY {column} DESC LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

async def start(update: Update, context: CallbackContext):
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

async def tasks(update: Update, context: CallbackContext):
    tasks_msg = "✅️ المهام المتاحة:\n"
    for task in load_tasks():
        tasks_msg += f"\n- {task['type']}: {task['reward']} نقاط\n{task['link']}"
    await update.message.reply_text(tasks_msg)

async def score(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    points, referrals = get_user_data(user_id)
    await update.message.reply_text(f"🤑 نقاطك: {points}\n🔥 عدد الإحالات: {referrals}")

async def top(update: Update, context: CallbackContext):
    top_users = get_top_users('points')
    message = "🥇 أفضل 10 لاعبين حسب النقاط:\n"
    for i, (uid, points) in enumerate(top_users, 1):
        message += f"{i}. ID {uid}: {points} نقطة\n"
    await update.message.reply_text(message)

async def referrals(update: Update, context: CallbackContext):
    user = update.effective_user
    ref_link = f"https://t.me/MinQX_Bot?start={user.id}"
    keyboard = [[InlineKeyboardButton("مشاركة الرابط", url=ref_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"🔥 رابط الإحالة الخاص بك:\n{ref_link}", reply_markup=reply_markup)

async def topreferrals(update: Update, context: CallbackContext):
    top_users = get_top_users('referrals')
    message = "🥇 أفضل 10 حسب عدد الإحالات:\n"
    for i, (uid, refs) in enumerate(top_users, 1):
        message += f"{i}. ID {uid}: {refs} إحالة\n"
    await update.message.reply_text(message)

async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "start":
        await start(update, context)
    elif data == "score":
        await score(update, context)
    elif data == "tasks":
        await tasks(update, context)
    elif data == "top":
        await top(update, context)
    elif data == "referrals":
        await referrals(update, context)
    elif data == "topreferrals":
        await topreferrals(update, context)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("referrals", referrals))
    app.add_handler(CommandHandler("topreferrals", topreferrals))
    app.add_handler(CommandHandler("points", score))  # alias for score
    app.add_handler(CommandHandler("top_referrals", topreferrals))  # optional
    app.add_handler(CommandHandler("top_players", top))  # optional
    app.add_handler(CommandHandler("myref", referrals))  # optional

    app.add_handler(telegram.ext.CallbackQueryHandler(handle_callback))

    app.run_polling()

if __name__ == '__main__':
    main()
