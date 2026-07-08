import asyncio
import aiohttp
import argparse
import re
import time
import sys
import random

# ==========================================
# الإعدادات (Configuration)
# ==========================================

# Telegram Configuration
TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

CONCURRENT_REQUESTS = 5 # عدد الفحوصات المتزامنة

# ==========================================
# وظائف المساعدة (Helper Functions)
# ==========================================

async def send_telegram_message(session, message):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        async with session.post(url, json=payload) as response:
            return response.status == 200
    except: return False

async def get_guest_token(session):
    """يولد Guest Token من تويتر تماماً كما يفعل المتصفح"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    }
    try:
        async with session.post("https://api.twitter.com/1.1/guest/activate.json", headers={'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7p9R4tJaba37As96K395Z9akgZ6u6U0A4053C'}, timeout=10) as response:
            data = await response.json()
            return data.get("guest_token")
    except: return None

# ==========================================
# محرك الفحص (Checking Engine)
# ==========================================

async def check_username(session, username, guest_token):
    """يفحص توفر اليوزر عبر واجهة الويب (Guest API)"""
    url = f"https://twitter.com/i/api/i/users/username_available.json?username={username}"
    headers = {
        'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7p9R4tJaba37As96K395Z9akgZ6u6U0A4053C',
        'X-Guest-Token': guest_token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    }
    
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                # إذا كانت القيمة valid هي true، فهذا يعني أن اليوزر متاح
                return username, data.get("valid", False)
            elif response.status == 429: # Rate Limit
                return username, "RATE_LIMIT"
            else:
                return username, False
    except:
        return username, False

async def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("username_file")
    args = arg_parser.parse_args()

    try:
        with open(args.username_file, 'r') as f:
            usernames = [line.strip() for line in f if len(line.strip()) == 4]
    except: 
        print("\033[1;31m[!] فشل قراءة الملف.\033[0m"); return

    if not usernames:
        print("\033[1;31m[!] لا توجد يوزرات رباعية صالحة.\033[0m"); return

    async with aiohttp.ClientSession() as session:
        print("\033[1;34m[+]\033[0m جاري توليد Guest Token للبدء...")
        guest_token = await get_guest_token(session)
        
        if not guest_token:
            print("\033[1;31m[!] فشل توليد التوكن. تأكد من اتصال الإنترنت.\033[0m")
            return

        print(f"\033[1;32m[✓] تم التوليد بنجاح. بدأ الفحص لـ {len(usernames)} يوزر بدون توكن مطور!\033[0m")
        await send_telegram_message(session, f"🚀 *بدأ الفحص بطريقة Guest API*\nالعدد: `{len(usernames)}` يوزر.\nالحالة: بدون توكن مطور ✅")

        start_time = time.time()
        available_count = 0
        
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

        async def worker(username):
            nonlocal available_count, guest_token
            async with semaphore:
                user, is_available = await check_username(session, username, guest_token)
                
                if is_available == "RATE_LIMIT":
                    # إذا حدث ضغط، نحدث التوكن وننتظر قليلاً
                    guest_token = await get_guest_token(session) or guest_token
                    await asyncio.sleep(2)
                    return await worker(username)
                
                if is_available:
                    available_count += 1
                    print(f"\033[1;32m[🎯 صيد!]\033[0m @{user}")
                    await send_telegram_message(session, f"🎯 *يوزر متاح:* `@{user}`")
                
                # تحديث العداد
                idx = usernames.index(username) + 1
                if idx % 10 == 0 or idx == len(usernames):
                    sys.stdout.write(f"\r\033[1;34m[*] تقدم الفحص:\033[0m {idx}/{len(usernames)}")
                    sys.stdout.flush()

        tasks = [worker(u) for u in usernames]
        await asyncio.gather(*tasks)

        duration = time.time() - start_time
        print(f"\n\n\033[1;32m[✓] اكتمل الفحص. المتاح: {available_count}. الوقت: {duration:.2f}s\033[0m")
        await send_telegram_message(session, f"🏁 *انتهى الفحص*\nالمتاحة: `{available_count}`")

if __name__ == "__main__":
    asyncio.run(main())
