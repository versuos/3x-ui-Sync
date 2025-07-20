# 3X-UI User Sync

اسکریپتی برای همگام‌سازی ترافیک و زمان انقضای کاربران با لینک سابسکریپشن یکسان (بر اساس subId) در پنل 3X-UI.

## پیش‌نیازها
- سرور لینوکس (ترجیحاً Ubuntu 20.04 یا بالاتر)
- پنل 3X-UI نصب‌شده
- Python 3.6 یا بالاتر
- دسترسی root

## نصب
1. اسکریپت نصب را اجرا کنید:
   ```bash
   bash <(curl -Ls https://raw.githubusercontent.com/your_username/3x-ui-sync/main/install.sh)
   ```
2. در طول نصب، اطلاعات زیر را وارد کنید:
   - توکن ربات تلگرام (از @BotFather)
   - Chat ID (از @UserInfoBot)
   - مدت زمان همگام‌سازی (به دقیقه، پیش‌فرض 10)
   - مسیر پایگاه داده 3X-UI (پیش‌فرض `/etc/x-ui/x-ui.db`)

3. سرویس به‌صورت خودکار فعال می‌شود. وضعیت آن را بررسی کنید:
   ```bash
   sudo systemctl status 3x-ui-sync.service
   ```

## عیب‌یابی
- **لاگ‌ها**: `/opt/3x-ui-sync/sync_xui.log`
- **بررسی پایگاه داده**:
  ```bash
  sqlite3 /etc/x-ui/x-ui.db "SELECT email, up, down, expiry_time, inbound_id FROM client_traffics"
  ```
- **بررسی اتصال تلگرام**:
  ```bash
  curl https://api.telegram.org
  ```
- **پشتیبان‌گیری**:
  ```bash
  sudo cp /etc/x-ui/x-ui.db /etc/x-ui/x-ui.db.bak
  ```

## پشتیبانی
برای مشکلات، به Issues مخزن مراجعه کنید.