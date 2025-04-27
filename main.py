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
    'error': '⚠️'
}

# 1. دوال اتصال قاعدة البيانات
def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

def init_database():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    referred_user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    referred_by BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (referred_user_id)
                )
            """)
            
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_referrals_by ON referrals(referred_by)
            """)
            
            conn.commit()
            print(f"{EMOJI['confetti']} تم تهيئة قاعدة البيانات بنجاح")
            return True
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في تهيئة قاعدة البيانات: {e}")
        return False
    finally:
        if conn:
            conn.close()

# ... [ابقاء دوال التعامل مع قاعدة البيانات كما هي] ...

# 3. دوال أوامر البوت مع تحسينات الواجهة
async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    print(f"{EMOJI['user']} بدء تشغيل من {user.username or user.id}")
    
    if not add_user(user.id, user.username):
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ في التسجيل")
        return
    
    # معالجة رابط الإحالة
    if context.args and context.args[0].isdigit():
        referral_id = int(context.args[0])
        if referral_id != user.id:
            if add_referral(user.id, referral_id):
                await update.message.reply_text(f"{EMOJI['confetti']} تم تسجيل إحالتك بنجاح وحصلت على {EMOJI['point']}10 نقاط!")
    
    # رسالة ترحيبية مخصصة
    welcome_message = f"""
{EMOJI['welcome']} *مرحباً {user.username or 'صديقي العزيز'}!* {EMOJI['welcome']}

{EMOJI['user']} *اسمك:* {user.first_name or 'لاعب جديد'}
{EMOJI['id']} *رقمك:* `{user.id}`

{EMOJI['link']} استخدم /referral للحصول على رابط الإحالة
{EMOJI['leaderboard']} استخدم /leaderboard لرؤية المتصدرين
{EMOJI['balance']} استخدم /balance لمعرفة رصيدك

{EMOJI['confetti']} *نتمنى لك تجربة ممتعة مع بوتنا!*
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def leaderboard(update: Update, context: CallbackContext):
    leaderboard_data = get_leaderboard()
    if not leaderboard_data:
        await update.message.reply_text(f"{EMOJI['leaderboard']} لا يوجد متصدرين بعد!")
        return
    
    # إنشاء رسالة المتصدرين بتنسيق جميل
    leaderboard_text = f"{EMOJI['leaderboard']} *أفضل 10 لاعبين:*\n\n"
    
    for i, (username, referral_count, balance) in enumerate(leaderboard_data, 1):
        medal = EMOJI['medal'][i-1] if i <= 3 else f"{i}."
        username_display = username or 'مجهول'
        leaderboard_text += (
            f"{medal} *{username_display}*\n"
            f"   {EMOJI['point']} {referral_count} إحالة\n"
            f"   {EMOJI['balance']} {balance} نقطة\n\n"
        )
    
    leaderboard_text += f"{EMOJI['link']} استخدم /referral لزيادة نقاطك!"
    await update.message.reply_text(leaderboard_text, parse_mode='Markdown')

async def referral(update: Update, context: CallbackContext):
    user = update.message.from_user
    link = f"https://t.me/MissionxX_bot?start={user.id}"
    balance = get_user_balance(user.id) or 0
    
    referral_message = f"""
{EMOJI['link']} *رابط الإحالة الخاص بك:*
`{link}`

{EMOJI['balance']} *رصيدك الحالي:* {balance} {EMOJI['point']}

{EMOJI['confetti']} *معلومات الإحالة:*
- ستحصل على {EMOJI['point']}10 نقاط لكل صديق ينضم عبر الرابط
- كلما زاد عدد الإحالات، ارتفع ترتيبك في لوحة المتصدرين {EMOJI['leaderboard']}
"""
    await update.message.reply_text(referral_message, parse_mode='Markdown')

async def balance(update: Update, context: CallbackContext):
    user = update.message.from_user
    balance = get_user_balance(user.id)
    
    if balance is None:
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ في جلب الرصيد")
        return
    
    balance_message = f"""
{EMOJI['balance']} *رصيدك الحالي:* {balance} {EMOJI['point']}

{EMOJI['link']} استخدم /referral لكسب المزيد من النقاط
{EMOJI['leaderboard']} استخدم /leaderboard لرؤية ترتيبك
"""
    await update.message.reply_text(balance_message, parse_mode='Markdown')

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
        app = Application.builder().token(TOKEN).build()
        
        # إضافة الأوامر
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("referral", referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("balance", balance))
        
        print(f"{EMOJI['confetti']} البوت يعمل الآن...")
        app.run_polling()
        
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في التشغيل الرئيسي: {e}")

if __name__ == "__main__":
    main()
