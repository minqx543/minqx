from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import psycopg2
import os
from dotenv import load_dotenv
import schedule
import time
import threading
from datetime import datetime, timedelta

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
    'error': '⚠️',
    'gift': '🎁'
}

# 1. دوال اتصال قاعدة البيانات
def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

def init_database():
    conn = None
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_reward_date DATE,
                    welcome_bonus_received BOOLEAN DEFAULT FALSE
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
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS weekly_rewards (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id),
                    reward_amount INTEGER NOT NULL,
                    reward_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rank INTEGER NOT NULL
                )
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
    conn = None
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
    conn = None
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
                RETURNING welcome_bonus_received
            """, (user_id, username))
            
            result = c.fetchone()
            welcome_bonus_received = result[0] if result else True
            conn.commit()
            
            if not welcome_bonus_received:
                # منح المكافأة الترحيبية
                c.execute("""
                    UPDATE users 
                    SET balance = balance + 100,
                        welcome_bonus_received = TRUE
                    WHERE user_id = %s
                """, (user_id,))
                conn.commit()
                
            return True
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في إضافة مستخدم: {e}")
        return False
    finally:
        if conn:
            conn.close()

def add_referral(referred_user_id, referred_by):
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        with conn.cursor() as c:
            c.execute("SELECT 1 FROM referrals WHERE referred_user_id = %s", (referred_user_id,))
            if c.fetchone():
                return False
                
            if not user_exists(referred_by):
                return False
                
            c.execute("""
                INSERT INTO referrals (referred_user_id, referred_by)
                VALUES (%s, %s)
                RETURNING id
            """, (referred_user_id, referred_by))
            
            if c.fetchone():
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
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor() as c:
            c.execute("""
                SELECT 
                    u.user_id,
                    u.username, 
                    (SELECT COUNT(*) FROM referrals r WHERE r.referred_by = u.user_id) as referral_count,
                    u.balance,
                    (SELECT COUNT(*) FROM weekly_rewards wr WHERE wr.user_id = u.user_id) as wins_count
                FROM users u
                ORDER BY referral_count DESC, u.balance DESC
                LIMIT 10
            """)
            results = c.fetchall()
            return [(username or 'مجهول', count or 0, balance or 0, wins or 0) 
                   for user_id, username, count, balance, wins in results]
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في جلب المتصدرين: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_user_balance(user_id):
    conn = None
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

def assign_weekly_rewards():
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        with conn.cursor() as c:
            # حذف الجوائز القديمة
            c.execute("DELETE FROM weekly_rewards WHERE reward_date < NOW() - INTERVAL '30 days'")
            
            # جلب أفضل 3 لاعبين لهذا الأسبوع
            c.execute("""
                SELECT u.user_id, u.username, 
                       COUNT(r.id) as referral_count
                FROM users u
                LEFT JOIN referrals r ON u.user_id = r.referred_by
                WHERE r.created_at >= NOW() - INTERVAL '7 days'
                GROUP BY u.user_id, u.username
                ORDER BY referral_count DESC
                LIMIT 3
            """)
            top_users = c.fetchall()

            rewards = [300, 200, 100]  # نقاط للمراكز 1، 2، 3
            
            for i, (user_id, username, _) in enumerate(top_users):
                # تسجيل الجائزة
                c.execute("""
                    INSERT INTO weekly_rewards (user_id, reward_amount, rank)
                    VALUES (%s, %s, %s)
                """, (user_id, rewards[i], i+1))
                
                # زيادة رصيد اللاعب
                c.execute("""
                    UPDATE users 
                    SET balance = balance + %s,
                        last_reward_date = NOW()
                    WHERE user_id = %s
                """, (rewards[i], user_id))
                
            conn.commit()
            return top_users
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في منح الجوائز الأسبوعية: {e}")
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
    
    if context.args and context.args[0].isdigit():
        referral_id = int(context.args[0])
        if referral_id != user.id:
            if add_referral(user.id, referral_id):
                await update.message.reply_text(f"{EMOJI['confetti']} تم تسجيل إحالتك بنجاح وحصلت على {EMOJI['point']}10 نقاط!")
    
    # التحقق إذا حصل المستخدم على المكافأة الترحيبية
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT welcome_bonus_received FROM users WHERE user_id = %s
            """, (user.id,))
            result = c.fetchone()
            if result and not result[0]:
                await update.message.reply_text(
                    f"{EMOJI['confetti']} مبروك! حصلت على 100 نقطة ترحيبية!",
                    parse_mode='Markdown'
                )
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في التحقق من المكافأة الترحيبية: {e}")
    finally:
        if conn:
            conn.close()
    
    welcome_message = f"""
{EMOJI['welcome']} *مرحباً {user.username or 'صديقي العزيز'}!* {EMOJI['welcome']}

{EMOJI['user']} *اسمك:* {user.first_name or 'لاعب جديد'}
{EMOJI['id']} *رقمك:* `{user.id}`

{EMOJI['gift']} *المكافآت المتاحة:*
- 100 نقطة ترحيبية عند أول استخدام
- 10 نقاط لكل صديق تدعوه
- جوائز أسبوعية لأكثر الأعضاء نشاطاً

{EMOJI['link']} استخدم /referral لدعوة الأصدقاء
{EMOJI['leaderboard']} استخدم /leaderboard لرؤية المتصدرين
{EMOJI['balance']} استخدم /balance لمعرفة رصيدك
{EMOJI['confetti']} استخدم /rewards لمعلومات الجوائز

{EMOJI['confetti']} *نتمنى لك تجربة ممتعة مع بوتنا!*
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def leaderboard(update: Update, context: CallbackContext):
    leaderboard_data = get_leaderboard()
    
    if not leaderboard_data:
        await update.message.reply_text(f"{EMOJI['leaderboard']} لا يوجد بيانات متاحة حالياً!")
        return
    
    if all(count == 0 and balance == 0 for _, count, balance, _ in leaderboard_data):
        await update.message.reply_text(f"{EMOJI['leaderboard']} لا يوجد نشاط كافي لعرض المتصدرين بعد!")
        return
    
    leaderboard_text = f"{EMOJI['leaderboard']} *أفضل 10 لاعبين:*\n\n"
    
    for i, (username, referral_count, balance, wins) in enumerate(leaderboard_data, 1):
        medal = EMOJI['medal'][i-1] if i <= 3 else f"{i}."
        leaderboard_text += (
            f"{medal} *{username}*\n"
            f"   {EMOJI['point']} {referral_count} إحالة\n"
            f"   {EMOJI['balance']} {balance} نقطة\n"
            f"   {EMOJI['gift']} {wins} فوز بالأسبوع\n\n"
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
- المراكز الأولى تحصل على جوائز أسبوعية {EMOJI['gift']}

استخدم /rewards لمعرفة تفاصيل الجوائز الأسبوعية
"""
    await update.message.reply_text(referral_message, parse_mode='Markdown')

