import asyncio
import aiohttp
import argparse
import random
import sys

# ==========================================
# الإعدادات (Configuration)
# ==========================================

TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

CONCURRENT_REQUESTS = 5
MIN_DELAY = 1.0
MAX_DELAY = 2.5

# ==========================================
# وظائف المساعدة (Helper Functions)
# ==========================================

async def check_availability(session, username, semaphore):
    async with semaphore:
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        
        url = f"https://x.com/{username}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        try:
            # Using allow_redirects=True to see where it lands
            async with session.get(url, headers=headers, allow_redirects=True) as r:
                final_url = str(r.url)
                status = r.status
                
                # If we land on a 'suspended' URL
                if "suspended" in final_url.lower():
                    return username, False, "suspended"
                
                if status == 404:
                    # 404 on X.com usually means the account is available
                    # We can double check the page content for specific strings
                    content = await r.text()
                    if "Account suspended" in content:
                        return username, False, "suspended"
                    return username, True, "available"
                
                elif status == 200:
                    # 200 means the page exists, so the username is taken
                    return username, False, "taken"
                
                else:
                    return username, False, f"status_{status}"
                    
        except Exception as e:
            return username, False, "error"

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    args = parser.parse_args()

    try:
        with open(args.file, 'r') as f:
            usernames = [line.strip().replace("@", "") for line in f if line.strip()]
    except Exception as e:
        print(f"[!] خطأ في قراءة الملف: {e}")
        return

    print(f"[*] فحص {len(usernames)} يوزر عبر فحص الصفحات المباشر...")
    
    # Use a session with a longer timeout and handle large headers
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        
        tasks = [check_availability(session, u, semaphore) for u in usernames]
        results = await asyncio.gather(*tasks)
        
        for user, is_avail, reason in results:
            if is_avail:
                print(f"\n[✅ متاح] @{user}")
                try:
                    tg_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
                    msg = f"🎯 يوزر متاح للتسجيل: @{user}\n\nهذا اليوزر غير مستخدم وغير متبند حالياً."
                    await session.post(tg_url, json={"chat_id": TG_CHAT_ID, "text": msg})
                except:
                    pass
            else:
                # We don't print anything for taken/suspended to keep it fast and clean as requested
                pass

        print("\n[✓] انتهى الفحص.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 async_username_checker.py usernames.txt")
    else:
        asyncio.run(main())
