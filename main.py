from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import sqlite3
import os

# إنشاء قاعدة بيانات SQLite لتخزين المهام والإحالات
conn = sqlite3.connect('tasks.db')
cursor = conn.cursor()

# إذا لم تكن الجداول موجودة، قم بإنشائها
cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task_name TEXT,
    completed INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS referrals (
    referrer_id INTEGER,
    referred_id INTEGER
)
''')

# دالة /start
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("مرحباً بك في بوت MissionX! استخدم /links لرؤية روابط المنصات، /referral لرابط الإحالة، و /leaderboard لعرض قائمة المتصدرين.")

# دالة عرض روابط المنصات
async def links(update: Update, context: CallbackContext) -> None:
    platform_links = (
        "🌐 روابط المنصات:\n"
        "🔹 [Telegram](https://t.me/MissionX_offici)\n"
        "🔹 [YouTube](https://youtube.com/@missionx_offici?si=4A549AkxABu523zi)\n"
        "🔹 [TikTok](https://www.tiktok.com/@missionx_offici?_t=ZS-8vgxNwgERtP&_r=1)\n"
        "🔹 [X](https://x.com/MissionX_Offici?t=eqZ5raOAaRfhwivFVe68rg&s=09)\n"
        "🔹 [Facebook](https://www.facebook.com/share/19AMU41hhs/)\n"
        "🔹 [Instagram](https://www.instagram.com/missionx_offici?igsh=MTRhNmJtNm1wYWxqYw==)\n"
    )
    await update.message.reply_text(platform_links, disable_web_page_preview=True)

# دالة عرض رابط الإحالة
async def referral(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    referral_link = f"https://t.me/MissionxX_bot?start={user_id}"
    await update.message.reply_text(f"رابط الإحالة الخاص بك:\n{referral_link}")

# دالة عرض المتصدرين مع عرض اسم المستخدم
async def leaderboard(update: Update, context: CallbackContext) -> None:
    cursor.execute('''
        SELECT referrer_id, COUNT(*) as total 
        FROM referrals 
        GROUP BY referrer_id 
        ORDER BY total DESC 
        LIMIT 10
    ''')
    top_referrers = cursor.fetchall()

    if not top_referrers:
        await update.message.reply_text("لا يوجد إحالات بعد.")
        return

    message = "🏆 قائمة المتصدرين:\n"
    for idx, (user_id, total) in enumerate(top_referrers, start=1):
        try:
            user = await context.bot.get_chat(user_id)
            name = user.username or user.first_name or f"مستخدم {user_id}"
        except:
            name = f"مستخدم {user_id}"
        message += f"{idx}. {name} - {total} إحالة\n"

    await update.message.reply_text(message)

# دالة إضافة إحالة تلقائياً عند البدء بالرابط
async def handle_referral(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    args = context.args

    if args:
        try:
            referrer_id = int(args[0])
            if referrer_id != user_id:
                cursor.execute("SELECT * FROM referrals WHERE referrer_id = ? AND referred_id = ?", (referrer_id, user_id))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, user_id))
                    conn.commit()
        except:
            pass
    await start(update, context)

# تشغيل البوت
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", handle_referral))
    application.add_handler(CommandHandler("links", links))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("leaderboard", leaderboard))

    application.run_polling()

if __name__ == "__main__":
    main()
