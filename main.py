from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import sqlite3
import os
import logging
from datetime import datetime
from contextlib import contextmanager

# إعداد نظام التسجيل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مسار قاعدة البيانات
DB_PATH = os.path.join(os.getcwd(), 'missionx_bot.db')

@contextmanager
def get_db_connection():
    """مدير سياق لإدارة اتصالات قاعدة البيانات"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"خطأ في قاعدة البيانات: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """تهيئة قاعدة البيانات والجداول"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # جدول المهام
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_name TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول الإحالات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (referrer_id, referred_id),
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_id) REFERENCES users(user_id)
            )
        """)
        
        # جدول المستخدمين (مضاف حديثاً)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info("تم تهيئة جداول قاعدة البيانات بنجاح")

# تهيئة قاعدة البيانات عند التشغيل
init_db()

async def start(update: Update, context: CallbackContext) -> None:
    """معالجة أمر /start"""
    user = update.effective_user
    logger.info(f"مستخدم {user.id} ({user.first_name}) قام بتشغيل البوت")
    
    # تسجيل المستخدم في قاعدة البيانات
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """, (user.id, user.username, user.first_name, user.last_name))
        conn.commit()
    
    welcome_message = (
        "مرحباً بك في بوت MissionX! 🚀\n\n"
        "الأوامر المتاحة:\n"
        "/links - روابط منصاتنا الرسمية\n"
        "/referral - الحصول على رابط الإحالة الخاص بك\n"
        "/leaderboard - عرض قائمة المتصدرين في الإحالات\n"
        "/help - عرض المساعدة"
    )
    await update.message.reply_text(welcome_message)

async def links(update: Update, context: CallbackContext) -> None:
    """عرض روابط المنصات"""
    user = update.effective_user
    logger.info(f"مستخدم {user.id} طلب روابط المنصات")
    
    platform_links = (
        "🌐 روابطنا الرسمية:\n\n"
        "🔹 [قناة التليجرام](https://t.me/MissionX_offici)\n"
        "🔹 [يوتيوب](https://youtube.com/@missionx_offici)\n"
        "🔹 [تيك توك](https://www.tiktok.com/@missionx_offici)\n"
        "🔹 [تويتر (X)](https://x.com/MissionX_Offici)\n"
        "🔹 [فيسبوك](https://www.facebook.com/share/19AMU41hhs/)\n"
        "🔹 [إنستجرام](https://www.instagram.com/missionx_offici)\n\n"
        "تابعنا على جميع المنصات لمزيد من المحتوى الحصري!"
    )
    await update.message.reply_text(platform_links, 
                                  disable_web_page_preview=True,
                                  parse_mode='Markdown')

async def referral(update: Update, context: CallbackContext) -> None:
    """إنشاء وعرض رابط الإحالة"""
    user = update.effective_user
    referral_link = f"https://t.me/MissionxX_bot?start={user.id}"
    
    logger.info(f"مستخدم {user.id} طلب رابط الإحالة")
    
    referral_message = (
        f"🎯 رابط الإحالة الخاص بك:\n\n"
        f"`{referral_link}`\n\n"
        "شارك هذا الرابط مع أصدقائك واحصل على نقاط عند انضمامهم!\n"
        "كلما أحلت المزيد من الأصدقاء، ارتفع ترتيبك في لوحة المتصدرين 🏆"
    )
    await update.message.reply_text(referral_message, parse_mode='Markdown')

