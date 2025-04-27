from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import psycopg2
import os
from dotenv import load_dotenv

# تحميل المتغيرات البيئية
load_dotenv()

# المتغيرات
TOKEN = os.getenv('TELEGRAM_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

# رموز وإيموجيز للواجهة
EMOJI = {
    'welcome': '✨',
    'user': '👤',
    'id': '🆔',
    'referral': '📨',
    'leaderboard': '🏆',
    'balance': '💰',
    'point': '⭐',
    'medal': ['🥇', '🥈', '🥉', '🎖️', '🎖️', '🎖️', '🎖️', '🎖️', '🎖️', '🎖️'],
    'confetti': '🎉',
    'link': '🔗',
    'error': '⚠️',
    'social': '🌐'
}

# ... (ابقى دوال اتصال قاعدة البيانات كما هي بدون تغيير) ...

# 3. دوال أوامر البوت
async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    print(f"{EMOJI['user']} بدء تشغيل من {user.username or user.id}")
    
    is_new_user = not user_exists(user.id)
    
    if not add_user(user.id, user.username):
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ في التسجيل")
        return
    
    if is_new_user:
        await update.message.reply_text(
            f"{EMOJI['confetti']} مبروك! لقد حصلت على 100 نقطة ترحيبية!",
            parse_mode='Markdown'
        )
    
    if context.args and context.args[0].isdigit():
        referral_id = int(context.args[0])
        if referral_id != user.id:
            if add_referral(user.id, referral_id):
                await update.message.reply_text(f"{EMOJI['confetti']} تم تسجيل إحالتك بنجاح وحصلت على {EMOJI['point']}10 نقاط!")
    
    welcome_message = f"""
{EMOJI['welcome']} *مرحباً {user.username or 'صديقي العزيز'}!* {EMOJI['welcome']}

{EMOJI['user']} *اسمك:* {user.first_name or 'لاعب جديد'}
{EMOJI['id']} *رقمك:* `{user.id}`

{EMOJI['confetti']} *لقد حصلت على 100 نقطة ترحيبية!*

{EMOJI['link']} استخدم /referral لدعوة الأصدقاء
{EMOJI['leaderboard']} استخدم /leaderboard لرؤية المتصدرين
{EMOJI['balance']} استخدم /balance لمعرفة رصيدك
{EMOJI['social']} استخدم /links لرؤية روابطنا على المنصات
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def links(update: Update, context: CallbackContext):
    """عرض روابط المنصات الرسمية"""
    links_message = f"""
{EMOJI['social']} *روابط المنصات الرسمية* {EMOJI['social']}

🔗 [Telegram](https://t.me/MissionX_offici)
🔗 [YouTube](https://youtube.com/@missionx_offici)
🔗 [TikTok](https://www.tiktok.com/@missionx_offici)
🔗 [X (Twitter)](https://x.com/MissionX_Offici)
🔗 [Facebook](https://www.facebook.com/MissionXOffici)
🔗 [Instagram](https://www.instagram.com/missionx_offici)

🎉 تابعنا على جميع المنصات لمزيد من التحديثات!
"""
    await update.message.reply_text(links_message, parse_mode='Markdown', disable_web_page_preview=True)

# ... (ابقى بقية الدوال كما هي بدون تغيير) ...

# 4. الدالة الرئيسية
def main():
    print(f"{EMOJI['welcome']} بدء تشغيل البوت...")
    
    if not TOKEN or not DATABASE_URL:
        print(f"{EMOJI['error']} يرجى تعيين المتغيرات البيئية")
        return
    
    if not init_database():
        print(f"{EMOJI['error']} فشل في تهيئة قاعدة البيانات")
        return
    
    try:
        app = Application.builder() \
            .token(TOKEN) \
            .concurrent_updates(True) \
            .build()
        
        app.add_error_handler(error_handler)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("referral", referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("balance", balance))
        app.add_handler(CommandHandler("links", links))
        
        print(f"{EMOJI['confetti']} البوت يعمل الآن...")
        app.run_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True
        )
        
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في التشغيل الرئيسي: {e}")
    finally:
        print(f"{EMOJI['error']} إيقاف البوت...")

if __name__ == "__main__":
    main()
