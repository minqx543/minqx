from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TELEGRAM_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

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
            # إنشاء جدول users مع عمود balance
            c.execute("""
                CREATE TABLE users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # إنشاء جدول referrals
            c.execute("""
                CREATE TABLE referrals (
                    id SERIAL PRIMARY KEY,
                    referred_user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    referred_by BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (referred_user_id)
                )
            """)
            
            # إنشاء فهرس
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

# ... [بقية الدوال تبقى كما هي بدون تغيير] ...

def initialize_database():
    # حذف الجداول القديمة أولاً
    if not drop_all_tables():
        return False
    
    # إنشاء الجداول الجديدة
    if not create_tables():
        return False
    
    return True

def main():
    print("🚀 بدء تشغيل البوت...")
    
    if not TOKEN or not DATABASE_URL:
        print("❌ يرجى تعيين المتغيرات البيئية")
        return
    
    # تهيئة قاعدة البيانات
    if not initialize_database():
        print("❌ فشل في تهيئة قاعدة البيانات")
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
