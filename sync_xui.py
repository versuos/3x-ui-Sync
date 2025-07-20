import sqlite3
import time
import schedule
from telegram import Bot
from datetime import datetime
import json
import logging

# تنظیم لاگ‌گیری
logging.basicConfig(filename='sync_xui.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# خواندن تنظیمات از config.json
try:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    TELEGRAM_BOT_TOKEN = config.get('telegram_bot_token', '')
    TELEGRAM_CHAT_ID = config.get('telegram_chat_id', '')
    DB_PATH = config.get('db_path', '/etc/x-ui/x-ui.db')
    SYNC_INTERVAL = config.get('sync_interval', 10)  # مدت زمان همگام‌سازی به دقیقه
except FileNotFoundError:
    logging.error("فایل config.json یافت نشد")
    exit(1)
except json.JSONDecodeError:
    logging.error("خطا در خواندن فایل config.json")
    exit(1)

async def send_telegram_message(message):
    """ارسال پیام به تلگرام"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logging.error(f"خطا در ارسال پیام تلگرام: {str(e)}")

def sync_users():
    """همگام‌سازی ترافیک و تاریخ انقضای تمام کاربران با subId یکسان"""
    try:
        # اتصال به پایگاه داده
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # دریافت تمام اطلاعات ترافیک
        cursor.execute("SELECT id, inbound_id, email, up, down, expiry_time FROM client_traffics")
        traffics = cursor.fetchall()

        # دریافت تنظیمات اینباند‌ها برای استخراج subId
        cursor.execute("SELECT id, settings FROM inbounds")
        inbounds = cursor.fetchall()

        # ایجاد دیکشنری برای نگاشت inbound_id و email به subId
        inbound_to_subid = {}
        for inbound_id, settings in inbounds:
            try:
                settings_json = json.loads(settings)
                clients = settings_json.get("clients", [])
                for client in clients:
                    sub_id = client.get("subId")
                    email = client.get("email")
                    if sub_id and email:
                        inbound_to_subid[(inbound_id, email)] = sub_id
            except json.JSONDecodeError:
                logging.warning(f"خطا در تجزیه JSON برای inbound_id: {inbound_id}")
                continue

        # گروه‌بندی کاربران بر اساس subId
        user_groups = {}
        for traffic in traffics:
            traffic_id, inbound_id, email, up, down, expiry_time = traffic
            sub_id = inbound_to_subid.get((inbound_id, email))
            if sub_id:
                if sub_id not in user_groups:
                    user_groups[sub_id] = []
                user_groups[sub_id].append(traffic)

        # همگام‌سازی ترافیک و تاریخ انقضا
        for sub_id, group in user_groups.items():
            if len(group) > 1:  # فقط کاربران با subId یکسان در اینباندهای مختلف
                # جمع‌آوری اطلاعات ترافیک و انقضا
                total_up = sum(traffic[3] for traffic in group if traffic[3] is not None)
                total_down = sum(traffic[4] for traffic in group if traffic[4] is not None)
                max_expiry = max(traffic[5] for traffic in group if traffic[5] is not None)

                # به‌روزرسانی تمام کاربران با مقادیر جمع‌شده
                for traffic in group:
                    traffic_id = traffic[0]
                    cursor.execute(
                        "UPDATE client_traffics SET up = ?, down = ?, expiry_time = ? WHERE id = ?",
                        (total_up, total_down, max_expiry, traffic_id)
                    )

                # ارسال گزارش به تلگرام
                emails = [traffic[2] for traffic in group]
                message = (
                    f"همگام‌سازی انجام شد برای subId: {sub_id}\n"
                    f"ایمیل‌ها: {', '.join(emails)}\n"
                    f"ترافیک آپلود: {total_up/(1024**3):.2f} GB\n"
                    f"ترافیک دانلود: {total_down/(1024**3):.2f} GB\n"
                    f"تاریخ انقضا: {datetime.fromtimestamp(max_expiry/1000) if max_expiry else 'نامشخص'}"
                )
                import asyncio
                asyncio.run(send_telegram_message(message))
                logging.info(f"همگام‌سازی برای subId: {sub_id} انجام شد")

        conn.commit()
        conn.close()
        print("همگام‌سازی با موفقیت انجام شد.")
        logging.info("همگام‌سازی با موفقیت انجام شد")

    except Exception as e:
        error_message = f"خطا در همگام‌سازی: {str(e)}"
        print(error_message)
        logging.error(error_message)
        import asyncio
        asyncio.run(send_telegram_message(error_message))

def main():
    # اجرای تابع sync_users با فاصله زمانی مشخص‌شده
    schedule.every(SYNC_INTERVAL).minutes.do(sync_users)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()