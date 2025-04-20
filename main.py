from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import sqlite3
import os
import logging
from datetime import datetime
from contextlib import contextmanager

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
    """تهيئة الجداول مع التعديلات اللازمة"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # إنشاء جدول المستخدمين أولاً
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # إنشاء جدول الإحالات مع الأسماء الصحيحة للأعمدة
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referred_by INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL,
                referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (referred_by, referred_user_id),
                FOREIGN KEY (referred_by) REFERENCES users(user_id),
                FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
            )
        """)
        
        conn.commit()
        logger.info("تم تهيئة جداول قاعدة البيانات بنجاح")

# تهيئة قاعدة البيانات عند التشغيل
init_db()

async def leaderboard(update: Update, context: CallbackContext) -> None:
    """لوحة المتصدرين مع الاستعلام الصحيح"""
    user = update.effective_user
    logger.info(f"طلب لوحة المتصدرين من المستخدم {user.id}")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # الاستعلام المعدل باستخدام الأسماء الصحيحة للأعمدة
            cursor.execute('''
                SELECT 
                    r.referred_by as referrer_id,
                    u.username,
                    u.first_name,
                    COUNT(*) as total 
                FROM referrals r
                LEFT JOIN users u ON r.referred_by = u.user_id
                GROUP BY r.referred_by
                ORDER BY total DESC 
                LIMIT 10
            ''')
            
            top_referrers = cursor.fetchall()
            
            if not top_referrers:
                await update.message.reply_text("لا توجد إحالات بعد. كن أول من يجلب أعضاء جدد!")
                return

            message = "🏆 <b>قائمة المتصدرين في الإحالات</b> 🏆\n\n"
            for idx, row in enumerate(top_referrers, start=1):
                rank_emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"#{idx}"
                username = f"@{row['username']}" if row['username'] else row['first_name'] or f"المستخدم #{row['referrer_id']}"
                
                message += f"{rank_emoji} {username} - {row['total']} إحالة\n"
            
            # إضافة ترتيب المستخدم الحالي
            cursor.execute('''
                SELECT COUNT(*) as user_total 
                FROM referrals 
                WHERE referred_by = ?
            ''', (user.id,))
            
            user_total = cursor.fetchone()['user_total']
            if user_total > 0 and not any(row['referrer_id'] == user.id for row in top_referrers):
                message += f"\n🔹 ترتيبك: {user_total} إحالة"
            
            await update.message.reply_text(message, parse_mode='HTML')
            
    except sqlite3.Error as e:
        logger.error(f"خطأ في قاعدة البيانات: {e}")
        await update.message.reply_text("حدث خطأ فني. يرجى المحاولة لاحقاً.")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")
        await update.message.reply_text("حدث خطأ غير متوقع. يرجى إبلاغ الإدارة.")

async def handle_referral(update: Update, context: CallbackContext) -> None:
    """معالجة الإحالات مع التعديلات اللازمة"""
    user = update.effective_user
    args = context.args
    
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        
        if referrer_id == user.id:
            await update.message.reply_text("⚠️ لا يمكنك استخدام رابط الإحالة الخاص بك!")
            return
            
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # تسجيل المستخدم الجديد
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                """, (user.id, user.username, user.first_name, user.last_name))
                
                # التحقق من عدم تكرار الإحالة
                cursor.execute("""
                    SELECT 1 FROM referrals 
                    WHERE referred_by = ? AND referred_user_id = ?
                """, (referrer_id, user.id))
                
                if cursor.fetchone():
                    await update.message.reply_text("تم تسجيل إحالتك مسبقاً! شكراً لك.")
                else:
                    # تسجيل الإحالة الجديدة
                    cursor.execute("""
                        INSERT INTO referrals (referred_by, referred_user_id)
                        VALUES (?, ?)
                    """, (referrer_id, user.id))
                    conn.commit()
                    
                    logger.info(f"تم تسجيل إحالة جديدة: {referrer_id} أحال {user.id}")
                    
                    # إرسال إشعار للمحيل
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 تم تسجيل إحالة جديدة بواسطة {user.first_name or 'مستخدم جديد'}!"
                        )
                    except Exception as e:
                        logger.warning(f"لا يمكن إرسال إشعار للمحيل: {e}")
                    
                    await update.message.reply_text(
                        f"شكراً لتسجيلك عبر إحالة المستخدم {get_user_display_name(referrer_id)}!"
                    )
        except sqlite3.Error as e:
            logger.error(f"خطأ في قاعدة البيانات: {e}")
            await update.message.reply_text("حدث خطأ فني. يرجى المحاولة لاحقاً.")
        except Exception as e:
            logger.error(f"خطأ غير متوقع: {e}")
            await update.message.reply_text("حدث خطأ غير متوقع. يرجى إبلاغ الإدارة.")
    
    await start(update, context)

def get_user_display_name(user_id: int) -> str:
    """الحصول على اسم مستخدم للعرض"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT username, first_name 
                FROM users 
                WHERE user_id = ?
            """, (user_id,))
            user = cursor.fetchone()
            return f"@{user['username']}" if user and user['username'] else f"المستخدم #{user_id}"
    except Exception as e:
        logger.error(f"خطأ في جلب اسم المستخدم: {e}")
        return f"المستخدم #{user_id}"

# ... (بقية الدوال تبقى كما هي)

def main():
    """تشغيل البوت"""
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("لم يتم تعيين BOT_TOKEN!")
        return

    try:
        app = Application.builder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", handle_referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        # ... (إضافة بقية المعالجات)
        
        logger.info("بدأ البوت في الاستماع للتحديثات...")
        app.run_polling()
        
    except Exception as e:
        logger.critical(f"تعطل البوت: {e}")

if __name__ == "__main__":
    main()
