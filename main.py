import logging
import asyncio
import os
from telegram import BotCommand
from telegram.ext import ApplicationBuilder

# استيراد الأوامر من ملف handlers
from handlers.start import start_handler
from handlers.referral import referral_handler
from handlers.leaderboard import leaderboard_handler
from handlers.links import links_handler

# إعداد سجل الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# الدالة الرئيسية لتشغيل البوت
async def main():
    token = os.getenv("BOT_TOKEN")  # تأكد من وجود هذا المتغير في بيئة Render
    if not token:
        raise ValueError("BOT_TOKEN not set in environment variables")

    application = ApplicationBuilder().token(token).build()

    # إضافة الهاندلرز (الأوامر)
    application.add_handler(start_handler)
    application.add_handler(referral_handler)
    application.add_handler(leaderboard_handler)
    application.add_handler(links_handler)

    # تعيين أوامر البوت في واجهة Telegram
    commands = [
        BotCommand("start", "بدء استخدام البوت"),
        BotCommand("referral", "رابط الإحالة الخاص بك"),
        BotCommand("leaderboard", "أفضل 10 محيلين"),
        BotCommand("links", "روابط المنصات")
    ]
    await application.bot.set_my_commands(commands)

    # تشغيل البوت باستخدام polling (لا نحتاج لمنفذ)
    await application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
