import logging
import asyncio
import os
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# إعداد سجل الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# دوال الأوامر

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك في البوت! 🎉")

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    referral_link = f"https://t.me/{context.bot.username}?start={user_id}"
    await update.message.reply_text(f"رابط الإحالة الخاص بك:\n{referral_link}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # هذه مجرد بيانات تجريبية
    top_referrals = [
        ("user1", 15),
        ("user2", 12),
        ("user3", 10)
    ]
    message = "🏆 أفضل المحيلين:\n"
    for i, (user, count) in enumerate(top_referrals, 1):
        message += f"{i}. {user} - {count} إحالة\n"
    await update.message.reply_text(message)

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = "📎 روابط المنصات:\n"
    message += "🔗 منصة 1: https://example.com/1\n"
    message += "🔗 منصة 2: https://example.com/2\n"
    await update.message.reply_text(message)

# الدالة الرئيسية لتشغيل البوت
async def main():
    token = os.getenv("BOT_TOKEN")  # تأكد من وجود هذا المتغير في بيئة Render
    if not token:
        raise ValueError("BOT_TOKEN not set in environment variables")

    application = ApplicationBuilder().token(token).build()

    # إضافة الهاندلرز
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("links", links))

    # تعيين أوامر البوت
    commands = [
        BotCommand("start", "بدء استخدام البوت"),
        BotCommand("referral", "رابط الإحالة الخاص بك"),
        BotCommand("leaderboard", "أفضل 10 محيلين"),
        BotCommand("links", "روابط المنصات")
    ]
    await application.bot.set_my_commands(commands)

    await application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
