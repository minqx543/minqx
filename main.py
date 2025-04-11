import os
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
)

# تكوين التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# حالات المحادثة
TASK_NAME, TASK_DUE_DATE, TASK_DESCRIPTION = range(3)

# قاعدة بيانات مؤقتة
tasks_db: Dict[int, Dict[int, Dict]] = {}  # {user_id: {task_id: task_data}}
accounts_db: Dict[int, Dict[str, str]] = {}  # {user_id: account_data}
scores_db: Dict[int, int] = {}  # {user_id: score}
referrals_db: Dict[int, Dict[str, str]] = {}  # {user_id: {ref_code: str, ref_count: int}}

# روابط ثابتة
BOT_USERNAME = "MinQX_Bot"
WELCOME_IMAGE_URL = "https://github.com/minqx543/minqx/blob/main/src/default_avatar.jpg.png?raw=true"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"

def start(update: Update, context: CallbackContext) -> None:
    """إرسال رسالة ترحيبية عند استخدام الأمر /start"""
    user = update.effective_user
    user_id = user.id
    
    # إنشاء سجل للمستخدم الجديد إذا لم يكن موجودًا
    if user_id not in scores_db:
        scores_db[user_id] = 0
    if user_id not in referrals_db:
        referrals_db[user_id] = {"ref_code": f"ref_{user_id}", "ref_count": 0}
    
    # التحقق من وجود رابط إحالة
    if context.args:
        referrer_code = context.args[0]
        for uid, data in referrals_db.items():
            if data["ref_code"] == referrer_code and uid != user_id:
                scores_db[uid] += 10  # إضافة 10 نقاط للمحيل
                referrals_db[uid]["ref_count"] += 1
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="🎉 تمت إحالتك بنجاح! 🎉\nYou have been successfully referred!"
                )
                break
    
    # رسالة الترحيب ثنائية اللغة
    welcome_message = (
        f"🎊 مرحبًا بك {user.first_name} في @{BOT_USERNAME} 🎊\n"
        f"✨ Welcome {user.first_name} to @{BOT_USERNAME} ✨\n\n"
        
        "📌 الأوامر المتاحة / Available Commands:\n"
        "/start - 🎉 بدء/Start 🎉\n"
        "/score - 🤑 النقاط/Points 🤑\n"
        "/tasks - ✅️ المهام/Tasks ✅️\n"
        "/top - 🥇 المتصدرين/Top Players 🥇\n"
        "/referrals - 🔥 الإحالات/Referrals 🔥\n"
        "/topreferrals - 🥇 أفضل المحيلين/Top Referrals 🥇\n\n"
        
        f"🔗 رابط البوت / Bot Link: @{BOT_USERNAME}\n"
        f"🌐 الرابط المباشر: {BOT_LINK}"
    )
    
    # أزرار الترحيب
    keyboard = [
        [
            InlineKeyboardButton("🚀 بدء الاستخدام / Start", callback_data="get_started"),
            InlineKeyboardButton("📢 مشاركة البوت / Share", url=f"https://t.me/share/url?url={BOT_LINK}&text=انضم%20إلى%20@{BOT_USERNAME}%20-%20بوت%20رائع%20لإدارة%20المهام%20والحسابات!")
        ],
        [
            InlineKeyboardButton("🌐 زيارة البوت / Visit Bot", url=BOT_LINK),
            InlineKeyboardButton("📊 لوحة التحكم / Dashboard", callback_data="dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # إرسال الصورة مع الرسالة
    try:
        update.message.reply_photo(
            photo=WELCOME_IMAGE_URL,
            caption=welcome_message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send welcome image: {e}")
        # إذا فشل إرسال الصورة، نرسل الرسالة فقط
        update.message.reply_text(
            text=welcome_message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# ... (بقية الدوال تبقى كما هي بدون تغيير)

def main() -> None:
    """تشغيل البوت"""
    # الحصول على توكن البوت من متغيرات البيئة
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("لم يتم تعيين TELEGRAM_BOT_TOKEN في متغيرات البيئة")
    
    # إنشاء Updater مع use_context=True
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher

    # تعريف معالج الأوامر
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("score", show_score))
    dispatcher.add_handler(CommandHandler("top", show_top_players))
    dispatcher.add_handler(CommandHandler("referrals", show_referral_link))
    dispatcher.add_handler(CommandHandler("topreferrals", show_top_referrals))
    dispatcher.add_handler(CommandHandler("tasks", tasks_menu))
    
    # معالج المحادثة لإضافة المهام
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('addtask', add_task_start)],
        states={
            TASK_NAME: [MessageHandler(Filters.text & ~Filters.command, add_task_name)],
            TASK_DUE_DATE: [MessageHandler(Filters.text & ~Filters.command, add_task_due_date)],
            TASK_DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, add_task_description)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dispatcher.add_handler(conv_handler)
    
    # معالج استدعاءات الأزرار
    dispatcher.add_handler(CallbackQueryHandler(view_task, pattern='^view_task_'))
    dispatcher.add_handler(CallbackQueryHandler(complete_task, pattern='^complete_task_'))
    dispatcher.add_handler(CallbackQueryHandler(delete_task, pattern='^delete_task_'))
    dispatcher.add_handler(CallbackQueryHandler(tasks_menu, pattern='^back_to_tasks$'))
    dispatcher.add_handler(CallbackQueryHandler(add_task_start, pattern='^add_new_task$'))
    
    # معالج الأخطاء
    dispatcher.add_error_handler(error_handler)

    # بدء البوت
    if os.getenv('ENVIRONMENT') == 'PRODUCTION':
        # في البيئة الإنتاجية (Render) نستخدم webhook
        port = int(os.getenv('PORT', 8443))
        webhook_url = os.getenv('WEBHOOK_URL')
        if not webhook_url:
            raise ValueError("لم يتم تعيين WEBHOOK_URL في متغيرات البيئة")
        
        updater.start_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=f"{webhook_url}/{token}"
        )
        logger.info("البوت يعمل في وضع webhook")
    else:
        # في البيئة التطويرية نستخدم polling
        updater.start_polling()
        logger.info("البوت يعمل في وضع polling")

    updater.idle()

if __name__ == '__main__':
    main()
