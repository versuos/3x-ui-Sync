#!/bin/bash

# اطمینان از اجرای اسکریپت با دسترسی root
if [ "$EUID" -ne 0 ]; then
  echo "لطفاً اسکریپت را با دسترسی root اجرا کنید (sudo)"
  exit 1
fi

# نصب وابستگی‌های سیستم
echo "نصب وابستگی‌های سیستمی..."
apt update
apt install -y python3 python3-pip sqlite3

# نصب پکیج‌های Python
echo "نصب پکیج‌های Python..."
pip3 install python-telegram-bot==20.7 schedule

# ایجاد دایرکتوری پروژه
INSTALL_DIR="/opt/3x-ui-sync"
mkdir -p "$INSTALL_DIR"

# دریافت اطلاعات از کاربر
echo "لطفاً اطلاعات زیر را وارد کنید:"
read -p "توکن ربات تلگرام (از @BotFather): " TELEGRAM_BOT_TOKEN
read -p "Chat ID (از @UserInfoBot): " TELEGRAM_CHAT_ID
read -p "مدت زمان همگام‌سازی (به دقیقه، پیش‌فرض 10): " SYNC_INTERVAL
read -p "مسیر پایگاه داده 3X-UI (پیش‌فرض /etc/x-ui/x-ui.db): " DB_PATH

# تنظیم مقادیر پیش‌فرض
SYNC_INTERVAL=${SYNC_INTERVAL:-10}
DB_PATH=${DB_PATH:-/etc/x-ui/x-ui.db}

# بررسی وجود فایل پایگاه داده
if [ ! -f "$DB_PATH" ]; then
  echo "خطا: فایل پایگاه داده ($DB_PATH) یافت نشد!"
  exit 1
fi

# دانلود فایل اصلی از GitHub
echo "دانلود فایل‌های پروژه..."
curl -L -o "$INSTALL_DIR/sync_xui.py" "https://raw.githubusercontent.com/versuos/3x-ui-sync/main/sync_xui.py"

# ایجاد فایل config.json
echo "ایجاد فایل تنظیمات..."
cat > "$INSTALL_DIR/config.json" << EOL
{
  "telegram_bot_token": "$TELEGRAM_BOT_TOKEN",
  "telegram_chat_id": "$TELEGRAM_CHAT_ID",
  "db_path": "$DB_PATH",
  "sync_interval": $SYNC_INTERVAL
}
EOL

# تنظیم مجوزها
chmod 600 "$INSTALL_DIR/sync_xui.py"
chmod 600 "$INSTALL_DIR/config.json"

# ایجاد سرویس Systemd
echo "تنظیم سرویس Systemd..."
cat > /etc/systemd/system/3x-ui-sync.service << EOL
[Unit]
Description=3X-UI User Sync Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/sync_xui.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOL

# فعال‌سازی و شروع سرویس
systemctl enable 3x-ui-sync.service
systemctl start 3x-ui-sync.service

echo "نصب با موفقیت انجام شد!"
echo "وضعیت سرویس را با دستور زیر بررسی کنید:"
echo "sudo systemctl status 3x-ui-sync.service"
echo "لاگ‌ها در $INSTALL_DIR/sync_xui.log ذخیره می‌شوند."