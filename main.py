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

# 2. دوال التعامل مع قاعدة البيانات
def user_exists(user_id):
    """تحقق من وجود مستخدم في قاعدة البيانات"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            c.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
            return c.fetchone() is not None
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في التحقق من المستخدم: {e}")
        return False
    finally:
        if conn:
            conn.close()

def add_user(user_id, username):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO users (user_id, username)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET username = EXCLUDED.username
            """, (user_id, username))
            conn.commit()
            return True
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في إضافة مستخدم: {e}")
        return False
    finally:
        if conn:
            conn.close()

def add_referral(referred_user_id, referred_by):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            # تحقق من عدم وجود إحالة سابقة لنفس المستخدم
            c.execute("SELECT 1 FROM referrals WHERE referred_user_id = %s", (referred_user_id,))
            if c.fetchone():
                return False
                
            # تحقق من وجود المستخدم المحيل
            if not user_exists(referred_by):
                return False
                
            # تسجيل الإحالة الجديدة
            c.execute("""
                INSERT INTO referrals (referred_user_id, referred_by)
                VALUES (%s, %s)
                RETURNING id
            """, (referred_user_id, referred_by))
            
            if c.fetchone():
                # زيادة رصيد المحيل
                c.execute("""
                    UPDATE users 
                    SET balance = balance + 10 
                    WHERE user_id = %s
                """, (referred_by,))
                conn.commit()
                print(f"{EMOJI['confetti']} تم تسجيل إحالة: {referred_user_id} بواسطة {referred_by}")
                return True
        return False
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في تسجيل الإحالة: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_leaderboard():
    """جلب بيانات المتصدرين مع التأكد من حساب الإحالات بشكل صحيح"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor() as c:
            c.execute("""
                SELECT 
                    u.username, 
                    COUNT(r.id) as referral_count,
                    u.balance
                FROM users u
                LEFT JOIN referrals r ON u.user_id = r.referred_by
                GROUP BY u.user_id, u.username, u.balance
                ORDER BY referral_count DESC, u.balance DESC
                LIMIT 10
            """)
            results = c.fetchall()
            # تحويل None إلى 0 في عدد الإحالات
            return [(username, count or 0, balance) for username, count, balance in results]
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في جلب المتصدرين: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_balance(user_id):
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor() as c:
            c.execute("""
                SELECT balance FROM users WHERE user_id = %s
            """, (user_id,))
            result = c.fetchone()
            return result[0] if result else 0
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في جلب الرصيد: {e}")
        return None
    finally:
        if conn:
            conn.close()

# 3. دوال أوامر البوت
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

async def error_handler(update: object, context: CallbackContext) -> None:
    """معالج الأخطاء العام"""
    print(f"{EMOJI['error']} حدث خطأ: {context.error}")
    if update and hasattr(update, 'message'):
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ غير متوقع. يرجى المحاولة لاحقًا.")

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
        # إنشاء تطبيق البوت مع إعدادات خاصة لمنع التعارض
        app = Application.builder() \
            .token(TOKEN) \
            .concurrent_updates(True) \  # السماح بمعالجة التحديثات بشكل متوازي
            .build()
        
        # إضافة معالج الأخطاء
        app.add_error_handler(error_handler)
        
        # تسجيل الأوامر
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("referral", referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("balance", balance))
        
        print(f"{EMOJI['confetti']} البوت يعمل الآن...")
        
        # تشغيل البوت مع إعدادات خاصة لمنع التعارض
        app.run_polling(
            poll_interval=2.0,  # زيادة الفترة بين طلبات التحديث
            timeout=20,  # زيادة مهلة الانتظار
            drop_pending_updates=True  # تجاهل التحديثات القديمة
        )
        
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في التشغيل الرئيسي: {e}")
    finally:
        print(f"{EMOJI['error']} إيقاف البوت...")

if __name__ == "__main__":
    main()
