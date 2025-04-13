import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# تحميل المهام من الملف
def load_tasks():
    with open("tasks.json", "r") as f:
        return json.load(f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = load_tasks()
    message = "مهام اليوم:\n"
    for i, task in enumerate(tasks, start=1):
        message += f"{i}. {task['type']} - {task['link']}\n"
    await update.message.reply_text(message)

if __name__ == "__main__":
    import os
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()
