import os
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
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
        context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=WELCOME_IMAGE_URL,
            caption=welcome_message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send welcome image: {e}")
        # إذا فشل إرسال الصورة، نرسل الرسالة فقط
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome_message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

def show_score(update: Update, context: CallbackContext) -> None:
    """عرض نقاط اللاعب"""
    user_id = update.effective_user.id
    score = scores_db.get(user_id, 0)
    
    # حساب المركز الحالي
    sorted_scores = sorted(scores_db.items(), key=lambda x: x[1], reverse=True)
    rank = next((i+1 for i, (uid, _) in enumerate(sorted_scores) if uid == user_id), len(sorted_scores)+1)
    
    message = (
        f"🤑 نقاطك الحالية: {score} نقطة 🤑\n"
        f"🏅 مركزك الحالي: {rank} من بين {len(scores_db)} لاعبًا 🏅"
    )
    update.message.reply_text(message)

def show_top_players(update: Update, context: CallbackContext) -> None:
    """عرض أفضل 10 لاعبين"""
    if not scores_db:
        update.message.reply_text("لا يوجد لاعبين حتى الآن!")
        return
    
    sorted_scores = sorted(scores_db.items(), key=lambda x: x[1], reverse=True)[:10]
    
    message = "🥇 أفضل 10 لاعبين 🥇\n\n"
    for i, (user_id, score) in enumerate(sorted_scores):
        try:
            user = context.bot.get_chat(user_id)
            name = user.first_name or user.username or f"User {user_id}"
        except:
            name = f"User {user_id}"
        
        message += f"{i+1}. {name} - {score} نقطة\n"
    
    update.message.reply_text(message)

