import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from aiohttp import web

# 1. إعدادات قاعدة البيانات
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. نموذج المستخدم
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String)
    points = Column(Integer, default=0)

# 3. إنشاء الجداول
def init_db():
    Base.metadata.create_all(bind=engine)

# 4. متغيرات البيئة
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "DEFAULT_SECRET")
PORT = int(os.environ.get("PORT", 5000))

# 5. إنشاء تطبيق البوت
app = ApplicationBuilder().token(TOKEN).build()

# 6. تهيئة قاعدة البيانات
init_db()

# 7. روابط وإعدادات البوت
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

# 8. أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=username, points=0)
            db.add(user)
            db.commit()
        
        welcome_message = f"🎉 مرحباً @{username} في MINQX!\n\n"
        welcome_message += "💥 لقد انضممت إلى مجتمعنا! استمر في إتمام المهام واحصل على المكافآت.\n\n"
        welcome_message += f"🎉 Welcome @{username} to MINQX!\n\n"
        welcome_message += "💥 You have joined our community! Keep completing tasks and earn rewards.\n\n"
        welcome_message += "\n📱 تابعنا على المنصات التالية:\n"
        for platform, link in platforms.items():
            welcome_message += f"{icons[platform]} {platform}: {link}\n"
        welcome_message += f"\n🌐 لمزيد من المعلومات، قم بزيارة: {site_url}"

        await update.message.reply_photo(avatar_url, caption=welcome_message)
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
    finally:
        db.close()

# 9. إعداد Webhook
async def setup_webhook():
    await app.bot.delete_webhook(drop_pending_updates=True)
    if WEBHOOK_URL:
        await app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/webhook",
            secret_token=SECRET_TOKEN
        )

async def handle_webhook(request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET_TOKEN:
        return web.Response(status=403)
    
    data = await request.json()
    update = Update.de_json(data, app.bot)
    await app.update_queue.put(update)
    return web.Response()

async def create_app():
    app_web = web.Application()
    app_web.router.add_post('/webhook', handle_webhook)
    app_web.router.add_get('/', lambda _: web.Response(text="Bot is running!"))
    return app_web

# 10. تشغيل الخادم
async def run_server():
    app_web = await create_app()
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Bot is running on port {PORT}")
    await asyncio.Event().wait()

# 11. الربط والتشغيل
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("mypoints", my_points))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("addpoints", add_points_for_platform))

async def main():
    await setup_webhook()
    await app.initialize()
    await app.start()
    print("Webhook set up successfully!")
    await run_server()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot is shutting down...")
    finally:
        asyncio.run(app.shutdown())
