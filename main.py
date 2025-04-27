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

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

def check_tables_exist():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        c.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name IN ('users', 'referrals')
        """)
        count = c.fetchone()[0]
        conn.close()
        return count == 2
    except Exception as e:
        print(f"❌ خطأ في التحقق من الجداول: {e}")
        if conn:
            conn.close()
        return False

def create_tables():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        
        # بدء معاملة جديدة
        c.execute("BEGIN;")
        
        # إنشاء جدول users إذا لم يكن موجوداً
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # إنشاء جدول referrals إذا لم يكن موجوداً
        c.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referred_user_id BIGINT NOT NULL,
                referred_by BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referred_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (referred_by) REFERENCES users(user_id) ON DELETE CASCADE,
                UNIQUE (referred_user_id)
            )
        ''')
        
        # إنشاء فهرس إذا لم يكن موجوداً
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_referrals_by ON referrals(referred_by)
        ''')
        
        conn.commit()
        conn.close()
        print("✅ تم إنشاء/تأكيد وجود الجداول بنجاح")
        return True
        
    except Exception as e:
        print(f"❌ خطأ في إنشاء الجداول: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

# ... [بقية الدوال تبقى كما هي بدون تغيير] ...

def main():
    try:
        print("🚀 بدء تشغيل البوت...")
        
        if not TOKEN or not DATABASE_URL:
            print("❌ يرجى تعيين كل من TELEGRAM_TOKEN و DATABASE_URL في ملف .env")
            return
        
        # التحقق من وجود الجداول أو إنشائها
        if not check_tables_exist():
            print("⚠️ الجداول غير موجودة، جاري الإنشاء...")
            if not create_tables():
                print("❌ فشل في إنشاء الجداول، يرجى التحقق من اتصال قاعدة البيانات")
                return
        else:
            print("✅ الجداول موجودة بالفعل")
        
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("referral", referral))
        application.add_handler(CommandHandler("leaderboard", leaderboard))
        application.add_handler(CommandHandler("balance", balance))
        
        print("🤖 البوت يعمل الآن...")
        application.run_polling()
        
    except Exception as e:
        print(f"❌ خطأ في التشغيل الرئيسي: {e}")

if __name__ == '__main__':
    main()
