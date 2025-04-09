import os
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from database import SessionLocal, User, Referral, init_db
import logging

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
app = ApplicationBuilder().token(TOKEN).build()

# تهيئة قاعدة البيانات
init_db()

# الرابط الخاص بالموقع
site_url = "https://minqx.onrender.com"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username

        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                user = User(
                    telegram_id=user_id,
                    username=username,
                    points=0,
                    referrals_count=0
                )
                db.add(user)
                db.commit()
                logger.info(f"New user registered: {username} (ID: {user_id})")

            # روابط المنصات
            platforms = {
                "YouTube": "https://www.youtube.com/@MinQX_Official",
                "Instagram": "https://www.instagram.com/minqx2025",
                "TikTok": "https://www.tiktok.com/@minqx2",
                "Twitter": "https://x.com/MinQX_Official",
                "Facebook": "https://www.facebook.com/share/1BjH4qcGXb/",
                "Telegram Group": "https://t.me/minqx1official"
            }

            icons = {
                "YouTube": "📺", "Instagram": "📷", "TikTok": "🎵",
                "Twitter": "🐦", "Facebook": "📘", "Telegram Group": "📱"
            }

            welcome_message = (
                f"🎉 مرحباً @{username} في MINQX!\n\n"
                "💥 لقد انضممت إلى مجتمعنا! استمر في إتمام المهام واحصل على المكافآت.\n\n"
                "🎉 Welcome @{username} to MINQX!\n\n"
                "💥 You have joined our community! Keep completing tasks and earn rewards.\n\n"
                "\n📱 تابعنا على المنصات التالية:\n"
            )

            welcome_message += "\n".join(
                f"{icons[platform]} {platform}: {link}"
                for platform, link in platforms.items()
            )

            welcome_message += f"\n\n🌐 لمزيد من المعلومات: {site_url}"

            avatar_url = "https://github.com/khamis1987/minqx/blob/main/src/default_avatar.jpg.png?raw=true"
            await update.message.reply_photo(avatar_url, caption=welcome_message)

        except Exception as e:
            db.rollback()
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text("حدث خطأ تقني، يرجى المحاولة لاحقاً")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Unexpected error in start: {e}")

async def add_points_for_platform(update: Update, platform: str):
    try:
        user_id = update.effective_user.id
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            if user:
                user.increase_points(10)
                db.commit()
                await update.message.reply_text(
                    f"✅ تم إضافة 10 نقاط لك لمتابعة {platform}. مجموع نقاطك: {user.points}"
                )
            else:
                await update.message.reply_text("❗ الرجاء البدء بالأمر /start أولاً")
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding points: {e}")
            await update.message.reply_text("حدث خطأ أثناء إضافة النقاط")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Unexpected error in add_points: {e}")

async def my_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=user_id).first()
            if user:
                await update.message.reply_text(f"🎯 رصيدك الحالي: {user.points} نقاط")
            else:
                await update.message.reply_text("❗ الرجاء البدء بالأمر /start أولاً")
        except Exception as e:
            logger.error(f"Error getting points: {e}")
            await update.message.reply_text("حدث خطأ أثناء جلب النقاط")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Unexpected error in my_points: {e}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = SessionLocal()
        try:
            top_players = db.query(User).order_by(User.points.desc()).limit(10).all()
            if top_players:
                msg = "🏆 أفضل 10 لاعبين:\n\n" + "\n".join(
                    f"{i}. @{p.username if p.username else 'لاعب'} - {p.points} نقطة"
                    for i, p in enumerate(top_players, 1)
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("لا يوجد لاعبين حتى الآن.")
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            await update.message.reply_text("حدث خطأ أثناء جلب اللاعبين")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Unexpected error in leaderboard: {e}")

async def referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        referral_link = f"https://t.me/MinQX_Bot?start={user_id}"
        message = (
            "🎯 قم بدعوة أصدقائك لكسب 100 نقطة لكل إحالة!\n\n"
            f"🔗 رابط الإحالة الخاص بك:\n{referral_link}\n\n"
            "💡 كلما زاد عدد الأصدقاء الذين تدعوهم، زادت نقاطك!"
        )
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in referrals command: {e}")

async def top_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = SessionLocal()
        try:
            top_referrers = db.query(User).order_by(User.referrals_count.desc()).limit(10).all()
            if top_referrers:
                msg = "🏆 أفضل 10 محيلين:\n\n" + "\n".join(
                    f"{i}. @{r.username if r.username else 'مستخدم'} - {r.referrals_count} إحالة"
                    for i, r in enumerate(top_referrers, 1))
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text("لا يوجد إحالات حتى الآن.")
        except Exception as e:
            logger.error(f"Error getting top referrals: {e}")
            await update.message.reply_text("حدث خطأ أثناء جلب المحيلين")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Unexpected error in top_referrals: {e}")

# تسجيل الأوامر
commands = [
    ("start", "🎉 بدء استخدام البوت"),
    ("points", "🤑 عرض نقاطك"),
    ("top", "🥇 أفضل 10 لاعبين"),
    ("referrals", "🔥 رابط الإحالات"),
    ("topreferrals", "🥇 أفضل 10 محيلين")
]

for cmd, desc in commands:
    app.add_handler(CommandHandler(cmd, eval(cmd)))

# أوامر المنصات
platforms = {
    "youtube": "YouTube",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "twitter": "Twitter",
    "facebook": "Facebook",
    "telegram": "Telegram Group"
}

for cmd, platform in platforms.items():
    app.add_handler(CommandHandler(cmd, lambda update, ctx, p=platform: add_points_for_platform(update, p)))

if __name__ == "__main__":
    logger.info("Starting bot...")
    app.run_polling()
