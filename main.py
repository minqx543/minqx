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

async def leaderboard(update: Update, context: CallbackContext) -> None:
    """لوحة المتصدرين مع عرض الأسماء بدلاً من الأرقام"""
    user = update.effective_user
    logger.info(f"طلب لوحة المتصدرين من المستخدم {user.id}")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # استعلام لجلب أفضل 10 محيلين مع أسمائهم
            cursor.execute('''
                SELECT 
                    u.user_id,
                    u.username,
                    u.first_name,
                    COUNT(r.referred_user_id) as referral_count
                FROM users u
                JOIN referrals r ON u.user_id = r.referred_by
                GROUP BY u.user_id
                ORDER BY referral_count DESC
                LIMIT 10
            ''')
            
            leaders = cursor.fetchall()
            
            if not leaders:
                await update.message.reply_text("🏆 لوحة المتصدرين فارغة حالياً!")
                return

            message = "🏆 <b>أفضل 10 أعضاء في الإحالات</b> 🏆\n\n"
            for idx, leader in enumerate(leaders, start=1):
                # عرض الاسم بأفضل صورة متاحة
                display_name = f"@{leader['username']}" if leader['username'] else leader['first_name'] or f"المستخدم {leader['user_id']}"
                
                message += f"{get_rank_emoji(idx)} {display_name} - {leader['referral_count']} إحالة\n"
            
            # إضافة ترتيب المستخدم الحالي إذا لم يكن في القائمة
            cursor.execute('''
                SELECT COUNT(*) as user_count 
                FROM referrals 
                WHERE referred_by = ?
            ''', (user.id,))
            
            user_count = cursor.fetchone()['user_count'] or 0
            if user_count > 0:
                message += f"\n📊 <b>ترتيبك الحالي:</b> {user_count} إحالة"
            
            await update.message.reply_text(message, parse_mode='HTML')
            
    except sqlite3.Error as e:
        logger.error(f"خطأ في قاعدة البيانات: {e}")
        await update.message.reply_text("حدث خطأ فني. يرجى المحاولة لاحقاً.")
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {e}")
        await update.message.reply_text("حدث خطأ غير متوقع. يرجى إبلاغ الإدارة.")

def get_rank_emoji(rank: int) -> str:
    """إرجاع إيموجي حسب الترتيب"""
    return {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }.get(rank, f"#{rank}")

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
            
            if user:
                if user['username']:
                    return f"@{user['username']}"
                elif user['first_name']:
                    return user['first_name']
            return f"المستخدم #{user_id}"
    except Exception as e:
        logger.error(f"خطأ في جلب اسم العرض للمستخدم {user_id}: {e}")
        return f"المستخدم #{user_id}"

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
        "كلما أحلت المزيد من الأصدق
