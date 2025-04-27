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

# التحقق من هيكل الجداول
def check_tables_structure():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        
        # التحقق من وجود الجداول الأساسية
        c.execute("""
            SELECT EXISTS(
                SELECT * FROM information_schema.tables 
                WHERE table_name='users'
            ) AND EXISTS(
                SELECT * FROM information_schema.tables 
                WHERE table_name='referrals'
            )
        """)
        tables_exist = c.fetchone()[0]
        
        if not tables_exist:
            conn.close()
            return False
            
        # التحقق من وجود الأعمدة الأساسية في جدول users
        c.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' 
            AND column_name IN ('user_id', 'username', 'balance')
        """)
        user_columns = {row[0] for row in c.fetchall()}
        required_user_columns = {'user_id', 'username', 'balance'}
        
        # التحقق من وجود الأعمدة الأساسية في جدول referrals
        c.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='referrals' 
            AND column_name IN ('referred_user_id', 'referred_by')
        """)
        referral_columns = {row[0] for row in c.fetchall()}
        required_referral_columns = {'referred_user_id', 'referred_by'}
        
        conn.close()
        return (required_user_columns.issubset(user_columns) and (required_referral_columns.issubset(referral_columns))
        
    except Exception as e:
        print(f"❌ خطأ في التحقق من هيكل الجداول: {e}")
        if conn:
            conn.close()
        return False

# إنشاء/إعادة إنشاء الجداول
def create_tables():
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        
        # بدء معاملة جديدة
        c.execute("BEGIN;")
        
        # حذف الجداول إذا كانت موجودة مع CASCADE لضمان حذف الجداول المرتبطة
        c.execute('DROP TABLE IF EXISTS referrals CASCADE;')
        c.execute('DROP TABLE IF EXISTS users CASCADE;')
        
        # إنشاء جدول users
        c.execute('''
            CREATE TABLE users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # إنشاء جدول referrals
        c.execute('''
            CREATE TABLE referrals (
                id SERIAL PRIMARY KEY,
                referred_user_id BIGINT NOT NULL,
                referred_by BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referred_user_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_by) REFERENCES users(user_id),
                UNIQUE (referred_user_id)  # لمنع تكرار الإحالات لنفس المستخدم
            );
        ''')
        
        # إنشاء فهرس لتحسين أداء الاستعلامات
        c.execute('CREATE INDEX idx_referrals_by ON referrals(referred_by);')
        
        conn.commit()
        conn.close()
        print("✅ تم إنشاء الجداول بنجاح")
        return True
    except Exception as e:
        print(f"❌ خطأ في إنشاء الجداول: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

# إضافة مستخدم جديد
def add_user(user_id, username):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        c.execute('SELECT 1 FROM users WHERE user_id = %s', (user_id,))
        if not c.fetchone():
            c.execute('''
                INSERT INTO users (user_id, username) 
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
            ''', (user_id, username))
            conn.commit()
            print(f"✅ تم إضافة/تحديث مستخدم: {username} (ID: {user_id})")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ خطأ في إضافة مستخدم: {e}")
        if conn:
            conn.close()
        return False

# تسجيل إحالة جديدة
def add_referral(referred_user_id, referred_by):
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        c = conn.cursor()
        
        # إضافة الإحالة
        c.execute('''
            INSERT INTO referrals (referred_user_id, referred_by)
            VALUES (%s, %s)
            ON CONFLICT (referred_user_id) DO NOTHING
            RETURNING id
        ''', (referred_user_id, referred_by))
        
        # إذا تمت الإضافة بنجاح (لم تكن موجودة من قبل)
        if c.fetchone():
            # زيادة رصيد المستخدم الذي قام بالإحالة
            c.execute('''
                UPDATE users 
                SET balance = balance + 10 
                WHERE user_id = %s
            ''', (referred_by,))
            
            conn.commit()
            print(f"✅ تم تسجيل إحالة: {referred_user_id} بواسطة {referred_by}")
            conn.close()
            return True
        
        conn.close()
        return False
    except Exception as e:
        print(f"❌ خطأ في تسجيل الإحالة: {e}")
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
            SELECT u.username, COUNT(r.id) as referral_count, u.balance
            FROM users u
            LEFT JOIN referrals r ON u.user_id = r.referred_by
            GROUP BY u.user_id, u.username, u.balance
            ORDER BY referral_count DESC, u.balance DESC
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

# جلب رصيد المستخدم
def get_user_balance(user_id):
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        c = conn.cursor()
        c.execute('''
            SELECT balance FROM users WHERE user_id = %s
        ''', (user_id,))
        balance = c.fetchone()
        conn.close()
        return balance[0] if balance else 0
    except Exception as e:
        print(f"❌ خطأ في جلب رصيد المستخدم: {e}")
        if conn:
            conn.close()
        return None

# أمر البدء
async def start(update: Update, context: CallbackContext) -> None:
    try:
        user = update.message.from_user
        print(f"📩 تم استقبال أمر start من {user.username} (ID: {user.id})")
        
        # التحقق مما إذا كان هناك رابط إحالة
        referral_id = None
        if context.args and context.args[0].isdigit():
            referral_id = int(context.args[0])
            if referral_id == user.id:
                await update.message.reply_text("⚠️ لا يمكنك استخدام رابط الإحالة الخاص بك!")
                referral_id = None
        
        # إضافة المستخدم الجديد
        if not add_user(user.id, user.username):
            await update.message.reply_text("⚠️ حدث خطأ في تسجيل بياناتك. يرجى المحاولة لاحقًا.")
            return
        
        # إذا كان هناك رابط إحالة صالح
        if referral_id:
            # تأكد من وجود المستخدم الذي قام بالإحالة
            conn = get_db_connection()
            if conn:
                c = conn.cursor()
                c.execute('SELECT 1 FROM users WHERE user_id = %s', (referral_id,))
                if c.fetchone():
                    add_referral(user.id, referral_id)
                conn.close()
        
        message = (
            f"مرحبًا {user.username or 'عزيزي'}! 👋\n\n"
            "🎮 أهلاً بك في بوت الإحالات!\n\n"
            "🔗 استخدم /referral للحصول على رابط الإحالة الخاص بك\n"
            "🏆 استخدم /leaderboard لرؤية أفضل 10 لاعبين\n"
            "💰 استخدم /balance لمعرفة رصيدك\n\n"
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
        balance = get_user_balance(user.id) or 0
        
        message = (
            f"🔗 رابط إحالتك الخاص:\n\n{link}\n\n"
            "📣 شارك هذا الرابط مع أصدقائك!\n\n"
            f"💰 رصيدك الحالي: {balance} نقطة\n"
            "سيحصل كل من ينضم عبر هذا الرابط على مكافأة 🎁\n"
            "وستحصل أنت على 10 نقاط لكل إحالة ناجحة!"
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
        for index, (username, referrals, balance) in enumerate(leaderboard_data, start=1):
            leaderboard_text += f"{index}. {username or 'مجهول'} - {referrals} إحالة - {balance} نقطة\n"
        
        leaderboard_text += "\n🔗 استخدم /referral لزيادة نقاطك!"
        await update.message.reply_text(leaderboard_text)
    except Exception as e:
        print(f"❌ خطأ في أمر leaderboard: {e}")
        await update.message.reply_text("⚠️ حدث خطأ في جلب بيانات المتصدرين. يرجى المحاولة لاحقًا.")

# أمر الرصيد
async def balance(update: Update, context: CallbackContext) -> None:
    try:
        user = update.message.from_user
        print(f"📩 تم استقبال أمر balance من {user.username} (ID: {user.id})")
        
        balance = get_user_balance(user.id)
        if balance is None:
            await update.message.reply_text("⚠️ حدث خطأ في جلب رصيدك.")
            return
            
        message = (
            f"💰 رصيدك الحالي: {balance} نقطة\n\n"
            "🔗 استخدم /referral للحصول على رابط الإحالة الخاص بك\n"
            "📣 كل إحالة ناجحة تحصل على 10 نقاط!"
        )
        await update.message.reply_text(message)
    except Exception as e:
        print(f"❌ خطأ في أمر balance: {e}")
        await update.message.reply_text("⚠️ حدث خطأ في جلب رصيدك. يرجى المحاولة لاحقًا.")

# الدالة الرئيسية
def main():
    try:
        print("🚀 بدء تشغيل البوت...")
        
        # التحقق من المتغيرات البيئية
        if not TOKEN or not DATABASE_URL:
            print("❌ يرجى تعيين كل من TELEGRAM_TOKEN و DATABASE_URL في ملف .env")
            return
        
        # التحقق من هيكل الجداول
        if not check_tables_structure():
            print("⚠️ هيكل الجداول غير صحيح، جاري إعادة الإنشاء...")
            if not create_tables():
                print("❌ فشل في إنشاء الجداول، يرجى التحقق من اتصال قاعدة البيانات")
                return
        
        # إعداد البوت
        application = Application.builder().token(TOKEN).build()
        
        # إضافة الأوامر
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
