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

CONCURRENT_REQUESTS = 5 
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# Bearer Token الأساسي لتويتر
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

class TwitterFinalHunter:
    def __init__(self, usernames, bot_token, chat_id, proxies=None):
        self.usernames = usernames
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.proxies = proxies if proxies else [None] # نضع None ليعمل بدون بروكسي
        self.results = {"available": [], "taken": 0, "suspended": 0, "restricted": 0, "errors": 0}
        self.total = len(usernames)
        self.checked = 0
        self.start_time = None
        self.guest_token_pool = {} # {proxy: guest_token}

    async def get_guest_token(self, session, proxy=None):
        """الحصول على توكن زائر مع محاولات إعادة الاتصال"""
        headers = {
            "Authorization": f"Bearer {BEARER}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        for _ in range(3): # 3 محاولات
            try:
                async with session.post("https://api.twitter.com/1.1/guest/activate.json", 
                                        headers=headers, 
                                        proxy=proxy, 
                                        timeout=15) as r:
                    if r.status == 200:
                        data = await r.json()
                        token = data.get("guest_token")
                        if token: return token
            except:
                await asyncio.sleep(2)
        return None

    async def send_telegram(self, session, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with session.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}) as r:
                return await r.json()
        except: return None

    async def check_user(self, session, username, semaphore):
        async with semaphore:
            # اختيار بروكسي وتوكن
            current_proxy = random.choice(self.proxies)
            
            # إذا لم يكن هناك توكن للبروكسي، نحاول استخراجه
            if current_proxy not in self.guest_token_pool or not self.guest_token_pool[current_proxy]:
                self.guest_token_pool[current_proxy] = await self.get_guest_token(session, current_proxy)

            guest_token = self.guest_token_pool.get(current_proxy)
            
            if not guest_token:
                self.results["errors"] += 1
                self.checked += 1
                self.print_progress(username, "token_fail")
                return

            # فلترة الأنماط غير الصالحة (يجب أن يبدأ بحرف)
            if not username[0].isalpha():
                self.results["restricted"] += 1
                self.checked += 1
                self.print_progress(username, "pattern_skip")
                return

            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            
            headers = {
                "Authorization": f"Bearer {BEARER}",
                "X-Guest-Token": str(guest_token),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://x.com/i/flow/signup"
            }
            
            try:
                # فحص GraphQL
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
                            # فحص Validation النهائي
                            val_url = "https://api.twitter.com/i/users/username_available.json"
                            async with session.get(val_url, params={"username": username}, headers=headers, proxy=current_proxy) as val_r:
                                if val_r.status == 200:
                                    val_data = await val_r.json()
                                    if val_data.get("valid") == True:
                                        self.results["available"].append(username)
                                        msg = f"💎 *يوزر متاح للتسجيل:*\n\n`@{username}`\n\nاليوزر متاح ونظيف 100%."
                                        await self.send_telegram(session, msg)
                                        self.checked += 1
                                        self.print_progress(username, "AVAIL")
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
                        # تجديد التوكن عند الحظر
                        self.guest_token_pool[current_proxy] = await self.get_guest_token(session, current_proxy)
                        self.results["errors"] += 1
                        self.checked += 1
                        self.print_progress(username, "rate_limit")
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
        print(f"[*] بدء الصيد النهائي (حل مشكلة التوكن)...")
        self.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # تجهيز التوكنات الأولية
            for p in self.proxies:
                self.guest_token_pool[p] = await self.get_guest_token(session, p)
                
            semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
            tasks = [self.check_user(session, u, semaphore) for u in self.usernames]
            await asyncio.gather(*tasks)
            
            duration = time.time() - self.start_time
            report = (
                f"🎯 *تقرير الصيد النهائي*\n\n"
                f"✅ متاح: {len(self.results['available'])}\n"
                f"❌ مأخوذ: {self.results['taken']}\n"
                f"🚫 أخطاء/حظر: {self.results['errors']}\n\n"
                f"⏱ الوقت: {duration/60:.1f} دقيقة"
            )
            print(f"\n\n[✓] انتهى الصيد.")
            await self.send_telegram(session, report)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--proxies", default=None)
    args = parser.parse_args()
    
    proxies = [None]
    if args.proxies and os.path.exists(args.proxies):
        with open(args.proxies, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
            proxies = [p if p.startswith('http') else f"http://{p}" for p in proxies]

    try:
        with open(args.file, 'r') as f:
            users = [line.strip().replace("@", "") for line in f if line.strip()]
        hunter = TwitterFinalHunter(users, TG_BOT_TOKEN, TG_CHAT_ID, proxies)
        asyncio.run(hunter.run())
    except Exception as e:
        print(f"[!] خطأ: {e}")
