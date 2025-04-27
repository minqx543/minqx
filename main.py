from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import psycopg2
import os
from dotenv import load_dotenv
import logging

# تحميل المتغيرات البيئية
load_dotenv()

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

class Database:
    @staticmethod
    def get_connection():
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception as e:
            logger.error(f"{EMOJI['error']} خطأ في الاتصال بقاعدة البيانات: {e}")
            return None

    @staticmethod
    def init_db():
        conn = None
        try:
            conn = Database.get_connection()
            if not conn:
                return False
                
            with conn.cursor() as cursor:
                # إنشاء جدول المستخدمين
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        balance INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        welcome_bonus_received BOOLEAN DEFAULT FALSE
                    )
                """)
                
                # إنشاء جدول الإحالات - تم تصحيح الخطأ هنا بإضافة القوس الناقص
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS referrals (
                        id SERIAL PRIMARY KEY,
                        referred_user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                        referred_by BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (referred_user_id)
                    )
                """)
                
                # إنشاء فهرس لتحسين الأداء
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_referrals_by ON referrals(referred_by)
                """)
                
                conn.commit()
                logger.info(f"{EMOJI['confetti']} تم تهيئة قاعدة البيانات بنجاح")
                return True
        except Exception as e:
            logger.error(f"{EMOJI['error']} خطأ في تهيئة قاعدة البيانات: {e}")
            return False
        finally:
            if conn:
                conn.close()

    # باقي دوال الفئة Database تبقى كما هي...
    @staticmethod
    def user_exists(user_id):
        conn = None
        try:
            conn = Database.get_connection()
            if not conn:
                return False
                
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"{EMOJI['error']} خطأ في التحقق من المستخدم: {e}")
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def add_user(user_id, username):
        conn = None
        try:
            conn = Database.get_connection()
            if not conn:
                return False
                
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (user_id, username)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET username = EXCLUDED.username
                    RETURNING welcome_bonus_received
                """, (user_id, username))
                
                result = cursor.fetchone()
                welcome_bonus_received = result[0] if result else True
                conn.commit()
                
                if not welcome_bonus_received:
                    cursor.execute("""
                        UPDATE users 
                        SET balance = balance + 100,
                            welcome_bonus_received = TRUE
                        WHERE user_id = %s
                    """, (user_id,))
                    conn.commit()
                return True
        except Exception as e:
            logger.error(f"{EMOJI['error']} خطأ في إضافة مستخدم: {e}")
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def add_referral(referred_user_id, referred_by):
        conn = None
        try:
            conn = Database.get_connection()
            if not conn:
                return False
                
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM referrals WHERE referred_user_id = %s", (referred_user_id,))
                if cursor.fetchone():
                    return False
                    
                if not Database.user_exists(referred_by):
                    return False
                    
                cursor.execute("""
                    INSERT INTO referrals (referred_user_id, referred_by)
                    VALUES (%s, %s)
                    RETURNING id
                """, (referred_user_id, referred_by))
                
                if cursor.fetchone():
                    cursor.execute("""
                        UPDATE users 
                        SET balance = balance + 10 
                        WHERE user_id = %s
                    """, (referred_by,))
                    conn.commit()
                    logger.info(f"{EMOJI['confetti']} تم تسجيل إحالة: {referred_user_id} بواسطة {referred_by}")
                    return True
            return False
        except Exception as e:
            logger.error(f"{EMOJI['error']} خطأ في تسجيل الإحالة: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_leaderboard():
        conn = None
        try:
            conn = Database.get_connection()
            if not conn:
                return None
                
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        u.user_id,
                        u.username, 
                        (SELECT COUNT(*) FROM referrals r WHERE r.referred_by = u.user_id) as referral_count,
                        u.balance
                    FROM users u
                    ORDER BY referral_count DESC, u.balance DESC
                    LIMIT 10
                """)
                results = cursor.fetchall()
                return [(username or 'مجهول', count or 0, balance or 0) for user_id, username, count, balance in results]
        except Exception as e:
            logger.error(f"{EMOJI['error']} خطأ في جلب المتصدرين: {e}")
            return None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_balance(user_id):
        conn = None
        try:
            conn = Database.get_connection()
            if not conn:
                return None
                
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"{EMOJI['error']} خطأ في جلب الرصيد: {e}")
            return None
        finally:
            if conn:
                conn.close()

# باقي الدوال والأوامر تبقى كما هي...
async def start(update: Update, context: CallbackContext):
    try:
        user = update.message.from_user
        logger.info(f"{EMOJI['user']} بدء تشغيل من {user.username or user.id}")
        
        is_new_user = not Database.user_exists(user.id)
        
        if not Database.add_user(user.id, user.username):
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
                if Database.add_referral(user.id, referral_id):
                    await update.message.reply_text(f"{EMOJI['confetti']} تم تسجيل إحالتك بنجاح وحصلت على {EMOJI['point']}10 نقاط!")
        
        welcome_msg = f"""
{EMOJI['welcome']} *مرحباً {user.username or 'صديقي العزيز'}!* {EMOJI['welcome']}

{EMOJI['user']} *اسمك:* {user.first_name or 'لاعب جديد'}
{EMOJI['id']} *رقمك:* `{user.id}`

{EMOJI['confetti']} *لقد حصلت على 100 نقطة ترحيبية!*

{EMOJI['link']} استخدم /referral لدعوة الأصدقاء
{EMOJI['leaderboard']} استخدم /leaderboard لرؤية المتصدرين
{EMOJI['balance']} استخدم /balance لمعرفة رصيدك
"""
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"{EMOJI['error']} خطأ في أمر start: {e}")
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ غير متوقع. يرجى المحاولة لاحقًا.")

async def leaderboard(update: Update, context: CallbackContext):
    try:
        leaderboard_data = Database.get_leaderboard()
        
        if not leaderboard_data:
            await update.message.reply_text(f"{EMOJI['leaderboard']} لا يوجد بيانات متاحة حالياً!")
            return
        
        if all(count == 0 and balance == 0 for _, count, balance in leaderboard_data):
            await update.message.reply_text(f"{EMOJI['leaderboard']} لا يوجد نشاط كافي لعرض المتصدرين بعد!")
            return
        
        leaderboard_text = f"{EMOJI['leaderboard']} *أفضل 10 لاعبين:*\n\n"
        
        for i, (username, referral_count, balance) in enumerate(leaderboard_data, 1):
            medal = EMOJI['medal'][i-1] if i <= 3 else f"{i}."
            leaderboard_text += (
                f"{medal} *{username}*\n"
                f"   {EMOJI['point']} {referral_count} إحالة\n"
                f"   {EMOJI['balance']} {balance} نقطة\n\n"
            )
        
        leaderboard_text += f"{EMOJI['link']} استخدم /referral لزيادة نقاطك!"
        await update.message.reply_text(leaderboard_text, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"{EMOJI['error']} خطأ في أمر leaderboard: {e}")
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ في جلب بيانات المتصدرين.")

async def referral(update: Update, context: CallbackContext):
    try:
        user = update.message.from_user
        link = f"https://t.me/MissionxX_bot?start={user.id}"
        balance = Database.get_balance(user.id) or 0
        
        referral_msg = f"""
{EMOJI['link']} *رابط الإحالة الخاص بك:*
`{link}`

{EMOJI['balance']} *رصيدك الحالي:* {balance} {EMOJI['point']}

{EMOJI['confetti']} *معلومات الإحالة:*
- ستحصل على {EMOJI['point']}10 نقاط لكل صديق ينضم عبر الرابط
- كلما زاد عدد الإحالات، ارتفع ترتيبك في لوحة المتصدرين {EMOJI['leaderboard']}
"""
        await update.message.reply_text(referral_msg, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"{EMOJI['error']} خطأ في أمر referral: {e}")
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ في إنشاء رابط الإحالة.")

async def balance(update: Update, context: CallbackContext):
    try:
        user = update.message.from_user
        balance = Database.get_balance(user.id)
        
        if balance is None:
            await update.message.reply_text(f"{EMOJI['error']} حدث خطأ في جلب الرصيد")
            return
        
        balance_msg = f"""
{EMOJI['balance']} *رصيدك الحالي:* {balance} {EMOJI['point']}

{EMOJI['link']} استخدم /referral لكسب المزيد من النقاط
{EMOJI['leaderboard']} استخدم /leaderboard لرؤية ترتيبك
"""
        await update.message.reply_text(balance_msg, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"{EMOJI['error']} خطأ في أمر balance: {e}")
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ في جلب الرصيد.")

async def error_handler(update: object, context: CallbackContext) -> None:
    error = context.error
    logger.error(f"{EMOJI['error']} حدث خطأ: {error}", exc_info=True)
    
    if update and hasattr(update, 'message'):
        try:
            await update.message.reply_text(
                f"{EMOJI['error']} حدث خطأ غير متوقع. يرجى المحاولة لاحقًا.\n\n"
                f"تفاصيل الخطأ: {str(error)}"
            )
        except Exception as e:
            logger.error(f"{EMOJI['error']} فشل في إرسال رسالة الخطأ: {e}")

def main():
    logger.info(f"{EMOJI['welcome']} بدء تشغيل البوت...")
    
    if not TOKEN or not DATABASE_URL:
        logger.error(f"{EMOJI['error']} يرجى تعيين المتغيرات البيئية (TELEGRAM_TOKEN و DATABASE_URL)")
        return
    
    if not Database.init_db():
        logger.error(f"{EMOJI['error']} فشل في تهيئة قاعدة البيانات")
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
        
        logger.info(f"{EMOJI['confetti']} البوت يعمل الآن...")
        app.run_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"{EMOJI['error']} خطأ في التشغيل الرئيسي: {e}")
    finally:
        logger.info(f"{EMOJI['error']} إيقاف البوت...")

if __name__ == "__main__":
    main()
