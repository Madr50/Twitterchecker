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

# Twitter Configuration
TOKEN = urllib.parse.unquote("AAAAAAAAAAAAAAAAAAAAALot%2BgEAAAAA%2FgqUMY5cY%2B8xyTeBtu55l%2BLMxlw%3Dp1fc0HPV1OKY13rSCz7qL5lDPlhPrR7qjtQIRG1vX37hl5U3MQ")
INACTIVE_THRESHOLD_YEAR = 2018
BATCH_SIZE = 100 
CONCURRENT_BATCHES = 5 

# Telegram Configuration
TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

# ==========================================
# وظائف تيليجرام (Telegram Functions)
# ==========================================

async def send_telegram_message(session, message, silent=False):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        async with session.post(url, json=payload) as response:
            res_data = await response.json()
            if response.status != 200:
                if not silent:
                    print(f"\n\033[1;31m[!] خطأ تيليجرام:\033[0m {res_data.get('description')}")
                return False
            return True
    except: return False

# ==========================================
# وظائف الفحص (Checking Functions)
# ==========================================

async def check_token_validity(session, token):
    """يفحص ما إذا كان التوكن يعمل فعلياً مع تويتر"""
    url = "https://api.twitter.com/2/users/by/username/Twitter"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200: return True
            data = await response.json()
            print(f"\033[1;31m[!] خطأ في التوكن (Status {response.status}):\033[0m {data.get('detail', 'Unauthorized')}")
            return False
    except Exception as e:
        print(f"\033[1;31m[!] خطأ في الاتصال بتويتر:\033[0m {e}")
        return False

async def fetch_batch(session, usernames_chunk, token):
    url = "https://api.twitter.com/2/users/by"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "usernames": ",".join(usernames_chunk),
        "user.fields": "id,created_at,name,username,verified,pinned_tweet_id,public_metrics",
    }

    try:
        async with session.get(url, headers=headers, params=params, timeout=30) as response:
            if response.status == 401:
                print("\n\033[1;31m[!!!] خطأ فادح: التوكن غير صالح (Unauthorized). يرجى تحديث الـ Bearer Token.\033[0m")
                sys.exit(1)
            
            if response.status == 429:
                await asyncio.sleep(15)
                return await fetch_batch(session, usernames_chunk, token)

            data = await response.json()
            results = []
            if "errors" in data:
                for error in data["errors"]:
                    if "Could not find user" in error.get("detail", ""):
                        results.append({"username": error.get("resource_id"), "status": "AVAILABLE"})
            if "data" in data:
                for user in data["data"]:
                    results.append({"username": user["username"], "status": "TAKEN"})
            return results
    except Exception: return []

async def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("username_file")
    args = arg_parser.parse_args()

    try:
        with open(args.username_file, 'r') as f:
            usernames = [line.strip() for line in f if len(line.strip()) == 4]
    except: 
        print("File error"); return

    async with aiohttp.ClientSession() as session:
        print("\033[1;36m[+]\033[0m جاري التحقق من صلاحية التوكن...")
        if not await check_token_validity(session, TOKEN):
            print("\033[1;31m[!] توقف الفحص: التوكن لا يعمل. يرجى التأكد من الـ Bearer Token من Twitter Developer Portal.\033[0m")
            return

        print("\033[1;32m[✓]\033[0m التوكن صالح. بدأ الفحص...")
        await send_telegram_message(session, f"🚀 بدأ الفحص لـ {len(usernames)} يوزر.")

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
                        await send_telegram_message(session, f"🎯 صيد: @{r['username']}")

        tasks = [process_chunk(c) for c in chunks]
        await asyncio.gather(*tasks)

        duration = time.time() - start_time
        print(f"\n\033[1;32m[✓] انتهى. المتاح: {available_count}. الوقت: {duration:.2f}s\033[0m")
        await send_telegram_message(session, f"🏁 انتهى. المتاح: {available_count}")

if __name__ == "__main__":
    asyncio.run(main())
