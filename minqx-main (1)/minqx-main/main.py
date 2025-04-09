import os
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from database import SessionLocal, User, Referral, init_db

TOKEN = os.environ.get("BOT_TOKEN")

app = ApplicationBuilder().token(TOKEN).build()

# إنشاء الجداول عند التشغيل
init_db()

# الرابط الخاص بالموقع
site_url = "https://minqx.onrender.com"

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
    avatar_url = "https://github.com/khamis1987/minqx/blob/main/src/default_avatar.jpg.png?raw=true"

    # روابط المنصات مع الأيقونات
    platforms = {
        "YouTube": "https://www.youtube.com/@MinQX_Official",
        "Instagram": "https://www.instagram.com/minqx2025?igsh=MTRhNmJtNm1wYWxqYw==",
        "TikTok": "https://www.tiktok.com/@minqx2?_t=ZS-8u9g1d9GPLe&_r=1",
        "Twitter": "https://x.com/MinQX_Official?t=xQGqqJLnypq5TKP4jmDm2A&s=09",
        "Facebook": "https://www.facebook.com/share/1BjH4qcGXb/",
        "Telegram Group": "https://t.me/minqx1official"
    }

    # الرموز التعبيرية المناسبة لكل منصة
    icons = {
        "YouTube": "📺",
        "Instagram": "📷",
        "TikTok": "🎵",
        "Twitter": "🐦",
        "Facebook": "📘",
        "Telegram Group": "📱"
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

    # إضافة رابط الموقع
    welcome_message += f"\n🌐 لمزيد من المعلومات، قم بزيارة: {site_url}"

    # إرسال رسالة ترحيب مع صورة
    await update.message.reply_photo(avatar_url, caption=welcome_message)

async def add_points_for_platform(update: Update, platform: str):
    user_id = update.effective_user.id
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=user_id).first()

    if user:
        user.points += 10  # إضافة 10 نقاط عند متابعة المنصة
        db.commit()

        # إرسال رسالة تأكيد للمستخدم
        await update.message.reply_text(f"✅ لقد تم إضافة 10 نقاط لك لمتابعتك {platform}. الآن لديك {user.points} نقطة.")
    else:
        await update.message.reply_text("❗️ لا يوجد سجل لك بعد، ابدأ بالأمر /start")
    db.close()

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

async def referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    referral_message = "🎯 قم بدعوة أصدقائك إلى البوت لكسب 100 نقطة لكل إحالة!\n\n"
    referral_message += "🔗 استخدم الرابط التالي لإحالة أصدقائك:\n"
    referral_message += "https://t.me/MinQX_Bot/MinQX\n\n"
    referral_message += "💡 كلما قمت بدعوة المزيد من الأصدقاء، زادت نقاطك!"

    await update.message.reply_text(referral_message)

async def top_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    top_referrers = db.query(User).join(Referral).group_by(User.id).order_by(User.referrals_count.desc()).limit(10).all()
    db.close()

    if not top_referrers:
        await update.message.reply_text("لا يوجد لاعبين قاموا بالإحالات بعد.")
        return

    msg = "🏆 أفضل 10 لاعبين في الإحالات:\n\n"
    for i, referrer in enumerate(top_referrers, start=1):
        msg += f"{i}. @{referrer.username} - {referrer.points} نقطة - {referrer.referrals_count} إحالة\n"

    await update.message.reply_text(msg)

# تسجيل الأوامر
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("points", my_points))
app.add_handler(CommandHandler("top", leaderboard))
app.add_handler(CommandHandler("referrals", referrals))  # إضافة أمر الإحالات
app.add_handler(CommandHandler("topreferrals", top_referrals))  # إضافة أمر أفضل الإحالات

# إضافة الأوامر للمنصات
app.add_handler(CommandHandler("youtube", lambda update, context: add_points_for_platform(update, "YouTube")))
app.add_handler(CommandHandler("instagram", lambda update, context: add_points_for_platform(update, "Instagram")))
app.add_handler(CommandHandler("tiktok", lambda update, context: add_points_for_platform(update, "TikTok")))
app.add_handler(CommandHandler("twitter", lambda update, context: add_points_for_platform(update, "Twitter")))
app.add_handler(CommandHandler("facebook", lambda update, context: add_points_for_platform(update, "Facebook")))
app.add_handler(CommandHandler("telegram", lambda update, context: add_points_for_platform(update, "Telegram Group")))

# تشغيل البوت
if __name__ == "__main__":
    app.run_polling()
