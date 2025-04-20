from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import os
import logging
from datetime import datetime
import psycopg2
from urllib.parse import urlparse
import asyncio

# إعداد نظام التسجيل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# اتصال قاعدة البيانات PostgreSQL
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

# تهيئة الجداول
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                task_name TEXT NOT NULL,
                completed INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (referrer_id, referred_id)
            )
        """)
        
        conn.commit()
        logger.info("تم تهيئة الجداول بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تهيئة الجداول: {str(e)}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

# استدعاء تهيئة قاعدة البيانات عند التشغيل
init_db()

# دالة /start
async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    logger.info(f"مستخدم {user.id} ({user.first_name}) قام بتشغيل البوت")
    await update.message.reply_text("مرحباً بك في بوت MissionX! استخدم /links لرؤية روابط المنصات، /referral لرابط الإحالة، و /leaderboard لعرض قائمة المتصدرين.")

# دالة عرض روابط المنصات
async def links(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    logger.info(f"مستخدم {user.id} طلب روابط المنصات")
    
    platform_links = (
        "🌐 روابط المنصات:\n"
        "🔹 [Telegram](https://t.me/MissionX_offici)\n"
        "🔹 [YouTube](https://youtube.com/@missionx_offici?si=4A549AkxABu523zi)\n"
        "🔹 [TikTok](https://www.tiktok.com/@missionx_offici?_t=ZS-8vgxNwgERtP&_r=1)\n"
        "🔹 [X](https://x.com/MissionX_Offici?t=eqZ5raOAaRfhwivFVe68rg&s=09)\n"
        "🔹 [Facebook](https://www.facebook.com/share/19AMU41hhs/)\n"
        "🔹 [Instagram](https://www.instagram.com/missionx_offici?igsh=MTRhNmJtNm1wYWxqYw==)\n"
    )
    await update.message.reply_text(platform_links, disable_web_page_preview=True)

# دالة عرض رابط الإحالة
async def referral(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    referral_link = f"https://t.me/MissionxX_bot?start={user_id}"
    
    logger.info(f"مستخدم {user_id} ({user.first_name}) طلب رابط الإحالة")
    await update.message.reply_text(f"رابط الإحالة الخاص بك:\n{referral_link}")

# دالة عرض المتصدرين
async def leaderboard(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    logger.info(f"مستخدم {user.id} طلب لوحة المتصدرين")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT referrer_id, COUNT(*) as total 
            FROM referrals 
            GROUP BY referrer_id 
            ORDER BY total DESC 
            LIMIT 10
        ''')
        top_referrers = cursor.fetchall()

        if not top_referrers:
            logger.info("لا توجد إحالات لعرضها")
            await update.message.reply_text("لا يوجد إحالات بعد.")
            return

        message = "🏆 قائمة المتصدرين:\n"
        for idx, (user_id, total) in enumerate(top_referrers, start=1):
            if idx == 1:
                rank = "🥇"
            elif idx == 2:
                rank = "🥈"
            elif idx == 3:
                rank = "🥉"
            else:
                rank = f"#{idx}"

            try:
                user = await context.bot.get_chat(user_id)
                user_name = f"@{user.username}" if user.username else user.first_name
                message += f"{rank} {user_name} - {total} إحالة\n"
            except Exception as e:
                logger.warning(f"خطأ في جلب معلومات المستخدم {user_id}: {e}")
                message += f"{rank} مستخدم #{user_id} - {total} إحالة\n"

        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"خطأ في جلب لوحة المتصدرين: {e}")
        await update.message.reply_text("حدث خطأ أثناء جلب لوحة المتصدرين.")
    finally:
        if 'conn' in locals():
            conn.close()

# دالة إضافة إحالة تلقائياً عند البدء بالرابط
async def handle_referral(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    args = context.args

    logger.info(f"مستخدم {user_id} بدأ التفاعل مع البوت {'بإحالة' if args else 'بدون إحالة'}")

    if args:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            referrer_id = int(args[0])
            if referrer_id != user_id:
                cursor.execute("SELECT * FROM referrals WHERE referrer_id = %s AND referred_id = %s", 
                             (referrer_id, user_id))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (%s, %s)", 
                                  (referrer_id, user_id))
                    conn.commit()
                    logger.info(f"تم تسجيل إحالة جديدة: {referrer_id} أحال {user_id}")
                    
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 تم تسجيل إحالة جديدة بواسطة {user.first_name}!"
                        )
                    except Exception as e:
                        logger.warning(f"لا يمكن إرسال إشعار للمحيل: {e}")
                    
                    try:
                        referred_user = await context.bot.get_chat(referrer_id)
                        username = f"@{referred_user.username}" if referred_user.username else str(referrer_id)
                        await update.message.reply_text(f"شكراً لتسجيلك عبر إحالة المستخدم {username}!")
                    except Exception as e:
                        logger.warning(f"خطأ في جلب معلومات المحيل: {e}")
                        await update.message.reply_text(f"شكراً لتسجيلك عبر إحالة المستخدم #{referrer_id}!")
                else:
                    logger.info(f"إحالة مكررة: {referrer_id} -> {user_id}")
        except ValueError:
            logger.warning(f"معرف إحالة غير صالح: {args[0]}")
        except Exception as e:
            logger.error(f"خطأ في معالجة الإحالة: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    await start(update, context)

# تشغيل البوت
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("لم يتم تعيين BOT_TOKEN في متغيرات البيئة!")
        raise ValueError("BOT_TOKEN غير موجود")
    
    try:
        application = Application.builder().token(TOKEN).build()
        logger.info("تم تهيئة تطبيق البوت بنجاح")

        application.add_handler(CommandHandler("start", handle_referral))
        application.add_handler(CommandHandler("links", links))
        application.add_handler(CommandHandler("referral", referral))
        application.add_handler(CommandHandler("leaderboard", leaderboard))

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
