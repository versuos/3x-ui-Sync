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

# دریافت ورودی‌های کاربر
read -p "توکن ربات تلگرام را وارد کنید: " TELEGRAM_BOT_TOKEN
read -p "شناسه چت تلگرام (Chat ID) را وارد کنید: " TELEGRAM_CHAT_ID
read -p "بازه زمانی همگام‌سازی (به دقیقه، پیش‌فرض 10): " SYNC_INTERVAL
SYNC_INTERVAL=${SYNC_INTERVAL:-10}  # پیش‌فرض 10 دقیقه

# ایجاد فایل تنظیمات
echo "ایجاد فایل تنظیمات..."
cat > "$INSTALL_DIR/config.json" << EOL
{
  "TELEGRAM_BOT_TOKEN": "$TELEGRAM_BOT_TOKEN",
  "TELEGRAM_CHAT_ID": "$TELEGRAM_CHAT_ID",
  "SYNC_INTERVAL": $SYNC_INTERVAL
}
EOL

# دانلود فایل اصلی از GitHub
echo "دانلود فایل‌های پروژه..."
curl -L -o "$INSTALL_DIR/sync_xui.py" "https://raw.githubusercontent.com/versuos/3x-ui-sync/main/sync_xui.py"

# تنظیم مجوزها
chmod 600 "$INSTALL_DIR/sync_xui.py"
chmod 600 "$INSTALL_DIR/config.json"

# بررسی وجود پایگاه داده
DB_PATH="/etc/x-ui/x-ui.db"
if [ ! -f "$DB_PATH" ]; then
  echo "خطا: فایل پایگاه داده ($DB_PATH) یافت نشد!"
  exit 1
fi

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
StandardOutput=append:/opt/3x-ui-sync/sync_xui.log
StandardError=append:/opt/3x-ui-sync/sync_xui.log

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
