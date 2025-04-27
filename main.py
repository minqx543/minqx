from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import psycopg2
import os
from dotenv import load_dotenv

# تحميل المتغيرات البيئية من ملف .env
load_dotenv()

# المتغيرات
TOKEN = os.getenv('TELEGRAM_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

# الاتصال بقاعدة البيانات مع معالجة الأخطاء
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

# إنشاء جدول إذا لم يكن موجودًا
def create_db():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    referrals INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()
        print("تم إنشاء الجدول بنجاح أو التأكد من وجوده")
        return True
    except Exception as e:
        print(f"خطأ في إنشاء الجدول: {e}")
        if conn:
            conn.close()
        return False

# تسجيل لاعب جديد
def add_user(user_id, username):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        if not c.fetchone():
            c.execute('INSERT INTO users (id, username) VALUES (%s, %s)', 
                     (user_id, username))
            conn.commit()
            print(f"تم إضافة مستخدم جديد: {username} (ID: {user_id})")
        conn.close()
        return True
    except Exception as e:
        print(f"خطأ في إضافة مستخدم: {e}")
        if conn:
            conn.close()
        return False

# تحديث عدد الإحالات
def update_referrals(user_id):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        c.execute('UPDATE users SET referrals = referrals + 1 WHERE id = %s', 
                 (user_id,))
        conn.commit()
        conn.close()
        print(f"تم تحديث إحالات المستخدم: {user_id}")
        return True
    except Exception as e:
        print(f"خطأ في تحديث الإحالات: {e}")
        if conn:
            conn.close()
        return False

# جلب ترتيب اللاعبين
def get_leaderboard():
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        c = conn.cursor()
        c.execute('SELECT username, referrals FROM users ORDER BY referrals DESC LIMIT 10')
        leaderboard = c.fetchall()
        conn.close()
        print("تم جلب بيانات لوحة المتصدرين بنجاح")
        return leaderboard
    except Exception as e:
        print(f"خطأ في جلب لوحة المتصدرين: {e}")
        if conn:
            conn.close()
        return None

# عند بدء البوت
async def start(update: Update, context: CallbackContext) -> None:
    try:
        user = update.message.from_user
        print(f"تم استقبال أمر start من {user.username} (ID: {user.id})")
        
        if not add_user(user.id, user.username):
            await update.message.reply_text("حدث خطأ في تسجيل بياناتك. يرجى المحاولة لاحقًا.")
            return
            
        message = (
            f'مرحبًا {user.username}!\n'
            'أهلاً بك في اللعبة! نتمنى لك حظًا سعيدًا.\n\n'
            '🎯 الأوامر المتاحة:\n'
            '/start - عرض رسالة الترحيب\n'
            '/referral - الحصول على رابط الإحالة الخاص بك\n'
            '/leaderboard - عرض أفضل 10 لاعبين\n\n'
            'إليك رابط البوت: @MissionxX_bot\n'
            f'🆔 معرفك: {user.id}'
        )
        await update.message.reply_text(message)
    except Exception as e:
        print(f"خطأ في أمر start: {e}")
        await update.message.reply_text("حدث خطأ غير متوقع. يرجى المحاولة لاحقًا.")

# أمر referral
async def referral(update: Update, context: CallbackContext) -> None:
    try:
        user = update.message.from_user
        print(f"تم استقبال أمر referral من {user.username} (ID: {user.id})")
        
        link = f'https://t.me/MissionxX_bot?start={user.id}'
        message = (
            f'🔗 رابط إحالتك الخاص:\n{link}\n\n'
            'عندما ينضم شخص عبر هذا الرابط، ستحصل على نقاط إحالة!'
        )
        await update.message.reply_text(message)
    except Exception as e:
        print(f"خطأ في أمر referral: {e}")
        await update.message.reply_text("حدث خطأ في إنشاء رابط الإحالة. يرجى المحاولة لاحقًا.")

# أمر leaderboard
async def leaderboard(update: Update, context: CallbackContext) -> None:
    try:
        user = update.message.from_user
        print(f"تم استقبال أمر leaderboard من {user.username} (ID: {user.id})")
        
        leaderboard_data = get_leaderboard()
        if not leaderboard_data:
            await update.message.reply_text("لا توجد بيانات متاحة حاليًا.")
            return
            
        leaderboard_text = "🏆 أفضل 10 لاعبين:\n\n"
        for index, (username, referrals) in enumerate(leaderboard_data, start=1):
            leaderboard_text += f'{index}. {username if username else "مجهول"} - عدد الإحالات: {referrals}\n'
        
        leaderboard_text += "\nاستخدم /referral للحصول على رابط الإحالة الخاص بك!"
        await update.message.reply_text(leaderboard_text)
    except Exception as e:
        print(f"خطأ في أمر leaderboard: {e}")
        await update.message.reply_text("حدث خطأ في جلب بيانات اللاعبين. يرجى المحاولة لاحقًا.")

def main():
    try:
        print("🚀 بدء تشغيل البوت...")
        
        # التحقق من وجود التوكن
        if not TOKEN:
            print("❌ لم يتم العثور على TELEGRAM_TOKEN")
            return
            
        if not DATABASE_URL:
            print("❌ لم يتم العثور على DATABASE_URL")
            return
            
        # إعداد البوت
        application = Application.builder().token(TOKEN).build()

        # إنشاء الجدول
        print("⚙️ جاري إنشاء/التأكد من وجود الجدول...")
        if not create_db():
            print("❌ فشل في إنشاء/التأكد من الجدول")
            return

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
