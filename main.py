import os
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from database import SessionLocal, User, init_db

TOKEN = os.environ.get("BOT_TOKEN")

app = ApplicationBuilder().token(TOKEN).build()

# إنشاء الجداول عند التشغيل
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        user = User(telegram_id=user_id, username=username, points=0)
        db.add(user)
        db.commit()
    db.close()

    # الرابط الخاص بالصورة الافتراضية
    avatar_url = "https://github.com/Twqcoin/twq/blob/master/src/default_avatar.jpg.png?raw=true"

    # روابط المنصات مع الأيقونات
    platforms = {
        "YouTube": "https://www.youtube.com/@MinQX_Official",
        "Instagram": "https://www.instagram.com/minqx2025?igsh=MTRhNmJtNm1wYWxqYw==",
        "TikTok": "https://www.tiktok.com/@minqx2?_t=ZS-8u9g1d9GPLe&_r=1",
        "Twitter": "https://x.com/MinQX_Official?t=xQGqqJLnypq5TKP4jmDm2A&s=09",
        "Facebook": "https://www.facebook.com/share/1BjH4qcGXb/",
        "Telegram Group": "https://t.me/minqx1official"  # إضافة رابط التليجرام
    }

    # الرموز التعبيرية المناسبة لكل منصة
    icons = {
        "YouTube": "📺",
        "Instagram": "📷",
        "TikTok": "🎵",
        "Twitter": "🐦",
        "Facebook": "📘",
        "Telegram Group": "📱"  # أيقونة التليجرام
    }

    # رسالة الترحيب باللغتين العربية والإنجليزية
    welcome_message = f"🎉 مرحباً @{username} في MINQX!\n\n"
    welcome_message += "💥 لقد انضممت إلى مجتمعنا! استمر في إتمام المهام واحصل على المكافآت.\n\n"
    welcome_message += "🎉 Welcome @{username} to MINQX!\n\n"
    welcome_message += "💥 You have joined our community! Keep completing tasks and earn rewards.\n\n"

    # إضافة روابط المنصات مع الأيقونات إلى الرسالة
    welcome_message += "\n📱 تابعنا على المنصات التالية:\n"
    for platform, link in platforms.items():
        welcome_message += f"{icons[platform]} {platform}: {link}\n"

    # إرسال رسالة ترحيب مع صورة
    await update.message.reply_photo(avatar_url, caption=welcome_message)

async def my_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    db.close()

    if user:
        await update.message.reply_text(f"🎯 رصيدك الحالي: {user.points} نقاط")
    else:
        await update.message.reply_text("❗️لا يوجد سجل لك بعد، ابدأ بالأمر /start")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    top_players = db.query(User).order_by(User.points.desc()).limit(10).all()
    db.close()

    if not top_players:
        await update.message.reply_text("لا يوجد لاعبين حتى الآن.")
        return

    msg = "🏆 أفضل 10 لاعبين:\n\n"
    for i, player in enumerate(top_players, start=1):
        name = f"@{player.username}" if player.username else f"لاعب {i}"
        msg += f"{i}. {name} - {player.points} نقطة\n"

    await update.message.reply_text(msg)

# تسجيل الأوامر
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("points", my_points))
app.add_handler(CommandHandler("top", leaderboard))

# تشغيل البوت
if __name__ == "__main__":
    app.run_polling()
