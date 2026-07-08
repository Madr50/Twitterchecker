import asyncio
import aiohttp
import argparse
import re
import time
import sys
import random

# ==========================================
# الإعدادات (Configuration)
# ==========================================

# Telegram Configuration
TG_BOT_TOKEN = "8654290922:AAHHOnPDU60i10z9neTNJq5HdsJw4RmfBbw"
TG_CHAT_ID = "8989271393"

# عدد الطلبات المتزامنة - لا تزيده كثيراً لتجنب الحظر
CONCURRENT_REQUESTS = 10

# تأخير عشوائي بين الطلبات (ثانية)
MIN_DELAY = 0.3
MAX_DELAY = 0.8

# عدد المحاولات عند الفشل
MAX_RETRIES = 3

# إرسال تقرير تيليجرام كل X يوزر
TELEGRAM_BATCH_SIZE = 50

# ==========================================
# قائمة User-Agents متنوعة
# ==========================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# ==========================================
# وظائف المساعدة (Helper Functions)
# ==========================================

async def send_telegram_message(session, message):
    """إرسال رسالة عبر تيليجرام"""
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    for attempt in range(3):
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return True
                elif response.status == 429:
                    await asyncio.sleep(5)
        except Exception:
            await asyncio.sleep(2)
    return False

def is_username_available(http_code: int, html_content: str) -> str:
    """
    تحديد حالة اليوزرنيم بناءً على كود HTTP ومحتوى الصفحة.
    
    المنطق:
    - HTTP 404 = اليوزر غير موجود (متاح)
    - HTTP 200 + عنوان يحتوي على اسم المستخدم = موجود (مشغول)
    - HTTP 200 + عنوان "Profile / X" = صفحة 404 مخفية (متاح)
    - HTTP 429 = Rate Limit
    - غير ذلك = خطأ
    """
    if http_code == 429:
        return "RATE_LIMIT"
    if http_code == 404:
        return "AVAILABLE"
    if http_code == 200:
        # X أحياناً يعيد 200 لصفحات 404 مع عنوان "Profile / X"
        titles = re.findall(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
        if titles:
            title = titles[0]
            if title.strip() == "Profile / X":
                return "AVAILABLE"
            elif "/ X" in title:
                return "TAKEN"
        return "TAKEN"
    if http_code in (400, 401, 403):
        return "ERROR"
    return "ERROR"

# ==========================================
# محرك الفحص (Checking Engine)
# ==========================================

async def check_username(session, username, semaphore, retry=0):
    """يفحص توفر اليوزر عبر صفحة X.com مباشرة"""
    async with semaphore:
        # تأخير عشوائي لتجنب الحظر
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
        
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }
        
        url = f"https://x.com/{username}"
        
        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=False
            ) as response:
                http_code = response.status
                
                if http_code == 429:
                    # Rate Limit - انتظر وأعد المحاولة
                    wait_time = 30 + (retry * 15)
                    await asyncio.sleep(wait_time)
                    if retry < MAX_RETRIES:
                        return await check_username(session, username, semaphore, retry + 1)
                    return username, "RATE_LIMIT"
                
                if http_code in (301, 302):
                    # Redirect - تتبع يدوياً
                    location = response.headers.get("Location", "")
                    if "redirect.x.com" in location or location.startswith("x-safari"):
                        # هذا يعني الصفحة موجودة (redirect للتطبيق)
                        return username, "TAKEN"
                    # redirect عادي - نتبعه
                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15),
                        allow_redirects=True
                    ) as resp2:
                        http_code = resp2.status
                        html = await resp2.text(encoding='utf-8', errors='ignore')
                        status = is_username_available(http_code, html)
                        return username, status
                
                html = await response.text(encoding='utf-8', errors='ignore')
                status = is_username_available(http_code, html)
                return username, status
                
        except asyncio.TimeoutError:
            if retry < MAX_RETRIES:
                await asyncio.sleep(3)
                return await check_username(session, username, semaphore, retry + 1)
            return username, "TIMEOUT"
        except Exception as e:
            if retry < MAX_RETRIES:
                await asyncio.sleep(2)
                return await check_username(session, username, semaphore, retry + 1)
            return username, "ERROR"

