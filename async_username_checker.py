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
            
            # 1. الفحص عبر الـ API الرسمي للتسجيل (أدق طريقة لليوزرات الرباعية)
            url = "https://api.twitter.com/i/users/username_available.json"
            headers = {
                "Authorization": f"Bearer {BEARER}",
                "X-Guest-Token": str(self.guest_token),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://x.com/i/flow/signup"
            }
            
            try:
                async with session.get(url, params={"username": username}, headers=headers) as r:
                    status = r.status
                    
                    if status == 200:
                        data = await r.json()
                        valid = data.get("valid", False)
                        reason = data.get("reason", "unknown")
                        
                        if valid:
                            # تأكيد إضافي عبر فحص البروفايل (للتأكد أنه ليس متبند)
                            async with session.get(f"https://x.com/{username}", headers=headers, allow_redirects=True) as r2:
                                if r2.status == 404:
                                    self.results["available"].append(username)
                                    self.checked += 1
                                    self.print_progress(username, "AVAILABLE")
                                    msg = f"💎 *صيد ثمين (يوزر رباعي متاح):*\n\n`@{username}`\n\nهذا اليوزر متاح للتسجيل الآن عبر نظام الـ Signup!"
                                    await self.send_telegram(session, msg)
                                else:
                                    self.results["taken"] += 1
                                    self.checked += 1
                                    self.print_progress(username, "taken")
                        else:
                            if reason == "taken":
                                self.results["taken"] += 1
                            elif reason == "suspended":
                                self.results["suspended"] += 1
                            else:
                                self.results["invalid"] += 1
                            self.checked += 1
                            self.print_progress(username, reason)
                    
                    elif status == 403:
                        # تجديد توكن الزائر عند الحظر
                        await self.get_guest_token(session)
                        self.results["errors"] += 1
                        self.checked += 1
                        self.print_progress(username, "rate_limit")
                    else:
                        self.results["errors"] += 1
                        self.checked += 1
                        self.print_progress(username, f"err_{status}")

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
        print(f"[*] بدء صيد {self.total} يوزر (تركيز على الرباعي)...")
        self.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            if not await self.get_guest_token(session):
                print("[!] فشل الحصول على توكن الزائر. تأكد من الإنترنت.")
                return
                
            semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
            tasks = [self.check_user(session, u, semaphore) for u in self.usernames]
            await asyncio.gather(*tasks)
            
            duration = time.time() - self.start_time
            report = (
                f"🎯 *تقرير الصيد النهائي*\n\n"
                f"✅ متاح للتسجيل: {len(self.results['available'])}\n"
                f"❌ مأخوذ: {self.results['taken']}\n"
                f"🚫 متبند: {self.results['suspended']}\n"
                f"⚠️ غير صالح: {self.results['invalid']}\n\n"
                f"⚡️ السرعة: {self.total/duration:.1f} يوزر/ثانية"
            )
            print(f"\n\n[✓] انتهى الصيد. تم إرسال التقرير لتلجرام.")
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
