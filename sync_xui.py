import sqlite3
import time
import schedule
from telegram import Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from datetime import datetime
import json
import logging
import asyncio
import re
import os

# تنظیم لاگ‌گیری
logging.basicConfig(filename='/opt/3x-ui-sync/sync_xui.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# تنظیمات ربات تلگرام
with open('/opt/3x-ui-sync/config.json') as f:
    config = json.load(f)
    TELEGRAM_BOT_TOKEN = config['TELEGRAM_BOT_TOKEN']
    TELEGRAM_CHAT_ID = config['TELEGRAM_CHAT_ID']
    sync_interval = config['SYNC_INTERVAL']

DB_PATH = "/etc/x-ui/x-ui.db"
V2RAY_SERVER_PATH = "/root/v2ray-sub-manager/server.js"

# متغیرهای جهانی
is_sync_running = True
INPUT_INTERVAL, INPUT_CONFIG = range(2)

async def send_telegram_message(message):
    """ارسال پیام به تلگرام"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info(f"پیام تلگرام ارسال شد: {message}")
    except Exception as e:
        logging.error(f"خطا در ارسال پیام تلگرام: {str(e)}")

def sync_users():
    """همگام‌سازی ترافیک، تاریخ انقضا و وضعیت کاربران با subId یکسان"""
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

        logging.info(f"گروه‌های کاربران: {user_groups}")

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
            message = "مصرف اینباند‌ها آپدیت شدند"
            asyncio.run(send_telegram_message(message))

        conn.commit()
        conn.close()
        logging.info("همگام‌سازی با موفقیت انجام شد")
    except Exception as e:
        error_message = f"خطا در همگام‌سازی: {str(e)}"
        logging.error(error_message)
        asyncio.run(send_telegram_message(error_message))

def update_external_config(new_config):
    """به‌روزرسانی کانفیگ خارجی در server.js"""
    try:
        if not re.match(r'^vless://[0-9a-f-]+@[0-9a-zA-Z.-]+:[0-9]+\?', new_config):
            raise ValueError("فرمت کانفیگ VLESS نامعتبر است")
        with open(V2RAY_SERVER_PATH, 'r') as f:
            content = f.read()
        new_content = re.sub(r"const externalConfig = 'vless://[^']*';",
                            f"const externalConfig = '{new_config}';", content)
        with open(V2RAY_SERVER_PATH, 'w') as f:
            f.write(new_content)
        os.system('pm2 restart server')
        logging.info(f"کانفیگ خارجی به‌روزرسانی شد: {new_config}")
        return True
    except Exception as e:
        logging.error(f"خطا در به‌روزرسانی کانفیگ خارجی: {str(e)}")
        return False

async def start(update, context):
    """نمایش کیبورد Reply با دستور /start"""
    keyboard = [
        [
            KeyboardButton("شروع"),
            KeyboardButton("توقف"),
            KeyboardButton("وضعیت"),
            KeyboardButton("تغییر زمان"),
            KeyboardButton("تغییر کانفیگ")
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("گزینه مورد نظر را انتخاب کنید:", reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_button(update, context):
    """مدیریت کلیک روی دکمه‌های Reply Keyboard"""
    global is_sync_running, sync_interval
    message_text = update.message.text

    if message_text == "شروع":
        is_sync_running = True
        schedule.clear()
        schedule.every(sync_interval).minutes.do(sync_users)
        await update.message.reply_text("همگام‌سازی شروع شد.")
        logging.info("همگام‌سازی توسط کاربر شروع شد")
    elif message_text == "توقف":
        is_sync_running = False
        schedule.clear()
        await update.message.reply_text("همگام‌سازی متوقف شد.")
        logging.info("همگام‌سازی توسط کاربر متوقف شد")
    elif message_text == "وضعیت":
        status = "در حال اجرا" if is_sync_running else "متوقف"
        await update.message.reply_text(f"وضعیت: {status}\nزمان همگام‌سازی: {sync_interval} دقیقه")
        logging.info(f"وضعیت بررسی شد: {status}")
    elif message_text == "تغییر زمان":
        await update.message.reply_text("مدت زمان جدید (دقیقه) را وارد کنید:")
        return INPUT_INTERVAL
    elif message_text == "تغییر کانفیگ":
        await update.message.reply_text("کانفیگ VLESS جدید را وارد کنید (شروع با vless://):")
        return INPUT_CONFIG
    return ConversationHandler.END

async def set_interval(update, context):
    """دریافت و اعمال مدت زمان جدید همگام‌سازی"""
    global sync_interval, is_sync_running
    try:
        new_interval = int(update.message.text)
        if new_interval <= 0:
            await update.message.reply_text("لطفاً عدد مثبت وارد کنید.")
            return INPUT_INTERVAL
        sync_interval = new_interval
        with open('/opt/3x-ui-sync/config.json', 'r') as f:
            config = json.load(f)
        config['SYNC_INTERVAL'] = sync_interval
        with open('/opt/3x-ui-sync/config.json', 'w') as f:
            json.dump(config, f, indent=2)
        if is_sync_running:
            schedule.clear()
            schedule.every(sync_interval).minutes.do(sync_users)
        await update.message.reply_text(f"زمان همگام‌سازی به {sync_interval} دقیقه تغییر کرد.")
        logging.info(f"مدت زمان همگام‌سازی به {sync_interval} دقیقه تغییر کرد")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("لطفاً عدد معتبر وارد کنید.")
        return INPUT_INTERVAL

async def set_config(update, context):
    """دریافت و اعمال کانفیگ خارجی جدید"""
    new_config = update.message.text
    if update_external_config(new_config):
        await update.message.reply_text(f"کانفیگ خارجی به‌روزرسانی شد: {new_config}\nسرور Node.js ری‌استارت شد.")
        asyncio.run(send_telegram_message(f"کانفیگ خارجی به‌روزرسانی شد: {new_config}"))
    else:
        await update.message.reply_text("خطا: کانفیگ نامعتبر است یا به‌روزرسانی انجام نشد.")
    return ConversationHandler.END

async def cancel(update, context):
    """لغو عملیات"""
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

def run_schedule():
    """اجرای وظایف زمان‌بندی‌شده"""
    while True:
        if is_sync_running:
            schedule.run_pending()
        time.sleep(1)

def main():
    """نقطه ورود اصلی برنامه"""
    schedule.every(sync_interval).minutes.do(sync_users)
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(تغییر زمان)$'), handle_button),
            MessageHandler(filters.Regex('^(تغییر کانفیگ)$'), handle_button)
        ],
        states={
            INPUT_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_interval)],
            INPUT_CONFIG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_config)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Regex('^(شروع|توقف|وضعیت|تغییر زمان|تغییر کانفیگ)$'), handle_button))
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_schedule)
    application.run_polling()

if __name__ == "__main__":
    main()
