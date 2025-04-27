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

# 1. دوال اتصال قاعدة البيانات
def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

def drop_all_tables():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            c.execute("""
                DROP TABLE IF EXISTS referrals CASCADE;
                DROP TABLE IF EXISTS users CASCADE;
            """)
            conn.commit()
            print("✅ تم حذف الجداول القديمة بنجاح")
            return True
    except Exception as e:
        print(f"❌ خطأ في حذف الجداول: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def create_tables():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            c.execute("""
                CREATE TABLE referrals (
                    id SERIAL PRIMARY KEY,
                    referred_user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    referred_by BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (referred_user_id)
                )
            """)
            
            c.execute("""
                CREATE INDEX idx_referrals_by ON referrals(referred_by)
            """)
            
            conn.commit()
            print("✅ تم إنشاء الجداول بنجاح")
            return True
    except Exception as e:
        print(f"❌ خطأ في إنشاء الجداول: {e}")
        if conn:
            conn.rollback()
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
        print(f"❌ خطأ في التحقق من المستخدم: {e}")
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
        print(f"❌ خطأ في إضافة مستخدم: {e}")
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
                print(f"✅ تم تسجيل إحالة: {referred_user_id} بواسطة {referred_by}")
                return True
        return False
    except Exception as e:
        print(f"❌ خطأ في تسجيل الإحالة: {e}")
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
        print(f"❌ خطأ في جلب المتصدرين: {e}")
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
        print(f"❌ خطأ في جلب الرصيد: {e}")
        return None
    finally:
        if conn:
            conn.close()

# 3. دوال أوامر البوت
async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    print(f"📩 بدء تشغيل من {user.username or user.id}")
    
    if not add_user(user.id, user.username):
        await update.message.reply_text("⚠️ حدث خطأ في التسجيل")
        return
    
    # معالجة رابط الإحالة
    if context.args and context.args[0].isdigit():
        referral_id = int(context.args[0])
        if referral_id != user.id:
            if add_referral(user.id, referral_id):
                await update.message.reply_text("🎉 تم تسجيل إحالتك بنجاح وحصلت على 10 نقاط!")
            else:
                print(f"⚠️ فشل في تسجيل إحالة من {user.id} إلى {referral_id}")
    
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
        f"🔗 رابط الإحالة الخاص بك:\n{link}\n\n"
        f"💰 رصيدك الحالي: {balance} نقطة\n"
        "ستحصل على 10 نقاط لكل صديق ينضم عبر هذا الرابط!"
    )

async def leaderboard(update: Update, context: CallbackContext):
    leaderboard_data = get_leaderboard()
    if not leaderboard_data:
        await update.message.reply_text("🏆 لا يوجد متصدرين بعد!")
        return
    
    text = "🏆 أفضل 10 لاعبين:\n\n"
    for i, (username, referral_count, balance) in enumerate(leaderboard_data, 1):
        text += f"{i}. {username or 'مجهول'} - {referral_count} إحالة - {balance} نقطة\n"
    
    text += "\n🔗 استخدم /referral لزيادة نقاطك!"
    await update.message.reply_text(text)

async def balance(update: Update, context: CallbackContext):
    user = update.message.from_user
    balance = get_user_balance(user.id)
    
    if balance is None:
        await update.message.reply_text("⚠️ حدث خطأ في جلب الرصيد")
        return
    
    await update.message.reply_text(
        f"💰 رصيدك الحالي: {balance} نقطة\n\n"
        "🔗 استخدم /referral لكسب المزيد من النقاط!"
    )

# 4. الدالة الرئيسية
def main():
    print("🚀 بدء تشغيل البوت...")
    
    if not TOKEN or not DATABASE_URL:
        print("❌ يرجى تعيين المتغيرات البيئية")
        return
    
    # إعادة إنشاء الجداول للتأكد من الهيكل الصحيح
    if not drop_all_tables() or not create_tables():
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
