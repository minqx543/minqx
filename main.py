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
    referral_link = f"https://t.me/{context.bot.username}?start={user_id}"
    await update.message.reply_text(f"🔗 رابط الإحالة الخاص بك:\n{referral_link}")

# دالة عرض قائمة المتصدرين
async def leaderboard(update: Update, context: CallbackContext) -> None:
    cursor.execute('''
    SELECT user_id, COUNT(*) as completed_tasks 
    FROM tasks 
    WHERE completed = 1 
    GROUP BY user_id 
    ORDER BY completed_tasks DESC 
    LIMIT 10
    ''')
    top_users = cursor.fetchall()

    if not top_users:
        await update.message.reply_text("لا يوجد متصدرون بعد.")
        return

    leaderboard_text = "🏆 قائمة أفضل 10 مستخدمين:\n"
    for rank, (user_id, completed_tasks) in enumerate(top_users, start=1):
        try:
            user = await context.bot.get_chat(user_id)
            name = user.username or user.first_name or f"مستخدم {user_id}"
        except:
            name = f"مستخدم {user_id}"
        leaderboard_text += f"{rank}. {name} - {completed_tasks} مهمة مكتملة\n"

    await update.message.reply_text(leaderboard_text)

# تشغيل البوت
def main() -> None:
    TOKEN = os.getenv("BOT_TOKEN")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("links", links))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("leaderboard", leaderboard))

    application.run_polling()

if __name__ == "__main__":
    main()
