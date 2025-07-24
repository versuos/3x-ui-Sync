import sqlite3
import time
import schedule
import requests
import urllib.parse
from telegram import Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
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

# متغیرهای جهانی
is_sync_running = True
sync_interval = 10  # بازه زمانی پیش‌فرض (دقیقه)
INPUT_INTERVAL, INPUT_VLESS_LINK = range(2)  # حالت‌های ConversationHandler

async def send_telegram_message(message):
    """ارسال پیام به تلگرام"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info(f"پیام تلگرام ارسال شد: {message}")
    except Exception as e:
        logging.error(f"خطا در ارسال پیام تلگرام: {str(e)}")

def sync_users():
    """همگام‌سازی ترافیک و افزودن کانفیگ خارجی به لینک سابسکریپشن"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # دریافت اطلاعات کاربران
        cursor.execute("SELECT id, inbound_id, email, up, down, expiry_time, enable FROM client_traffics")
        traffics = cursor.fetchall()

        # دریافت تنظیمات اینباند‌ها
        cursor.execute("SELECT id, settings FROM inbounds")
        inbounds = cursor.fetchall()

        # گروه‌بندی بر اساس subId
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

        user_groups = {}
        for traffic in traffics:
            traffic_id, inbound_id, email, up, down, expiry_time, enable = traffic
            sub_id = inbound_to_subid.get((inbound_id, email))
            if sub_id:
                if sub_id not in user_groups:
                    user_groups[sub_id] = []
                user_groups[sub_id].append((traffic_id, inbound_id, email))

        # همگام‌سازی و مدیریت کانفیگ
        for sub_id, group in user_groups.items():
            if len(group) > 1:  # فقط گروه‌های با بیش از یک کاربر
                # انتخاب نماینده (اولین کاربر)
                representative = group[0]
                rep_traffic_id, rep_inbound_id, rep_email = representative

                # محاسبه حداکثر ترافیک و انقضا
                max_up = max(traffic[3] for traffic in traffics if traffic[1] in [g[1] for g in group] and traffic[3] is not None)
                max_down = max(traffic[4] for traffic in traffics if traffic[1] in [g[1] for g in group] and traffic[4] is not None)
                max_expiry = max(traffic[5] for traffic in traffics if traffic[1] in [g[1] for g in group] and traffic[5] is not None)

                # بررسی وضعیت غیرفعال
                is_any_disabled = False
                for traffic in traffics:
                    if traffic[1] in [g[1] for g in group]:
                        total = next((inbound_to_total.get((traffic[1], traffic[2]), 0) for _, settings in inbounds if _ == traffic[1]), 0)
                        if total > 0 and (traffic[3] + traffic[4]) >= total:
                            is_any_disabled = True
                            break
                        current_time = int(time.time() * 1000)
                        if traffic[5] > 0 and traffic[5] <= current_time:
                            is_any_disabled = True
                            break
                        if traffic[6] == 0:
                            is_any_disabled = True
                            break

                # به‌روزرسانی همه کاربران گروه
                for traffic_id, inbound_id, email in group:
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

