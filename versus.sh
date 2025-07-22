#!/bin/bash

# اطمینان از اجرای اسکریپت با دسترسی root
if [ "$EUID" -ne 0 ]; then
  echo "لطفاً اسکریپت را با دسترسی root اجرا کنید (sudo)"
  exit 1
fi

INSTALL_DIR="/opt/3x-ui-sync"
CONFIG_FILE="$INSTALL_DIR/config.json"
EXTERNAL_CONFIG_FILE="$INSTALL_DIR/external_configs.txt"

while true; do
  clear
  echo "منوی مدیریت 3X-UI Sync"
  echo "1. تغییر تنظیمات همگام‌سازی (توکن ربات و چت آیدی)"
  echo "2. مدیریت لینک‌های خارجی (اضافه، مشاهده، حذف) و پورت"
  echo "3. ریستارت سرویس‌ها"
  echo "4. حذف کامل اسکریپت"
  echo "5. خروج"
  read -p "لطفاً گزینه را انتخاب کنید (1-5): " choice

  case $choice in
    1)
      echo "لطفاً توکن جدید ربات تلگرام را وارد کنید:"
      read TELEGRAM_BOT_TOKEN
      echo "لطفاً چت آیدی جدید تلگرام را وارد کنید:"
      read TELEGRAM_CHAT_ID
      jq ".telegram_bot_token = \"$TELEGRAM_BOT_TOKEN\" | .telegram_chat_id = \"$TELEGRAM_CHAT_ID\"" "$CONFIG_FILE" > tmp.json && mv tmp.json "$CONFIG_FILE"
      echo "تنظیمات همگام‌سازی به‌روزرسانی شد."
      read -p "برای ادامه Enter را فشار دهید..."
      ;;
    2)
      while true; do
        clear
        echo "مدیریت لینک‌های خارجی"
        echo "1. اضافه کردن لینک خارجی"
        echo "2. مشاهده لینک‌های خارجی"
        echo "3. حذف لینک خارجی"
        echo "4. تغییر پورت سرویس صفحه سابسکرایبشن"
        echo "5. بازگشت"
        read -p "لطفاً گزینه را انتخاب کنید (1-5): " sub_choice

        case $sub_choice in
          1)
            echo "لطفاً لینک کانفیگ خارجی را وارد کنید (مثل vless://...):"
            read config
            echo "$config" >> "$EXTERNAL_CONFIG_FILE"
            echo "لینک اضافه شد."
            read -p "برای ادامه Enter را فشار دهید..."
            ;;
          2)
            if [ -s "$EXTERNAL_CONFIG_FILE" ]; then
              echo "لینک‌های خارجی:"
              cat "$EXTERNAL_CONFIG_FILE"
            else
              echo "هیچ لینک خارجی وجود ندارد."
            fi
            read -p "برای ادامه Enter را فشار دهید..."
            ;;
          3)
            if [ -s "$EXTERNAL_CONFIG_FILE" ]; then
              echo "لینک‌های خارجی:"
              cat -n "$EXTERNAL_CONFIG_FILE"
              echo "شماره خط لینک مورد نظر برای حذف را وارد کنید:"
              read line_number
              sed -i "${line_number}d" "$EXTERNAL_CONFIG_FILE"
              echo "لینک حذف شد."
            else
              echo "هیچ لینک خارجی وجود ندارد."
            fi
            read -p "برای ادامه Enter را فشار دهید..."
            ;;
          4)
            echo "لطفاً پورت جدید سرویس صفحه سابسکرایبشن را وارد کنید:"
            read SUBSCRIPTION_PORT
            jq ".subscription_port = $SUBSCRIPTION_PORT" "$CONFIG_FILE" > tmp.json && mv tmp.json "$CONFIG_FILE"
            echo "پورت به‌روزرسانی شد. سرویس را ریستارت کنید."
            read -p "برای ادامه Enter را فشار دهید..."
            ;;
          5)
            break
            ;;
          *)
            echo "گزینه نامعتبر!"
            read -p "برای ادامه Enter را فشار دهید..."
            ;;
        esac
      done
      ;;
    3)
      systemctl restart 3x-ui-sync.service
      systemctl restart subscription-page.service
      echo "سرویس‌ها ریستارت شدند."
      read -p "برای ادامه Enter را فشار دهید..."
      ;;
    4)
      echo "آیا مطمئن هستید که می‌خواهید اسکریپت را کاملاً حذف کنید؟ (y/n)"
      read confirm
      if [ "$confirm" = "y" ]; then
        systemctl stop 3x-ui-sync.service
        systemctl stop subscription-page.service
        systemctl disable 3x-ui-sync.service
        systemctl disable subscription-page.service
        rm -f /etc/systemd/system/3x-ui-sync.service
        rm -f /etc/systemd/system/subscription-page.service
        systemctl daemon-reload
        rm -rf "$INSTALL_DIR"
        rm -f /usr/local/bin/versus
        echo "اسکریپت و سرویس‌ها حذف شدند."
        exit 0
      fi
      read -p "برای ادامه Enter را فشار دهید..."
      ;;
    5)
      echo "خروج از منو."
      exit 0
      ;;
    *)
      echo "گزینه نامعتبر!"
      read -p "برای ادامه Enter را فشار دهید..."
      ;;
  esac
done