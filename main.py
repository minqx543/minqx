import os
import asyncio
import asyncpg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# قراءة رابط قاعدة البيانات من المتغير البيئي
DATABASE_URL = os.getenv("DATABASE_URL")

# إعداد الاتصال بقاعدة البيانات
async def create_tables():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            referrals INTEGER DEFAULT 0,
            invited_by BIGINT
        )
    ''')
    await conn.close()

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.first_name

    conn = await asyncpg.connect(DATABASE_URL)

    referrer_id = None
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id == user_id:
                referrer_id = None  # لا يمكن للاعب دعوة نفسه
        except:
            pass

    user_exist = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)

    if not user_exist:
        await conn.execute(
            'INSERT INTO users (user_id, username, invited_by) VALUES ($1, $2, $3)',
            user_id, username, referrer_id
        )
        if referrer_id:
            await conn.execute(
                'UPDATE users SET referrals = referrals + 1 WHERE user_id = $1',
                referrer_id
            )

    await conn.close()

    await update.message.reply_text(f"أهلا بك {username} في البوت!")

# أمر /referral
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"

    keyboard = [
        [InlineKeyboardButton("مشاركة رابط الإحالة", url=referral_link)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "رابط الإحالة الخاص بك:",
        reply_markup=reply_markup
    )

# أمر /leaderboard
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await asyncpg.connect(DATABASE_URL)
    top_users = await conn.fetch(
        'SELECT username, referrals FROM users ORDER BY referrals DESC LIMIT 10'
    )
    await conn.close()

    if not top_users:
        await update.message.reply_text("لا يوجد لاعبين بعد.")
        return

    medals = ['🥇', '🥈', '🥉'] + ['🏅'] * 7
    text = "🏆 أفضل 10 لاعبين:\n\n"
    for i, user in enumerate(top_users):
        name = user['username'] or 'لاعب'
        referrals = user['referrals']
        medal = medals[i] if i < len(medals) else '🏅'
        text += f"{medal} {name}: {referrals} إحالة\n"

    await update.message.reply_text(text)

# التشغيل الرئيسي
async def main():
    await create_tables()

    app = ApplicationBuilder().token("توكن البوت هنا").initialize()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    await app.start()
    print("Bot started...")
    await app.idle()

if __name__ == '__main__':
    asyncio.run(main())
