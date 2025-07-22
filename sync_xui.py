import sqlite3
import time
import schedule
import json
import logging
import asyncio  # اضافه کردن asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# تنظیم لاگ‌گیری
logging.basicConfig(filename='/opt/3x-ui-sync/sync_xui.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# مسیر فایل تنظیمات و پایگاه داده
CONFIG_PATH = "/opt/3x-ui-sync/config.json"
DB_PATH = "/etc/x-ui/x-ui.db"

# حالت‌های ConversationHandler
SET_TOKEN, SET_CHATID, SET_INTERVAL = range(3)

# بارگذاری تنظیمات
def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"خطا در بارگذاری تنظیمات: {str(e)}")
        return None

# ذخیره تنظیمات
def save_config(config):
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        logging.info("تنظیمات با موفقیت ذخیره شد")
    except Exception as e:
        logging.error(f"خطا در ذخیره تنظیمات: {str(e)}")

# تابع ارسال پیام به تلگرام
async def send_telegram_message(token, chat_id, message):
    try:
        from telegram import Bot
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message)
        logging.info(f"پیام تلگرام ارسال شد: {message}")
    except Exception as e:
        logging.error(f"خطا در ارسال پیام تلگرام: {str(e)}")

# تابع بررسی دسترسی ادمین
def check_admin(update: Update, config):
    return str(update.effective_chat.id) == config['TELEGRAM_CHAT_ID']

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not config or not check_admin(update, config):
        await update.message.reply_text("دسترسی غیرمجاز!")
        return

    keyboard = [
        [InlineKeyboardButton("🛠 تغییر توکن ربات", callback_data='set_token')],
        [InlineKeyboardButton("👤 تغییر شناسه چت", callback_data='set_chatid')],
        [InlineKeyboardButton("⏰ تغییر بازه زمانی", callback_data='set_interval')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "به ربات 3X-UI User Sync خوش آمدید!\nیکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=reply_markup
    )

# مدیریت انتخاب دکمه‌ها
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = load_config()
    if not config or not check_admin(query, config):
        await query.message.reply_text("دسترسی غیرمجاز!")
        return ConversationHandler.END

    if query.data == 'set_token':
        await query.message.reply_text("لطفاً توکن جدید ربات را وارد کنید:")
        return SET_TOKEN
    elif query.data == 'set_chatid':
        await query.message.reply_text("لطفاً شناسه چت جدید را وارد کنید:")
        return SET_CHATID
    elif query.data == 'set_interval':
        await query.message.reply_text("لطفاً بازه زمانی همگام‌سازی (به دقیقه) را وارد کنید:")
        return SET_INTERVAL

# مدیریت دریافت توکن
async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not config or not check_admin(update, config):
        await update.message.reply_text("دسترسی غیرمجاز!")
        return ConversationHandler.END

    token = update.message.text.strip()
    config['TELEGRAM_BOT_TOKEN'] = token
    save_config(config)
    await update.message.reply_text("توکن ربات با موفقیت تغییر کرد! لطفاً سرویس را ری‌استارت کنید:\n`sudo systemctl restart 3x-ui-sync.service`")
    logging.info(f"توکن ربات تغییر کرد: {token}")
    return ConversationHandler.END

# مدیریت دریافت چت آیدی
async def receive_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not config or not check_admin(update, config):
        await update.message.reply_text("دسترسی غیرمجاز!")
        return ConversationHandler.END

    chat_id = update.message.text.strip()
    config['TELEGRAM_CHAT_ID'] = chat_id
    save_config(config)
    await update.message.reply_text("شناسه چت با موفقیت تغییر کرد!")
    logging.info(f"شناسه چت تغییر کرد: {chat_id}")
    return ConversationHandler.END

# مدیریت دریافت بازه زمانی
async def receive_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not config or not check_admin(update, config):
        await update.message.reply_text("دسترسی غیرمجاز!")
        return ConversationHandler.END

    interval = update.message.text.strip()
    if not interval.isdigit():
        await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید!")
        return SET_INTERVAL
    config['SYNC_INTERVAL'] = int(interval)
    save_config(config)
    schedule.clear()  # پاک کردن زمان‌بندی قبلی
    schedule.every(config['SYNC_INTERVAL']).minutes.do(sync_users)
    await update.message.reply_text(f"بازه زمانی همگام‌سازی به {interval} دقیقه تغییر کرد!")
    logging.info(f"بازه زمانی همگام‌سازی تغییر کرد: {interval} دقیقه")
    return ConversationHandler.END

# لغو عملیات
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

# تابع همگام‌سازی کاربران
def sync_users():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, inbound_id, email, up, down, expiry_time, enable FROM client_traffics")
        traffics = cursor.fetchall()
        cursor.execute("SELECT id, settings FROM inbounds")
        inbounds = cursor.fetchall()

        inbound_to_subid = {}
        inbound_to_total = {}
        for inbound_id, settings in inbounds:
            try:
                settings_json = json.loads(settings)
                clients = settings_json.get("clients", [])
                for client in clients:
                    sub_id = client.get("subId")
                    email = client.get("email")
                    total = client.get("total", 0)
                    if sub_id and email:
                        inbound_to_subid[(inbound_id, email)] = sub_id
                        inbound_to_total[(inbound_id, email)] = total
            except json.JSONDecodeError:
                logging.warning(f"خطا در تجزیه JSON برای inbound_id: {inbound_id}")
                continue

        user_groups = {}
        for traffic in traffics:
            traffic_id, inbound_id, email, up, down, expiry_time, enable = traffic
            sub_id = inbound_to_subid.get((inbound_id, email))
            if sub_id:
                if sub_id not in user_groups:
                    user_groups[sub_id] = []
                user_groups[sub_id].append(traffic)

        logging.info(f"تعداد گروه‌های کاربران: {len(user_groups)}")
        for sub_id, group in user_groups.items():
            if len(group) > 1:
                max_up = max(traffic[3] for traffic in group if traffic[3] is not None)
                max_down = max(traffic[4] for traffic in group if traffic[4] is not None)
                max_expiry = max(traffic[5] for traffic in group if traffic[5] is not None)
                is_any_disabled = False
                for traffic in group:
                    traffic_id, inbound_id, email, up, down, expiry_time, enable = traffic
                    total = inbound_to_total.get((inbound_id, email), 0)
                    if total > 0 and (up + down) >= total:
                        is_any_disabled = True
                        break
                    current_time = int(time.time() * 1000)
                    if expiry_time > 0 and expiry_time <= current_time:
                        is_any_disabled = True
                        break
                    if enable == 0:
                        is_any_disabled = True
                        break
                for traffic in group:
                    traffic_id = traffic[0]
                    enable_status = 0 if is_any_disabled else 1
                    cursor.execute(
                        "UPDATE client_traffics SET up = ?, down = ?, expiry_time = ?, enable = ? WHERE id = ?",
                        (max_up, max_down, max_expiry, enable_status, traffic_id)
                    )
                logging.info(f"همگام‌سازی برای subId: {sub_id} انجام شد - وضعیت: {'غیرفعال' if is_any_disabled else 'فعال'}")

        if user_groups:
            config = load_config()
            if config:
                asyncio.run(send_telegram_message(config['TELEGRAM_BOT_TOKEN'], config['TELEGRAM_CHAT_ID'], "مصرف اینباند‌ها آپدیت شدند"))
        conn.commit()
        conn.close()
        logging.info("همگام‌سازی با موفقیت انجام شد")

    except Exception as e:
        error_message = f"خطا در همگام‌سازی: {str(e)}"
        logging.error(error_message)
        config = load_config()
        if config:
            asyncio.run(send_telegram_message(config['TELEGRAM_BOT_TOKEN'], config['TELEGRAM_CHAT_ID'], error_message))

# تابع اصلی
def main():
    # بارگذاری تنظیمات
    config = load_config()
    if not config:
        logging.error("نمی‌توان تنظیمات را بارگذاری کرد. خروج...")
        return

    # راه‌اندازی ربات تلگرام
    application = Application.builder().token(config['TELEGRAM_BOT_TOKEN']).build()
    
    # تعریف ConversationHandler با تنظیم per_message=True برای رفع هشدار
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CallbackQueryHandler(button)],
        states={
            SET_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
            SET_CHATID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_chatid)],
            SET_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_interval)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=True  # رفع هشدار PTBUserWarning
    )
    application.add_handler(conv_handler)

    # زمان‌بندی همگام‌سازی
    schedule.every(config['SYNC_INTERVAL']).minutes.do(sync_users)

    # اجرای ربات و زمان‌بندی به‌صورت همزمان
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(application.run_polling())
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
