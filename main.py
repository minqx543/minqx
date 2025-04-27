import os
import logging
import asyncpg
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext
from typing import Optional, Dict, Any

# إعداد نظام التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# إعداد اتصال PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    logger.critical("لم يتم تعيين DATABASE_URL!")
    raise ValueError("DATABASE_URL environment variable is required")

class Database:
    _pool: Optional[asyncpg.pool.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.pool.Pool:
        """إنشاء أو إرجاع اتصال قاعدة البيانات"""
        if cls._pool is None:
            try:
                cls._pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10,
                    command_timeout=60
                )
                logger.info("تم إنشاء اتصال قاعدة البيانات بنجاح")
            except Exception as e:
                logger.error(f"فشل في إنشاء اتصال قاعدة البيانات: {e}")
                raise
        return cls._pool

    @classmethod
    async def close_pool(cls) -> None:
        """إغلاق اتصال قاعدة البيانات"""
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None
            logger.info("تم إغلاق اتصال قاعدة البيانات")

async def init_db() -> None:
    """تهيئة الجداول في PostgreSQL"""
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        join_date TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
                        last_active TIMESTAMP WITH TIME ZONE,
                        points INTEGER DEFAULT 0 CHECK (points >= 0),
                        CONSTRAINT valid_username CHECK (username IS NULL OR username ~ '^[a-zA-Z0-9_]{1,32}$')
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS referrals (
                        id SERIAL PRIMARY KEY,
                        referred_by BIGINT NOT NULL,
                        referred_user_id BIGINT NOT NULL UNIQUE,
                        referral_date TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
                        FOREIGN KEY (referred_by) REFERENCES users(user_id) ON DELETE CASCADE,
                        FOREIGN KEY (referred_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                        CONSTRAINT no_self_referral CHECK (referred_by != referred_user_id)
                    )
                ''')
                
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_referred_by ON referrals(referred_by)
                ''')
                
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_referred_user ON referrals(referred_user_id)
                ''')
                
        logger.info("تم تهيئة جداول PostgreSQL بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تهيئة قاعدة البيانات: {e}", exc_info=True)
        raise

def get_user_display_name(user: Dict[str, Any]) -> str:
    """الحصول على اسم مستخدم للعرض مع التحقق من الصحة"""
    try:
        name_parts = []
        if user.get('first_name'):
            name_parts.append(str(user['first_name']))
        if user.get('last_name'):
            name_parts.append(str(user['last_name']))
        
        full_name = ' '.join(name_parts).strip() if name_parts else None
        
        if user.get('username'):
            username = f"@{user['username']}"
            if full_name:
                return f"{username} ({full_name})"
            return username
        elif full_name:
            return full_name
        return f"المستخدم {user.get('user_id')}"
    except Exception as e:
        logger.error(f"خطأ في تنسيق اسم المستخدم: {e}")
        return "مستخدم غير معروف"

def get_rank_emoji(rank: int) -> str:
    """إرجاع إيموجي حسب الترتيب مع التحقق من الصحة"""
    try:
        rank = max(1, int(rank))
        return {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }.get(rank, f"#{rank}")
    except (ValueError, TypeError):
        return f"#{rank}"

async def start(update: Update, context: CallbackContext) -> None:
    """معالجة أمر /start مع دعم الإحالات"""
    if not update.message or not update.effective_user:
        return
        
    user = update.effective_user
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # تسجيل أو تحديث بيانات المستخدم
                await conn.execute('''
                    INSERT INTO users (user_id, username, first_name, last_name, last_active)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_active = EXCLUDED.last_active
                ''', user.id, user.username, user.first_name, user.last_name, datetime.now(timezone.utc))
                
                # معالجة الإحالة إذا وجدت
                if context.args and context.args[0].isdigit():
                    referrer_id = int(context.args[0])
                    if referrer_id != user.id:
                        try:
                            # تسجيل الإحالة وزيادة النقاط
                            result = await conn.execute('''
                                INSERT INTO referrals (referred_by, referred_user_id)
                                VALUES ($1, $2)
                                ON CONFLICT (referred_user_id) DO NOTHING
                                RETURNING id
                            ''', referrer_id, user.id)
                            
                            if result:
                                await conn.execute('''
                                    UPDATE users SET points = points + 10 
                                    WHERE user_id = $1
                                ''', referrer_id)
                                
                                # إعلام المستخدم الجديد
                                referrer = await conn.fetchrow(
                                    'SELECT * FROM users WHERE user_id = $1', 
                                    referrer_id
                                )
                                
                                if referrer:
                                    await update.message.reply_text(
                                        f"🎉 شكراً للانضمام عبر إحالة {get_user_display_name(referrer)}!\n"
                                        f"تم تسجيل إحالتك بنجاح."
                                    )
                                    
                                    # إعلام المحيل
                                    try:
                                        await context.bot.send_message(
                                            chat_id=referrer_id,
                                            text=f"🎊 لديك إحالة جديدة!\n"
                                                 f"المستخدم: {get_user_display_name({
                                                     'user_id': user.id,
                                                     'username': user.username,
                                                     'first_name': user.first_name,
                                                     'last_name': user.last_name
                                                 })}\n"
                                                 f"🎯 النقاط المضافة: +10"
                                        )
                                    except Exception as e:
                                        logger.warning(f"لا يمكن إرسال إشعار للمحيل: {e}")
                                        
                        except Exception as e:
                            logger.error(f"خطأ في معالجة الإحالة: {e}")
        
        # رسالة الترحيب
        welcome_msg = (
            f"مرحباً {user.first_name} في بوت MissionX! 🚀\n\n"
            "📌 الأوامر المتاحة:\n"
            "/start - بدء استخدام البوت\n"
            "/links - روابط المنصات\n"
            "/referral - رابط الإحالة الخاص بك\n"
            "/leaderboard - لوحة المتصدرين\n"
            "/help - المساعدة"
        )
        
        await update.message.reply_text(welcome_msg)
        
    except Exception as e:
        logger.error(f"خطأ في أمر /start: {e}", exc_info=True)
        await update.message.reply_text("حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقاً.")

async def links(update: Update, context: CallbackContext) -> None:
    """عرض روابط المنصات مع التحقق من الصحة"""
    if not update.message:
        return
        
    links_text = (
        "🌐 <b>روابطنا الرسمية:</b>\n\n"
        "🔹 <a href='https://t.me/MissionX_offici'>قناة التليجرام</a>\n"
        "🔹 <a href='https://youtube.com/@missionx_offici'>يوتيوب</a>\n"
        "🔹 <a href='https://www.tiktok.com/@missionx_offici'>تيك توك</a>\n"
        "🔹 <a href='https://x.com/MissionX_Offici'>تويتر (X)</a>\n"
        "🔹 <a href='https://www.facebook.com/share/19AMU41hhs/'>فيسبوك</a>\n"
        "🔹 <a href='https://www.instagram.com/missionx_offici'>إنستجرام</a>"
    )
    
    try:
        await update.message.reply_text(
            links_text,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"خطأ في عرض الروابط: {e}")

async def referral(update: Update, context: CallbackContext) -> None:
    """إنشاء وعرض رابط الإحالة"""
    if not update.message or not update.effective_user:
        return
        
    user = update.effective_user
    bot_username = context.bot.username if context.bot.username else "your_bot_username"
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # إحصائيات الإحالات
                referral_count = await conn.fetchval(
                    'SELECT COUNT(*) FROM referrals WHERE referred_by = $1', 
                    user.id
                ) or 0
                
                # النقاط والترتيب
                points = await conn.fetchval(
                    'SELECT points FROM users WHERE user_id = $1', 
                    user.id
                ) or 0
                
                rank = await conn.fetchval('''
                    SELECT COUNT(*) + 1 FROM (
                        SELECT referred_by, COUNT(*) as count 
                        FROM referrals 
                        GROUP BY referred_by
                        HAVING COUNT(*) > (
                            SELECT COUNT(*) FROM referrals WHERE referred_by = $1
                        )
                    ) t
                ''', user.id) or 1
    
    except Exception as e:
        logger.error(f"خطأ في جلب إحصائيات الإحالة: {e}")
        referral_count = 0
        points = 0
        rank = 1
    
    # زر المشاركة
    keyboard = [[
        InlineKeyboardButton(
            "📤 مشاركة الرابط", 
            url=f"https://t.me/share/url?url={referral_link}&text=انضم%20إلى%20بوت%20MissionX%20المميز!"
        )
    ]]
    
    try:
        await update.message.reply_text(
            f"🎯 <b>رابط الإحالة الخاص بك:</b>\n\n"
            f"<code>{referral_link}</code>\n\n"
            f"📊 <b>الإحالات الناجحة:</b> {referral_count}\n"
            f"🏅 <b>ترتيبك:</b> {get_rank_emoji(rank)}\n"
            f"⭐ <b>نقاطك:</b> {points}\n\n"
            "شارك هذا الرابط مع أصدقائك واحصل على 10 نقاط لكل إحالة ناجحة!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال رابط الإحالة: {e}")

async def leaderboard(update: Update, context: CallbackContext) -> None:
    """عرض لوحة المتصدرين"""
    if not update.message or not update.effective_user:
        return
        
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # أفضل 10 أعضاء
                top_users = await conn.fetch('''
                    SELECT 
                        u.user_id, u.username, u.first_name, u.last_name,
                        COUNT(r.id) as referral_count,
                        u.points
                    FROM users u
                    LEFT JOIN referrals r ON u.user_id = r.referred_by
                    GROUP BY u.user_id
                    ORDER BY referral_count DESC, u.points DESC
                    LIMIT 10
                ''')
                
                if not top_users:
                    await update.message.reply_text("لا توجد إحالات مسجلة بعد!")
                    return
                
                message = "🏆 <b>أفضل 10 أعضاء في الإحالات</b> 🏆\n\n"
                for idx, user in enumerate(top_users, 1):
                    message += (
                        f"{get_rank_emoji(idx)} {get_user_display_name(user)} - "
                        f"📊 {user['referral_count']} إحالة - "
                        f"⭐ {user['points']} نقطة\n"
                    )
                
                # إحصائيات المستخدم الحالي
                user_stats = await conn.fetchrow('''
                    SELECT 
                        (SELECT COUNT(*) FROM referrals WHERE referred_by = $1) as referral_count,
                        points
                    FROM users
                    WHERE user_id = $1
                ''', update.effective_user.id)
                
                if user_stats:
                    message += (
                        f"\n📌 <b>إحصائياتك:</b>\n"
                        f"• عدد إحالاتك: {user_stats['referral_count']}\n"
                        f"• نقاطك: {user_stats['points']}\n\n"
                        f"استخدم /referral للحصول على رابط إحالتك!"
                    )
                
                await update.message.reply_text(message, parse_mode='HTML')
                
    except Exception as e:
        logger.error(f"خطأ في لوحة المتصدرين: {e}", exc_info=True)
        await update.message.reply_text("حدث خطأ في جلب بيانات المتصدرين. يرجى المحاولة لاحقاً.")

async def help_command(update: Update, context: CallbackContext) -> None:
    """عرض رسالة المساعدة"""
    if not update.message:
        return
        
    help_text = (
        "🆘 <b>مساعدة بوت MissionX</b>\n\n"
        "📌 <b>الأوامر المتاحة:</b>\n"
        "/start - بدء استخدام البوت\n"
        "/links - روابط المنصات الرسمية\n"
        "/referral - الحصول على رابط الإحالة الخاص بك\n"
        "/leaderboard - عرض أفضل الأعضاء في الإحالات\n"
        "/help - عرض هذه الرسالة\n\n"
        "🔗 <b>نظام الإحالات:</b>\n"
        "1. احصل على رابط إحالتك باستخدام /referral\n"
        "2. شارك الرابط مع أصدقائك\n"
        "3. عندما ينضمون عبر الرابط، تحصل على 10 نقاط لكل إحالة\n"
        "4. تظهر في لوحة المتصدرين كلما زادت إحالاتك\n\n"
        "⭐ <b>نظام النقاط:</b>\n"
        "- 10 نقاط لكل إحالة ناجحة\n"
        "- النقاط تظهر في ملفك الشخصي ولوحة المتصدرين"
    )
    try:
        await update.message.reply_text(help_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"خطأ في إرسال رسالة المساعدة: {e}")

async def on_shutdown(app: Application) -> None:
    """إغلاق اتصالات قاعدة البيانات عند إيقاف البوت"""
    try:
        await Database.close_pool()
        logger.info("تم إغلاق اتصال PostgreSQL")
    except Exception as e:
        logger.error(f"خطأ أثناء إغلاق اتصال قاعدة البيانات: {e}")

async def check_referrals(update: Update, context: CallbackContext) -> None:
    """فحص الإحالات (لأغراض التصحيح)"""
    ADMIN_IDS = [123456789]  # استبدل بأيدي المشرفين الفعليين
    
    if not update.message or not update.effective_user:
        return
        
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("هذا الأمر للمشرفين فقط!")
        return
    
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                stats = await conn.fetchrow('''
                    SELECT 
                        COUNT(*) as total_referrals,
                        COUNT(DISTINCT referred_by) as unique_referrers,
                        COUNT(DISTINCT referred_user_id) as unique_referred_users
                    FROM referrals
                ''')
                
                message = (
                    "📊 <b>إحصائيات الإحالات:</b>\n\n"
                    f"• إجمالي الإحالات: {stats['total_referrals']}\n"
                    f"• عدد المحيلين المختلفين: {stats['unique_referrers']}\n"
                    f"• عدد المستخدمين المحالين المختلفين: {stats['unique_referred_users']}\n\n"
                    "آخر 5 إحالات:\n"
                )
                
                last_refs = await conn.fetch('''
                    SELECT r.*, u1.username as referrer_username, u2.username as referred_username
                    FROM referrals r
                    LEFT JOIN users u1 ON r.referred_by = u1.user_id
                    LEFT JOIN users u2 ON r.referred_user_id = u2.user_id
                    ORDER BY r.referral_date DESC
                    LIMIT 5
                ''')
                
                for ref in last_refs:
                    message += (
                        f"- {ref['referrer_username'] or ref['referred_by']} أحال "
                        f"{ref['referred_username'] or ref['referred_user_id']} "
                        f"في {ref['referral_date'].astimezone().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                
                await update.message.reply_text(message, parse_mode='HTML')
                
    except Exception as e:
        logger.error(f"خطأ في فحص الإحالات: {e}")
        await update.message.reply_text("حدث خطأ أثناء جلب الإحصائيات.")

def main() -> None:
    """تشغيل البوت"""
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("لم يتم تعيين BOT_TOKEN!")
        raise ValueError("BOT_TOKEN environment variable is required")

    try:
        app = Application.builder().token(TOKEN).build()
        
        # تسجيل المعالجات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("links", links))
        app.add_handler(CommandHandler("referral", referral))
        app.add_handler(CommandHandler("leaderboard", leaderboard))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("check_refs", check_referrals))
        
        # إدارة إيقاف التشغيل
        app.on_shutdown(on_shutdown)
        
        logger.info("بدأ البوت في الاستماع...")
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.critical(f"تعطل البوت: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(init_db())
        main()
    except Exception as e:
        logger.critical(f"فشل تشغيل البوت: {e}", exc_info=True)