# ==========================================
# البرنامج الرئيسي
# ==========================================

async def main():
    arg_parser = argparse.ArgumentParser(
        description="فاحص يوزرنيمات تويتر/X مع إشعارات تيليجرام"
    )
    arg_parser.add_argument("username_file", help="ملف txt يحتوي على اليوزرنيمات (سطر لكل يوزر)")
    arg_parser.add_argument("--min-len", type=int, default=1, help="الحد الأدنى لطول اليوزر (افتراضي: 1)")
    arg_parser.add_argument("--max-len", type=int, default=15, help="الحد الأقصى لطول اليوزر (افتراضي: 15)")
    arg_parser.add_argument("--concurrency", type=int, default=CONCURRENT_REQUESTS, help=f"عدد الطلبات المتزامنة (افتراضي: {CONCURRENT_REQUESTS})")
    args = arg_parser.parse_args()

    # قراءة الملف
    try:
        with open(args.username_file, 'r', encoding='utf-8') as f:
            raw_lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"\033[1;31m[!] الملف غير موجود: {args.username_file}\033[0m")
        return
    except Exception as e:
        print(f"\033[1;31m[!] فشل قراءة الملف: {e}\033[0m")
        return

    # تصفية اليوزرنيمات الصالحة
    valid_usernames = []
    for u in raw_lines:
        # تويتر: 1-15 حرف، أحرف وأرقام وشرطة سفلية فقط
        if re.match(r'^[A-Za-z0-9_]{1,15}$', u) and args.min_len <= len(u) <= args.max_len:
            valid_usernames.append(u)

    if not valid_usernames:
        print(f"\033[1;31m[!] لا توجد يوزرنيمات صالحة في الملف (طول {args.min_len}-{args.max_len} حرف).\033[0m")
        return

    total = len(valid_usernames)
    print(f"\033[1;34m[+]\033[0m تم تحميل \033[1;33m{total}\033[0m يوزر صالح للفحص.")
    print(f"\033[1;34m[+]\033[0m الطلبات المتزامنة: {args.concurrency} | التأخير: {MIN_DELAY}-{MAX_DELAY}s")
    print(f"\033[1;34m[+]\033[0m سيتم إرسال النتائج المتاحة مباشرة عبر تيليجرام.\n")

    # إعداد الجلسة
    connector = aiohttp.TCPConnector(
        limit=args.concurrency * 2,
        ttl_dns_cache=300,
        ssl=False  # تسريع الاتصال
    )
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # إرسال رسالة بداية لتيليجرام
        start_msg = (
            f"🚀 *بدأ الفحص*\n"
            f"📋 عدد اليوزرات: `{total}`\n"
            f"⚡ الطلبات المتزامنة: `{args.concurrency}`\n"
            f"🕐 وقت البدء: `{time.strftime('%H:%M:%S')}`"
        )
        tg_ok = await send_telegram_message(session, start_msg)
        if tg_ok:
            print(f"\033[1;32m[✓]\033[0m تم الاتصال بتيليجرام بنجاح.")
        else:
            print(f"\033[1;33m[!]\033[0m تحذير: فشل الاتصال بتيليجرام، سيستمر الفحص محلياً.")

        start_time = time.time()
        semaphore = asyncio.Semaphore(args.concurrency)
        
        # إحصائيات
        stats = {
            "available": 0,
            "taken": 0,
            "error": 0,
            "rate_limit": 0,
            "processed": 0
        }
        
        available_batch = []  # تجميع المتاحين لإرسالهم دفعة واحدة

        async def worker(username):
            user, status = await check_username(session, username, semaphore)
            
            stats["processed"] += 1
            idx = stats["processed"]
            
            if status == "AVAILABLE":
                stats["available"] += 1
                available_batch.append(user)
                print(f"\033[1;32m[🎯 متاح!]\033[0m @{user}")
                # إرسال فوري لتيليجرام
                await send_telegram_message(session, f"🎯 *يوزر متاح:* `@{user}`")
                
            elif status == "TAKEN":
                stats["taken"] += 1
                print(f"\033[0;90m[✗ مشغول]\033[0m @{user}", end="\r")
                
            elif status == "RATE_LIMIT":
                stats["rate_limit"] += 1
                print(f"\033[1;33m[⚠ Rate Limit]\033[0m @{user} - تم الانتظار تلقائياً")
                
            elif status in ("ERROR", "TIMEOUT"):
                stats["error"] += 1
            
            # تحديث شريط التقدم
            elapsed = time.time() - start_time
            speed = idx / elapsed if elapsed > 0 else 0
            remaining = (total - idx) / speed if speed > 0 else 0
            
            sys.stdout.write(
                f"\r\033[1;34m[*]\033[0m التقدم: {idx}/{total} "
                f"| ✅ متاح: {stats['available']} "
                f"| ❌ مشغول: {stats['taken']} "
                f"| ⚠ خطأ: {stats['error']} "
                f"| ⚡ {speed:.1f}/s "
                f"| ⏱ متبقي: {remaining:.0f}s    "
            )
            sys.stdout.flush()
            
            # إرسال تقرير دوري لتيليجرام
            if idx % TELEGRAM_BATCH_SIZE == 0 or idx == total:
                elapsed_min = elapsed / 60
                progress_msg = (
                    f"📊 *تقرير التقدم*\n"
                    f"✅ تم فحص: `{idx}/{total}`\n"
                    f"🎯 متاحة: `{stats['available']}`\n"
                    f"❌ مشغولة: `{stats['taken']}`\n"
                    f"⚠ أخطاء: `{stats['error']}`\n"
                    f"⏱ الوقت: `{elapsed_min:.1f} دقيقة`\n"
                    f"⚡ السرعة: `{speed:.1f} يوزر/ثانية`"
                )
                await send_telegram_message(session, progress_msg)

        # تشغيل جميع المهام
        tasks = [worker(u) for u in valid_usernames]
        await asyncio.gather(*tasks)

        # النتيجة النهائية
        duration = time.time() - start_time
        print(f"\n\n{'='*60}")
        print(f"\033[1;32m[✓] اكتمل الفحص!\033[0m")
        print(f"{'='*60}")
        print(f"  📋 إجمالي اليوزرات: {total}")
        print(f"  🎯 المتاحة:          {stats['available']}")
        print(f"  ❌ المشغولة:         {stats['taken']}")
        print(f"  ⚠  الأخطاء:          {stats['error']}")
        print(f"  ⏱  الوقت الكلي:      {duration:.1f} ثانية ({duration/60:.1f} دقيقة)")
        print(f"  ⚡ متوسط السرعة:     {total/duration:.1f} يوزر/ثانية")
        print(f"{'='*60}\n")

        # رسالة ختامية لتيليجرام
        final_msg = (
            f"🏁 *انتهى الفحص الكامل!*\n\n"
            f"📋 إجمالي: `{total}` يوزر\n"
            f"🎯 المتاحة: `{stats['available']}`\n"
            f"❌ المشغولة: `{stats['taken']}`\n"
            f"⚠ الأخطاء: `{stats['error']}`\n"
            f"⏱ الوقت: `{duration/60:.1f} دقيقة`\n"
            f"⚡ السرعة: `{total/duration:.1f} يوزر/ثانية`"
        )
        await send_telegram_message(session, final_msg)

if __name__ == "__main__":
    asyncio.run(main())
