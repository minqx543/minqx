from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import sqlite3
import os
import logging
from contextlib import contextmanager
from datetime import datetime

# إعداد نظام التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مسار قاعدة البيانات
DB_PATH = os.path.join(os.getcwd(), 'missionx_bot.db')

@contextmanager
def get_db_connection():
    """إدارة اتصالات قاعدة البيانات بشكل آمن"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """تهيئة الجداول مع تحسينات"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referred_by INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL,
                referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(referred_by, referred_user_id),
                FOREIGN KEY (referred_by) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (referred_user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referred_by ON referrals(referred_by)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referred_user ON referrals(referred_user_id)")
        conn.commit()

init_db()

async def update_user_activity(user_id: int):
    """تحديث نشاط المستخدم"""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, last_active)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                last_active=excluded.last_active
            """, (user_id, datetime.now()))
            conn.commit()
    except Exception as e:
        logger.error(f"خطأ في تحديث نشاط المستخدم: {e}")

async def get_user_display_name(user_id: int) -> str:
    """الحصول على اسم مستخدم للعرض"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, first_name, last_name FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            if user:
                if user['username']:
                    return f"@{user['username']}"
                full_name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
                return full_name if full_name else f"المستخدم {user_id}"
    except Exception as e:
        logger.error(f"خطأ في جلب اسم المستخدم: {e}")
    return f"المستخدم {user_id}"

async def start(update: Update, context: CallbackContext) -> None:
    """معالجة أمر /start مع دعم الإحالات"""
    user = update.effective_user
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, last_active)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                last_active=excluded.last_active
            """, (user.id, user.username, user.first_name, user.last_name, datetime.now()))
            
            if context.args and context.args[0].isdigit():
                referrer_id = int(context.args[0])
                if referrer_id != user.id:
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO referrals (referred_by, referred_user_id)
                            VALUES (?, ?)
                        """, (referrer_id, user.id))
                        conn.commit()
                        referrer_name = await get_user_display_name(referrer_id)
                        await update.message.reply_text(
                            f"شكراً لتسجيلك عبر إحالة {referrer_name}! 🎉\n"
                            f"تم تسجيل إحالتك بنجاح."
                        )
                    except sqlite3.Error as e:
                        logger.error(f"خطأ في تسجيل الإحالة: {e}")
        
        await update.message.reply_text(
            "مرحباً بك في بوت MissionX! 🚀\n\n"
            "الأوامر المتاحة:\n"
            "/start - بدء استخدام البوت\n"
            "/links - روابط المنصات\n"
            "/referral - رابط الإحالة الخاص بك\n"
            "/leaderboard - لوحة المتصدرين\n"
            "/help - المساعدة"
        )
    except Exception as e:
        logger.error(f"خطأ في أمر /start: {e}")
        await update.message.reply_text("حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقاً.")

async def leaderboard(update: Update, context: CallbackContext) -> None:
    """عرض لوحة المتصدرين مع تحسينات"""
    await update_user_activity(update.effective_user.id)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    u.user_id,
                    COUNT(r.id) as referral_count
                FROM referrals r
                JOIN users u ON u.user_id = r.referred_by
                GROUP BY r.referred_by
                ORDER BY referral_count DESC
                LIMIT 10
            ''')
            
            leaders = cursor.fetchall()
            
            if not leaders:
                await update.message.reply_text("لا توجد إحالات بعد! كن أول من يجلب أعضاء جدد.")
                return

            message = "🏆 <b>أفضل 10 أعضاء في الإحالات</b> 🏆\n\n"
            for idx, leader in enumerate(leaders, 1):
                user_name = await get_user_display_name(leader['user_id'])
                message += f"{get_rank_emoji(idx)} {user_name} - {leader['referral_count']} إحالة\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"خطأ في لوحة المتصدرين: {e}")
        await update.message.reply_text("حدث خطأ في جلب البيانات. حاول لاحقاً.")

# باقي الدوال (links, referral, help_command) تبقى كما هي بدون تغيير

def main():
    """تشغيل البوت مع معالجة الأخطاء المحسنة"""
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("لم يتم تعيين BOT_TOKEN! يرجى تعيين متغير البيئة.")
        return

    try:
        app = Application.builder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("links", links))
        app.add_handler(CommandHandler("referral", referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("help", help_command))
        
        logger.info("بدأ البوت في الاستماع للتحديثات...")
        app.run_polling()
        
    except Exception as e:
        logger.critical(f"تعطل البوت: {e}")
        raise

if __name__ == "__main__":
    main()
