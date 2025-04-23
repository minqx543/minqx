#!/usr/bin/env python3
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    filters
)
from referral_system import ReferralSystem
import os
import logging
from datetime import datetime

# Configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MissionXBot:
    def __init__(self):
        self.referral_system = ReferralSystem('missionx_bot.db')
        self.bot_token = os.getenv("BOT_TOKEN")
        if not self.bot_token:
            logger.critical("BOT_TOKEN not found in environment variables!")
            raise ValueError("Missing BOT_TOKEN")

    async def start(self, update: Update, context: CallbackContext) -> None:
        """Handle /start command with referral support"""
        user = update.effective_user
        try:
            with self.referral_system.get_db_connection() as conn:
                # Register/update user
                conn.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name, last_active)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_name=excluded.last_name,
                    last_active=excluded.last_active
                """, (user.id, user.username, user.first_name, user.last_name, datetime.now()))
                
                # Process referral if exists
                if context.args and context.args[0].isdigit():
                    referrer_id = int(context.args[0])
                    if referrer_id != user.id and self.referral_system.add_referral(referrer_id, user.id):
                        referrer_name = self.referral_system.get_user_display_name(referrer_id)
                        await update.message.reply_text(
                            f"شكراً لتسجيلك عبر إحالة {referrer_name}! 🎉\n"
                            f"تم تسجيل إحالتك بنجاح."
                        )
            
            await update.message.reply_text(
                "مرحباً بك في بوت MissionX! 🚀\n\n"
                "الأوامر المتاحة:\n"
                "/start - بدء استخدام البوت\n"
                "/links - روابط المنصات\n"
                "/referral - رابط الإحالة الخاص بك\n"
                "/leaderboard - لوحة المتصدرين\n"
                "/help - المساعدة"
            )
        except Exception as e:
            logger.error(f"Error in /start: {e}")
            await update.message.reply_text("حدث خطأ أثناء معالجة طلبك.")

    async def show_links(self, update: Update, context: CallbackContext) -> None:
        """Show platform links"""
        await update.message.reply_text(
            "🌐 <b>روابطنا الرسمية:</b>\n\n"
            "🔹 <a href='https://t.me/MissionX_offici'>قناة التليجرام</a>\n"
            "🔹 <a href='https://youtube.com/@missionx_offici'>يوتيوب</a>\n"
            "🔹 <a href='https://www.tiktok.com/@missionx_offici'>تيك توك</a>\n"
            "🔹 <a href='https://x.com/MissionX_Offici'>تويتر (X)</a>\n"
            "🔹 <a href='https://www.facebook.com/share/19AMU41hhs/'>فيسبوك</a>\n"
            "🔹 <a href='https://www.instagram.com/missionx_offici'>إنستجرام</a>",
            parse_mode='HTML',
            disable_web_page_preview=True
        )

    async def generate_referral(self, update: Update, context: CallbackContext) -> None:
        """Generate and show referral link"""
        user = update.effective_user
        referral_link = f"https://t.me/MissionxX_bot?start={user.id}"
        count = self.referral_system.get_referral_count(user.id)
        
        await update.message.reply_text(
            f"🎯 <b>رابط الإحالة الخاص بك:</b>\n\n"
            f"<code>{referral_link}</code>\n\n"
            f"📊 عدد الإحالات الناجحة: <b>{count}</b>\n\n"
            "شارك هذا الرابط مع أصدقائك واحصل على نقاط عند انضمامهم!",
            parse_mode='HTML'
        )

    async def show_leaderboard(self, update: Update, context: CallbackContext) -> None:
        """Display referral leaderboard"""
        leaders = self.referral_system.get_leaderboard()
        
        if not leaders:
            await update.message.reply_text("لا توجد إحالات بعد! كن أول من يجلب أعضاء جدد.")
            return

        message = "🏆 <b>أفضل 10 أعضاء في الإحالات</b> 🏆\n\n"
        for idx, leader in enumerate(leaders, 1):
            display_name = self.referral_system._format_display_name(leader)
            message += f"{self._get_rank_emoji(idx)} {display_name} - {leader['referral_count']} إحالة\n"
        
        message += "\nاستخدم /referral للحصول على رابط إحالتك!"
        await update.message.reply_text(message, parse_mode='HTML')

    async def show_help(self, update: Update, context: CallbackContext) -> None:
        """Show help message"""
        await update.message.reply_text(
            "🆘 <b>مساعدة بوت MissionX</b>\n\n"
            "📌 <b>الأوامر المتاحة:</b>\n"
            "/start - بدء استخدام البوت\n"
            "/links - روابط المنصات الرسمية\n"
            "/referral - الحصول على رابط الإحالة الخاص بك\n"
            "/leaderboard - عرض أفضل الأعضاء في الإحالات\n"
            "/help - عرض هذه الرسالة",
            parse_mode='HTML'
        )

    def _get_rank_emoji(self, rank: int) -> str:
        return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")

    def setup_handlers(self, application: Application) -> None:
        """Setup all command handlers"""
        handlers = [
            CommandHandler('start', self.start),
            CommandHandler('links', self.show_links),
            CommandHandler('referral', self.generate_referral),
            CommandHandler('leaderboard', self.show_leaderboard),
            CommandHandler('help', self.show_help),
        ]
        application.add_handlers(handlers)

    def run(self):
        """Run the bot"""
        application = Application.builder().token(self.bot_token).build()
        self.setup_handlers(application)
        
        logger.info("Starting MissionX Bot...")
        application.run_polling()

if __name__ == '__main__':
    try:
        bot = MissionXBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Bot failed: {e}")
        raise
