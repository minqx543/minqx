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
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # جدول المهام
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        task_name TEXT NOT NULL,
                        completed INTEGER DEFAULT 0
                    )
                """)
                
                # جدول الإحالات (تم تعديل اسم العمود إلى referred_by)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS referrals (
                        referred_by INTEGER NOT NULL,
                        referred_id INTEGER NOT NULL,
                        referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (referred_by, referred_id)
                    )
                """)
                
                conn.commit()
                logger.info("تم تهيئة الجداول بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تهيئة الجداول: {str(e)}")
        raise

# استدعاء تهيئة قاعدة البيانات عند التشغيل
init_db()

# دالة /start
async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    logger.info(f"مستخدم {user.id} ({user.first_name}) قام بتشغيل البوت")
    await update.message.reply_text(
        "مرحباً بك في بوت MissionX!\n"
        "استخدم /links لرؤية روابط المنصات\n"
        "/referral لرابط الإحالة\n"
        "/leaderboard لعرض قائمة المتصدرين"
    )

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
    await update.message.reply_text(
        f"رابط الإحالة الخاص بك:\n{referral_link}\n\n"
        "شارك هذا الرابط مع أصدقائك واحصل على نقاط عند تسجيلهم!"
    )

# دالة عرض المتصدرين
async def leaderboard(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    logger.info(f"مستخدم {user.id} طلب لوحة المتصدرين")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT referred_by, COUNT(*) as total 
                    FROM referrals 
                    GROUP BY referred_by 
                    ORDER BY total DESC 
                    LIMIT 10
                ''')
                top_referrers = cursor.fetchall()

        if not top_referrers:
            await update.message.reply_text(
                "لا يوجد إحالات بعد.\n"
                "كن أول من يجلب أعضاء جدد باستخدام رابط الإحالة الخاص بك (/referral)!"
            )
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

# دالة إضافة إحالة تلقائياً عند البدء بالرابط
async def handle_referral(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    args = context.args

    logger.info(f"مستخدم {user_id} بدأ التفاعل مع البوت {'بإحالة' if args else 'بدون إحالة'}")

    if args:
        try:
            referrer_id = int(args[0])
            
            # التحقق من عدم استخدام المستخدم لرابطه الخاص
            if referrer_id == user_id:
                await update.message.reply_text("⚠️ لا يمكنك استخدام رابط الإحالة الخاص بك!")
                return
                
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # التحقق من عدم تكرار الإحالة
                    cursor.execute("""
                        SELECT * FROM referrals 
                        WHERE referred_by = %s AND referred_id = %s
                    """, (referrer_id, user_id))
                    
                    if cursor.fetchone():
                        logger.info(f"إحالة مكررة: {referrer_id} -> {user_id}")
                        await update.message.reply_text("تم تسجيل إحالتك مسبقاً!")
                    else:
                        # تسجيل الإحالة الجديدة
                        cursor.execute("""
                            INSERT INTO referrals (referred_by, referred_id) 
                            VALUES (%s, %s)
                        """, (referrer_id, user_id))
                        conn.commit()
                        logger.info(f"تم تسجيل إحالة جديدة: {referrer_id} أحال {user_id}")
                        
                        # إرسال إشعار للمحيل
                        try:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=f"🎉 تم تسجيل إحالة جديدة بواسطة {user.first_name}!"
                            )
                        except Exception as e:
                            logger.warning(f"لا يمكن إرسال إشعار للمحيل: {e}")
                        
                        # إرسال رسالة للمستخدم الجديد
                        try:
                            referred_user = await context.bot.get_chat(referrer_id)
                            username = f"@{referred_user.username}" if referred_user.username else referred_user.first_name
                            await update.message.reply_text(
                                f"شكراً لتسجيلك عبر إحالة المستخدم {username}!\n"
                                "استخدم /help لمعرفة كيفية استخدام البوت"
                            )
                        except Exception as e:
                            logger.warning(f"خطأ في جلب معلومات المحيل: {e}")
                            await update.message.reply_text(
                                f"شكراً لتسجيلك عبر إحالة المستخدم #{referrer_id}!\n"
                                "استخدم /help لمعرفة كيفية استخدام البوت"
                            )
        except ValueError:
            logger.warning(f"معرف إحالة غير صالح: {args[0]}")
            await update.message.reply_text("رابط الإحالة غير صالح!")
        except Exception as e:
            logger.error(f"خطأ في معالجة الإحالة: {e}")
            await update.message.reply_text("حدث خطأ أثناء معالجة إحالتك.")

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

        # إضافة معالجات الأوامر
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
