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
        
        # جدول المستخدمين (يجب أن يكون أول جدول ينشأ بسبب العلاقات)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول المهام
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_name TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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
        
        conn.commit()
        logger.info("تم تهيئة جداول قاعدة البيانات بنجاح")

# تهيئة قاعدة البيانات عند التشغيل
init_db()

async def start(update: Update, context: CallbackContext) -> None:
    """معالجة أمر /start"""
    user = update.effective_user
    logger.info(f"مستخدم {user.id} ({user.first_name}) قام بتشغيل البوت")
    
    # تسجيل المستخدم في قاعدة البيانات
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user.id, user.username, user.first_name, user.last_name))
            conn.commit()
    except Exception as e:
        logger.error(f"خطأ في تسجيل المستخدم: {e}")
    
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
        "🌐 <b>روابطنا الرسمية:</b>\n\n"
        "🔹 <a href='https://t.me/MissionX_offici'>قناة التليجرام</a>\n"
        "🔹 <a href='https://youtube.com/@missionx_offici'>يوتيوب</a>\n"
        "🔹 <a href='https://www.tiktok.com/@missionx_offici'>تيك توك</a>\n"
        "🔹 <a href='https://x.com/MissionX_Offici'>تويتر (X)</a>\n"
        "🔹 <a href='https://www.facebook.com/share/19AMU41hhs/'>فيسبوك</a>\n"
        "🔹 <a href='https://www.instagram.com/missionx_offici'>إنستجرام</a>\n\n"
        "تابعنا على جميع المنصات لمزيد من المحتوى الحصري!"
    )
    await update.message.reply_text(platform_links, 
                                  disable_web_page_preview=True,
                                  parse_mode='HTML')

async def referral(update: Update, context: CallbackContext) -> None:
    """إنشاء وعرض رابط الإحالة"""
    user = update.effective_user
    referral_link = f"https://t.me/MissionxX_bot?start={user.id}"
    
    logger.info(f"مستخدم {user.id} طلب رابط الإحالة")
    
    referral_message = (
        "🎯 <b>رابط الإحالة الخاص بك:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        "شارك هذا الرابط مع أصدقائك واحصل على نقاط عند انضمامهم!\n"
        "كلما أحلت المزيد من الأصدقاء، ارتفع ترتيبك في لوحة المتصدرين 🏆"
    )
    await update.message.reply_text(referral_message, parse_mode='HTML')

async def leaderboard(update: Update, context: CallbackContext) -> None:
    """عرض لوحة المتصدرين للإحالات"""
    user = update.effective_user
    logger.info(f"مستخدم {user.id} طلب لوحة المتصدرين")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # استعلام أكثر قوة مع التعامل مع القيم الفارغة
            cursor.execute('''
                SELECT 
                    r.referrer_id,
                    COALESCE(u.username, '') as username,
                    COALESCE(u.first_name, '') as first_name,
                    COUNT(*) as total 
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

            message = "🏆 <b>قائمة المتصدرين في الإحالات</b> 🏆\n\n"
            for idx, row in enumerate(top_referrers, start=1):
                rank_emoji = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"<b>#{idx}</b>"
                
                # عرض اسم المستخدم بأفضل طريقة متاحة
                user_display = f"@{row['username']}" if row['username'] else row['first_name'] or f"المستخدم #{row['referrer_id']}"
                
                message += f"{rank_emoji} {user_display} - {row['total']} إحالة\n"
            
            # إضافة ترتيب المستخدم الحالي
            cursor.execute('''
                SELECT COUNT(*) as user_total 
                FROM referrals 
                WHERE referrer_id = ?
            ''', (user.id,))
            
            user_result = cursor.fetchone()
            user_total = user_result['user_total'] if user_result else 0
            
            if user_total > 0:
                message += f"\n🔹 <b>ترتيبك:</b> {user_total} إحالة"
            
            await update.message.reply_text(message, parse_mode='HTML')
            
    except sqlite3.Error as db_error:
        logger.error(f"خطأ في قاعدة البيانات: {db_error}")
        await update.message.reply_text("حدث خطأ فني أثناء جلب البيانات. يرجى المحاولة لاحقاً.")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")
        await update.message.reply_text("حدث خطأ غير متوقع. يرجى إبلاغ الإدارة.")

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
                        referrals_count = get_user_referrals_count(referrer_id)
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 تهانينا! قام {user.first_name or 'مستخدم جديد'} بالتسجيل عبر رابط الإحالة الخاص بك!\n"
                                 f"إجمالي إحالاتك الآن: {referrals_count}",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.warning(f"لا يمكن إرسال إشعار للمحيل: {e}")
                    
                    await update.message.reply_text(
                        f"شكراً لتسجيلك عبر إحالة المستخدم {get_user_display_name(referrer_id)}!\n\n"
                        "استخدم /help لمعرفة المزيد عن كيفية استخدام البوت.",
                        parse_mode='HTML'
                    )
        except sqlite3.Error as db_error:
            logger.error(f"خطأ في قاعدة البيانات أثناء معالجة الإحالة: {db_error}")
            await update.message.reply_text("حدث خطأ فني. يرجى المحاولة لاحقاً.")
        except Exception as e:
            logger.error(f"خطأ غير متوقع أثناء معالجة الإحالة: {e}")
            await update.message.reply_text("حدث خطأ غير متوقع. يرجى إبلاغ الإدارة.")
    
    await start(update, context)

def get_user_referrals_count(user_id: int) -> int:
    """الحصول على عدد إحالات مستخدم"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM referrals 
                WHERE referrer_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            return result['count'] if result else 0
    except Exception as e:
        logger.error(f"خطأ في جلب عدد الإحالات للمستخدم {user_id}: {e}")
        return 0

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
            
            if user:
                if user['username']:
                    return f"@{user['username']}"
                elif user['first_name']:
                    return user['first_name']
            return f"المستخدم #{user_id}"
    except Exception as e:
        logger.error(f"خطأ في جلب اسم العرض للمستخدم {user_id}: {e}")
        return f"المستخدم #{user_id}"

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger
