from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import os
import logging
import psycopg2
from urllib.parse import urlparse
import asyncio

# إعداد نظام التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# اتصال قاعدة البيانات
def get_db_connection():
    try:
        DATABASE_URL = os.getenv('DATABASE_URL')
        result = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
            sslmode='require'
        )
        return conn
    except Exception as e:
        logger.error(f"خطأ في الاتصال بقاعدة البيانات: {str(e)}")
        raise

# تهيئة الجداول (تم التعديل)
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # إنشاء جدول المهام
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                task_name TEXT NOT NULL,
                completed INTEGER DEFAULT 0
            )
        """)
        
        # إنشاء جدول الإحالات (تم التعديل)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL,
                referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (referrer_id, referred_user_id)
            )
        """)
        
        conn.commit()
        logger.info("تم تهيئة الجداول بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تهيئة الجداول: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

# استدعاء تهيئة قاعدة البيانات
init_db()

# دالة معالجة الإحالة (تم التعديل)
async def handle_referral(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    args = context.args
    
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        
        if referrer_id == user.id:
            await update.message.reply_text("⚠️ لا يمكنك استخدام رابط الإحالة الخاص بك!")
            return
            
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # التحقق من عدم تكرار الإحالة (تم التعديل)
            cursor.execute("""
                SELECT * FROM referrals 
                WHERE referrer_id = %s AND referred_user_id = %s
            """, (referrer_id, user.id))
            
            if cursor.fetchone():
                await update.message.reply_text("تم تسجيل إحالتك مسبقاً!")
            else:
                # تسجيل الإحالة الجديدة (تم التعديل)
                cursor.execute("""
                    INSERT INTO referrals (referrer_id, referred_user_id)
                    VALUES (%s, %s)
                """, (referrer_id, user.id))
                conn.commit()
                
                # إرسال إشعار للمحيل
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 تم تسجيل إحالة جديدة بواسطة {user.first_name}!"
                    )
                except Exception as e:
                    logger.warning(f"لا يمكن إرسال إشعار للمحيل: {e}")
                
                await update.message.reply_text(
                    f"شكراً لتسجيلك عبر إحالة المستخدم #{referrer_id}!\n"
                    "استخدم /help لمعرفة المزيد"
                )
        except Exception as e:
            logger.error(f"خطأ في معالجة الإحالة: {e}")
            await update.message.reply_text("حدث خطأ أثناء معالجة إحالتك.")
        finally:
            if conn:
                conn.close()
    else:
        await start(update, context)

# دالة عرض المتصدرين (تم التعديل)
async def leaderboard(update: Update, context: CallbackContext) -> None:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # استعلام لوحة المتصدرين (تم التعديل)
        cursor.execute('''
            SELECT referrer_id, COUNT(*) as total 
            FROM referrals 
            GROUP BY referrer_id 
            ORDER BY total DESC 
            LIMIT 10
        ''')
        
        top_referrers = cursor.fetchall()
        
        if not top_referrers:
            await update.message.reply_text("لا يوجد إحالات بعد.")
            return
            
        message = "🏆 قائمة المتصدرين:\n"
        for idx, (user_id, total) in enumerate(top_referrers, start=1):
            rank = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"#{idx}"
            
            try:
                user = await context.bot.get_chat(user_id)
                username = f"@{user.username}" if user.username else user.first_name
                message += f"{rank} {username} - {total} إحالة\n"
            except:
                message += f"{rank} مستخدم #{user_id} - {total} إحالة\n"
                
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"خطأ في جلب لوحة المتصدرين: {e}")
        await update.message.reply_text("حدث خطأ أثناء جلب البيانات.")
    finally:
        if conn:
            conn.close()

# باقي دوال البوت (start, links, referral) تبقى كما هي بدون تغيير

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.error("لم يتم تعيين BOT_TOKEN")
        return

    application = Application.builder().token(TOKEN).build()
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", handle_referral))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    # إضافة باقي المعالجات...
    
    application.run_polling()

if __name__ == "__main__":
    main()
