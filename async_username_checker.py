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

CONCURRENT_REQUESTS = 3 # تقليل العدد لزيادة الدقة وتجنب الحظر
MIN_DELAY = 2.0
MAX_DELAY = 4.0

BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# ==========================================
# الكلاس الأساسي للفحص العميق
# ==========================================

class TwitterEliteHunter:
    def __init__(self, usernames, bot_token, chat_id):
        self.usernames = usernames
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.results = {"available": [], "taken": 0, "suspended": 0, "client_error_risk": 0, "errors": 0}
        self.total = len(usernames)
        self.checked = 0
        self.start_time = None
        self.guest_token = None

    async def get_guest_token(self, session):
        try:
            headers = {"Authorization": f"Bearer {BEARER}"}
            async with session.post("https://api.twitter.com/1.1/guest/activate.json", headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    self.guest_token = data.get("guest_token")
                    return True
        except: pass
        return False

    async def send_telegram(self, session, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with session.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}) as r:
                return await r.json()
        except: return None

    def is_risky_pattern(self, username):
        """فلترة الأنماط التي تسبب غالباً Client Error"""
        # 1. اليوزرات الرباعية التي تبدأ بـ _
        if len(username) <= 4 and username.startswith('_'):
            return True
        # 2. اليوزرات التي تنتهي بـ _ (غالباً محجوزة)
        if username.endswith('_'):
            return True
        # 3. اليوزرات التي تحتوي على أحرف مكررة بشكل مشبوه (اختياري)
        return False

    async def check_user(self, session, username, semaphore):
        async with semaphore:
            await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            
            # فلترة أولية للأنماط الخطرة
            if self.is_risky_pattern(username):
                self.results["client_error_risk"] += 1
                self.checked += 1
                self.print_progress(username, "risky_pattern")
                return

            headers = {
                "Authorization": f"Bearer {BEARER}",
                "X-Guest-Token": str(self.guest_token),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://x.com/i/flow/signup"
            }
            
            try:
                # 1. الفحص عبر GraphQL (أدق نظام حالياً)
                # نستخدم Query الخاص بـ UserByScreenName
                query_id = "9n9be9_jshZ_7fWpS_iUow"
                url = f"https://x.com/i/api/graphql/{query_id}/UserByScreenName"
                variables = {"screen_name": username, "withSafetyModeUserFields": True}
                features = {"hidden_profile_subscriptions_enabled": True, "rweb_tipjar_consumption_enabled": True, "responsive_web_graphql_exclude_directive_enabled": True, "verified_phone_label_enabled": False, "subscriptions_verification_info_is_identity_verified_enabled": True, "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True, "responsive_web_graphql_timeline_navigation_enabled": True, "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False, "responsive_web_reg_month_day_enabled": True, "vibe_api_enabled": True, "responsive_web_twitter_article_tweet_consumption_enabled": True, "tweet_awards_web_tipping_enabled": False, "creator_subscriptions_tweet_preview_api_enabled": True, "freedom_of_speech_not_reach_fetch_enabled": True, "standardized_nudges_misinfo": True, "tweet_with_visibility_results_prefer_gql_limited_actions_tweet_enabled": True, "responsive_web_enhance_cards_enabled": False}
                
                params = {"variables": json.dumps(variables), "features": json.dumps(features)}
                
                async with session.get(url, params=params, headers=headers) as r:
                    if r.status == 200:
                        data = await r.json()
                        user_result = data.get("data", {}).get("user", {}).get("result", {})
                        
                        # إذا لم يوجد مستخدم بهذا اليوزر
                        if not user_result or user_result.get("__typename") == "UserUnavailable":
                            
                            # 2. فحص إضافي عبر Signup Validation لضمان عدم وجود Client Error
                            val_url = "https://api.twitter.com/i/users/username_available.json"
                            async with session.get(val_url, params={"username": username}, headers=headers) as val_r:
                                if val_r.status == 200:
                                    val_data = await val_r.json()
                                    if val_data.get("valid") == True:
                                        # يوزر ذهبي متاح 100%
                                        self.results["available"].append(username)
                                        msg = f"🌟 *صيد ملكي (متاح 100%):*\n\n`@{username}`\n\nهذا اليوزر مر من فحص GraphQL وفحص الـ Validation بنجاح!"
                                        await self.send_telegram(session, msg)
                                        self.checked += 1
                                        self.print_progress(username, "ELITE_AVAIL")
                                        return
                                    else:
                                        self.results["client_error_risk"] += 1
                                        self.checked += 1
                                        self.print_progress(username, "restricted")
                                        return
                        else:
                            self.results["taken"] += 1
                            self.checked += 1
                            self.print_progress(username, "taken")
                    
                    elif r.status == 403:
                        await self.get_guest_token(session)
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
        print(f"[*] بدء الصيد الملكي (نظام GraphQL + فلترة Client Error)...")
        self.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            await self.get_guest_token(session)
            semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
            tasks = [self.check_user(session, u, semaphore) for u in self.usernames]
            await asyncio.gather(*tasks)
            
            duration = time.time() - self.start_time
            report = (
                f"👑 *تقرير الصيد الملكي النهائي*\n\n"
                f"✅ متاح 100%: {len(self.results['available'])}\n"
                f"❌ مأخوذ: {self.results['taken']}\n"
                f"⚠️ مخاطرة (Client Error): {self.results['client_error_risk']}\n"
                f"🚫 متبند/أخطاء: {self.results['suspended'] + self.results['errors']}\n\n"
                f"⚡️ السرعة: {self.total/duration:.1f} يوزر/ثانية"
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
        hunter = TwitterEliteHunter(users, TG_BOT_TOKEN, TG_CHAT_ID)
        asyncio.run(hunter.run())
    except Exception as e:
        print(f"[!] خطأ: {e}")
