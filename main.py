import os
import asyncio
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Application
)
from dotenv import load_dotenv

load_dotenv()

class TelegramBot:
    def __init__(self):
        self.app: Application = None
        self.db_pool = None

    async def init_db(self):
        """تهيئة اتصال قاعدة البيانات مع Connection Pool"""
        try:
            self.db_pool = await asyncpg.create_pool(
                dsn=os.getenv("DATABASE_URL"),
                min_size=1,
                max_size=5
            )
            
            async with self.db_pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        referrals INTEGER DEFAULT 0,
                        invited_by BIGINT
                    )
                ''')
            print("✅ تم الاتصال بقاعدة البيانات بنجاح")
        except Exception as e:
            print(f"🔥 فشل الاتصال بقاعدة البيانات: {str(e)}")
            raise

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة أمر /start مع تتبع الأخطاء المحسنة"""
        try:
            async with self.db_pool.acquire() as conn:
                user = update.effective_user
                referrer_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
                
                exists = await conn.fetchrow('SELECT 1 FROM users WHERE user_id = $1', user.id)
                if not exists:
                    await conn.execute(
                        'INSERT INTO users (user_id, username, invited_by) VALUES ($1, $2, $3)',
                        user.id, user.first_name or "مستخدم", referrer_id
                    )
                    if referrer_id:
                        await conn.execute(
                            'UPDATE users SET referrals = referrals + 1 WHERE user_id = $1',
                            referrer_id
                        )
                
                await update.message.reply_text(f"مرحباً {user.first_name}! البوت يعمل ✅")
        except Exception as e:
            print(f"⛔ خطأ في /start: {str(e)}")
            await update.message.reply_text("حدث خطأ غير متوقع، الرجاء المحاولة لاحقاً")

    async def run(self):
        """تشغيل البوت مع معالجة محسنة للأخطاء"""
        try:
            await self.init_db()
            
            self.app = (
                ApplicationBuilder()
                .token(os.getenv("TELEGRAM_TOKEN"))
                .post_init(self.post_init)
                .build()
            )
            
            self.app.add_handler(CommandHandler("start", self.start))
            
            print("🚀 بدء تشغيل البوت...")
            await self.app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            
        except Exception as e:
            print(f"💥 انهيار البوت: {str(e)}")
        finally:
            await self.cleanup()

    async def post_init(self, application: Application):
        """وظيفة ما بعد التهيئة"""
        print("🔔 البوت جاهز للاستقبال الأوامر")

    async def cleanup(self):
        """تنظيف الموارد"""
        try:
            if self.db_pool:
                await self.db_pool.close()
            if self.app:
                await self.app.shutdown()
            print("🛑 تم إيقاف البوت بسلام")
        except Exception as e:
            print(f"⚠️ خطأ أثناء التنظيف: {str(e)}")

if __name__ == '__main__':
    bot = TelegramBot()
    
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("⏹ تم إيقاف البوت يدوياً")
    except Exception as e:
        print(f"☠️ خطأ غير متوقع: {str(e)}")
