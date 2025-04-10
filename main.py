import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from aiohttp import web
import logging

# 1. إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. إعدادات قاعدة البيانات (الطريقة الحديثة المتوافقة مع SQLAlchemy 2.0)
class Base(DeclarativeBase):
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. نموذج المستخدم
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String)
    points = Column(Integer, default=0)

# 4. إنشاء الجداول
def init_db():
    Base.metadata.create_all(bind=engine)

# 5. متغيرات البيئة
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("لم يتم تعيين BOT_TOKEN في متغيرات البيئة")

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "DEFAULT_SECRET")
PORT = int(os.environ.get("PORT", 5000))

# 6. إنشاء تطبيق البوت
app = ApplicationBuilder().token(TOKEN).build()

# 7. تهيئة قاعدة البيانات
init_db()

# 8. روابط وإعدادات البوت
site_url = "https://minqx.onrender.com"
avatar_url = "https://github.com/khamis1987/minqx/blob/main/src/default_avatar.jpg.png?raw=true"

platforms = {
    "YouTube": "https://www.youtube.com/@MinQX_Official",
    "Instagram": "https://www.instagram.com/minqx2025?igsh=MTRhNmJtNm1wYWxqYw==",
    "TikTok": "https://www.tiktok.com/@minqx2?_t=ZS-8u9g1d9GPLe&_r=1",
    "Twitter": "https://x.com/MinQX_Official?t=xQGqqJLnypq5TKP4jmDm2A&s=09",
    "Facebook": "https://www.facebook.com/share/1BjH4qcGXb/",
    "Telegram Group": "https://t.me/minqx1official"
}

icons = {
    "YouTube": "📺",
    "Instagram": "📷",
    "TikTok": "🎵",
    "Twitter": "🐦",
    "Facebook": "📘",
    "Telegram Group": "📱"
}

# 9. أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "مستخدم"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=username, points=0)
            db.add(user)
            db.commit()
        
        welcome_message = (
            f"🎉 مرحباً @{username} في MINQX!\n\n"
            "💥 لقد انضممت إلى مجتمعنا! استمر في إتمام المهام واحصل على المكافآت.\n\n"
            f"🎉 Welcome @{username} to MINQX!\n\n"
            "💥 You have joined our community! Keep completing tasks and earn rewards.\n\n"
            "📱 تابعنا على المنصات التالية:\n"
        )
        welcome_message += "\n".join(f"{icons[platform]} {platform}: {link}" for platform, link in platforms.items())
        welcome_message += f"\n\n🌐 لمزيد من المعلومات، قم بزيارة: {site_url}"

        await update.message.reply_photo(avatar_url, caption=welcome_message)
    except Exception as e:
        logger.error(f"Error in start command: {e}")
    finally:
        db.close()

async def my_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user:
            await update.message.reply_text(f"🎯 رصيدك الحالي: {user.points} نقاط")
        else:
            await update.message.reply_text("❗️لا يوجد سجل لك بعد، ابدأ بالأمر /start")
    except Exception as e:
        logger.error(f"Error in my_points command: {e}")
    finally:
        db.close()

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        top_players = db.query(User).order_by(User.points.desc()).limit(10).all()
        if not top_players:
            await update.message.reply_text("لا يوجد لاعبين حتى الآن.")
            return

        msg = "🏆 أفضل 10 لاعبين:\n\n"
        for i, player in enumerate(top_players, start=1):
            name = f"@{player.username}" if player.username else f"لاعب {i}"
            msg += f"{i}. {name} - {player.points} نقاط\n"
        await update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}")
    finally:
        db.close()

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
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.points += 10
            db.commit()
            await update.message.reply_text(f"✅ تم إضافة 10 نقاط لك لمتابعتك {platform}. رصيدك الآن: {user.points} نقطة.")
        else:
            await update.message.reply_text("❗️لا يوجد سجل لك بعد، ابدأ بالأمر /start")
    except Exception as e:
        logger.error(f"Error in add_points_for_platform: {e}")
    finally:
        db.close()

# 10. إعداد Webhook
async def setup_webhook():
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        if WEBHOOK_URL:
            await app.bot.set_webhook(
                url=f"{WEBHOOK_URL}/webhook",
                secret_token=SECRET_TOKEN
            )
            logger.info("Webhook set up successfully")
    except Exception as e:
        logger.error(f"Error setting up webhook: {e}")

async def handle_webhook(request):
    try:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET_TOKEN:
            return web.Response(status=403)
        
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return web.Response()
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return web.Response(status=500)

async def create_app():
    app_web = web.Application()
    app_web.router.add_post('/webhook', handle_webhook)
    app_web.router.add_get('/', lambda _: web.Response(text="Bot is running!"))
    return app_web

# 11. تشغيل الخادم
async def run_server():
    try:
        app_web = await create_app()
        runner = web.AppRunner(app_web)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        logger.info(f"Bot is running on port {PORT}")
        await asyncio.Event().wait()
    except Exception as e:
        logger.error(f"Server error: {e}")

# 12. إعداد معالجات الأوامر
def setup_handlers():
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mypoints", my_points))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("addpoints", add_points_for_platform))

# 13. الدالة الرئيسية
async def main():
    setup_handlers()
    
    try:
        await setup_webhook()
        await app.initialize()
        await app.start()
        await run_server()
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot is shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
