import base64
import requests
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import uvicorn
import logging
import json

# تنظیم لاگ‌گیری
logging.basicConfig(filename='/opt/3x-ui-sync/subscription_page.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# خواندن تنظیمات
CONFIG_FILE = "/opt/3x-ui-sync/config.json"
with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)
SUBSCRIPTION_PORT = config['subscription_port']
XUI_PANEL_URL = "http://localhost:2053"
EXTERNAL_CONFIG_FILE = "/opt/3x-ui-sync/external_configs.txt"

app = FastAPI()

def read_external_configs():
    """خواندن لینک‌های کانفیگ خارجی از فایل"""
    try:
        with open(EXTERNAL_CONFIG_FILE, 'r') as file:
            configs = [line.strip() for line in file if line.strip()]
        logging.info(f"کانفیگ‌های خارجی خوانده شدند: {configs}")
        return configs
    except Exception as e:
        logging.error(f"خطا در خواندن فایل کانفیگ‌های خارجی: {str(e)}")
        return []

@app.get("/sub/{sub_id}", response_class=PlainTextResponse)
async def subscription_page(sub_id: str, request: Request):
    """ارائه پاسخ متنی خام برای نمایش در مرورگر"""
    try:
        panel_url = f"{XUI_PANEL_URL}/sub/{sub_id}"
        response = requests.get(panel_url, headers=request.headers)
        
        if response.status_code != 200:
            logging.error(f"خطا در دریافت پاسخ از پنل: {response.status_code}")
            return PlainTextResponse("Error fetching subscription", status_code=response.status_code)

        original_content = response.text
        logging.info(f"پاسخ اصلی پنل دریافت شد: {original_content[:50]}...")

        try:
            decoded_content = base64.b64decode(original_content).decode('utf-8')
        except:
            decoded_content = original_content
            logging.warning("پاسخ پنل Base64 نیست")

        external_configs = read_external_configs()
        combined_content = decoded_content
        if combined_content and not combined_content.endswith('\n'):
            combined_content += '\n'
        combined_content += '\n'.join(external_configs)

        return PlainTextResponse(combined_content, status_code=200)

    except Exception as e:
        logging.error(f"خطا در پردازش درخواست: {str(e)}")
        return PlainTextResponse(f"Error: {str(e)}", status_code=500)

@app.get("/sub/{sub_id}/raw", response_class=PlainTextResponse)
async def subscription_raw(sub_id: str, request: Request):
    """ارائه پاسخ خام Base64 برای کلاینت‌های VPN"""
    try:
        panel_url = f"{XUI_PANEL_URL}/sub/{sub_id}"
        response = requests.get(panel_url, headers=request.headers)
        
        if response.status_code != 200:
            logging.error(f"خطا در دریافت پاسخ از پنل: {response.status_code}")
            return PlainTextResponse("Error fetching subscription", status_code=response.status_code)

        original_content = response.text
        try:
            decoded_content = base64.b64decode(original_content).decode('utf-8')
        except:
            decoded_content = original_content

        external_configs = read_external_configs()
        combined_content = decoded_content
        if combined_content and not combined_content.endswith('\n'):
            combined_content += '\n'
        combined_content += '\n'.join(external_configs)

        encoded_content = base64.b64encode(combined_content.encode('utf-8')).decode('utf-8')
        return PlainTextResponse(encoded_content, status_code=200)

    except Exception as e:
        logging.error(f"خطا در پردازش درخواست خام: {str(e)}")
        return PlainTextResponse(f"Error: {str(e)}", status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SUBSCRIPTION_PORT)