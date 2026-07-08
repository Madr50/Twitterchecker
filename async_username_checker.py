import asyncio
import aiohttp
import argparse
import random
import sys
import time
from datetime import datetime

# ==========================================
# الإعدادات (Configuration)
# ==========================================

TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

# سرعة الفحص (تعديل حسب الرغبة)
CONCURRENT_REQUESTS = 10 
MIN_DELAY = 0.5
MAX_DELAY = 1.0

# ==========================================
# الكلاس الأساسي للفحص
# ==========================================

class TwitterChecker:
    def __init__(self, usernames, bot_token, chat_id):
        self.usernames = usernames
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.results = {"available": [], "taken": 0, "suspended": 0, "errors": 0}
        self.total = len(usernames)
        self.checked = 0
        self.start_time = None

    async def send_telegram(self, session, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with session.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}) as r:
                return await r.json()
        except:
            return None

    async def check_user(self, session, username, semaphore):
        async with semaphore:
            # تأخير بسيط لتجنب الحظر
            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            
            url = f"https://x.com/{username}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            
            try:
                async with session.get(url, headers=headers, allow_redirects=True, timeout=10) as r:
                    final_url = str(r.url)
                    status = r.status
                    content = await r.text()
                    
                    is_available = False
                    reason = "taken"

                    # 1. فحص إذا كان الحساب متبند (Suspended)
                    if "suspended" in final_url.lower() or "Account suspended" in content:
                        self.results["suspended"] += 1
                        reason = "suspended"
                    
                    # 2. فحص إذا كان الحساب متاح (404 ولا يوجد أثر لتبنيد)
                    elif status == 404:
                        if "Account suspended" not in content:
                            is_available = True
                            self.results["available"].append(username)
                            reason = "available"
                        else:
                            self.results["suspended"] += 1
                            reason = "suspended"
                    
                    # 3. الحساب مأخوذ (200)
                    elif status == 200:
                        self.results["taken"] += 1
                        reason = "taken"
                    
                    else:
                        self.results["errors"] += 1
                        reason = f"status_{status}"

                    self.checked += 1
                    self.print_progress(username, reason)

                    if is_available:
                        msg = f"🎯 *يوزر متاح للتسجيل:*\n\n`@{username}`\n\nهذا اليوزر غير مستخدم وغير متبند حالياً."
                        await self.send_telegram(session, msg)

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
        
        sys.stdout.write(f"\r|{bar}| {percent:.1f}% [{self.checked}/{self.total}] Speed: {speed:.1f} u/s | Last: @{current_user} ({status})")
        sys.stdout.flush()

    async def run(self):
        print(f"[*] بدء فحص {self.total} يوزر...")
        self.start_time = time.time()
        
        connector = aiohttp.TCPConnector(ssl=False, limit=0)
        async with aiohttp.ClientSession(connector=connector) as session:
            semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
            tasks = [self.check_user(session, u, semaphore) for u in self.usernames]
            await asyncio.gather(*tasks)
            
            end_time = time.time()
            duration = end_time - self.start_time
            speed = self.total / duration if duration > 0 else 0
            
            final_report = (
                f"📊 *تقرير فحص يوزرات تويتر*\n\n"
                f"✅ متاح: {len(self.results['available'])}\n"
                f"❌ مشغول: {self.results['taken']}\n"
                f"🚫 متبند: {self.results['suspended']}\n"
                f"⚠️ أخطاء: {self.results['errors']}\n\n"
                f"⏱ الوقت: {duration/60:.1f} دقيقة\n"
                f"⚡️ السرعة: {speed:.1f} يوزر/ثانية"
            )
            print("\n\n[✓] انتهى الفحص.")
            await self.send_telegram(session, final_report)

# ==========================================
# تشغيل البرنامج
# ==========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to the usernames.txt file")
    args = parser.parse_args()

    try:
        with open(args.file, 'r') as f:
            users = [line.strip().replace("@", "") for line in f if line.strip()]
        
        if not users:
            print("[!] الملف فارغ.")
            sys.exit(1)
            
        checker = TwitterChecker(users, TG_BOT_TOKEN, TG_CHAT_ID)
        asyncio.run(checker.run())
        
    except FileNotFoundError:
        print(f"[!] الملف غير موجود: {args.file}")
    except KeyboardInterrupt:
        print("\n[!] تم إيقاف الفحص بواسطة المستخدم.")
