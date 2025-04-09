import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from database import SessionLocal, User, init_db

# Token من المتغيرات البيئية
TOKEN = os.environ.get("BOT_TOKEN")

# إنشاء التطبيق
app = ApplicationBuilder().token(TOKEN).build()

# إنشاء الجداول عند التشغيل
init_db()

# رابط الموقع
site_url = "https://minqx.onrender.com"

# الصورة الافتراضية للترحيب
avatar_url = "https://github.com/khamis1987/minqx/blob/main/src/default_avatar.jpg.png?raw=true"

# روابط المنصات
platforms = {
    "YouTube": "https://www.youtube.com/@MinQX_Official",
    "Instagram": "https://www.instagram.com/minqx2025?igsh=MTRhNmJtNm1wYWxqYw==",
    "TikTok": "https://www.tiktok.com/@minqx2?_t=ZS-8u9g1d9GPLe&_r=1",
    "Twitter": "https://x.com/MinQX_Official?t=xQGqqJLnypq5TKP4jmDm2A&s=09",
    "Facebook": "https://www.facebook.com/share/1BjH4qcGXb/",
    "Telegram Group": "https://t.me/minqx1official"
}

# الأيقونات الخاصة بكل منصة
icons = {
    "YouTube": "📺",
    "Instagram": "📷",
    "TikTok": "🎵",
    "Twitter": "🐦",
    "Facebook": "📘",
    "Telegram Group": "📱"
}

# أمر البدء
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

    welcome_message = f"🎉 مرحباً @{username} في MINQX!\n\n"
    welcome_message += "💥 لقد انضممت إلى مجتمعنا! استمر في إتمام المهام واحصل على المكافآت.\n\n"
    welcome_message += f"🎉 Welcome @{username} to MINQX!\n\n"
    welcome_message += "💥 You have joined our community! Keep completing tasks and earn rewards.\n\n"
    welcome_message += "\n📱 تابعنا على المنصات التالية:\n"
    for platform, link in platforms.items():
        welcome_message += f"{icons[platform]} {platform}: {link}\n"
    welcome_message += f"\n🌐 لمزيد من المعلومات، قم بزيارة: {site_url}"

    await update.message.reply_photo(avatar_url, caption=welcome_message)

# أمر معرفة الرصيد
async def my_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    db.close()

    if user:
        await update.message.reply_text(f"🎯 رصيدك الحالي: {user.points} نقاط")
    else:
        await update.message.reply_text("❗️لا يوجد سجل لك بعد، ابدأ بالأمر /start")

# أمر لوحة المتصدرين
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
        msg += f"{i}. {name} - {player.points} نقاط\n"
    await update.message.reply_text(msg)

# إضافة نقاط عند متابعة منصة معينة
async def add_points_for_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text("❗️يرجى تحديد اسم المنصة، مثل:\n/addpoints YouTube")
        return

    platform = args[0]
    if platform not in platforms:
        await update.message.reply_text("❗️اسم المنصة غير صحيح. يرجى استخدام واحدة من: " + ", ".join(platforms.keys()))
        return

    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    if user:
        user.points += 10
        db.commit()
        await update.message.reply_text(f"✅ تم إضافة 10 نقاط لك لمتابعتك {platform}. رصيدك الآن: {user.points} نقطة.")
    else:
        await update.message.reply_text("❗️لا يوجد سجل لك بعد، ابدأ بالأمر /start")
    db.close()

# ربط الأوامر بالتطبيق
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("mypoints", my_points))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("addpoints", add_points_for_platform))  # مثل: /addpoints Twitter

# تشغيل التطبيق
if __name__ == "__main__":
    app.run_polling()
