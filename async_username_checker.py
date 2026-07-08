import asyncio
import aiohttp
import argparse
import re
from dateutil import parser
import time
import urllib.parse
import sys

# ==========================================
# الإعدادات الأساسية (Configuration)
# ==========================================

# تم تحديث التوكن الجديد وفك تشفيره لضمان العمل 100%
RAW_TOKEN = "AAAAAAAAAAAAAAAAAAAAALot%2BgEAAAAALDJdMfecK72FvOTXX%2FYyJLA%2BBY4%3DwQ2HvlIbyt7ijnhNM46iUcYGIxYtuEBuImldL7EKAKaWVLcWo2"
TOKEN = urllib.parse.unquote(RAW_TOKEN)

# Telegram Configuration
TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

BATCH_SIZE = 100 
CONCURRENT_BATCHES = 5 

# ==========================================
# وظائف تيليجرام (Telegram Functions)
# ==========================================

async def send_telegram_message(session, message):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        async with session.post(url, json=payload) as response:
            return response.status == 200
    except: return False

# ==========================================
# وظائف الفحص (Checking Functions)
# ==========================================

async def check_token_validity(session, token):
    """يتحقق من أن التوكن يعمل فعلياً مع تويتر قبل بدء الفحص"""
    # نستخدم يوزر تويتر الرسمي للفحص
    url = "https://api.twitter.com/2/users/by/username/Twitter"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return True, "صالح"
            elif response.status == 401:
                return False, "غير صالح (Unauthorized)"
            elif response.status == 403:
                return False, "مرفوض (Forbidden - قد يكون الحساب مقيداً)"
            else:
                data = await response.json()
                return False, f"خطأ {response.status}: {data.get('detail', 'Unknown error')}"
    except Exception as e:
        return False, f"خطأ في الاتصال: {e}"

async def fetch_batch(session, usernames_chunk, token):
    url = "https://api.twitter.com/2/users/by"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "usernames": ",".join(usernames_chunk),
        "user.fields": "id,created_at,public_metrics",
    }

    try:
        async with session.get(url, headers=headers, params=params, timeout=30) as response:
            if response.status == 401:
                print("\n\033[1;31m[!!!] التوكن توقف عن العمل فجأة (Unauthorized).\033[0m")
                sys.exit(1)
            
            if response.status == 429:
                await asyncio.sleep(15)
                return await fetch_batch(session, usernames_chunk, token)

            data = await response.json()
            results = []
            
            # اليوزرات المتاحة هي التي تظهر في قائمة errors مع رسالة "Could not find user"
            if "errors" in data:
                for error in data["errors"]:
                    if "Could not find user" in error.get("detail", ""):
                        results.append({"username": error.get("resource_id"), "status": "AVAILABLE"})
            
            # اليوزرات المحجوزة تظهر في قائمة data
            if "data" in data:
                for user in data["data"]:
                    results.append({"username": user["username"], "status": "TAKEN"})
                    
            return results
    except Exception: return []

async def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("username_file")
    args = arg_parser.parse_args()

    # قراءة اليوزرات الرباعية فقط
    try:
        with open(args.username_file, 'r') as f:
            usernames = [line.strip() for line in f if len(line.strip()) == 4]
    except: 
        print("\033[1;31m[!] فشل قراءة الملف.\033[0m"); return

    if not usernames:
        print("\033[1;31m[!] لا توجد يوزرات رباعية صالحة في الملف.\033[0m"); return

    async with aiohttp.ClientSession() as session:
        print("\033[1;34m[+]\033[0m جاري فحص صلاحية التوكن الجديد...")
        is_valid, message = await check_token_validity(session, TOKEN)
        
        if not is_valid:
            print(f"\033[1;31m[!] التوكن {message}. يرجى مراجعة إعدادات حساب المطور.\033[0m")
            return

        print("\033[1;32m[✓] التوكن يعمل بنجاح! بدأ الفحص الحقيقي الآن...\033[0m")
        await send_telegram_message(session, f"🚀 *بدأ الفحص الحقيقي*\nالعدد: `{len(usernames)}` يوزر.\nالحالة: التوكن صالح ✅")

        start_time = time.time()
        available_count = 0
        chunks = [usernames[i:i + BATCH_SIZE] for i in range(0, len(usernames), BATCH_SIZE)]
        
        semaphore = asyncio.Semaphore(CONCURRENT_BATCHES)

        async def process_chunk(chunk):
            nonlocal available_count
            async with semaphore:
                results = await fetch_batch(session, chunk, TOKEN)
                for r in results:
                    if r["status"] == "AVAILABLE":
                        available_count += 1
                        print(f"\033[1;32m[🎯 صيد!]\033[0m @{r['username']}")
                        await send_telegram_message(session, f"🎯 *يوزر متاح:* `@{r['username']}`")
                
                # تحديث العداد على الشاشة
                current_idx = (usernames.index(chunk[0]) + len(chunk))
                sys.stdout.write(f"\r\033[1;34m[*] تقدم الفحص:\033[0m {current_idx}/{len(usernames)}")
                sys.stdout.flush()

        tasks = [process_chunk(c) for c in chunks]
        await asyncio.gather(*tasks)

        duration = time.time() - start_time
        final_msg = f"🏁 *انتهى الفحص*\nالمتاحة: `{available_count}`\nالوقت: `{duration:.2f}s`"
        await send_telegram_message(session, final_msg)
        print(f"\n\n\033[1;32m[✓] اكتملت المهمة. تم إيجاد {available_count} يوزر متاح.\033[0m")

if __name__ == "__main__":
    asyncio.run(main())