async def start(update, context):
    """نمایش کیبورد Reply با دستور /start"""
    keyboard = [
        [
            KeyboardButton("شروع"),
            KeyboardButton("توقف"),
            KeyboardButton("وضعیت"),
            KeyboardButton("تغییر زمان"),
            KeyboardButton("اضافه کردن لینک vless"),
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
    elif message_text == "اضافه کردن لینک vless":
        await update.message.reply_text("لینک vless (مثل vless://...) را ارسال کنید:")
        return INPUT_VLESS_LINK
    return ConversationHandler.END

async def add_vless_config(update, context):
    """دریافت و اضافه کردن کانفیگ vless از لینک"""
    try:
        vless_link = update.message.text
        # تحلیل لینک vless
        if not vless_link.startswith("vless://"):
            raise ValueError("لینک معتبر vless نیست.")
        
        # استخراج بخش‌های لینک
        parsed_url = urllib.parse.urlparse(vless_link.replace("vless://", ""))
        user_info = urllib.parse.unquote(parsed_url.username)
        host, port = parsed_url.hostname, parsed_url.port or 443
        params = urllib.parse.parse_qs(parsed_url.query)
        fragment = urllib.parse.unquote(parsed_url.fragment)

        # ساخت کانفیگ JSON
        vless_config = {
            "clients": [
                {
                    "subId": "custom_subid",  # باید با subId موجود تطبیق داده شود
                    "email": "vless_user@example.com",  # باید با email موجود تطبیق داده شود
                    "total": 1073741824,  # حجم پیش‌فرض 1GB
                    "id": user_info,
                    "protocol": "vless",
                    "settings": {
                        "vnext": [
                            {
                                "address": host,
                                "port": port,
                                "users": [
                                    {
                                        "id": user_info,
                                        "security": params.get("security", ["none"])[0],
                                        "encryption": params.get("encryption", ["none"])[0],
                                        "flow": params.get("type", [""])[0] if "type" in params else ""
                                    }
                                ]
                            }
                        ]
                    },
                    "streamSettings": {
                        "network": params.get("type", ["grpc"])[0] if "type" in params else "tcp",
                        "security": params.get("security", ["reality"])[0] if "security" in params else "none",
                        "realitySettings": {
                            "publicKey": params.get("pbk", [""])[0],
                            "shortId": params.get("sid", [""])[0],
                            "spiderX": params.get("spx", [""])[0]
                        } if "security" in params and params["security"][0] == "reality" else {},
                        "grpcSettings": {
                            "serviceName": params.get("serviceName", [""])[0]
                        } if params.get("type", [""])[0] == "grpc" else {}
                    }
                }
            ]
        }

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # دریافت اطلاعات کاربران و اینباند‌ها
        cursor.execute("SELECT id, inbound_id, email FROM client_traffics")
        traffics = cursor.fetchall()
        cursor.execute("SELECT id, settings FROM inbounds")
        inbounds = cursor.fetchall()

        # گروه‌بندی بر اساس subId
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

        user_groups = {}
        for traffic_id, inbound_id, email in traffics:
            sub_id = inbound_to_subid.get((inbound_id, email))
            if sub_id:
                if sub_id not in user_groups:
                    user_groups[sub_id] = []
                user_groups[sub_id].append((traffic_id, inbound_id, email))

        # افزودن کانفیگ به نماینده هر گروه
        for sub_id, group in user_groups.items():
            if group:
                representative = group[0]
                rep_traffic_id, rep_inbound_id, rep_email = representative
                cursor.execute("SELECT settings FROM inbounds WHERE id = ?", (rep_inbound_id,))
                settings = cursor.fetchone()
                if settings:
                    settings_json = json.loads(settings[0])
                    external_clients = vless_config["clients"]
                    # تطبیق subId و email
                    for client in external_clients:
                        client["subId"] = sub_id
                        client["email"] = rep_email
                    settings_json["clients"].extend(external_clients)
                    cursor.execute(
                        "UPDATE inbounds SET settings = ? WHERE id = ?",
                        (json.dumps(settings_json), rep_inbound_id)
                    )
                    logging.info(f"کانفیگ vless به inbound_id {rep_inbound_id} اضافه شد")

        conn.commit()
        conn.close()
        await update.message.reply_text(f"کانفیگ vless با موفقیت اضافه شد: {vless_link}")
        return ConversationHandler.END
    except ValueError as e:
        await update.message.reply_text(f"خطا: {str(e)}")
        return INPUT_VLESS_LINK
    except Exception as e:
        await update.message.reply_text(f"خطا در پردازش لینک: {str(e)}")
        logging.error(f"خطا در افزودن کانفیگ vless: {str(e)}")
        return INPUT_VLESS_LINK

async def set_interval(update, context):
    """دریافت و اعمال مدت زمان جدید همگام‌سازی"""
    global sync_interval, is_sync_running
    try:
        new_interval = int(update.message.text)
        if new_interval <= 0:
            await update.message.reply_text("لطفاً عدد مثبت وارد کنید.")
            return INPUT_INTERVAL
        sync_interval = new_interval
        if is_sync_running:
            schedule.clear()
            schedule.every(sync_interval).minutes.do(sync_users)
        await update.message.reply_text(f"زمان همگام‌سازی به {sync_interval} دقیقه تغییر کرد.")
        logging.info(f"مدت زمان همگام‌سازی به {sync_interval} دقیقه تغییر کرد")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("لطفاً عدد معتبر وارد کنید.")
        return INPUT_INTERVAL

async def cancel(update, context):
    """لغو عملیات تغییر مدت زمان یا افزودن لینک"""
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
    # تنظیم زمان‌بندی پیش‌فرض
    schedule.every(sync_interval).minutes.do(sync_users)

    # تنظیم ربات تلگرام
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # تنظیم ConversationHandler برای تغییر مدت زمان و افزودن لینک vless
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(تغییر زمان|اضافه کردن لینک vless)$'), handle_button)
        ],
        states={
            INPUT_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_interval)],
            INPUT_VLESS_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_vless_config)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Regex('^(شروع|توقف|وضعیت|تغییر زمان|اضافه کردن لینک vless)$'), handle_button))

    # اجرای ربات و زمان‌بندی در تردهای جداگانه
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_schedule)
    application.run_polling()

if __name__ == "__main__":
    main()