def show_referral_link(update: Update, context: CallbackContext) -> None:
    """عرض رابط الإحالة الخاص باللاعب"""
    user_id = update.effective_user.id
    
    if user_id not in referrals_db:
        referrals_db[user_id] = {"ref_code": f"ref_{user_id}", "ref_count": 0}
    
    ref_code = referrals_db[user_id]["ref_code"]
    ref_count = referrals_db[user_id]["ref_count"]
    ref_link = f"https://t.me/{BOT_USERNAME}?start={ref_code}"
    
    message = (
        f"🔥 رابط الإحالة الخاص بك 🔥\n\n"
        f"🔗 [رابط الإحالة]({ref_link})\n\n"
        f"📊 عدد الأشخاص الذين أحلتهم: {ref_count}\n"
        f"💰 ستحصل على 10 نقاط لكل شخص يسجل باستخدام رابطك!\n\n"
        f"رابط البوت: @{BOT_USERNAME}"
    )
    
    keyboard = [
        [InlineKeyboardButton("مشاركة الرابط", url=f"https://t.me/share/url?url={ref_link}&text=انضم%20إلى%20هذا%20البوت%20الرائع%20باستخدام%20رابطي%20الخاص!")],
        [InlineKeyboardButton("زيارة البوت", url=BOT_LINK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        message, 
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

def show_top_referrals(update: Update, context: CallbackContext) -> None:
    """عرض أفضل 10 أشخاص في الإحالات"""
    if not referrals_db:
        update.message.reply_text("لا يوجد بيانات إحالات حتى الآن!")
        return
    
    sorted_refs = sorted(referrals_db.items(), key=lambda x: x[1]["ref_count"], reverse=True)[:10]
    
    message = "🥇 أفضل 10 أشخاص في الإحالات 🥇\n\n"
    for i, (user_id, data) in enumerate(sorted_refs):
        try:
            user = context.bot.get_chat(user_id)
            name = user.first_name or user.username or f"User {user_id}"
        except:
            name = f"User {user_id}"
        
        message += f"{i+1}. {name} - {data['ref_count']} إحالة\n"
    
    update.message.reply_text(message)

def tasks_menu(update: Update, context: CallbackContext) -> None:
    """عرض قائمة المهام"""
    user_id = update.effective_user.id
    
    # إضافة 5 نقاط لكل مرة يزور فيها المستخدم قائمة المهام
    scores_db[user_id] = scores_db.get(user_id, 0) + 5
    
    if user_id not in tasks_db or not tasks_db[user_id]:
        update.message.reply_text("✅️ لا يوجد لديك أي مهام حالية. ✅️")
        return

    tasks = tasks_db[user_id]
    keyboard = []
    for task_id, task in tasks.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{task['name']} - {task['due_date']}",
                callback_data=f"view_task_{task_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("إضافة مهمة جديدة", callback_data="add_new_task")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("✅️ المهام المتاحة ✅️", reply_markup=reply_markup)

def view_task(update: Update, context: CallbackContext) -> None:
    """عرض تفاصيل مهمة محددة"""
    query = update.callback_query
    query.answer()
    task_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    task = tasks_db[user_id][task_id]
    due_date = datetime.strptime(task['due_date'], "%Y-%m-%d").date()
    days_left = (due_date - datetime.now().date()).days
    
    task_details = (
        f"اسم المهمة: {task['name']}\n"
        f"تاريخ الاستحقاق: {task['due_date']} (باقي {days_left} يوم)\n"
        f"الوصف: {task['description']}\n"
        f"الحالة: {'مكتملة' if task['completed'] else 'غير مكتملة'}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("تم الإنجاز", callback_data=f"complete_task_{task_id}"),
            InlineKeyboardButton("حذف", callback_data=f"delete_task_{task_id}"),
        ],
        [InlineKeyboardButton("العودة إلى القائمة", callback_data="back_to_tasks")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=task_details, reply_markup=reply_markup)

def complete_task(update: Update, context: CallbackContext) -> None:
    """تحديد المهمة كمكتملة"""
    query = update.callback_query
    query.answer()
    task_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    tasks_db[user_id][task_id]['completed'] = True
    query.edit_message_text(text="تم تحديث حالة المهمة إلى مكتملة.")

def delete_task(update: Update, context: CallbackContext) -> None:
    """حذف مهمة"""
    query = update.callback_query
    query.answer()
    task_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    
    del tasks_db[user_id][task_id]
    query.edit_message_text(text="تم حذف المهمة بنجاح.")

def add_task_start(update: Update, context: CallbackContext) -> int:
    """بدء عملية إضافة مهمة جديدة"""
    update.message.reply_text("ما هو اسم المهمة؟")
    return TASK_NAME

def add_task_name(update: Update, context: CallbackContext) -> int:
    """حفظ اسم المهمة والانتقال إلى تاريخ الاستحقاق"""
    context.user_data['task_name'] = update.message.text
    update.message.reply_text("ما هو تاريخ استحقاق المهمة؟ (YYYY-MM-DD)")
    return TASK_DUE_DATE

def add_task_due_date(update: Update, context: CallbackContext) -> int:
    """حفظ تاريخ الاستحقاق والانتقال إلى الوصف"""
    try:
        due_date = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        context.user_data['due_date'] = update.message.text
        update.message.reply_text("أدخل وصفًا للمهمة (اختياري):")
        return TASK_DESCRIPTION
    except ValueError:
        update.message.reply_text("صيغة التاريخ غير صحيحة. الرجاء إدخال التاريخ بالصيغة YYYY-MM-DD")
        return TASK_DUE_DATE

def add_task_description(update: Update, context: CallbackContext) -> int:
    """حفظ الوصف وإنهاء العملية"""
    user_id = update.effective_user.id
    task_name = context.user_data['task_name']
    due_date = context.user_data['due_date']
    description = update.message.text
    
    if user_id not in tasks_db:
        tasks_db[user_id] = {}
    
    task_id = max(tasks_db[user_id].keys(), default=0) + 1
    tasks_db[user_id][task_id] = {
        'name': task_name,
        'due_date': due_date,
        'description': description,
        'completed': False,
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    update.message.reply_text(f"تمت إضافة المهمة '{task_name}' بنجاح!")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """إلغاء المحادثة"""
    update.message.reply_text('تم الإلغاء.')
    return ConversationHandler.END

def error_handler(update: Update, context: CallbackContext) -> None:
    """معالجة الأخطاء"""
    logger.error(msg="حدث خطأ في البوت", exc_info=context.error)
    if update.message:
        update.message.reply_text('عذرًا، حدث خطأ ما. الرجاء المحاولة لاحقًا.')

def main() -> None:
    """تشغيل البوت"""
    # الحصول على توكن البوت من متغيرات البيئة
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("لم يتم تعيين TELEGRAM_BOT_TOKEN في متغيرات البيئة")
    
    updater = Updater(token)
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
            TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_name)],
            TASK_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_due_date)],
            TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_description)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dispatcher.add_handler(conv_handler)
    
    # معالج استدعاءات الأزرار
    dispatcher.add_handler(CallbackQueryHandler(view_task, pattern=r'^view_task_\d+$'))
    dispatcher.add_handler(CallbackQueryHandler(complete_task, pattern=r'^complete_task_\d+$'))
    dispatcher.add_handler(CallbackQueryHandler(delete_task, pattern=r'^delete_task_\d+$'))
    dispatcher.add_handler(CallbackQueryHandler(tasks_menu, pattern=r'^back_to_tasks$'))
    dispatcher.add_handler(CallbackQueryHandler(add_task_start, pattern=r'^add_new_task$'))
    
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
            url_path=token,
            webhook_url=f"{webhook_url}/{token}"
        )
        updater.bot.set_webhook(f"{webhook_url}/{token}")
        logger.info("البوت يعمل في وضع webhook")
    else:
        # في البيئة التطويرية نستخدم polling
        updater.start_polling()
        logger.info("البوت يعمل في وضع polling")

    updater.idle()

if __name__ == '__main__':
    main()
