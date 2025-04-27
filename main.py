import os
import asyncio
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env
load_dotenv()

# قراءة رابط قاعدة البيانات والتوكن من المتغيرات البيئية
DATABASE_URL = os.getenv("DATABASE_URL")
TOKEN = os.getenv("TELEGRAM_TOKEN")

# إعداد اتصال قاعدة البيانات مع إدارة الأخطاء
async def create_db_connection():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"فشل الاتصال بقاعدة البيانات: {e}")
        raise

# إعداد الجداول في قاعدة البيانات
async def create_tables():
    try:
        conn = await create_db_connection()
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                referrals INTEGER DEFAULT 0,
                invited_by BIGINT
            )
        ''')
    finally:
        if conn:
            await conn.close()

# أمر /start مع تحسينات إدارة الاتصال
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.first_name or "مستخدم"
    
    conn = None
    try:
        conn = await create_db_connection()
        
        referrer_id = None
        if context.args:
            try:
                referrer_id = int(context.args[0])
                if referrer_id == user_id:
                    referrer_id = None
            except (ValueError, IndexError):
                pass

        user_exists = await conn.fetchrow('SELECT 1 FROM users WHERE user_id = $1', user_id)
        
        if not user_exists:
            await conn.execute(
                'INSERT INTO users (user_id, username, invited_by) VALUES ($1, $2, $3)',
                user_id, username, referrer_id
            )
            
            if referrer_id:
                await conn.execute(
                    'UPDATE users SET referrals = referrals + 1 WHERE user_id = $1',
                    referrer_id
                )
        
        await update.message.reply_text(f"أهلاً بك {username} في البوت! 🎉")
        
    except Exception as e:
        print(f"حدث خطأ: {e}")
        await update.message.reply_text("حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقاً.")
    finally:
        if conn:
            await conn.close()

# أمر /referral مع زر المشاركة
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        
        keyboard = [[InlineKeyboardButton("مشاركة رابط الإحالة", url=f"tg://msg_url?url={referral_link}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"رابط الإحالة الخاص بك:\n{referral_link}",
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"خطأ في أمر referral: {e}")
        await update.message.reply_text("حدث خطأ أثناء إنشاء رابط الإحالة")

# أمر /leaderboard مع تحسينات الأداء
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = None
    try:
        conn = await create_db_connection()
        top_users = await conn.fetch(
            'SELECT username, referrals FROM users ORDER BY referrals DESC LIMIT 10'
        )
        
        if not top_users:
            await update.message.reply_text("لا يوجد لاعبين بعد.")
            return

        medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        text = "🏆 ترتيب أفضل 10 لاعبين:\n\n"
        
        for i, user in enumerate(top_users):
            name = user['username'] or 'لاعب'
            referrals = user['referrals']
            medal = medals[i] if i < len(medals) else '🔹'
            text += f"{medal} {name}: {referrals} إحالة\n"
        
        await update.message.reply_text(text)
        
    except Exception as e:
        print(f"خطأ في أمر leaderboard: {e}")
        await update.message.reply_text("حدث خطأ أثناء جلب بيانات اللاعبين")
    finally:
        if conn:
            await conn.close()

# التشغيل الرئيسي مع إدارة الأخطاء
async def main():
    try:
        await create_tables()
        
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("referral", referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        
        print("✅ البوت يعمل الآن...")
        await app.run_polling()
        
    except Exception as e:
        print(f"❌ فشل تشغيل البوت: {e}")
    finally:
        print("جارٍ إيقاف البوت...")

if __name__ == '__main__':
    asyncio.run(main())
