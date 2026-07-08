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
    """يرسل رسالة إلى تيليجرام مع معالجة الأخطاء الشائعة"""
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        async with session.post(url, json=payload) as response:
            res_data = await response.json()
            if response.status != 200:
                if not silent:
                    print(f"\n\033[1;31m[!] خطأ في تيليجرام:\033[0m {res_data.get('description')}")
                    if "chat not found" in res_data.get('description', '').lower():
                        print("\033[1;33m[تنبيه]\033[0m يرجى التأكد من إرسال رسالة /start للبوت أولاً من حسابك.")
                return False
            return True
    except Exception as e:
        if not silent:
            print(f"\n\033[1;31m[!] خطأ في الاتصال بتيليجرام:\033[0m {e}")
        return False

# ==========================================
# وظائف الفحص (Checking Functions)
# ==========================================

async def read_usernames(file_path):
    """يقرأ اليوزرات الرباعية فقط من الملف"""
    try:
        with open(file_path, 'r') as f:
            raw_usernames = {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        print(f"\033[1;31m[!] خطأ:\033[0m الملف '{file_path}' غير موجود.")
        sys.exit(1)

    pattern = r"^[A-Za-z0-9_]{4}$"
    valid_usernames = [u for u in raw_usernames if re.match(pattern, u)]
    return valid_usernames

async def fetch_batch(session, usernames_chunk, token):
    """يفحص مجموعة من 100 يوزر في طلب واحد من تويتر"""
    results = []
    url = "https://api.twitter.com/2/users/by"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "usernames": ",".join(usernames_chunk),
        "user.fields": "id,created_at,name,username,verified,pinned_tweet_id,public_metrics",
    }

    try:
        async with session.get(url, headers=headers, params=params, timeout=30) as response:
            if response.status == 429: # Rate Limit
                print("\033[1;33m[!]\033[0m تم الوصول لحد الطلبات (Rate Limit)، سأنتظر قليلاً...")
                await asyncio.sleep(15) # انتظر 15 ثانية ثم حاول لاحقاً (بشكل مبسط)
                return await fetch_batch(session, usernames_chunk, token)

            data = await response.json()
            
            if response.status != 200:
                print(f"\033[1;31m[!] خطأ من تويتر:\033[0m {data.get('detail', 'خطأ غير معروف')}")
                return []

            # معالجة اليوزرات المتاحة (غير الموجودة في تويتر)
            if "errors" in data:
                for error in data["errors"]:
                    username = error.get("resource_id")
                    detail = error.get("detail", "")
                    if "Could not find user" in detail:
                        results.append({"username": username, "status": "AVAILABLE"})
                    elif "suspended" in detail.lower():
                        results.append({"username": username, "status": "SUSPENDED"})

            # معالجة اليوزرات المحجوزة
            if "data" in data:
                for user in data["data"]:
                    username = user["username"]
                    # فحص النشاط
                    created_at = user.get("created_at", "2000-01-01")
                    year = parser.parse(created_at).year
                    metrics = user.get("public_metrics", {})
                    
                    is_active = (
                        year > INACTIVE_THRESHOLD_YEAR or 
                        user.get("verified", False) or 
                        "pinned_tweet_id" in user or 
                        metrics.get("tweet_count", 0) > 0
                    )
                    results.append({
                        "username": username, 
                        "status": "TAKEN_ACTIVE" if is_active else "TAKEN_INACTIVE"
                    })
    except Exception as e:
        print(f"\033[1;31m[!] خطأ أثناء الفحص:\033[0m {e}")
    
    return results

# ==========================================
# المحرك الرئيسي (Main Engine)
# ==========================================

async def main():
    arg_parser = argparse.ArgumentParser(description="Twitter Quad Username Hunter")
    arg_parser.add_argument("username_file", help="Path to the file containing usernames")
    args = arg_parser.parse_args()

    # 1. قراءة اليوزرات
    usernames_to_check = await read_usernames(args.username_file)
    if not usernames_to_check:
        print("\033[1;31m[!] لا توجد يوزرات رباعية صالحة للفحص في الملف.\033[0m")
        return

    print(f"\033[1;36m[+]\033[0m تم تحميل \033[1;32m{len(usernames_to_check)}\033[0m يوزر رباعي للفحص.")
    
    async with aiohttp.ClientSession() as session:
        # 2. فحص اتصال تيليجرام
        print("\033[1;36m[+]\033[0m جاري فحص اتصال تيليجرام...")
        test_msg = "🚀 *بدأ نظام الفحص الحقيقي*\nالعدد: `{}` يوزر رباعي.".format(len(usernames_to_check))
        if not await send_telegram_message(session, test_msg):
            print("\033[1;31m[!]\033[0m فشل إرسال تنبيه البدء لتيليجرام. سأستمر في الفحص على الشاشة فقط.")
        else:
            print("\033[1;32m[✓]\033[0m تم الاتصال بتيليجرام بنجاح.")

        # 3. بدء الفحص المجمّع
        start_time = time.time()
        available_count = 0
        chunks = [usernames_to_check[i:i + BATCH_SIZE] for i in range(0, len(usernames_to_check), BATCH_SIZE)]
        
        semaphore = asyncio.Semaphore(CONCURRENT_BATCHES)

        async def process_chunk(chunk):
            nonlocal available_count
            async with semaphore:
                batch_results = await fetch_batch(session, chunk, TOKEN)
                for res in batch_results:
                    if res["status"] == "AVAILABLE":
                        available_count += 1
                        msg = "🎯 *صيد جديد!*\nاليوزر: `@{}`\nالحالة: متاح 100% ✅".format(res["username"])
                        await send_telegram_message(session, msg, silent=True)
                        print(f"\033[1;32m[🎯 صيد!]\033[0m @{res['username']}")
                
                # تحديث التقدم في الشاشة
                sys.stdout.write(f"\r\033[1;34m[*] جاري الفحص...\033[0m تم فحص {min(len(usernames_to_check), (usernames_to_check.index(chunk[0]) + len(chunk)))} يوزر.")
                sys.stdout.flush()

        print("\033[1;36m[+]\033[0m بدأ الفحص الفعلي الآن...")
        tasks = [process_chunk(c) for c in chunks]
        await asyncio.gather(*tasks)

        # 4. التقرير النهائي
        duration = time.time() - start_time
        summary = (f"🏁 *اكتمل الصيد!*\n\n"
                   f"🎯 المتاحة: `{available_count}`\n"
                   f"⏱ الوقت: `{duration:.2f}` ثانية\n"
                   f"📊 الإجمالي: `{len(usernames_to_check)}`")
        
        await send_telegram_message(session, summary)
        print(f"\n\n\033[1;32m[✓] انتهى الفحص. تم إيجاد {available_count} يوزر متاح.\033[0m")
        print(f"\033[1;36m[i] الوقت المستغرق: {duration:.2f} ثانية.\033[0m")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\033[1;31m[!] تم إيقاف الفحص يدوياً.\033[0m")
