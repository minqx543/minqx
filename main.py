import os
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or 'YOUR_BOT_TOKEN_HERE'

# روابط المنصات مع الأيقونات
platforms = [
    {"name": "تيليجرام", "icon": "📲", "link": "https://t.me/MissionX_offici"},
    {"name": "انستغرام", "icon": "📸", "link": "https://www.instagram.com/missionx_offici?igsh=MTRhNmJtNm1wYWxqYw=="},
    {"name": "فيسبوك", "icon": "📘", "link": "https://www.facebook.com/share/15y7bKugWt/"},
    {"name": "تويتر", "icon": "🐦", "link": "https://x.com/MissionX_Offici?t=2a_ntYJ4pOs8FteAPyLnuQ&s=09"},
    {"name": "تيك توك", "icon": "🎵", "link": "https://www.tiktok.com/@missionx_offici?_t=ZS-8vYmInEMU48&_r=1"},
    {"name": "يوتيوب", "icon": "▶️", "link": "https://www.youtube.com/@MissionX_offici"},
]

# إنشاء قاعدة البيانات
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
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
def update_user(user_id, full_name, referrals=0, last_login=None, invited_by=None):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)', (user_id, full_name))
    if invited_by is not None:
        cursor.execute('''
            UPDATE users
            SET referrals = referrals + ?, last_login = ?, invited_by = ?, full_name = ?
            WHERE user_id = ?
        ''', (referrals, last_login, invited_by, full_name, user_id))
    else:
        cursor.execute('''
            UPDATE users
            SET referrals = referrals + ?, last_login = ?, full_name = ?
            WHERE user_id = ?
        ''', (referrals, last_login, full_name, user_id))
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
        update_user(user.id, user.full_name, last_login=str(datetime.now()), invited_by=inviter_id)
        update_user(inviter_id, "", referrals=1)
        await context.bot.send_message(
            chat_id=inviter_id,
            text=f"🎉 لقد حصلت على إحالة جديدة من {user.full_name}!"
        )
    else:
        update_user(user.id, user.full_name, last_login=str(datetime.now()))

    # إرسال روابط المنصات
    message = "🌐 *روابط منصات MissionX:*\n\n"
    for p in platforms:
        message += f"{p['icon']} [{p['name']}]({p['link']})\n"

    # إرسال رابط الإحالة
    referral_link = f"https://t.me/{context.bot.username}?start={user.id}"
    message += f"\n🎯 *رابط الإحالة الخاص بك:*\n{referral_link}"
    message += "\n\n✉️ أرسل هذا الرابط لأصدقائك وكل من يسجل عن طريقك يحسب لك إحالة!"

    await context.bot.send_message(
        chat_id=user.id,
        text=message,
        parse_mode='Markdown'
    )

# أمر /myrefs
async def myrefs(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    referrals, _, _ = get_user_data(user_id)
    referrals = referrals or 0
    await update.message.reply_text(f"📊 لديك {referrals} إحالة.")

# أمر /top10
async def top10(update: Update, context: CallbackContext):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT full_name, referrals FROM users ORDER BY referrals DESC LIMIT 10')
    top_users = cursor.fetchall()
    conn.close()

    if not top_users:
        await update.message.reply_text("لا يوجد إحالات بعد.")
        return

    message = "🏆 *أفضل 10 مستخدمين حسب عدد الإحالات:*\n\n"
    for idx, (name, refs) in enumerate(top_users, 1):
        message += f"{idx}. {name or 'مستخدم'} - {refs} إحالة\n"

    await update.message.reply_text(message, parse_mode='Markdown')

# تشغيل البوت
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myrefs", myrefs))
    app.add_handler(CommandHandler("top10", top10))
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
