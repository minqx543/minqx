import os
import asyncio
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
TOKEN = os.getenv("TELEGRAM_TOKEN")

class TelegramBot:
    def __init__(self):
        self.app = None
        self._running = False

    async def init_db(self):
        """تهيئة اتصال قاعدة البيانات وإنشاء الجداول"""
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    referrals INTEGER DEFAULT 0,
                    invited_by BIGINT
                )
            ''')
        finally:
            await conn.close()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة أمر /start"""
        conn = await asyncpg.connect(DATABASE_URL)
        try:
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
            
            await update.message.reply_text(f"أهلاً بك {user.first_name} في البوت! 🎉")
        except Exception as e:
            print(f"Error in /start: {e}")
            await update.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً")
        finally:
            await conn.close()

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
            print(f"Error in /referral: {e}")
            await update.message.reply_text("حدث خطأ في إنشاء الرابط")

    async def leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة أمر /leaderboard"""
        conn = await asyncpg.connect(DATABASE_URL)
        try:
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
            print(f"Error in /leaderboard: {e}")
            await update.message.reply_text("حدث خطأ في جلب البيانات")
        finally:
            await conn.close()

    async def run(self):
        """تشغيل البوت الرئيسي"""
        try:
            await self.init_db()
            self.app = ApplicationBuilder().token(TOKEN).build()
            
            self.app.add_handler(CommandHandler("start", self.start))
            self.app.add_handler(CommandHandler("referral", self.referral))
            self.app.add_handler(CommandHandler("leaderboard", self.leaderboard))
            
            self._running = True
            print("✅ البوت يعمل الآن...")
            await self.app.run_polling()
            
        except Exception as e:
            print(f"❌ فشل تشغيل البوت: {e}")
        finally:
            await self.stop()

    async def stop(self):
        """إيقاف البوت بشكل آمن"""
        if self.app and self._running:
            try:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                print(f"⚠️ خطأ أثناء الإيقاف: {e}")
            finally:
                self._running = False
                print("تم إيقاف البوت")

async def main():
    bot = TelegramBot()
    await bot.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nتم إيقاف البوت يدوياً")
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
