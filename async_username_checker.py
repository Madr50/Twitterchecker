import asyncio
import aiohttp
import argparse
import re
from dateutil import parser
import time
import urllib.parse

# Twitter Configuration
TOKEN = urllib.parse.unquote("AAAAAAAAAAAAAAAAAAAAALot%2BgEAAAAA%2FgqUMY5cY%2B8xyTeBtu55l%2BLMxlw%3Dp1fc0HPV1OKY13rSCz7qL5lDPlhPrR7qjtQIRG1vX37hl5U3MQ")
INACTIVE_THRESHOLD_YEAR = 2018
BATCH_SIZE = 100 
CONCURRENT_BATCHES = 5 

# Telegram Configuration
TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

async def send_telegram_message(session, message):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                print(f"\033[1;31mTelegram Error:\033[0m {await response.text()}")
    except Exception as e:
        print(f"\033[1;31mTelegram Connection Error:\033[0m {e}")

async def read_usernames(file_path):
    try:
        with open(file_path, 'r') as f:
            raw_usernames = {line.strip() for line in f}
    except FileNotFoundError:
        print(f"Error: No such file '{file_path}'")
        exit(1)

    pattern = r"^[A-Za-z0-9_]{4}$"
    valid_usernames = []
    for username in raw_usernames:
        if re.match(pattern, username):
            valid_usernames.append(username)
    return valid_usernames

async def fetch_batch(session, usernames_chunk, token):
    results = []
    try:
        async with session.get(
            url="https://api.twitter.com/2/users/by",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "usernames": ",".join(usernames_chunk),
                "user.fields": "id,created_at,name,username,verified,pinned_tweet_id,public_metrics",
            },
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            data = await response.json()
            if response.status != 200:
                for u in usernames_chunk: results.append({"username": u, "status": f"API_ERROR"})
                return results

            if "errors" in data:
                for error in data["errors"]:
                    username = error.get("resource_id", "Unknown")
                    if "suspended" in error.get("detail", ""):
                        results.append({"username": username, "status": "SUSPENDED"})
                    elif "Could not find user" in error.get("detail", ""):
                        results.append({"username": username, "status": "AVAILABLE"})

            if "data" in data:
                for user in data["data"]:
                    username = user["username"]
                    user_created_year = parser.parse(user["created_at"]).year
                    is_active = (user_created_year > INACTIVE_THRESHOLD_YEAR or user.get("verified", False) or 
                                 "pinned_tweet_id" in user or user.get("public_metrics", {}).get("tweet_count", 0) > 0)
                    results.append({"username": username, "status": "TAKEN_ACTIVE" if is_active else "TAKEN_INACTIVE"})
    except Exception:
        for u in usernames_chunk: results.append({"username": u, "status": "ERROR"})
    return results

async def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("username_file")
    args = arg_parser.parse_args()

    usernames_to_check = await read_usernames(args.username_file)
    print(f"\033[1;34mStarting check for {len(usernames_to_check)} usernames...\033[0m")
    
    start_time = time.time()
    available_usernames = []
    
    username_chunks = [usernames_to_check[i : i + BATCH_SIZE] for i in range(0, len(usernames_to_check), BATCH_SIZE)]

    async with aiohttp.ClientSession() as session:
        await send_telegram_message(session, f"🚀 *بدأ فحص اليوزرات*\nالعدد الإجمالي: `{len(usernames_to_check)}` يوزر رباعي.")
        
        semaphore = asyncio.Semaphore(CONCURRENT_BATCHES)
        async def bounded_fetch(chunk):
            async with semaphore:
                res = await fetch_batch(session, chunk, TOKEN)
                for r in res:
                    if r["status"] == "AVAILABLE":
                        available_usernames.append(r["username"])
                        # Send instant notification for available username
                        await send_telegram_message(session, f"✅ *يوزر متاح:* `@{r['username']}`")
                        print(f"\033[1;32mAVAILABLE:\033[0m {r['username']}")
                return res

        tasks = [bounded_fetch(chunk) for chunk in username_chunks]
        await asyncio.gather(*tasks)

    duration = time.time() - start_time
    summary = (f"🏁 *اكتمل الفحص!*\n\n"
               f"✅ المتاحة: `{len(available_usernames)}`\n"
               f"⏱ الوقت: `{duration:.2f}` ثانية\n"
               f"📊 الإجمالي: `{len(usernames_to_check)}`")
    
    async with aiohttp.ClientSession() as session:
        await send_telegram_message(session, summary)

    print(f"\n\033[1;32mDone! Found {len(available_usernames)} available usernames.\033[0m")

if __name__ == "__main__":
    asyncio.run(main())
