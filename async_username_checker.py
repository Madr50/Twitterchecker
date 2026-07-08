import asyncio
import aiohttp
import argparse
import random
import sys
import time
import json
import os

# ==========================================
# الإعدادات (Configuration)
# ==========================================

TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

CONCURRENT_REQUESTS = 10 # يمكن زيادتها عند استخدام البروكسيات
MIN_DELAY = 1.0
MAX_DELAY = 2.0

BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# ==========================================
# الكلاس الأساسي للصيد الاحترافي (Pro Hunter)
# ==========================================

class TwitterProHunter:
    def __init__(self, usernames, bot_token, chat_id, proxies=None):
        self.usernames = usernames
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.proxies = proxies if proxies else []
        self.results = {"available": [], "taken": 0, "suspended": 0, "restricted": 0, "errors": 0}
        self.total = len(usernames)
        self.checked = 0
        self.start_time = None
        self.guest_token_pool = {} # {proxy: guest_token}
        self.token_lock = asyncio.Lock()

    async def get_guest_token(self, session, proxy=None):
        """الحصول على توكن زائر لبروكسي معين"""
        try:
            headers = {"Authorization": f"Bearer {BEARER}"}
            async with session.post("https://api.twitter.com/1.1/guest/activate.json", 
                                    headers=headers, 
                                    proxy=proxy, 
                                    timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("guest_token")
        except: pass
        return None

    async def send_telegram(self, session, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with session.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}) as r:
                return await r.json()
        except: return None

    def is_safe_pattern(self, username):
        """فلترة صارمة لليوزرات التي تسبب أخطاء تسجيل"""
        # 1. استبعاد أي يوزر يبدأ برقم أو _
        if not username[0].isalpha():
            return False
        # 2. استبعاد أي يوزر يحتوي على أحرف مكررة أكثر من مرتين (اختياري للصيد النقي)
        # 3. التأكد من أن اليوزر لا ينتهي بـ _
        if username.endswith('_'):
            return False
        return True

    async def check_user(self, session, username, semaphore):
        async with semaphore:
            # اختيار بروكسي عشوائي من القائمة
            current_proxy = random.choice(self.proxies) if self.proxies else None
            
            # فلترة الأنماط غير الصالحة مسبقاً
            if not self.is_safe_pattern(username):
                self.results["restricted"] += 1
                self.checked += 1
                self.print_progress(username, "pattern_skip")
                return

            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            
            # التأكد من وجود توكن للبروكسي الحالي
            if current_proxy not in self.guest_token_pool:
                self.guest_token_pool[current_proxy] = await self.get_guest_token(session, current_proxy)

            guest_token = self.guest_token_pool.get(current_proxy)
            if not guest_token:
                self.results["errors"] += 1
                self.checked += 1
                self.print_progress(username, "token_fail")
                return

            headers = {
                "Authorization": f"Bearer {BEARER}",
                "X-Guest-Token": str(guest_token),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://x.com/i/flow/signup"
            }
            
            try:
                # المرحلة 1: فحص GraphQL (أدق نظام لكشف الوجود)
                query_id = "9n9be9_jshZ_7fWpS_iUow"
                url = f"https://x.com/i/api/graphql/{query_id}/UserByScreenName"
                variables = {"screen_name": username, "withSafetyModeUserFields": True}
                features = {"hidden_profile_subscriptions_enabled": True, "rweb_tipjar_consumption_enabled": True, "responsive_web_graphql_exclude_directive_enabled": True, "verified_phone_label_enabled": False, "subscriptions_verification_info_is_identity_verified_enabled": True, "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True, "responsive_web_graphql_timeline_navigation_enabled": True, "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False, "responsive_web_reg_month_day_enabled": True, "vibe_api_enabled": True, "responsive_web_twitter_article_tweet_consumption_enabled": True, "tweet_awards_web_tipping_enabled": False, "creator_subscriptions_tweet_preview_api_enabled": True, "freedom_of_speech_not_reach_fetch_enabled": True, "standardized_nudges_misinfo": True, "tweet_with_visibility_results_prefer_gql_limited_actions_tweet_enabled": True, "responsive_web_enhance_cards_enabled": False}
                params = {"variables": json.dumps(variables), "features": json.dumps(features)}
                
                async with session.get(url, params=params, headers=headers, proxy=current_proxy) as r:
                    if r.status == 200:
                        data = await r.json()
                        user_result = data.get("data", {}).get("user", {}).get("result", {})
                        
                        if not user_result or user_result.get("__typename") == "UserUnavailable":
                            # المرحلة 2: فحص الصلاحية الفعلي (Signup Validation) لمنع Client Error
                            val_url = "https://api.twitter.com/i/users/username_available.json"
                            async with session.get(val_url, params={"username": username}, headers=headers, proxy=current_proxy) as val_r:
                                if val_r.status == 200:
                                    val_data = await val_r.json()
                                    if val_data.get("valid") == True:
                                        # يوزر ذهبي متاح وصالح للتسجيل
                                        self.results["available"].append(username)
                                        msg = f"💎 *صيد نقي (يوزر متاح للتسجيل):*\n\n`@{username}`\n\nاليوزر مر من فحص GraphQL وفحص الصلاحية بنجاح. جاهز للتسجيل الآن!"
                                        await self.send_telegram(session, msg)
                                        self.checked += 1
                                        self.print_progress(username, "PURE_AVAIL")
                                        return
                                    else:
                                        self.results["restricted"] += 1
                                        self.checked += 1
                                        self.print_progress(username, "restricted")
                                        return
                        else:
                            self.results["taken"] += 1
                            self.checked += 1
                            self.print_progress(username, "taken")
                    
                    elif r.status == 403:
                        # تجديد التوكن للبروكسي الحالي عند الحظر
                        self.guest_token_pool[current_proxy] = await self.get_guest_token(session, current_proxy)
                        self.results["errors"] += 1
                        self.checked += 1
                        self.print_progress(username, "rate_limit_refresh")
                    else:
                        self.results["errors"] += 1
                        self.checked += 1
                        self.print_progress(username, f"err_{r.status}")

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
        print(f"[*] بدء الصيد الاحترافي (دعم البروكسيات + الفحص النقي)...")
        self.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # تحميل التوكنات الأولية
            print("[*] جاري تجهيز توكنات الزائر...")
            if self.proxies:
                for p in self.proxies[:10]: # تجهيز أول 10 فقط لتسريع البداية
                    self.guest_token_pool[p] = await self.get_guest_token(session, p)
            else:
                self.guest_token_pool[None] = await self.get_guest_token(session)
                
            semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
            tasks = [self.check_user(session, u, semaphore) for u in self.usernames]
            await asyncio.gather(*tasks)
            
            duration = time.time() - self.start_time
            report = (
                f"🚀 *تقرير الصيد الاحترافي النهائي*\n\n"
                f"✅ متاح نقي: {len(self.results['available'])}\n"
                f"❌ مأخوذ: {self.results['taken']}\n"
                f"⚠️ مقيد/محجوز: {self.results['restricted']}\n"
                f"🚫 أخطاء: {self.results['errors']}\n\n"
                f"⏱ الوقت: {duration/60:.1f} دقيقة"
            )
            print(f"\n\n[✓] انتهى الصيد.")
            await self.send_telegram(session, report)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="ملف اليوزرات")
    parser.add_argument("--proxies", help="ملف البروكسيات (اختياري)", default=None)
    args = parser.parse_args()
    
    proxies = []
    if args.proxies and os.path.exists(args.proxies):
        with open(args.proxies, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
            # التأكد من صيغة البروكسي (http://user:pass@ip:port)
            proxies = [p if p.startswith('http') else f"http://{p}" for p in proxies]
            print(f"[*] تم تحميل {len(proxies)} بروكسي.")

    try:
        with open(args.file, 'r') as f:
            users = [line.strip().replace("@", "") for line in f if line.strip()]
        hunter = TwitterProHunter(users, TG_BOT_TOKEN, TG_CHAT_ID, proxies)
        asyncio.run(hunter.run())
    except Exception as e:
        print(f"[!] خطأ: {e}")
