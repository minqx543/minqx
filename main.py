from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# قائمة روابط المنصات مع الأيقونات الخاصة بها
platform_links = {
    'Telegram': 'https://t.me/MissionX_offici',
    'YouTube': 'https://youtube.com/@missionx_offici?si=qfAeZiZLbocPNPEg',
    'Instagram': 'https://www.instagram.com/missionx_offici?igsh=MTRhNmJtNm1wYWxqYw==',
    'Facebook': 'https://www.facebook.com/share/16XnNU7d2f/',
    'TikTok': 'https://www.tiktok.com/@missionx_offici?_t=ZS-8vgkpj65Axz&_r=1',
    'Twitter': 'https://x.com/MissionX_Offici?t=m8UsTWjQrgF59mZ5s88CFA&s=09'
}

# نموذج بيانات الإحالات
referrals = {
    1: {'user': 'User1', 'referrals_count': 15},
    2: {'user': 'User2', 'referrals_count': 12},
    3: {'user': 'User3', 'referrals_count': 10},
    4: {'user': 'User4', 'referrals_count': 9},
    5: {'user': 'User5', 'referrals_count': 8},
    6: {'user': 'User6', 'referrals_count': 7},
    7: {'user': 'User7', 'referrals_count': 6},
    8: {'user': 'User8', 'referrals_count': 5},
    9: {'user': 'User9', 'referrals_count': 4},
    10: {'user': 'User10', 'referrals_count': 3}
}

# دالة لعرض روابط المنصات
async def show_platform_links(update: Update, context: CallbackContext):
    message = "🌐 روابط المنصات:\n\n"
    for platform, link in platform_links.items():
        message += f"{platform}: {link}\n"
    await update.message.reply_text(message)

# دالة لعرض رابط مخصص للاعب
async def send_referral_link(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    referral_link = f'http://t.me/MissionxX_bot?start={user_id}'
    await update.message.reply_text(f"🔗 رابطك المخصص: {referral_link}")

# دالة لعرض أول 10 إحالات
async def show_top_referrals(update: Update, context: CallbackContext):
    message = "🏆 أول 10 إحالات:\n\n"
    sorted_referrals = sorted(referrals.items(), key=lambda x: x[1]['referrals_count'], reverse=True)
    for rank, (key, value) in enumerate(sorted_referrals[:10], start=1):
        message += f"{rank}. {value['user']} - {value['referrals_count']} إحالات\n"
    await update.message.reply_text(message)

async def main():
    # أدخل التوكن الخاص بك هنا
    application = Application.builder().token("YOUR_BOT_TOKEN").build()

    # إضافة الأوامر
    application.add_handler(CommandHandler('platforms', show_platform_links))  # أمر لعرض روابط المنصات
    application.add_handler(CommandHandler('referral_link', send_referral_link))  # أمر لإرسال الرابط المخصص للاعب
    application.add_handler(CommandHandler('top_referrals', show_top_referrals))  # أمر لعرض أول 10 إحالات

    # بدء البوت
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
