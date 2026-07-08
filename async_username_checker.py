import asyncio
import aiohttp
import argparse
import random
import sys
import re

# ==========================================
# الإعدادات (Configuration)
# ==========================================

TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

CONCURRENT_REQUESTS = 5
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# ==========================================
# وظائف المساعدة (Helper Functions)
# ==========================================

async def get_tokens(session):
    """استخراج التوكنات اللازمة للفحص من تويتر"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
    try:
        async with session.get("https://x.com", headers=headers) as r:
            text = await r.text()
            js_url = re.search(r'https://abs\.twimg\.com/responsive-web/client-web/main\.[a-z0-9]+\.js', text).group(0)
            
        async with session.get(js_url) as r:
            js_content = await r.text()
            bearer = re.search(r'AAAAA[a-zA-Z0-9%=\-_]+', js_content).group(0)
            
        headers["Authorization"] = f"Bearer {bearer}"
        async with session.post("https://api.twitter.com/1.1/guest/activate.json", headers=headers) as r:
            data = await r.json()
            return bearer, data.get("guest_token")
    except:
        # توكن احتياطي في حال فشل الاستخراج
        return "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA", None

async def check_availability(session, username, bearer, guest_token, semaphore):
    async with semaphore:
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        
        url = "https://x.com/i/api/i/users/username_available.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Authorization": f"Bearer {bearer}",
            "X-Guest-Token": str(guest_token),
            "Referer": "https://x.com/i/flow/signup"
        }
        
        try:
            async with session.get(url, params={"username": username}, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    return username, data.get("valid", False)
                return username, False
        except:
            return username, False

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    args = parser.parse_args()

    try:
        with open(args.file, 'r') as f:
            usernames = [line.strip() for line in f if line.strip()]
    except: return

    print(f"[*] فحص {len(usernames)} يوزر بالـ API الرسمي...")
    
    async with aiohttp.ClientSession() as session:
        bearer, guest = await get_tokens(session)
        if not guest:
            print("[!] فشل الحصول على Guest Token. تأكد من اتصال الإنترنت."); return

        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
        
        async def worker(u):
            user, is_avail = await check_availability(session, u, bearer, guest, semaphore)
            if is_avail:
                print(f"[✅ متاح] @{user}")
                url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
                await session.post(url, json={"chat_id": TG_CHAT_ID, "text": f"🎯 متاح للتسجيل: @{user}"})
            else:
                sys.stdout.write(f"\r[✗ مشغول] @{user}          ")
                sys.stdout.flush()

        await asyncio.gather(*(worker(u) for u in usernames))
        print("\n[✓] انتهى الفحص.")

if __name__ == "__main__":
    asyncio.run(main())
