import os
import asyncio
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("❗ لم يتم تعيين TELEGRAM_TOKEN في ملف .env")

class TelegramBot:
    def __init__(self):
        self.app = None
        self.db_pool = None

    async def init_db(self):
        """تهيئة قاعدة البيانات"""
        try:
            self.db_pool = await asyncpg.create_pool(DATABASE_URL)
            async with self.db_pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        referrals INTEGER DEFAULT 0,
                        invited_by BIGINT
                    )
                ''')
            print("✅ تم تهيئة قاعدة البيانات بنجاح")
        except Exception as e:
            print(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
            raise

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة أمر /start"""
        try:
            user = update.effective_user
            referrer_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
            
            async with self.db_pool.acquire() as conn:
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
            
            await update.message.reply_text(f"أهلاً بك {user.first_name} في البوت!")
        except Exception as e:
            print(f"خطأ في /start: {e}")
            await update.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً")

    async def referral(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة أمر /referral"""
        try:
            bot_username = (await context.bot.get_me()).username
            link = f"https://t.me/{bot_username}?start={update.effective_user.id}"
            keyboard = [[InlineKeyboardButton("مشاركة الرابط", url=f"tg://msg_url?url={link}")]]
            await update.message.reply_text(
                f"رابط الإحالة الخاص بك:\n{link}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            print(f"خطأ في /referral: {e}")
            await update.message.reply_text("حدث خطأ في إنشاء الرابط")

    async def leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة أمر /leaderboard"""
        try:
            async with self.db_pool.acquire() as conn:
                top_users = await conn.fetch(
                    'SELECT username, referrals FROM users ORDER BY referrals DESC LIMIT 10'
                )
                
                if not top_users:
                    await update.message.reply_text("لا يوجد لاعبين بعد.")
                    return

                medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
                response = "🏆 ترتيب أفضل 10 لاعبين:\n\n" + "\n".join(
                    f"{medals[i]} {user['username'] or 'لاعب'}: {user['referrals']} إحالة"
                    for i, user in enumerate(top_users)
                )
                
                await update.message.reply_text(response)
        except Exception as e:
            print(f"خطأ في /leaderboard: {e}")
            await update.message.reply_text("حدث خطأ في جلب البيانات")

    async def run(self):
        """تشغيل البوت"""
        try:
            await self.init_db()
            self.app = ApplicationBuilder().token(TOKEN).build()
            
            self.app.add_handler(CommandHandler("start", self.start))
            self.app.add_handler(CommandHandler("referral", self.referral))
            self.app.add_handler(CommandHandler("leaderboard", self.leaderboard))

            print("✅ بدء تشغيل البوت...")
            await self.app.initialize()
            await self.app.start()
            if self.app.updater:
                await self.app.updater.start_polling()
            
            print("🤖 البوت يعمل الآن...")
            await self.app.idle()
            
        except Exception as e:
            print(f"❌ فشل في بدء تشغيل البوت: {e}")
        finally:
            if self.app:
                await self.app.stop()
            if self.db_pool:
                await self.db_pool.close()

async def main():
    bot = TelegramBot()
    await bot.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("تم إيقاف البوت بواسطة المستخدم")
