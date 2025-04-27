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

# اتصال قاعدة البيانات مع معالجة الأخطاء
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

# التحقق من هيكل الجدول
def check_table_structure():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        
        # التحقق من وجود الجدول
        c.execute("""
            SELECT EXISTS(
                SELECT * FROM information_schema.tables 
                WHERE table_name='users'
            )
        """)
        table_exists = c.fetchone()[0]
        
        if not table_exists:
            conn.close()
            return False
            
        # التحقق من وجود الأعمدة الأساسية
        c.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' 
            AND column_name IN ('user_id', 'username', 'referrals')
        """)
        columns = {row[0] for row in c.fetchall()}
        required_columns = {'user_id', 'username', 'referrals'}
        
        conn.close()
        return required_columns.issubset(columns)
        
    except Exception as e:
        print(f"❌ خطأ في التحقق من هيكل الجدول: {e}")
        if conn:
            conn.close()
        return False

# إنشاء/إعادة إنشاء الجدول
def create_db():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        
        # حذف الجدول إذا كان موجوداً (اختياري)
        c.execute('DROP TABLE IF EXISTS users')
        
        # إنشاء الجدول بهيكل جديد
        c.execute('''
            CREATE TABLE users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                referrals INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ تم إنشاء جدول users بنجاح")
        return True
    except Exception as e:
        print(f"❌ خطأ في إنشاء الجدول: {e}")
        if conn:
            conn.close()
        return False

# إضافة مستخدم جديد
def add_user(user_id, username):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        if not c.fetchone():
            c.execute('''
                INSERT INTO users (user_id, username) 
                VALUES (%s, %s)
            ''', (user_id, username))
            conn.commit()
            print(f"✅ تم إضافة مستخدم جديد: {username} (ID: {user_id})")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ خطأ في إضافة مستخدم: {e}")
        if conn:
            conn.close()
        return False

# تحديث الإحالات
def update_referrals(user_id):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        c.execute('''
            UPDATE users 
            SET referrals = referrals + 1 
            WHERE user_id = %s
        ''', (user_id,))
        conn.commit()
        conn.close()
        print(f"✅ تم تحديث إحالات المستخدم: {user_id}")
        return True
    except Exception as e:
        print(f"❌ خطأ في تحديث الإحالات: {e}")
        if conn:
            conn.close()
        return False

# جلب لوحة المتصدرين
def get_leaderboard():
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        c = conn.cursor()
        c.execute('''
            SELECT username, referrals 
            FROM users 
            ORDER BY referrals DESC 
            LIMIT 10
        ''')
        leaderboard = c.fetchall()
        conn.close()
        print("✅ تم جلب بيانات المتصدرين بنجاح")
        return leaderboard
    except Exception as e:
        print(f"❌ خطأ في جلب لوحة المتصدرين: {e}")
        if conn:
            conn.close()
        return None

# أمر البدء
async def start(update: Update, context: CallbackContext) -> None:
    try:
        user = update.message.from_user
        print(f"📩 تم استقبال أمر start من {user.username} (ID: {user.id})")
        
        if not add_user(user.id, user.username):
            await update.message.reply_text("⚠️ حدث خطأ في تسجيل بياناتك. يرجى المحاولة لاحقًا.")
            return
            
        message = (
            f"مرحبًا {user.username}! 👋\n\n"
            "🎮 أهلاً بك في بوت الإحالات!\n\n"
            "🔗 استخدم /referral للحصول على رابط الإحالة الخاص بك\n"
            "🏆 استخدم /leaderboard لرؤية أفضل 10 لاعبين\n\n"
            f"🆔 معرفك: {user.id}"
        )
        await update.message.reply_text(message)
    except Exception as e:
        print(f"❌ خطأ في أمر start: {e}")
        await update.message.reply_text("⚠️ حدث خطأ غير متوقع. يرجى المحاولة لاحقًا.")

# أمر الإحالة
async def referral(update: Update, context: CallbackContext) -> None:
    try:
        user = update.message.from_user
        print(f"📩 تم استقبال أمر referral من {user.username} (ID: {user.id})")
        
        link = f'https://t.me/MissionxX_bot?start={user.id}'
        message = (
            f"🔗 رابط إحالتك الخاص:\n\n{link}\n\n"
            "📣 شارك هذا الرابط مع أصدقائك!\n"
            "سيحصل كل من ينضم عبر هذا الرابط على مكافأة 🎁"
        )
        await update.message.reply_text(message)
    except Exception as e:
        print(f"❌ خطأ في أمر referral: {e}")
        await update.message.reply_text("⚠️ حدث خطأ في إنشاء رابط الإحالة. يرجى المحاولة لاحقًا.")

# أمر لوحة المتصدرين
async def leaderboard(update: Update, context: CallbackContext) -> None:
    try:
        user = update.message.from_user
        print(f"📩 تم استقبال أمر leaderboard من {user.username} (ID: {user.id})")
        
        leaderboard_data = get_leaderboard()
        if not leaderboard_data:
            await update.message.reply_text("⚠️ لا توجد بيانات متاحة حالياً.")
            return
            
        leaderboard_text = "🏆 أفضل 10 لاعبين:\n\n"
        for index, (username, referrals) in enumerate(leaderboard_data, start=1):
            leaderboard_text += f"{index}. {username if username else 'مجهول'} - {referrals} إحالة\n"
        
        leaderboard_text += "\n🔗 استخدم /referral لزيادة نقاطك!"
        await update.message.reply_text(leaderboard_text)
    except Exception as e:
        print(f"❌ خطأ في أمر leaderboard: {e}")
        await update.message.reply_text("⚠️ حدث خطأ في جلب بيانات المتصدرين. يرجى المحاولة لاحقًا.")

# الدالة الرئيسية
def main():
    try:
        print("🚀 بدء تشغيل البوت...")
        
        # التحقق من المتغيرات البيئية
        if not TOKEN or not DATABASE_URL:
            print("❌ يرجى تعيين كل من TELEGRAM_TOKEN و DATABASE_URL في ملف .env")
            return
        
        # التحقق من هيكل الجدول
        if not check_table_structure():
            print("⚠️ هيكل الجدول غير صحيح، جاري إعادة الإنشاء...")
            if not create_db():
                print("❌ فشل في إنشاء الجدول، يرجى التحقق من اتصال قاعدة البيانات")
                return
        
        # إعداد البوت
        application = Application.builder().token(TOKEN).build()
        
        # إضافة الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("referral", referral))
        application.add_handler(CommandHandler("leaderboard", leaderboard))
        
        print("🤖 البوت يعمل الآن...")
        application.run_polling()
        
    except Exception as e:
        print(f"❌ خطأ في التشغيل الرئيسي: {e}")

if __name__ == '__main__':
    main()