async def balance(update: Update, context: CallbackContext):
    user = update.message.from_user
    balance = get_user_balance(user.id)
    
    if balance is None:
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ في جلب الرصيد")
        return
    
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT COUNT(*) FROM weekly_rewards WHERE user_id = %s
            """, (user.id,))
            wins = c.fetchone()[0] or 0
            
            c.execute("""
                SELECT COUNT(*) FROM referrals WHERE referred_by = %s
            """, (user.id,))
            referrals = c.fetchone()[0] or 0
            
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في جلب إحصائيات المستخدم: {e}")
        wins = 0
        referrals = 0
    finally:
        if conn:
            conn.close()
    
    balance_message = f"""
{EMOJI['balance']} *رصيدك الحالي:* {balance} {EMOJI['point']}

{EMOJI['point']} *عدد الإحالات:* {referrals}
{EMOJI['gift']} *عدد الجوائز الأسبوعية:* {wins}

{EMOJI['link']} استخدم /referral لكسب المزيد من النقاط
{EMOJI['leaderboard']} استخدم /leaderboard لرؤية ترتيبك
{EMOJI['confetti']} استخدم /rewards لمعلومات الجوائز
"""
    await update.message.reply_text(balance_message, parse_mode='Markdown')

async def rewards_info(update: Update, context: CallbackContext):
    info_text = f"""
{EMOJI['confetti']} *نظام الجوائز والمكافآت* {EMOJI['confetti']}

{EMOJI['gift']} *المكافآت الحالية:*
- 100 نقطة ترحيبية عند أول استخدام للبوت
- 10 نقاط لكل صديق تدعوه عبر رابط الإحالة

{EMOJI['medal'][0]} *الجوائز الأسبوعية:*
- المركز الأول: 300 نقطة
- المركز الثاني: 200 نقطة
- المركز الثالث: 100 نقطة

{EMOJI['confetti']} *كيف تربح؟*
1. ادعُ أصدقاءك عبر رابط الإحالة (/referral)
2. كلما زاد عدد الإحالات، زادت فرصتك في الفوز
3. يتم حساب النتائج كل يوم أحد

{EMOJI['balance']} استخدم /balance لمعرفة رصيدك
{EMOJI['leaderboard']} استخدم /leaderboard لرؤية المتصدرين
"""
    await update.message.reply_text(info_text, parse_mode='Markdown')

async def error_handler(update: object, context: CallbackContext) -> None:
    print(f"{EMOJI['error']} حدث خطأ: {context.error}")
    if update and hasattr(update, 'message'):
        await update.message.reply_text(f"{EMOJI['error']} حدث خطأ غير متوقع. يرجى المحاولة لاحقًا.")

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)  # التحقق كل دقيقة

# 4. الدالة الرئيسية
def main():
    print(f"{EMOJI['welcome']} بدء تشغيل البوت...")
    
    if not TOKEN or not DATABASE_URL:
        print(f"{EMOJI['error']} يرجى تعيين المتغيرات البيئية")
        return
    
    if not init_database():
        print(f"{EMOJI['error']} فشل في تهيئة قاعدة البيانات")
        return
    
    # جدولة الجوائز الأسبوعية كل يوم أحد الساعة 00:00
    schedule.every().sunday.at("00:00").do(assign_weekly_rewards)
    
    # بدء السكيدولر في ثريد منفصل
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    try:
        app = (Application.builder()
            .token(TOKEN)
            .concurrent_updates(True)
            .build())
        
        app.add_error_handler(error_handler)
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("referral", referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("balance", balance))
        app.add_handler(CommandHandler("rewards", rewards_info))
        
        print(f"{EMOJI['confetti']} البوت يعمل الآن...")
        
        app.run_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True
        )
        
    except Exception as e:
        print(f"{EMOJI['error']} خطأ في التشغيل الرئيسي: {e}")
    finally:
        print(f"{EMOJI['error']} إيقاف البوت...")

if __name__ == "__main__":
    main()
