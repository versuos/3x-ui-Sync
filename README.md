3X-UI User Sync
اسکریپتی برای همگام‌سازی ترافیک، زمان انقضا و وضعیت فعال/غیرفعال کاربران با لینک سابسکریپشن یکسان (بر اساس subId) در پنل 3X-UI.
پیش‌نیازها

سرور لینوکس (ترجیحاً Ubuntu 20.04 یا بالاتر)
پنل 3X-UI نصب‌شده
Python 3.6 یا بالاتر
دسترسی root

نصب

اسکریپت نصب را اجرا کنید:
bash <(curl -Ls https://raw.githubusercontent.com/versuos/3x-ui-sync/main/install.sh)


در طول نصب، اطلاعات زیر را وارد کنید:

توکن ربات تلگرام (از @BotFather)
Chat ID (از @UserInfoBot)
بازه زمانی همگام‌سازی (به دقیقه، پیش‌فرض 10)


سرویس به‌صورت خودکار فعال می‌شود. وضعیت آن را بررسی کنید:
sudo systemctl status 3x-ui-sync.service



مدیریت ربات
ربات تلگرامی امکان تغییر تنظیمات را از طریق منو فراهم می‌کند. دستورات زیر را در چت تلگرام با ربات اجرا کنید:

/start: نمایش منوی دستورات
/set_token <توکن>: تغییر توکن ربات
/set_chatid <شناسه>: تغییر شناسه چت
/set_interval <دقیقه>: تغییر بازه زمانی همگام‌سازی (به دقیقه)

توجه: فقط چت آیدی ثبت‌شده (ادمین) می‌تواند از این دستورات استفاده کند.
ریستارت سرویس
sudo systemctl restart 3x-ui-sync.service

حذف
برای حذف کامل:
sudo systemctl stop 3x-ui-sync.service
sudo systemctl disable 3x-ui-sync.service
sudo rm /etc/systemd/system/3x-ui-sync.service
sudo systemctl daemon-reload
sudo rm -rf /opt/3x-ui-sync

عیب‌یابی

لاگ‌ها: /opt/3x-ui-sync/sync_xui.log
بررسی پایگاه داده:sqlite3 /etc/x-ui/x-ui.db "SELECT email, up, down, expiry_time, inbound_id FROM client_traffics"


بررسی اتصال تلگرام:curl https://api.telegram.org


پشتیبان‌گیری:sudo cp /etc/x-ui/x-ui.db /etc/x-ui/x-ui.db.bak



پشتیبانی
برای مشکلات، به Issues مخزن مراجعه کنید.
