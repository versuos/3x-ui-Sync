#!/bin/bash

# اطمینان از اجرای اسکریپت با دسترسی root
if [ "$EUID" -ne 0 ]; then
  echo "لطفاً اسکریپت را با دسترسی root اجرا کنید (sudo)"
  exit 1
fi

# دایرکتوری پروژه
INSTALL_DIR="/opt/3x-ui-sync"
CONFIG_FILE="$INSTALL_DIR/config.json"

# نصب وابستگی‌های سیستم
echo "نصب وابستگی‌های سیستمی..."
apt update
apt install -y python3 python3-pip sqlite3

# نصب پکیج‌های Python
echo "نصب پکیج‌های Python..."
pip3 install python-telegram-bot==20.7 schedule fastapi uvicorn requests

# ایجاد دایرکتوری پروژه
mkdir -p "$INSTALL_DIR"

# دریافت ورودی‌های کاربر
echo "لطفاً توکن ربات تلگرام را وارد کنید:"
read TELEGRAM_BOT_TOKEN
echo "لطفاً چت آیدی تلگرام را وارد کنید:"
read TELEGRAM_CHAT_ID
echo "لطفاً پورت سرویس صفحه سابسکرایبشن را وارد کنید (پیش‌فرض 8080):"
read SUBSCRIPTION_PORT
SUBSCRIPTION_PORT=${SUBSCRIPTION_PORT:-8080}

# بررسی وجود پایگاه داده
DB_PATH="/etc/x-ui/x-ui.db"
if [ ! -f "$DB_PATH" ]; then
  echo "خطا: فایل پایگاه داده ($DB_PATH) یافت نشد!"
  exit 1
fi

# دانلود فایل‌های اصلی از GitHub
echo "دانلود فایل‌های پروژه..."
curl -L -o "$INSTALL_DIR/sync_xui.py" "https://raw.githubusercontent.com/ali123/3x-ui-sync/main/sync_xui.py"
curl -L -o "$INSTALL_DIR/subscription_page.py" "https://raw.githubusercontent.com/ali123/3x-ui-sync/main/subscription_page.py"
curl -L -o "$INSTALL_DIR/versus.sh" "https://raw.githubusercontent.com/ali123/3x-ui-sync/main/versus.sh"

# تنظیم مجوزها
chmod 600 "$INSTALL_DIR/sync_xui.py"
chmod 600 "$INSTALL_DIR/subscription_page.py"
chmod +x "$INSTALL_DIR/versus.sh"

# ایجاد یا به‌روزرسانی فایل تنظیمات
echo "ایجاد فایل تنظیمات..."
cat > "$CONFIG_FILE" << EOL
{
  "telegram_bot_token": "$TELEGRAM_BOT_TOKEN",
  "telegram_chat_id": "$TELEGRAM_CHAT_ID",
  "subscription_port": $SUBSCRIPTION_PORT
}
EOL
chmod 600 "$CONFIG_FILE"

# ایجاد فایل external_configs.txt اگر وجود نداشته باشد
if [ ! -f "$INSTALL_DIR/external_configs.txt" ]; then
  touch "$INSTALL_DIR/external_configs.txt"
  chmod 600 "$INSTALL_DIR/external_configs.txt"
fi

# ایجاد سرویس Systemd برای sync_xui
echo "تنظیم سرویس sync_xui..."
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

# ایجاد سرویس Systemd برای subscription_page
echo "تنظیم سرویس subscription_page..."
cat > /etc/systemd/system/subscription-page.service << EOL
[Unit]
Description=3X-UI Subscription Page Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/subscription_page.py
Restart=always
User=root
StandardOutput=append:/opt/3x-ui-sync/subscription_page.log
StandardError=append:/opt/3x-ui-sync/subscription_page.log

[Install]
WantedBy=multi-user.target
EOL

# نصب اسکریپت versus
echo "نصب اسکریپت versus..."
ln -sf "$INSTALL_DIR/versus.sh" /usr/local/bin/versus
chmod +x /usr/local/bin/versus

# فعال‌سازی و شروع سرویس‌ها
systemctl daemon-reload
systemctl enable 3x-ui-sync.service
systemctl start 3x-ui-sync.service
systemctl enable subscription-page.service
systemctl start subscription-page.service

echo "نصب با موفقیت انجام شد!"
echo "برای دسترسی به منوی تعاملی، دستور 'versus' را اجرا کنید."

# اجرای منوی تعاملی
/usr/local/bin/versus