async def leaderboard(update: Update, context: CallbackContext) -> None:
    """عرض لوحة المتصدرين للإحالات"""
    user = update.effective_user
    logger.info(f"مستخدم {user.id} طلب لوحة المتصدرين")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # جلب أفضل 10 محيلين
            cursor.execute('''
                SELECT r.referrer_id, u.username, u.first_name, COUNT(*) as total 
                FROM referrals r
                LEFT JOIN users u ON r.referrer_id = u.user_id
                GROUP BY r.referrer_id 
                ORDER BY total DESC 
                LIMIT 10
            ''')
            
            top_referrers = cursor.fetchall()
            
            if not top_referrers:
                await update.message.reply_text(
                    "لا توجد إحالات بعد.\n"
                    "كن أول من يجلب أعضاء جدد باستخدام رابط الإحالة الخاص بك (/referral)!"
                )
                return

            message = "🏆 **قائمة المتصدرين في الإحالات** 🏆\n\n"
            for idx, row in enumerate(top_referrers, start=1):
                rank_emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"**#{idx}**"
                username = f"@{row['username']}" if row['username'] else row['first_name'] or f"المستخدم #{row['referrer_id']}"
                
                message += f"{rank_emoji} {username} - {row['total']} إحالة\n"
            
            # إضافة ترتيب المستخدم الحالي إذا لم يكن في القائمة
            cursor.execute('''
                SELECT COUNT(*) as user_total 
                FROM referrals 
                WHERE referrer_id = ?
            ''', (user.id,))
            
            user_total = cursor.fetchone()['user_total']
            if user_total > 0 and not any(row['referrer_id'] == user.id for row in top_referrers):
                message += f"\n🔹 ترتيبك: {user_total} إحالة"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"خطأ في جلب لوحة المتصدرين: {e}")
        await update.message.reply_text("حدث خطأ أثناء جلب بيانات المتصدرين. يرجى المحاولة لاحقاً.")

async def handle_referral(update: Update, context: CallbackContext) -> None:
    """معالجة الإحالات عند استخدام رابط الإحالة"""
    user = update.effective_user
    args = context.args
    
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        
        # منع المستخدم من إحالة نفسه
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
                    WHERE referrer_id = ? AND referred_id = ?
                """, (referrer_id, user.id))
                
                if cursor.fetchone():
                    await update.message.reply_text("تم تسجيل إحالتك مسبقاً! شكراً لك.")
                else:
                    # تسجيل الإحالة الجديدة
                    cursor.execute("""
                        INSERT INTO referrals (referrer_id, referred_id)
                        VALUES (?, ?)
                    """, (referrer_id, user.id))
                    conn.commit()
                    
                    logger.info(f"تم تسجيل إحالة جديدة: {referrer_id} أحال {user.id}")
                    
                    # إرسال إشعار للمحيل
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 تهانينا! قام {user.first_name or 'مستخدم جديد'} بالتسجيل عبر رابط الإحالة الخاص بك!\n"
                                 f"إجمالي إحالاتك الآن: {get_user_referrals_count(referrer_id)}"
                        )
                    except Exception as e:
                        logger.warning(f"لا يمكن إرسال إشعار للمحيل: {e}")
                    
                    await update.message.reply_text(
                        f"شكراً لتسجيلك عبر إحالة المستخدم {get_user_display_name(referrer_id)}!\n\n"
                        "استخدم /help لمعرفة المزيد عن كيفية استخدام البوت."
                    )
        except Exception as e:
            logger.error(f"خطأ في معالجة الإحالة: {e}")
            await update.message.reply_text("حدث خطأ أثناء معالجة إحالتك. يرجى المحاولة لاحقاً.")
    
    await start(update, context)

def get_user_referrals_count(user_id):
    """الحصول على عدد إحالات مستخدم"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?", (user_id,))
        return cursor.fetchone()['count']

def get_user_display_name(user_id):
    """الحصول على اسم مستخدم للعرض"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, first_name FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        return f"@{user['username']}" if user and user['username'] else f"المستخدم #{user_id}"

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("لم يتم تعيين BOT_TOKEN في متغيرات البيئة!")
        raise ValueError("BOT_TOKEN غير موجود")
    
    try:
        application = Application.builder().token(TOKEN).build()
        logger.info("تم تهيئة تطبيق البوت بنجاح")

        # إضافة معالجات الأوامر
        application.add_handler(CommandHandler("start", handle_referral))
        application.add_handler(CommandHandler("links", links))
        application.add_handler(CommandHandler("referral", referral))
        application.add_handler(CommandHandler("leaderboard", leaderboard))
        application.add_handler(CommandHandler("help", start))

        logger.info("بدأ البوت في الاستماع للتحديثات...")
        application.run_polling()
        
    except Exception as e:
        logger.critical(f"خطأ فادح في تشغيل البوت: {e}")
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"انتهى البوت بسبب خطأ: {e}")
