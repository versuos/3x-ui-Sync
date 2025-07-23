import sqlite3
import time
import schedule
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from datetime import datetime
import json
import logging
import asyncio

# تنظیم لاگ‌گیری
logging.basicConfig(filename='/opt/3x-ui-sync/sync_xui.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# تنظیمات ربات تلگرام
TELEGRAM_BOT_TOKEN = "8036904228:AAELw-wxr92SPpsfHPlJcIITCg8bHdukJss"  # توکن ربات
TELEGRAM_CHAT_ID = "54515010"     # شناسه مدیر یا کانال
DB_PATH = "/etc/x-ui/x-ui.db"     # مسیر پایگاه داده 3X-UI

# متغیر برای کنترل وضعیت همگام‌سازی
is_sync_running = True

async def send_telegram_message(message):
    """ارسال پیام به تلگرام"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info(f"پیام تلگرام ارسال شد: {message}")
    except Exception as e:
        logging.error(f"خطا در ارسال پیام تلگرام: {str(e)}")

def sync_users():
    """همگام‌سازی ترافیک، تاریخ انقضا و وضعیت فعال/غیرفعال کاربران با subId یکسان"""
    try:
        # اتصال به پایگاه داده
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # دریافت تمام اطلاعات ترافیک
        cursor.execute("SELECT id, inbound_id, email, up, down, expiry_time, enable FROM client_traffics")
        traffics = cursor.fetchall()

        # دریافت تنظیمات اینباند‌ها برای استخراج subId و total
        cursor.execute("SELECT id, settings FROM inbounds")
        inbounds = cursor.fetchall()

        # ایجاد دیکشنری برای نگاشت inbound_id و email به subId و total
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

        # گروه‌بندی کاربران بر اساس subId
        user_groups = {}
        for traffic in traffics:
            traffic_id, inbound_id, email, up, down, expiry_time, enable = traffic
            sub_id = inbound_to_subid.get((inbound_id, email))
            if sub_id:
                if sub_id not in user_groups:
                    user_groups[sub_id] = []
                user_groups[sub_id].append(traffic)

        # چاپ گروه‌ها برای عیب‌یابی
        logging.info(f"گروه‌های کاربران: {user_groups}")

        # همگام‌سازی ترافیک، تاریخ انقضا و وضعیت فعال/غیرفعال
        for sub_id, group in user_groups.items():
            if len(group) > 1:  # فقط کاربران با subId یکسان در اینباندهای مختلف
                # انتخاب بیشترین مقدار ترافیک و انقضا
                max_up = max(traffic[3] for traffic in group if traffic[3] is not None)
                max_down = max(traffic[4] for traffic in group if traffic[4] is not None)
                max_expiry = max(traffic[5] for traffic in group if traffic[5] is not None)

                # بررسی وضعیت غیرفعال بودن (اتمام حجم یا زمان)
                is_any_disabled = False
                for traffic in group:
                    traffic_id, inbound_id, email, up, down, expiry_time, enable = traffic
                    total = inbound_to_total.get((inbound_id, email), 0)
                    # بررسی اتمام حجم
                    if total > 0 and (up + down) >= total:
                        is_any_disabled = True
                        break
                    # بررسی اتمام زمان
                    current_time = int(time.time() * 1000)  # زمان فعلی به میلی‌ثانیه
                    if expiry_time > 0 and expiry_time <= current_time:
                        is_any_disabled = True
                        break
                    # بررسی غیرفعال بودن
                    if enable == 0:
                        is_any_disabled = True
                        break

                # به‌روزرسانی تمام کاربران در گروه
                for traffic in group:
                    traffic_id = traffic[0]
                    enable_status = 0 if is_any_disabled else 1
                    cursor.execute(
                        "UPDATE client_traffics SET up = ?, down = ?, expiry_time = ?, enable = ? WHERE id = ?",
                        (max_up, max_down, max_expiry, enable_status, traffic_id)
                    )

                logging.info(f"همگام‌سازی برای subId: {sub_id} انجام شد - وضعیت: {'غیرفعال' if is_any_disabled else 'فعال'}")

        # ارسال پیام تلگرام پس از اتمام همگام‌سازی
        if user_groups:  # فقط اگر گروه‌هایی برای همگام‌سازی وجود داشت
            message = "مصرف اینباند‌ها آپدیت شدند"
            asyncio.run(send_telegram_message(message))

        conn.commit()
        conn.close()
        logging.info("همگام‌سازی با موفقیت انجام شد")

    except Exception as e:
        error_message = f"خطا در همگام‌سازی: {str(e)}"
        logging.error(error_message)
        asyncio.run(send_telegram_message(error_message))

async def start(update, context):
    """نمایش منوی Inline با دستور /start"""
    keyboard = [
        [InlineKeyboardButton("شروع همگام‌سازی", callback_data='start_sync')],
        [InlineKeyboardButton("توقف همگام‌سازی", callback_data='stop_sync')],
        [InlineKeyboardButton("بررسی وضعیت", callback_data='status')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لطفاً یک گزینه را انتخاب کنید:", reply_markup=reply_markup)

async def button_callback(update, context):
    """مدیریت کلیک روی دکمه‌های Inline"""
    global is_sync_running
    query = update.callback_query
    await query.answer()

    if query.data == 'start_sync':
        is_sync_running = True
        await query.message.reply_text("همگام‌سازی شروع شد.")
        logging.info("همگام‌سازی توسط کاربر شروع شد")
    elif query.data == 'stop_sync':
        is_sync_running = False
        schedule.clear()  # پاک کردن تمام وظایف زمان‌بندی‌شده
        await query.message.reply_text("همگام‌سازی متوقف شد.")
        logging.info("همگام‌سازی توسط کاربر متوقف شد")
    elif query.data == 'status':
        status = "در حال اجرا" if is_sync_running else "متوقف"
        await query.message.reply_text(f"وضعیت همگام‌سازی: {status}")
        logging.info(f"وضعیت بررسی شد: {status}")

def run_schedule():
    """اجرای وظایف زمان‌بندی‌شده"""
    while True:
        if is_sync_running:
            schedule.run_pending()
        time.sleep(1)

def main():
    """نقطه ورود اصلی برنامه"""
    # تنظیم زمان‌بندی همگام‌سازی هر 10 دقیقه
    schedule.every(10).minutes.do(sync_users)

    # تنظیم ربات تلگرام
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))

    # اجرای ربات و زمان‌بندی در تردهای جداگانه
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_schedule)
    application.run_polling()

if __name__ == "__main__":
    main()
