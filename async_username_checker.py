import asyncio
import aiohttp
import argparse
import random
import sys
import time
import json

# ==========================================
# الإعدادات (Configuration)
# ==========================================

TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

CONCURRENT_REQUESTS = 5
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# Standard Bearer for Twitter Web
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# ==========================================
# الكلاس الأساسي للفحص المتقدم
# ==========================================

class TwitterHunter:
    def __init__(self, usernames, bot_token, chat_id):
        self.usernames = usernames
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.results = {"available": [], "taken": 0, "suspended": 0, "invalid": 0, "errors": 0}
        self.total = len(usernames)
        self.checked = 0
        self.start_time = None
        self.guest_token = None

    async def get_guest_token(self, session):
        headers = {"Authorization": f"Bearer {BEARER}"}
        try:
            async with session.post("https://api.twitter.com/1.1/guest/activate.json", headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    self.guest_token = data.get("guest_token")
                    return True
        except:
            pass
        return False

    async def send_telegram(self, session, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with session.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}) as r:
                return await r.json()
        except:
            return None

    async def check_user(self, session, username, semaphore):
        async with semaphore:
            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            
            # Use the profile page check first - it's fast and handles the 404/200/suspended logic well
            url = f"https://x.com/{username}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            
            try:
                async with session.get(url, headers=headers, allow_redirects=True, timeout=10) as r:
                    status = r.status
                    final_url = str(r.url)
                    content = await r.text()
                    
                    if "suspended" in final_url.lower() or "Account suspended" in content:
                        self.results["suspended"] += 1
                        self.checked += 1
                        self.print_progress(username, "suspended")
                        return

                    if status == 404:
                        # If 404, it might be available. Now check length policy.
                        if len(username) < 5:
                            # For 4-char usernames, we must be extra careful.
                            # We check if the word 'available' or 'sign up' appears in the context of this username
                            # But a more reliable way is to hit the signup validation if guest token is active
                            if self.guest_token:
                                val_url = "https://api.twitter.com/i/users/username_available.json"
                                val_headers = {
                                    "Authorization": f"Bearer {BEARER}",
                                    "X-Guest-Token": str(self.guest_token),
                                    "Referer": "https://x.com/i/flow/signup"
                                }
                                async with session.get(val_url, params={"username": username}, headers=val_headers) as val_r:
                                    if val_r.status == 200:
                                        val_data = await val_r.json()
                                        if val_data.get("valid") == True:
                                            self.results["available"].append(username)
                                            msg = f"💎 *يوزر رباعي متاح للتسجيل:*\n\n`@{username}`\n\nهذا اليوزر تجاوز فحص الحماية ومتاح حالياً!"
                                            await self.send_telegram(session, msg)
                                            self.checked += 1
                                            self.print_progress(username, "AVAILABLE")
                                            return
                                        else:
                                            self.results["invalid"] += 1
                                            self.checked += 1
                                            self.print_progress(username, "restricted")
                                            return
                        
                        # For 5+ chars or if validation passed
                        self.results["available"].append(username)
                        msg = f"🎯 *يوزر متاح للتسجيل:*\n\n`@{username}`\n\nاليوزر غير مستخدم ومتاح حالياً."
                        await self.send_telegram(session, msg)
                        self.checked += 1
                        self.print_progress(username, "AVAILABLE")
                        
                    elif status == 200:
                        self.results["taken"] += 1
                        self.checked += 1
                        self.print_progress(username, "taken")
                    else:
                        self.results["errors"] += 1
                        self.checked += 1
                        self.print_progress(username, f"status_{status}")

            except Exception as e:
                self.results["errors"] += 1
                self.checked += 1
                self.print_progress(username, "error")

    def print_progress(self, current_user, status):
        percent = (self.checked / self.total) * 100
        bar_length = 20
        filled_length = int(bar_length * self.checked // self.total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        elapsed = time.time() - self.start_time
        speed = self.checked / elapsed if elapsed > 0 else 0
        sys.stdout.write(f"\r|{bar}| {percent:.1f}% [{self.checked}/{self.total}] {speed:.1f} u/s | @{current_user} ({status})")
        sys.stdout.flush()

    async def run(self):
        print(f"[*] بدء الصيد (تم تفعيل فلتر الحماية لليوزرات الرباعية)...")
        self.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            await self.get_guest_token(session)
            semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
            tasks = [self.check_user(session, u, semaphore) for u in self.usernames]
            await asyncio.gather(*tasks)
            
            duration = time.time() - self.start_time
            report = (
                f"📊 *تقرير الصيد النهائي*\n\n"
                f"✅ متاح فعلياً: {len(self.results['available'])}\n"
                f"❌ مأخوذ: {self.results['taken']}\n"
                f"🚫 متبند: {self.results['suspended']}\n"
                f"⚠️ محجوز/غير صالح: {self.results['invalid']}\n\n"
                f"⏱ الوقت: {duration/60:.1f} دقيقة"
            )
            print(f"\n\n[✓] انتهى الصيد.")
            await self.send_telegram(session, report)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    args = parser.parse_args()
    try:
        with open(args.file, 'r') as f:
            users = [line.strip().replace("@", "") for line in f if line.strip()]
        hunter = TwitterHunter(users, TG_BOT_TOKEN, TG_CHAT_ID)
        asyncio.run(hunter.run())
    except Exception as e:
        print(f"[!] خطأ: {e}")
