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

# اتصال قاعدة البيانات
def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

# التحقق من وجود الجداول
def check_tables_exist():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            c.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name IN ('users', 'referrals')
            """)
            return c.fetchone()[0] == 2
    except Exception as e:
        print(f"❌ خطأ في التحقق من الجداول: {e}")
        return False
    finally:
        if conn:
            conn.close()

# إنشاء الجداول
def create_tables():
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
            return True
    except Exception as e:
        print(f"❌ خطأ في إنشاء الجداول: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# إضافة مستخدم
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
        print(f"❌ خطأ في إضافة مستخدم: {e}")
        return False
    finally:
        if conn:
            conn.close()

# تسجيل إحالة
def add_referral(referred_user_id, referred_by):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO referrals (referred_user_id, referred_by)
                VALUES (%s, %s)
                ON CONFLICT (referred_user_id) DO NOTHING
                RETURNING id
            """, (referred_user_id, referred_by))
            
            if c.fetchone():
                c.execute("""
                    UPDATE users 
                    SET balance = balance + 10 
                    WHERE user_id = %s
                """, (referred_by,))
                conn.commit()
                return True
        return False
    except Exception as e:
        print(f"❌ خطأ في تسجيل الإحالة: {e}")
        return False
    finally:
        if conn:
            conn.close()

# جلب المتصدرين
def get_leaderboard():
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor() as c:
            c.execute("""
                SELECT u.username, COUNT(r.id), u.balance
                FROM users u
                LEFT JOIN referrals r ON u.user_id = r.referred_by
                GROUP BY u.user_id
                ORDER BY COUNT(r.id) DESC, u.balance DESC
                LIMIT 10
            """)
            return c.fetchall()
    except Exception as e:
        print(f"❌ خطأ في جلب المتصدرين: {e}")
        return None
    finally:
        if conn:
            conn.close()

# جلب الرصيد
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
        print(f"❌ خطأ في جلب الرصيد: {e}")
        return None
    finally:
        if conn:
            conn.close()

# تعريف أوامر البوت
async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    print(f"📩 بدء تشغيل من {user.username or user.id}")
    
    if not add_user(user.id, user.username):
        await update.message.reply_text("⚠️ حدث خطأ في التسجيل")
        return
    
    if context.args and context.args[0].isdigit():
        referral_id = int(context.args[0])
        if referral_id != user.id:
            add_referral(user.id, referral_id)
    
    await update.message.reply_text(
        f"مرحباً {user.username or 'عزيزي'}!\n"
        "استخدم /referral للحصول على رابط الإحالة\n"
        "استخدم /leaderboard لرؤية المتصدرين\n"
        "استخدم /balance لمعرفة رصيدك"
    )

async def referral(update: Update, context: CallbackContext):
    user = update.message.from_user
    link = f"https://t.me/MissionxX_bot?start={user.id}"
    balance = get_user_balance(user.id) or 0
    
    await update.message.reply_text(
        f"🔗 رابط الإحالة: {link}\n"
        f"💰 رصيدك: {balance} نقطة\n"
        "ستحصل على 10 نقاط لكل إحالة ناجحة!"
    )

async def leaderboard(update: Update, context: CallbackContext):
    leaderboard = get_leaderboard()
    if not leaderboard:
        await update.message.reply_text("⚠️ لا توجد بيانات متاحة")
        return
    
    text = "🏆 أفضل 10 لاعبين:\n\n"
    for i, (username, count, balance) in enumerate(leaderboard, 1):
        text += f"{i}. {username or 'مجهول'} - {count} إحالة - {balance} نقطة\n"
    
    await update.message.reply_text(text)

async def balance(update: Update, context: CallbackContext):
    user = update.message.from_user
    balance = get_user_balance(user.id)
    
    if balance is None:
        await update.message.reply_text("⚠️ حدث خطأ في جلب الرصيد")
        return
    
    await update.message.reply_text(f"💰 رصيدك الحالي: {balance} نقطة")

# التشغيل الرئيسي
def main():
    print("🚀 بدء تشغيل البوت...")
    
    if not TOKEN or not DATABASE_URL:
        print("❌ يرجى تعيين المتغيرات البيئية")
        return
    
    if not check_tables_exist() and not create_tables():
        print("❌ فشل في إعداد قاعدة البيانات")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("balance", balance))
    
    print("🤖 البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
