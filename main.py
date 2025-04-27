import discord
from discord.ext import commands
import psycopg2
import os

# المتغيرات
TOKEN = 'توكن_البوت_هنا'
DATABASE_URL = os.getenv('DATABASE_URL')  # استخدام متغير البيئة الخاص بـ Render

# إعداد البوت
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# الاتصال بقاعدة البيانات
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# إنشاء جدول إذا لم يكن موجودًا
def create_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    referrals INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

# تسجيل لاعب جديد
def add_user(user_id, username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    if not c.fetchone():
        c.execute('INSERT INTO users (id, username) VALUES (%s, %s)', (user_id, username))
        conn.commit()
    conn.close()

# تحديث عدد الإحالات
def update_referrals(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET referrals = referrals + 1 WHERE id = %s', (user_id,))
    conn.commit()
    conn.close()

# جلب ترتيب اللاعبين
def get_leaderboard():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT username, referrals FROM users ORDER BY referrals DESC LIMIT 10')
    leaderboard = c.fetchall()
    conn.close()
    return leaderboard

# عند بدء البوت
@bot.event
async def on_ready():
    create_db()
    print(f'Logged in as {bot.user}')

# الأمر !start
@bot.command()
async def start(ctx):
    add_user(ctx.author.id, ctx.author.name)
    await ctx.send(f'مرحبًا {ctx.author.name}! أهلاً بك في اللعبة. نتمنى لك حظًا سعيدًا!')

# الأمر !referral
@bot.command()
async def referral(ctx):
    link = f'https://yourwebsite.com/referral/{ctx.author.id}'
    await ctx.send(f'رابط إحالتك الخاص هو: {link}')

# الأمر !leaderboard
@bot.command()
async def leaderboard(ctx):
    leaderboard = get_leaderboard()
    embed = discord.Embed(title="أفضل 10 لاعبين")
    for index, (username, referrals) in enumerate(leaderboard, start=1):
        embed.add_field(name=f'{index}. {username}', value=f'عدد الإحالات: {referrals}', inline=False)
    await ctx.send(embed=embed)

# تشغيل البوت
bot.run(TOKEN)
