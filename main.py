import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import InputMediaPhoto
from database import SessionLocal, User, init_db

TOKEN = os.environ.get("BOT_TOKEN")

app = ApplicationBuilder().token(TOKEN).build()

# إنشاء الجداول عند التشغيل
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name or "لاعب"

    # إضافة اللاعب إلى قاعدة البيانات إذا لم يكن موجوداً
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        user = User(telegram_id=user_id, username=username, points=0)
        db.add(user)
        db.commit()
    db.close()

    # إرسال صورة الترحيب
    photo_url = "https://github.com/Twqcoin/twq/blob/master/src/default_avatar.jpg.png?raw=true"
    welcome_message = (
        f"🎉 Welcome {first_name} to MINQX!\n"
        "انضم إلى جروبنا الرسمي للمزيد من التحديثات:\n"
        "📢 https://t.me/minqx1official\n"
        "استخدم /points لرؤية نقاطك، و /top لترتيب اللاعبين."
    )
    
    # إرسال الصورة مع الرسالة
    await update.message.reply_photo(photo=photo_url, caption=welcome_message)

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
