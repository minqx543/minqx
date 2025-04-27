import os
import asyncio
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# تحميل المتغيرات البيئية
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
TOKEN = os.getenv("TELEGRAM_TOKEN")

class BotManager:
    def __init__(self):
        self.app = None
        self.running = False

    async def create_db_connection(self):
        return await asyncpg.connect(DATABASE_URL)

    async def create_tables(self):
        conn = await self.create_db_connection()
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
        conn = await self.create_db_connection()
        try:
            user = update.effective_user
            user_id = user.id
            username = user.first_name or "مستخدم"
            
            referrer_id = int(context.args[0]) if context.args and context.args[0].isdigit() and int(context.args[0]) != user_id else None

            if not await conn.fetchrow('SELECT 1 FROM users WHERE user_id = $1', user_id):
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
            print(f"Error in start: {e}")
            await update.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً")
        finally:
            await conn.close()

    async def referral(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            bot_username = (await context.bot.get_me()).username
            referral_link = f"https://t.me/{bot_username}?start={user.id}"
            
            keyboard = [[InlineKeyboardButton("مشاركة رابط الإحالة", url=f"tg://msg_url?url={referral_link}")]]
            await update.message.reply_text(
                f"رابط الإحالة الخاص بك:\n{referral_link}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            print(f"Error in referral: {e}")
            await update.message.reply_text("حدث خطأ في إنشاء الرابط")

    async def leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = await self.create_db_connection()
        try:
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
                text += f"{medals[i]} {name}: {user['referrals']} إحالة\n"
            
            await update.message.reply_text(text)
        except Exception as e:
            print(f"Error in leaderboard: {e}")
            await update.message.reply_text("حدث خطأ في جلب البيانات")
        finally:
            await conn.close()

    async def run(self):
        try:
            await self.create_tables()
            
            self.app = ApplicationBuilder().token(TOKEN).build()
            self.running = True
            
            self.app.add_handler(CommandHandler("start", self.start))
            self.app.add_handler(CommandHandler("referral", self.referral))
            self.app.add_handler(CommandHandler("leaderboard", self.leaderboard))
            
            print("✅ البوت يعمل الآن...")
            await self.app.run_polling()
            
        except Exception as e:
            print(f"❌ فشل تشغيل البوت: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        if self.app and self.running:
            try:
                await self.app.stop()
                await self.app.shutdown()
                print("تم إيقاف البوت بنجاح")
            except Exception as e:
                print(f"خطأ أثناء الإيقاف: {e}")
            finally:
                self.running = False

async def main():
    bot = BotManager()
    await bot.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nتم إيقاف البوت يدوياً")
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
