from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import sqlite3
import os
import logging
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
    """تهيئة الجداول"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
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

init_db()

async def start(update: Update, context: CallbackContext) -> None:
    """معالجة أمر /start"""
    user = update.effective_user
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user.id, user.username, user.first_name, user.last_name))
    except Exception as e:
        logger.error(f"خطأ في تسجيل المستخدم: {e}")
    
    await update.message.reply_text(
        "مرحباً بك في بوت MissionX! 🚀\n\n"
        "الأوامر المتاحة:\n"
        "/start - بدء استخدام البوت\n"
        "/links - روابط المنصات\n"
        "/referral - رابط الإحالة الخاص بك\n"
        "/leaderboard - لوحة المتصدرين\n"
        "/help - المساعدة"
    )

async def links(update: Update, context: CallbackContext) -> None:
    """عرض روابط المنصات"""
    await update.message.reply_text(
        "🌐 <b>روابطنا الرسمية:</b>\n\n"
        "🔹 <a href='https://t.me/MissionX_offici'>قناة التليجرام</a>\n"
        "🔹 <a href='https://youtube.com/@missionx_offici'>يوتيوب</a>\n"
        "🔹 <a href='https://www.tiktok.com/@missionx_offici'>تيك توك</a>\n"
        "🔹 <a href='https://x.com/MissionX_Offici'>تويتر (X)</a>\n"
        "🔹 <a href='https://www.facebook.com/share/19AMU41hhs/'>فيسبوك</a>\n"
        "🔹 <a href='https://www.instagram.com/missionx_offici'>إنستجرام</a>",
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def referral(update: Update, context: CallbackContext) -> None:
    """إنشاء وعرض رابط الإحالة"""
    user = update.effective_user
    referral_link = f"https://t.me/MissionxX_bot?start={user.id}"
    await update.message.reply_text(
        f"🎯 <b>رابط الإحالة الخاص بك:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        "شارك هذا الرابط مع أصدقائك واحصل على نقاط عند انضمامهم!",
        parse_mode='HTML'
    )

async def leaderboard(update: Update, context: CallbackContext) -> None:
    """عرض لوحة المتصدرين"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    u.user_id,
                    u.username,
                    u.first_name,
                    COUNT(r.referred_user_id) as count
                FROM users u
                JOIN referrals r ON u.user_id = r.referred_by
                GROUP BY u.user_id
                ORDER BY count DESC
                LIMIT 10
            ''')
            
            leaders = cursor.fetchall()
            
            if not leaders:
                await update.message.reply_text("لا توجد إحالات بعد!")
                return

            message = "🏆 <b>أفضل 10 أعضاء في الإحالات</b> 🏆\n\n"
            for idx, leader in enumerate(leaders, 1):
                name = f"@{leader['username']}" if leader['username'] else leader['first_name'] or f"المستخدم {leader['user_id']}"
                message += f"{get_rank_emoji(idx)} {name} - {leader['count']} إحالة\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"خطأ في لوحة المتصدرين: {e}")
        await update.message.reply_text("حدث خطأ في جلب البيانات. حاول لاحقاً.")

def get_rank_emoji(rank: int) -> str:
    """إرجاع إيموجي حسب الترتيب"""
    return {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }.get(rank, f"#{rank}")

async def handle_referral(update: Update, context: CallbackContext) -> None:
    """معالجة الإحالات"""
    user = update.effective_user
    if not context.args:
        await start(update, context)
        return
        
    try:
        referrer_id = int(context.args[0])
        if referrer_id == user.id:
            await update.message.reply_text("⚠️ لا يمكنك استخدام رابطك الخاص!")
            return
            
        with get_db_connection() as conn:
            # تسجيل المستخدم الجديد
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user.id, user.username, user.first_name, user.last_name))
            
            # تسجيل الإحالة
            conn.execute("""
                INSERT OR IGNORE INTO referrals (referred_by, referred_user_id)
                VALUES (?, ?)
            """, (referrer_id, user.id))
            
            await update.message.reply_text(
                f"شكراً لتسجيلك عبر إحالة المستخدم {get_user_display_name(referrer_id)}!"
            )
            
    except Exception as e:
        logger.error(f"خطأ في معالجة الإحالة: {e}")
        await update.message.reply_text("حدث خطأ في التسجيل. حاول لاحقاً.")

def get_user_display_name(user_id: int) -> str:
    """الحصول على اسم مستخدم للعرض"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, first_name FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            if user:
                return f"@{user['username']}" if user['username'] else user['first_name'] or f"المستخدم {user_id}"
    except Exception as e:
        logger.error(f"خطأ في جلب اسم المستخدم: {e}")
    return f"المستخدم {user_id}"

def main():
    """تشغيل البوت"""
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("لم يتم تعيين BOT_TOKEN!")
        return

    try:
        app = Application.builder().token(TOKEN).build()
        
        # تسجيل جميع المعالجات هنا
        app.add_handler(CommandHandler("start", handle_referral))
        app.add_handler(CommandHandler("links", links))
        app.add_handler(CommandHandler("referral", referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("help", start))
        
        logger.info("بدأ البوت في الاستماع للتحديثات...")
        app.run_polling()
        
    except Exception as e:
        logger.critical(f"تعطل البوت: {e}")

if __name__ == "__main__":
    main()
