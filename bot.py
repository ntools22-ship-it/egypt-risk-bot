import feedparser
import requests
import hashlib
import time
import os
import io
import re
import json
import difflib

from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse, parse_qs, unquote

from bs4 import BeautifulSoup


# ══════════════════════════════════════════════════════════════════
# إعدادات
# ══════════════════════════════════════════════════════════════════

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

CHANNEL_ID = "@egypt_risk_radar"

API_URL = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else ""
)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    if GEMINI_KEY
    else ""
)

FONT_PATH = "/tmp/Amiri-Regular.ttf"

FONT_URL = (
    "https://github.com/aliftype/amiri/raw/main/fonts/"
    "Amiri-Regular.ttf"
)

HTTP_TIMEOUT = 20
TELEGRAM_TIMEOUT = 30
MAX_TELEGRAM_MESSAGE = 4000


# ══════════════════════════════════════════════════════════════════
# الأخبار التي لا نريد نشرها
# ══════════════════════════════════════════════════════════════════

EXCLUDE_KW = [
    "مواعيد قطارات",
    "مواعيد القطار",
    "مواعيد القطارات",
    "جدول قطارات",
    "جدول القطارات",
    "أسعار تذاكر القطارات",
    "اسعار تذاكر القطارات",
    "حجز تذاكر القطارات",
    "حجز تذاكر القطار",
    "محطات القطارات",
    "محطة القطار",
    "قطارات اليوم",
    "القطار اليوم",
    "قطار اليوم",
    "حركة القطارات",
    "حركة القطارات اليوم",
    "تأخيرات القطارات",
    "تأخير القطارات",
    "مواعيد المترو",
    "مواعيد الأتوبيسات",
    "مواعيد الاتوبيسات",
    "جدول المترو",
    "مواعيد وسائل النقل",
]


UPDATE_KW = [
    "ارتفاع عدد",
    "حصيلة",
    "حصيلة جديدة",
    "تطورات",
    "آخر التطورات",
    "تحديث",
    "تفاصيل جديدة",
    "كشف سبب",
    "كشفت التحقيقات",
    "التحقيقات",
    "النيابة",
    "ضبط",
    "القبض على",
    "إصابة",
    "إصابات",
    "وفاة",
    "وفيات",
    "انتشال",
    "إخماد",
    "السيطرة على",
    "استمرار",
    "استكمال",
    "فتح تحقيق",
    "إحالة",
    "قرار جديد",
    "بيان جديد",
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,*/*;q=0.8"
    ),
    "Referer": "https://www.google.com/",
}


# ══════════════════════════════════════════════════════════════════
# المصادر — RSS
# ══════════════════════════════════════════════════════════════════

RSS_SOURCES = [

    {
        "id": "amwal_banks",
        "name": "أموال الغد - بنوك",
        "url": (
            "https://amwalalghad.com/category/"
            "%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-"
            "%d9%85%d8%a7%d9%84%d9%8a%d8%a9/feed/"
        ),
        "tab": "banks",
        "exclude": ["سعر"]
    },

    {
        "id": "masrafeyoun_banks",
        "name": "المصرفيون",
        "url": (
            "https://masrafeyoun.ebi.gov.eg/"
            "category/banksnews/feed/"
        ),
        "tab": "banks",
        "exclude": []
    },

    {
        "id": "hapi_credit",
        "name": "حابي - تمويل",
        "url": (
            "https://hapijournal.com/category/"
            "%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/"
        ),
        "tab": "credit",
        "exclude": []
    },

    {
        "id": "motawwer_credit",
        "name": "المطور - تمويل",
        "url": (
            "https://almotawwer.com/tag/"
            "%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%b9%d8%a7%d8%aa-"
            "%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%b1%d8%a9/feed/"
        ),
        "tab": "credit",
        "exclude": []
    },

    {
        "id": "amwal_micro",
        "name": "أموال الغد - تمويل",
        "url": (
            "https://amwalalghad.com/tag/"
            "%d9%85%d8%aa%d9%86%d8%a7%d9%87%d9%8a-%d8%a7%d9%84%d8%b5%d8%ba%d8%b1/feed/"
        ),
        "tab": "credit",
        "exclude": []
    },

    {
        "id": "hapi_fx",
        "name": "حابي - دولار",
        "url": (
            "https://hapijournal.com/tag/"
            "%d8%a3%d8%b3%d8%b9%d8%a7%d8%b1-%d8%a7%d9%84%d8%af%d9%88%d9%84%d8%a7%d8%b1/feed/"
        ),
        "tab": "fx",
        "exclude": []
    },

    {
        "id": "skynews_business",
        "name": "سكاي نيوز - اقتصاد",
        "url": "https://www.skynewsarabia.com/rss/business.xml",
        "tab": "global",
        "exclude": []
    },

    # ══════════════════════════════════════════════════════════════
    # البورصة نيوز - قطاعات
    # ══════════════════════════════════════════════════════════════

    {
        "id": "borsaa_agri",
        "name": "البورصة نيوز - زراعة",
        "url": (
            "https://www.alborsaanews.com/tag/"
            "%d8%a7%d9%84%d8%b2%d8%b1%d8%a7%d8%b9%d8%a9/feed/"
        ),
        "tab": "sector_agri",
        "exclude": []
    },

    {
        "id": "borsaa_industry",
        "name": "البورصة نيوز - صناعة",
        "url": (
            "https://www.alborsaanews.com/tag/"
            "%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d8%a9/feed/"
        ),
        "tab": "sector_industry",
        "exclude": []
    },

    {
        "id": "borsaa_realestate",
        "name": "البورصة نيوز - عقارات",
        "url": (
            "https://www.alborsaanews.com/category/"
            "%d8%a7%d9%84%d8%b9%d9%82%d8%a7%d8%b1%d8%a7%d8%aa/feed/"
        ),
        "tab": "sector_realestate",
        "exclude": []
    },

    # ══════════════════════════════════════════════════════════════
    # البورصة نيوز - بنوك
    # تم استبدال الـ General Feed بهذا المصدر
    # ══════════════════════════════════════════════════════════════

    {
        "id": "borsaa_banks",
        "name": "البورصة نيوز - بنوك",
        "url": (
            "https://www.alborsaanews.com/category/"
            "%d8%a7%d9%84%d8%a8%d9%86%d9%88%d9%83/feed/"
        ),
        "tab": "banks",
        "exclude": []
    },

    # ══════════════════════════════════════════════════════════════
    # أموال الغد
    # ══════════════════════════════════════════════════════════════

    {
        "id": "amwal_energy",
        "name": "أموال الغد - طاقة",
        "url": (
            "https://amwalalghad.com/category/"
            "%d8%b7%d8%a7%d9%82%d8%a9/feed/"
        ),
        "tab": "sector_energy",
        "exclude": []
    },

    {
        "id": "amwal_transport",
        "name": "أموال الغد - نقل",
        "url": (
            "https://amwalalghad.com/category/"
            "%d9%86%d9%82%d9%84-%d9%88-%d9%85%d9%84%d8%a7%d8%ad%d8%a9/feed/"
        ),
        "tab": "sector_transport",
        "exclude": []
    },

    {
        "id": "amwal_tech",
        "name": "أموال الغد - تكنولوجيا",
        "url": (
            "https://amwalalghad.com/category/"
            "%d8%aa%d9%83%d9%86%d9%88%d9%84%d9%88%d8%ac%d9%8a%d8%a7-%d9%88%d8%a7%d8%aa%d8%b5%d8%a7%d9%84%d8%a7%d8%aa/feed/"
        ),
        "tab": "sector_tech",
        "exclude": []
    },

    # ══════════════════════════════════════════════════════════════
    # المصادر العامة → عاجل
    # ══════════════════════════════════════════════════════════════

    {
        "id": "hapi_all",
        "name": "حابي",
        "url": "https://hapijournal.com/feed/",
        "tab": None,
        "exclude": []
    },

    {
        "id": "febanks_all",
        "name": "في البنوك",
        "url": "https://febanks.com/feed/",
        "tab": None,
        "exclude": []
    },

    {
        "id": "masrafeyoun_all",
        "name": "المصرفيون",
        "url": "https://masrafeyoun.ebi.gov.eg/feed/",
        "tab": None,
        "exclude": []
    },
]


# ══════════════════════════════════════════════════════════════════
# المصادر — Scraping
# ══════════════════════════════════════════════════════════════════

SCRAPE_SOURCES = [

    {
        "id": "independent_breaking",
        "name": "Independent عربي",
        "url": (
            "https://www.independentarabia.com/tags/"
            "%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A"
        ),
        "tab": "breaking",
        "base": "https://www.independentarabia.com",
        "exclude": []
    },

    {
        "id": "almal_cbe",
        "name": "المال - مركزي",
        "url": (
            "https://almalnews.com/tag/"
            "%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A/"
        ),
        "tab": "cbe",
        "base": "https://almalnews.com",
        "exclude": []
    },

    {
        "id": "economyplus_breaking",
        "name": "Economy Plus - أخبار",
        "url": (
            "https://economyplusme.com/category/"
            "%d8%a3%d8%ae%d8%a8%d8%a7%d8%b1/"
        ),
        "tab": "breaking",
        "base": "https://economyplusme.com",
        "exclude": []
    },

    # صدى البلد — حريق مصنع
    {
        "id": "elbalad_factory_fire",
        "name": "صدى البلد - حريق مصنع",
        "url": (
            "https://www.elbalad.news/search/term?"
            "search=%D8%AD%D8%B1%D9%8A%D9%82-%D9%85%D8%B5%D9%86%D8%B9"
            "&pageIndex=1"
        ),
        "tab": "breaking",
        "base": "https://www.elbalad.news",
        "exclude": []
    },

    # Google News → بوابة الأهرام → حريق مصنع
    {
        "id": "google_ahram_factory_fire",
        "name": "بوابة الأهرام - حريق مصنع",
        "url": (
            "https://www.google.com/search?"
            "q=%D8%A8%D9%88%D8%A7%D8%A8%D9%87+%D8%A7%D9%84%D8%A7%D9%87%D8%B1%D8%A7%D9%85+"
            "%D8%AD%D8%B1%D9%8A%D9%82+%D9%85%D8%B5%D9%86%D8%B9"
            "&tbm=nws"
        ),
        "tab": "breaking",
        "base": "https://www.google.com",
        "exclude": [],
        "google_news": True,
        "allowed_domains": [
            "gate.ahram.org.eg"
        ]
    },

    # حابي → أهم الأخبار
    {
        "id": "hapi_important_breaking",
        "name": "حابي - أهم الأخبار",
        "url": (
            "https://hapijournal.com/tag/"
            "%d8%a3%d9%87%d9%85-%d8%a7%d9%84%d8%a3%d8%ae%d8%a8%d8%a7%d8%b1/"
        ),
        "tab": "breaking",
        "base": "https://hapijournal.com",
        "exclude": []
    },

    # مباشر بنوك مصر
    {
        "id": "egyptbanks_banks",
        "name": "مباشر بنوك مصر",
        "url": "https://egyptbanks.info/news",
        "tab": "banks",
        "base": "https://egyptbanks.info",
        "exclude": []
    },
]


# ══════════════════════════════════════════════════════════════════
# Labels
# ══════════════════════════════════════════════════════════════════

TAB_LABELS = {
    "breaking":          "⚡ عاجل",
    "banks":             "🏦 أخبار البنوك",
    "credit":            "💰 تمويل وائتمان",
    "warning":           "⚠️ إنذار مبكر",
    "fx":                "💵 أسعار الدولار",
    "cbe":               "🏛️ أخبار المركزي",
    "global":             "🌍 اقتصاد الشرق والعالم",
    "sector_agri":       "🌾 زراعة",
    "sector_industry":   "🏭 صناعة",
    "sector_realestate": "🏗️ عقارات",
    "sector_energy":     "⚡ طاقة",
    "sector_transport":  "🚢 نقل وملاحة",
    "sector_tech":       "💻 تكنولوجيا واتصالات",
}


DIGEST_PRIORITY = [
    "warning",
    "credit",
    "cbe",
    "banks",
    "fx",
    "global",
    "breaking",
    "sector_agri",
    "sector_industry",
    "sector_realestate",
    "sector_energy",
    "sector_transport",
    "sector_tech"
]


# ══════════════════════════════════════════════════════════════════
# Telegram
# ══════════════════════════════════════════════════════════════════

def escape_markdown(text):
    """
    حماية النصوص الديناميكية من أخطاء Telegram Markdown.
    """

    if text is None:
        return ""

    text = str(text)

    return (
        text
        .replace("\\", "\\\\")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("`", "\\`")
    )


def split_telegram_message(text, max_length=MAX_TELEGRAM_MESSAGE):
    """
    تقسيم الرسائل الطويلة حتى لا يرفضها Telegram.
    """

    if not text:
        return []

    text = str(text)

    if len(text) <= max_length:
        return [text]

    chunks = []

    while len(text) > max_length:

        cut = text.rfind(
            "\n",
            0,
            max_length
        )

        if cut < max_length * 0.5:
            cut = max_length

        chunks.append(
            text[:cut]
        )

        text = text[cut:].lstrip()

    if text:
        chunks.append(text)

    return chunks


def send(text):
    """
    إرسال رسالة إلى Telegram.

    إذا فشل Markdown بسبب نص صادر من مصدر خارجي،
    تتم إعادة المحاولة بدون parse_mode بدل فقد الرسالة.
    """

    if not BOT_TOKEN:
        print("    ❌ BOT_TOKEN غير موجود")
        return False

    if not CHANNEL_ID:
        print("    ❌ CHANNEL_ID غير موجود")
        return False

    if not text:
        print("    ❌ محاولة إرسال رسالة فارغة")
        return False

    chunks = split_telegram_message(text)

    all_ok = True

    for index, chunk in enumerate(chunks, start=1):

        payload = {
            "chat_id": CHANNEL_ID,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }

        try:

            r = requests.post(
                f"{API_URL}/sendMessage",
                json=payload,
                timeout=TELEGRAM_TIMEOUT
            )

            if r.status_code == 200:

                if len(chunks) > 1:
                    print(
                        f"    📤 Telegram "
                        f"{index}/{len(chunks)} تم"
                    )
                else:
                    print(
                        "    📤 تم الإرسال إلى Telegram"
                    )

                continue

            print(
                f"    ⚠️ Telegram Markdown HTTP "
                f"{r.status_code}: "
                f"{r.text[:400]}"
            )

            # إعادة محاولة بدون Markdown
            fallback_payload = {
                "chat_id": CHANNEL_ID,
                "text": chunk,
                "disable_web_page_preview": True
            }

            r2 = requests.post(
                f"{API_URL}/sendMessage",
                json=fallback_payload,
                timeout=TELEGRAM_TIMEOUT
            )

            if r2.status_code == 200:

                print(
                    "    📤 تم الإرسال بدون Markdown"
                )

                continue

            print(
                f"    ❌ Telegram fallback HTTP "
                f"{r2.status_code}: "
                f"{r2.text[:400]}"
            )

            all_ok = False

        except requests.RequestException as e:

            print(
                f"    ❌ Telegram connection error: {e}"
            )

            all_ok = False

        except Exception as e:

            print(
                f"    ❌ Telegram send error: {e}"
            )

            all_ok = False

        if index < len(chunks):
            time.sleep(1)

    return all_ok


def telegram_health_check():
    """
    التأكد أن BOT_TOKEN صالح وأن Telegram API يستجيب.

    لا يرسل أي رسالة للمستخدم.
    """

    if not BOT_TOKEN:
        print("❌ Telegram: BOT_TOKEN غير موجود")
        return False

    if not CHANNEL_ID:
        print("❌ Telegram: CHANNEL_ID غير موجود")
        return False

    try:

        r = requests.get(
            f"{API_URL}/getMe",
            timeout=15
        )

        if r.status_code != 200:

            print(
                f"❌ Telegram getMe HTTP "
                f"{r.status_code}: {r.text[:400]}"
            )

            return False

        data = r.json()

        if not data.get("ok"):

            print(
                f"❌ Telegram getMe: "
                f"{str(data)[:400]}"
            )

            return False

        bot = data.get(
            "result",
            {}
        )

        print(
            f"✅ Telegram Bot: "
            f"@{bot.get('username', 'unknown')}"
        )

        # فحص القناة
        r2 = requests.get(
            f"{API_URL}/getChat",
            params={
                "chat_id": CHANNEL_ID
            },
            timeout=15
        )

        if r2.status_code != 200:

            print(
                f"❌ Telegram Channel HTTP "
                f"{r2.status_code}: "
                f"{r2.text[:500]}"
            )

            print(
                "   تأكد أن البوت موجود في القناة "
                "ولديه صلاحية النشر."
            )

            return False

        data2 = r2.json()

        if not data2.get("ok"):

            print(
                f"❌ Telegram Channel error: "
                f"{str(data2)[:500]}"
            )

            return False

        chat = data2.get(
            "result",
            {}
        )

        print(
            f"✅ Telegram Channel: "
            f"{chat.get('title', CHANNEL_ID)}"
        )

        return True

    except Exception as e:

        print(
            f"❌ Telegram health check error: {e}"
        )

        return False


# ══════════════════════════════════════════════════════════════════
# تنسيق الرسائل
# ══════════════════════════════════════════════════════════════════

def format_msg(
    title,
    url,
    source_name,
    tabs
):

    labels = " | ".join(
        TAB_LABELS.get(
            tab,
            tab
        )
        for tab in tabs
    )

    safe_title = escape_markdown(
        title
    )

    safe_source = escape_markdown(
        source_name
    )

    safe_url = escape_markdown(
        url
    )

    return (
        f"{labels}\n\n"
        f"*{safe_title}*\n\n"
        f"📰 المصدر: {safe_source}\n"
        f"🔗 {safe_url}\n\n"
        f"🛡 @egypt\\_risk\\_radar"
    )


# ══════════════════════════════════════════════════════════════════
# Supabase
# ══════════════════════════════════════════════════════════════════

def sb_headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


def supabase_ready():

    return bool(
        SUPABASE_URL
        and SUPABASE_KEY
    )


def supabase_get_hashes():

    if not supabase_ready():

        print(
            "⚠️ Supabase غير مُعد — تم تجاوز تحميل hash"
        )

        return set()

    try:

        since = (
            datetime.now(timezone.utc)
            - timedelta(days=7)
        ).isoformat()

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news",
            params={
                "select": "hash",
                "created_at": f"gte.{since}"
            },
            headers=sb_headers(),
            timeout=15
        )

        if r.status_code == 200:

            return {
                item["hash"]
                for item in r.json()
                if item.get("hash")
            }

        print(
            f"Supabase get_hashes HTTP "
            f"{r.status_code}: "
            f"{r.text[:300]}"
        )

    except Exception as e:

        print(
            f"Supabase get_hashes error: {e}"
        )

    return set()


def supabase_get_recent_news_for_dedupe():

    if not supabase_ready():

        print(
            "⚠️ Supabase غير مُعد — "
            "ذاكرة منع التكرار ستبدأ فارغة"
        )

        return []

    all_items = []
    offset = 0
    page_size = 1000

    try:

        while True:

            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/news",
                params={
                    "select": (
                        "title,url,source_name,created_at"
                    ),
                    "order": "created_at.desc",
                    "limit": page_size,
                    "offset": offset
                },
                headers=sb_headers(),
                timeout=20
            )

            if r.status_code != 200:

                print(
                    f"Supabase recent news HTTP "
                    f"{r.status_code}: "
                    f"{r.text[:300]}"
                )

                break

            data = r.json()

            if not data:
                break

            all_items.extend(data)

            if len(data) < page_size:
                break

            offset += page_size

            if len(all_items) >= 20000:

                print(
                    "⚠️ تم الوصول إلى حد "
                    "20,000 خبر في ذاكرة منع التكرار"
                )

                break

        return all_items

    except Exception as e:

        print(
            f"Supabase recent news error: {e}"
        )

    return []


def supabase_save_news(
    title,
    url,
    source_name,
    tabs,
    h
):

    if not supabase_ready():

        print(
            "    ⚠️ Supabase غير مُعد — "
            "لم يتم حفظ الخبر"
        )

        return False

    try:

        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/news",
            headers={
                **sb_headers(),
                "Prefer": "resolution=ignore-duplicates"
            },
            json={
                "title": title,
                "url": url,
                "source_name": source_name,
                "tabs": tabs,
                "hash": h
            },
            timeout=15
        )

        if r.status_code not in (
            200,
            201,
            204
        ):

            print(
                f"Supabase save HTTP "
                f"{r.status_code}: "
                f"{r.text[:300]}"
            )

            return False

        return True

    except Exception as e:

        print(
            f"Supabase save error: {e}"
        )

        return False


def supabase_get_last_24h():

    if not supabase_ready():
        return []

    try:

        since = (
            datetime.now(timezone.utc)
            - timedelta(hours=24)
        ).isoformat()

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news",
            params={
                "select": "title,tabs",
                "created_at": f"gte.{since}",
                "order": "created_at.asc"
            },
            headers=sb_headers(),
            timeout=15
        )

        if r.status_code == 200:
            return r.json()

        print(
            f"Supabase last24h HTTP "
            f"{r.status_code}: {r.text[:300]}"
        )

    except Exception as e:

        print(
            f"Supabase get_last_24h error: {e}"
        )

    return []


def supabase_get_news_for_pdf():

    if not supabase_ready():
        return []

    try:

        since = (
            datetime.now(timezone.utc)
            - timedelta(hours=24)
        ).isoformat()

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news",
            params={
                "select": (
                    "title,url,source_name,tabs,created_at"
                ),
                "created_at": f"gte.{since}",
                "order": "created_at.asc"
            },
            headers=sb_headers(),
            timeout=20
        )

        if r.status_code == 200:
            return r.json()

        print(
            f"Supabase PDF HTTP "
            f"{r.status_code}: {r.text[:300]}"
        )

    except Exception as e:

        print(
            f"Supabase get_news_for_pdf error: {e}"
        )

    return []


def supabase_save_digest(
    tab_key,
    tab_label,
    content,
    news_count,
    digest_date
):

    if not supabase_ready():
        return False

    try:

        requests.delete(
            f"{SUPABASE_URL}/rest/v1/digest",
            params={
                "tab_key": f"eq.{tab_key}",
                "digest_date": f"eq.{digest_date}"
            },
            headers=sb_headers(),
            timeout=10
        )

        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/digest",
            headers=sb_headers(),
            json={
                "tab_key": tab_key,
                "tab_label": tab_label,
                "content": content,
                "news_count": news_count,
                "digest_date": digest_date
            },
            timeout=10
        )

        return r.status_code in (
            200,
            201,
            204
        )

    except Exception as e:

        print(
            f"Supabase save_digest error: {e}"
        )

        return False


# ══════════════════════════════════════════════════════════════════
# تنظيف ومقارنة الأخبار
# ══════════════════════════════════════════════════════════════════

def normalize_arabic_text(text):

    if not text:
        return ""

    text = str(text).lower().strip()

    text = re.sub(
        r"[\u064B-\u065F\u0670]",
        "",
        text
    )

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new
        )

    text = re.sub(
        r"[^\w\u0600-\u06FF]+",
        " ",
        text,
        flags=re.UNICODE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


def title_tokens(text):

    normalized = normalize_arabic_text(
        text
    )

    stop_words = {
        "مصر",
        "اليوم",
        "غدا",
        "المصري",
        "المصرية",
        "في",
        "من",
        "على",
        "عن",
        "بعد",
        "قبل",
        "مع",
        "الى",
        "إلى",
        "هذا",
        "هذه",
        "التي",
        "الذي",
        "و",
        "ب",
        "ل",
        "ا",
    }

    return {
        word
        for word in normalized.split()
        if len(word) >= 2
        and word not in stop_words
    }


def is_update_title(title):

    normalized = normalize_arabic_text(
        title
    )

    return any(
        normalize_arabic_text(k)
        in normalized
        for k in UPDATE_KW
    )


def titles_are_probable_duplicate(
    title1,
    title2
):

    n1 = normalize_arabic_text(
        title1
    )

    n2 = normalize_arabic_text(
        title2
    )

    if not n1 or not n2:
        return False

    if n1 == n2:
        return True

    ratio = difflib.SequenceMatcher(
        None,
        n1,
        n2
    ).ratio()

    if ratio >= 0.88:
        return True

    t1 = title_tokens(title1)
    t2 = title_tokens(title2)

    if not t1 or not t2:
        return False

    common = t1 & t2

    smaller = min(
        len(t1),
        len(t2)
    )

    overlap = (
        len(common) / smaller
    )

    return (
        overlap >= 0.80
        and ratio >= 0.58
    )


def is_excluded_title(
    title,
    extra_exclude=None
):

    text = normalize_arabic_text(
        title
    )

    keywords = list(
        EXCLUDE_KW
    )

    if extra_exclude:
        keywords.extend(
            extra_exclude
        )

    for kw in keywords:

        if normalize_arabic_text(
            kw
        ) in text:

            return True

    return False


def is_recent_datetime(
    dt,
    max_age_hours=24
):

    if not dt:
        return False

    now = datetime.now(
        timezone.utc
    )

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=timezone.utc
        )

    age = now - dt

    if age < timedelta(
        minutes=-10
    ):

        return False

    return age <= timedelta(
        hours=max_age_hours
    )


def parse_any_datetime(value):

    if not value:
        return None

    if isinstance(
        value,
        datetime
    ):

        dt = value

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    value = str(
        value
    ).strip()

    try:

        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:
        pass

    try:

        from email.utils import (
            parsedate_to_datetime
        )

        dt = parsedate_to_datetime(
            value
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:
        pass

    formats = [
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    for fmt in formats:

        try:

            dt = datetime.strptime(
                value,
                fmt
            )

            return dt.replace(
                tzinfo=timezone.utc
            )

        except Exception:
            continue

    return None


# ══════════════════════════════════════════════════════════════════
# تاريخ المقال
# ══════════════════════════════════════════════════════════════════

def extract_article_date(url):

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        if r.status_code != 200:
            return None

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        # JSON-LD
        for script in soup.find_all(
            "script",
            type="application/ld+json"
        ):

            try:

                raw = script.get_text(
                    strip=True
                )

                if not raw:
                    continue

                data = json.loads(
                    raw
                )

                objects = []

                if isinstance(
                    data,
                    dict
                ):

                    objects.append(
                        data
                    )

                    if isinstance(
                        data.get("@graph"),
                        list
                    ):

                        objects.extend(
                            data["@graph"]
                        )

                elif isinstance(
                    data,
                    list
                ):

                    objects.extend(
                        data
                    )

                for obj in objects:

                    if not isinstance(
                        obj,
                        dict
                    ):
                        continue

                    published = (
                        obj.get("datePublished")
                        or obj.get("datepublished")
                    )

                    dt = parse_any_datetime(
                        published
                    )

                    if dt:
                        return dt

            except Exception:
                continue

        meta_names = [
            ("property", "article:published_time"),
            ("name", "article:published_time"),
            ("property", "date"),
            ("name", "date"),
            ("property", "publishdate"),
            ("name", "publishdate"),
            ("property", "published_time"),
            ("name", "published_time"),
        ]

        for attr, value in meta_names:

            tag = soup.find(
                "meta",
                attrs={
                    attr: value
                }
            )

            if (
                tag
                and tag.get("content")
            ):

                dt = parse_any_datetime(
                    tag.get("content")
                )

                if dt:
                    return dt

        # time
        for tag in soup.find_all(
            "time"
        ):

            value = (
                tag.get("datetime")
                or tag.get("content")
                or tag.get_text(
                    " ",
                    strip=True
                )
            )

            dt = parse_any_datetime(
                value
            )

            if dt:
                return dt

        # dateModified fallback
        for script in soup.find_all(
            "script",
            type="application/ld+json"
        ):

            try:

                raw = script.get_text(
                    strip=True
                )

                if not raw:
                    continue

                data = json.loads(
                    raw
                )

                objects = []

                if isinstance(
                    data,
                    dict
                ):

                    objects.append(
                        data
                    )

                    if isinstance(
                        data.get("@graph"),
                        list
                    ):

                        objects.extend(
                            data["@graph"]
                        )

                elif isinstance(
                    data,
                    list
                ):

                    objects.extend(
                        data
                    )

                for obj in objects:

                    if not isinstance(
                        obj,
                        dict
                    ):
                        continue

                    modified = obj.get(
                        "dateModified"
                    )

                    dt = parse_any_datetime(
                        modified
                    )

                    if dt:
                        return dt

            except Exception:
                continue

    except Exception as e:

        print(
            f"      ⚠️ Date extraction error "
            f"{url[:80]}: {e}"
        )

    return None


# ══════════════════════════════════════════════════════════════════
# أدوات مساعدة
# ══════════════════════════════════════════════════════════════════

def is_arabic(text):

    if not text:
        return False

    count = sum(
        1
        for c in str(text)
        if "\u0600" <= c <= "\u06ff"
    )

    return (
        count / max(
            len(str(text)),
            1
        )
        > 0.3
    )


# ══════════════════════════════════════════════════════════════════
# التصنيف حسب المصدر فقط
# ══════════════════════════════════════════════════════════════════

def get_tabs(
    title,
    summary,
    primary_tab
):

    if primary_tab:
        return [primary_tab]

    return ["breaking"]


# ══════════════════════════════════════════════════════════════════
# Hash
# ══════════════════════════════════════════════════════════════════

def make_hash(title):

    normalized = normalize_arabic_text(
        title
    )

    return hashlib.md5(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


# ══════════════════════════════════════════════════════════════════
# الرابط القياسي
# ══════════════════════════════════════════════════════════════════

def canonical_url(url):

    if not url:
        return ""

    url = str(url).strip()

    parsed = urlparse(
        url
    )

    clean = parsed._replace(
        fragment=""
    ).geturl()

    parsed = urlparse(
        clean
    )

    query = parse_qs(
        parsed.query,
        keep_blank_values=True
    )

    tracking_prefixes = (
        "utm_",
        "fbclid",
        "gclid",
        "ved",
        "ei",
    )

    filtered = {}

    for key, values in query.items():

        if any(
            key.lower().startswith(
                prefix
            )
            for prefix in tracking_prefixes
        ):
            continue

        filtered[key] = values

    query_parts = []

    for key in sorted(
        filtered
    ):

        for value in filtered[key]:

            query_parts.append(
                f"{key}={value}"
            )

    query_string = "&".join(
        query_parts
    )

    result = parsed._replace(
        query=query_string,
        fragment=""
    ).geturl()

    return result.rstrip("/")


# ══════════════════════════════════════════════════════════════════
# مصدر الخبر الحقيقي
# ══════════════════════════════════════════════════════════════════

def source_domain(url):

    if not url:
        return ""

    try:

        host = (
            urlparse(url)
            .netloc
            .lower()
            .split("@")[-1]
            .split(":")[0]
        )

        if host.startswith("www."):
            host = host[4:]

        return host

    except Exception:
        return ""


def source_identity(
    source_name,
    article_url
):

    domain = source_domain(
        article_url
    )

    if domain:
        return domain

    return normalize_arabic_text(
        source_name
    )


# ══════════════════════════════════════════════════════════════════
# منع التكرار — نفس المصدر فقط
# ══════════════════════════════════════════════════════════════════

def is_duplicate_against_recent(
    title,
    url,
    source_name,
    recent_news
):

    current_url = canonical_url(
        url
    )

    current_norm = normalize_arabic_text(
        title
    )

    current_source = source_identity(
        source_name,
        current_url
    )

    for item in recent_news:

        old_title = item.get(
            "title",
            ""
        )

        old_url = canonical_url(
            item.get(
                "url",
                ""
            )
        )

        old_source_name = item.get(
            "source_name",
            ""
        )

        old_source = source_identity(
            old_source_name,
            old_url
        )

        # مصادر مختلفة = مسموح
        if (
            current_source
            and old_source
            and current_source != old_source
        ):
            continue

        if not current_source or not old_source:

            if normalize_arabic_text(
                source_name
            ) != normalize_arabic_text(
                old_source_name
            ):
                continue

        # نفس الرابط
        if (
            current_url
            and old_url
            and current_url == old_url
        ):

            return True, "نفس الرابط من نفس المصدر"

        # نفس العنوان
        old_norm = normalize_arabic_text(
            old_title
        )

        if (
            current_norm
            and old_norm
            and current_norm == old_norm
        ):

            return True, "نفس العنوان من نفس المصدر"

        # تشابه قوي
        if titles_are_probable_duplicate(
            title,
            old_title
        ):

            return True, "عنوان مشابه جدًا من نفس المصدر"

    return False, ""


# ══════════════════════════════════════════════════════════════════
# معالجة الخبر
# ══════════════════════════════════════════════════════════════════

def process_item(
    title,
    url,
    source_name,
    primary_tab,
    summary,
    exclude,
    sent_hashes,
    recent_news,
    published_at=None
):

    if not title or not url:

        return (
            False,
            sent_hashes,
            recent_news
        )

    title = str(title).strip()

    url = canonical_url(
        url
    )

    if not is_arabic(
        title
    ):

        return (
            False,
            sent_hashes,
            recent_news
        )

    if is_excluded_title(
        title,
        exclude
    ):

        print(
            f"    ⛔ مستبعد: "
            f"{title[:80]}"
        )

        return (
            False,
            sent_hashes,
            recent_news
        )

    if published_at is not None:

        if not is_recent_datetime(
            published_at,
            max_age_hours=24
        ):

            print(
                f"    ⏳ خبر قديم: "
                f"{title[:70]}"
            )

            return (
                False,
                sent_hashes,
                recent_news
            )

    duplicate, reason = (
        is_duplicate_against_recent(
            title,
            url,
            source_name,
            recent_news
        )
    )

    if duplicate:

        print(
            f"    ♻️ مكرر "
            f"({reason}): "
            f"{title[:70]}"
        )

        return (
            False,
            sent_hashes,
            recent_news
        )

    tabs = get_tabs(
        title,
        summary,
        primary_tab
    )

    if not tabs:

        return (
            False,
            sent_hashes,
            recent_news
        )

    msg = format_msg(
        title,
        url,
        source_name,
        tabs
    )

    if send(msg):

        h = make_hash(
            title
        )

        saved = supabase_save_news(
            title,
            url,
            source_name,
            tabs,
            h
        )

        if not saved:

            print(
                "    ⚠️ تم إرسال الخبر إلى Telegram "
                "لكن فشل حفظه في Supabase"
            )

        recent_news.insert(
            0,
            {
                "title": title,
                "url": url,
                "source_name": source_name,
                "created_at": datetime.now(
                    timezone.utc
                ).isoformat()
            }
        )

        sent_hashes.add(
            h
        )

        print(
            f"    ✅ {title[:80]}"
        )

        time.sleep(2)

        return (
            True,
            sent_hashes,
            recent_news
        )

    print(
        f"    ❌ فشل إرسال: "
        f"{title[:60]}"
    )

    return (
        False,
        sent_hashes,
        recent_news
    )


# ══════════════════════════════════════════════════════════════════
# RSS
# ══════════════════════════════════════════════════════════════════

def get_feed_entry_date(entry):

    for field in (
        "published_parsed",
        "updated_parsed"
    ):

        value = entry.get(
            field
        )

        if value:

            try:

                from calendar import timegm

                timestamp = timegm(
                    value
                )

                return datetime.fromtimestamp(
                    timestamp,
                    timezone.utc
                )

            except Exception:
                pass

    for field in (
        "published",
        "updated",
        "created"
    ):

        value = entry.get(
            field
        )

        dt = parse_any_datetime(
            value
        )

        if dt:
            return dt

    return None


def fetch_rss(
    src,
    sent_hashes,
    recent_news
):

    count = 0

    try:

        response = requests.get(
            src["url"],
            headers=HEADERS,
            timeout=HTTP_TIMEOUT
        )

        if response.status_code != 200:

            print(
                f"    ⚠️ RSS HTTP "
                f"{response.status_code}: "
                f"{src['name']}"
            )

            return (
                0,
                sent_hashes,
                recent_news
            )

        feed = feedparser.parse(
            response.content
        )

        if getattr(
            feed,
            "bozo",
            False
        ):

            print(
                f"    ⚠️ RSS warning: "
                f"{src['name']}"
            )

        entries = getattr(
            feed,
            "entries",
            []
        )

        print(
            f"    📥 {len(entries)} خبر في RSS"
        )

        for entry in entries[:100]:

            published_at = (
                get_feed_entry_date(
                    entry
                )
            )

            ok, sent_hashes, recent_news = (
                process_item(
                    entry.get(
                        "title",
                        ""
                    ).strip(),
                    entry.get(
                        "link",
                        ""
                    ),
                    src["name"],
                    src["tab"],
                    entry.get(
                        "summary",
                        ""
                    )[:400],
                    src.get(
                        "exclude",
                        []
                    ),
                    sent_hashes,
                    recent_news,
                    published_at
                )
            )

            if ok:
                count += 1

    except requests.RequestException as e:

        print(
            f"    ⚠️ RSS connection error "
            f"{src['name']}: {e}"
        )

    except Exception as e:

        print(
            f"    ⚠️ RSS error "
            f"{src['name']}: {e}"
        )

    return (
        count,
        sent_hashes,
        recent_news
    )


# ══════════════════════════════════════════════════════════════════
# Scraping
# ══════════════════════════════════════════════════════════════════

def absolute_url(
    base,
    href
):

    if not href:
        return ""

    href = href.strip()

    if href.startswith(
        "//"
    ):

        return "https:" + href

    return urljoin(
        base,
        href
    )


def extract_listing_items(
    soup,
    base,
    limit=50
):

    items = []

    seen_urls = set()

    for article in soup.find_all(
        "article"
    ):

        heading = article.find(
            [
                "h1",
                "h2",
                "h3",
                "h4"
            ]
        )

        if not heading:
            continue

        anchor = (
            heading.find(
                "a",
                href=True
            )
            or article.find(
                "a",
                href=True
            )
        )

        if not anchor:
            continue

        title = heading.get_text(
            " ",
            strip=True
        )

        link = absolute_url(
            base,
            anchor.get(
                "href"
            )
        )

        if (
            len(title) < 15
            or not link
        ):
            continue

        link = canonical_url(
            link
        )

        if link in seen_urls:
            continue

        seen_urls.add(
            link
        )

        items.append(
            (
                title,
                link
            )
        )

        if len(items) >= limit:
            break

    if len(items) < limit:

        for heading in soup.find_all(
            [
                "h1",
                "h2",
                "h3",
                "h4"
            ]
        ):

            anchor = heading.find(
                "a",
                href=True
            )

            if not anchor:
                continue

            title = heading.get_text(
                " ",
                strip=True
            )

            link = absolute_url(
                base,
                anchor.get(
                    "href"
                )
            )

            if (
                len(title) < 15
                or not link
            ):
                continue

            link = canonical_url(
                link
            )

            if link in seen_urls:
                continue

            seen_urls.add(
                link
            )

            items.append(
                (
                    title,
                    link
                )
            )

            if len(items) >= limit:
                break

    return items


# ══════════════════════════════════════════════════════════════════
# Google News
# ══════════════════════════════════════════════════════════════════

def google_news_real_url(
    href
):

    if not href:
        return ""

    href = unquote(
        href
    )

    parsed = urlparse(
        href
    )

    if parsed.path == "/url":

        qs = parse_qs(
            parsed.query
        )

        for key in (
            "q",
            "url"
        ):

            if qs.get(
                key
            ):

                return qs[key][0]

    return href


def is_allowed_domain(
    url,
    allowed_domains
):

    try:

        host = (
            urlparse(
                url
            )
            .netloc
            .lower()
        )

        host = host.split(
            "@"
        )[-1]

        return any(
            host == domain
            or host.endswith(
                "." + domain
            )
            for domain in allowed_domains
        )

    except Exception:
        return False


def extract_google_news_items(
    soup,
    allowed_domains,
    limit=30
):

    items = []

    seen = set()

    for heading in soup.find_all(
        "h3"
    ):

        title = heading.get_text(
            " ",
            strip=True
        )

        anchor = heading.find_parent(
            "a",
            href=True
        )

        if not anchor:

            anchor = heading.find(
                "a",
                href=True
            )

        if not anchor:
            continue

        href = google_news_real_url(
            anchor.get(
                "href"
            )
        )

        if not href:
            continue

        if not is_allowed_domain(
            href,
            allowed_domains
        ):
            continue

        href = canonical_url(
            href
        )

        if href in seen:
            continue

        seen.add(
            href
        )

        if len(title) < 15:
            continue

        items.append(
            (
                title,
                href
            )
        )

        if len(items) >= limit:
            break

    if len(items) < limit:

        for anchor in soup.find_all(
            "a",
            href=True
        ):

            href = google_news_real_url(
                anchor.get(
                    "href"
                )
            )

            if not is_allowed_domain(
                href,
                allowed_domains
            ):
                continue

            text = anchor.get_text(
                " ",
                strip=True
            )

            if len(text) < 15:
                continue

            href = canonical_url(
                href
            )

            if href in seen:
                continue

            seen.add(
                href
            )

            items.append(
                (
                    text,
                    href
                )
            )

            if len(items) >= limit:
                break

    return items


def fetch_scrape(
    src,
    sent_hashes,
    recent_news
):

    count = 0

    try:

        r = requests.get(
            src["url"],
            headers=HEADERS,
            timeout=HTTP_TIMEOUT
        )

        if r.status_code != 200:

            print(
                f"    ⚠️ HTTP "
                f"{r.status_code}: "
                f"{src['name']}"
            )

            return (
                0,
                sent_hashes,
                recent_news
            )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        if src.get(
            "google_news"
        ):

            items = (
                extract_google_news_items(
                    soup,
                    src.get(
                        "allowed_domains",
                        []
                    ),
                    limit=30
                )
            )

        else:

            items = (
                extract_listing_items(
                    soup,
                    src["base"],
                    limit=50
                )
            )

        print(
            f"    🔎 تم العثور على "
            f"{len(items)} نتيجة في "
            f"{src['name']}"
        )

        for title, link in items:

            published_at = (
                extract_article_date(
                    link
                )
            )

            if published_at is None:

                print(
                    f"    ⚠️ لا يوجد تاريخ موثوق: "
                    f"{title[:70]}"
                )

                continue

            ok, sent_hashes, recent_news = (
                process_item(
                    title,
                    link,
                    src["name"],
                    src["tab"],
                    "",
                    src.get(
                        "exclude",
                        []
                    ),
                    sent_hashes,
                    recent_news,
                    published_at
                )
            )

            if ok:
                count += 1

    except requests.RequestException as e:

        print(
            f"    ⚠️ Scrape connection error "
            f"{src['name']}: {e}"
        )

    except Exception as e:

        print(
            f"    ⚠️ Scrape error "
            f"{src['name']}: {e}"
        )

    return (
        count,
        sent_hashes,
        recent_news
    )


# ══════════════════════════════════════════════════════════════════
# PDF
# ══════════════════════════════════════════════════════════════════

def download_font():

    if os.path.exists(
        FONT_PATH
    ):
        return True

    print(
        "⬇️ جاري تحميل الخط العربي..."
    )

    try:

        r = requests.get(
            FONT_URL,
            timeout=30
        )

        if r.status_code != 200:

            print(
                f"❌ فشل تحميل الخط: "
                f"HTTP {r.status_code}"
            )

            return False

        with open(
            FONT_PATH,
            "wb"
        ) as f:

            f.write(
                r.content
            )

        print(
            "✅ تم تحميل الخط"
        )

        return True

    except Exception as e:

        print(
            f"❌ Font download error: {e}"
        )

        return False


def ar(text):

    try:

        import arabic_reshaper

        from bidi.algorithm import (
            get_display
        )

        return get_display(
            arabic_reshaper.reshape(
                str(text)
            )
        )

    except Exception:

        return str(text)


def generate_daily_pdf(
    news_list,
    now_egypt
):

    from fpdf import FPDF

    if not download_font():
        raise RuntimeError(
            "تعذر تحميل خط Amiri"
        )

    date_str = now_egypt.strftime(
        "%d/%m/%Y"
    )

    grouped = {}

    for item in news_list:

        for tab in item.get(
            "tabs",
            []
        ):

            grouped.setdefault(
                tab,
                []
            ).append(
                item
            )

    ordered_tabs = sorted(
        grouped.keys(),
        key=lambda x:
            DIGEST_PRIORITY.index(x)
            if x in DIGEST_PRIORITY
            else 99
    )

    pdf = FPDF()

    pdf.set_auto_page_break(
        auto=True,
        margin=15
    )

    pdf.add_font(
        "Amiri",
        "",
        FONT_PATH,
        uni=True
    )

    pdf.add_page()

    pdf.set_fill_color(
        26,
        60,
        94
    )

    pdf.rect(
        0,
        0,
        210,
        30,
        "F"
    )

    pdf.set_font(
        "Amiri",
        size=18
    )

    pdf.set_text_color(
        255,
        255,
        255
    )

    pdf.set_y(
        6
    )

    pdf.cell(
        0,
        9,
        ar(
            "رادار المخاطر — تقرير الأخبار اليومي"
        ),
        ln=True,
        align="C"
    )

    pdf.set_font(
        "Amiri",
        size=11
    )

    pdf.cell(
        0,
        8,
        ar(
            f"{date_str}  |  إجمالي: "
            f"{len(news_list)} خبر في "
            f"{len(grouped)} تبويبات"
        ),
        ln=True,
        align="C"
    )

    pdf.ln(
        8
    )

    for tab in ordered_tabs:

        items = grouped[
            tab
        ]

        tab_label = TAB_LABELS.get(
            tab,
            tab
        )

        pdf.set_fill_color(
            26,
            60,
            94
        )

        pdf.set_text_color(
            255,
            255,
            255
        )

        pdf.set_font(
            "Amiri",
            size=13
        )

        pdf.cell(
            0,
            10,
            ar(
                f"{tab_label} "
                f"({len(items)} خبر)"
            ),
            ln=True,
            align="R",
            fill=True
        )

        pdf.ln(
            1
        )

        for i, item in enumerate(
            items
        ):

            title = item.get(
                "title",
                ""
            )

            url = item.get(
                "url",
                ""
            )

            source = item.get(
                "source_name",
                ""
            )

            created_at = item.get(
                "created_at",
                ""
            )

            try:

                dt = datetime.fromisoformat(
                    created_at.replace(
                        "Z",
                        "+00:00"
                    )
                )

                dt = (
                    dt
                    + timedelta(
                        hours=2
                    )
                )

                time_str = dt.strftime(
                    "%H:%M"
                )

            except Exception:

                time_str = ""

            if i % 2 == 0:

                pdf.set_fill_color(
                    245,
                    249,
                    252
                )

            else:

                pdf.set_fill_color(
                    255,
                    255,
                    255
                )

            pdf.set_font(
                "Amiri",
                size=10
            )

            pdf.set_text_color(
                26,
                60,
                94
            )

            title_display = ar(
                title
            )

            pdf.multi_cell(
                0,
                7,
                f"  {title_display}",
                align="R",
                fill=True,
                link=url if url else ""
            )

            pdf.set_font(
                "Amiri",
                size=9
            )

            pdf.set_text_color(
                130,
                130,
                130
            )

            pdf.cell(
                0,
                6,
                f"  {ar(source)} | "
                f"{time_str}",
                ln=True,
                align="R"
            )

            pdf.ln(
                1
            )

        pdf.ln(
            5
        )

    pdf.set_y(
        -15
    )

    pdf.set_font(
        "Amiri",
        size=8
    )

    pdf.set_text_color(
        170,
        170,
        170
    )

    pdf.cell(
        0,
        8,
        ar(
            f"رادار المخاطر — "
            f"@egypt_risk_radar — "
            f"{date_str}"
        ),
        align="C"
    )

    return bytes(
        pdf.output()
    )


def send_pdf_to_telegram(
    pdf_bytes,
    date_str
):

    if not BOT_TOKEN:
        print(
            "❌ PDF: BOT_TOKEN غير موجود"
        )
        return False

    try:

        filename = (
            f"رادار_المخاطر_"
            f"{date_str.replace('/', '-')}.pdf"
        )

        caption = (
            f"📋 *تقرير أخبار اليوم — "
            f"{date_str}*\n"
            f"_جميع أخبار الـ 24 ساعة الماضية "
            f"مصنفة بالتبويبات_\n\n"
            f"🛡 @egypt\\_risk\\_radar"
        )

        files = {
            "document": (
                filename,
                io.BytesIO(
                    pdf_bytes
                ),
                "application/pdf"
            )
        }

        data = {
            "chat_id": CHANNEL_ID,
            "caption": caption,
            "parse_mode": "Markdown"
        }

        r = requests.post(
            f"{API_URL}/sendDocument",
            files=files,
            data=data,
            timeout=60
        )

        if r.status_code == 200:
            return True

        print(
            f"❌ PDF Telegram HTTP "
            f"{r.status_code}: "
            f"{r.text[:500]}"
        )

        return False

    except Exception as e:

        print(
            f"Send PDF error: {e}"
        )

        return False


def run_pdf_report():

    print(
        "📋 جاري إعداد التقرير اليومي PDF..."
    )

    news = (
        supabase_get_news_for_pdf()
    )

    if not news:

        print(
            "لا توجد أخبار في "
            "الـ 24 ساعة الماضية"
        )

        return

    now_egypt = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            hours=2
        )
    )

    date_str = now_egypt.strftime(
        "%d/%m/%Y"
    )

    print(
        f"  {len(news)} خبر — "
        f"جاري توليد PDF..."
    )

    try:

        pdf_bytes = generate_daily_pdf(
            news,
            now_egypt
        )

    except Exception as e:

        print(
            f"❌ PDF generation error: {e}"
        )

        return

    if send_pdf_to_telegram(
        pdf_bytes,
        date_str
    ):

        print(
            f"✅ تم إرسال PDF "
            f"({len(news)} خبر)"
        )

    else:

        print(
            "❌ فشل إرسال PDF"
        )


# ══════════════════════════════════════════════════════════════════
# Gemini
# ══════════════════════════════════════════════════════════════════

def ask_gemini(prompt):

    if not GEMINI_KEY:
        print(
            "❌ GEMINI_API_KEY غير موجود"
        )
        return None

    try:

        r = requests.post(
            GEMINI_URL,
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            },
            timeout=60
        )

        if r.status_code != 200:

            print(
                f"Gemini HTTP "
                f"{r.status_code}: "
                f"{r.text[:500]}"
            )

            return None

        data = r.json()

        candidates = data.get(
            "candidates",
            []
        )

        if not candidates:
            return None

        content = candidates[0].get(
            "content",
            {}
        )

        parts = content.get(
            "parts",
            []
        )

        if not parts:
            return None

        text = parts[0].get(
            "text"
        )

        return text.strip() if text else None

    except requests.RequestException as e:

        print(
            f"Gemini connection error: {e}"
        )

        return None

    except Exception as e:

        print(
            f"Gemini error: {e}"
        )

        return None


def group_by_tab(
    news_list
):

    grouped = {}

    for item in news_list:

        for tab in item.get(
            "tabs",
            []
        ):

            grouped.setdefault(
                tab,
                []
            ).append(
                item.get(
                    "title",
                    ""
                )
            )

    return grouped


def build_prompt(
    tab_label,
    headlines
):

    headlines_text = "\n".join(
        f"- {h}"
        for h in headlines
    )

    return (
        f"أنت محلل أول في قسم "
        f"المخاطر والائتمان في أحد "
        f"البنوك المصرية الكبرى.\n"
        f'لديك عناوين أخبار تبويب '
        f'"{tab_label}" خلال الـ 24 ساعة الماضية:\n\n'
        f"{headlines_text}\n\n"
        f"المطلوب:\n"
        f"1. عناوين الأخبار الأبرز في نقاط مختصرة\n"
        f"2. تحليل: ما الذي يستوجب الانتباه "
        f"من منظور مخاطر وائتمان؟\n"
        f"3. تعليق مهني واحد للعاملين في القطاع\n\n"
        f"اكتب بأسلوب احترافي وموجز "
        f"باللغة العربية، بدون مقدمات أو تحيات."
    )


def run_daily_digest():

    print(
        "📊 جاري إعداد الموجز اليومي..."
    )

    news = (
        supabase_get_last_24h()
    )

    if not news:

        print(
            "لا توجد أخبار في "
            "الـ 24 ساعة الماضية"
        )

        return

    grouped = group_by_tab(
        news
    )

    now = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            hours=2
        )
    )

    date_str = now.strftime(
        "%d/%m/%Y"
    )

    send(
        f"🗞️ *موجز أنباء وتحليلات — "
        f"{date_str}*\n"
        f"_تقرير يومي لمتخصصي "
        f"الائتمان والمخاطر_\n\n"
        f"رصدنا اليوم *{len(news)} "
        f"خبراً* في *{len(grouped)} قطاعات*\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🛡 @egypt\\_risk\\_radar"
    )

    time.sleep(
        3
    )

    ordered_tabs = sorted(
        grouped.keys(),
        key=lambda x:
            DIGEST_PRIORITY.index(x)
            if x in DIGEST_PRIORITY
            else 99
    )

    for tab in ordered_tabs:

        headlines = grouped[
            tab
        ]

        if not headlines:
            continue

        tab_label = TAB_LABELS.get(
            tab,
            tab
        )

        print(
            f"  🤖 Gemini: "
            f"{tab_label} "
            f"({len(headlines)} خبر)..."
        )

        analysis = ask_gemini(
            build_prompt(
                tab_label,
                headlines
            )
        )

        if not analysis:
            continue

        analysis = analysis.replace(
            "**",
            "*"
        )

        msg = (
            f"{'━' * 16}\n"
            f"*{tab_label}*  \\| "
            f"{len(headlines)} خبر\n"
            f"{'━' * 16}\n\n"
            f"{analysis}\n\n"
            f"🛡 @egypt\\_risk\\_radar"
        )

        send(
            msg
        )

        supabase_save_digest(
            tab,
            tab_label,
            analysis,
            len(headlines),
            now.strftime(
                "%Y-%m-%d"
            )
        )

        time.sleep(
            5
        )

    send(
        f"✅ *انتهى موجز {date_str}*\n\n"
        f"تابع أخبار السوق لحظة بلحظة\n"
        f"🛡 @egypt\\_risk\\_radar"
    )

    print(
        "✅ انتهى الموجز اليومي"
    )


# ══════════════════════════════════════════════════════════════════
# فحص الإعدادات
# ══════════════════════════════════════════════════════════════════

def configuration_check():

    print(
        "\n🔐 فحص إعدادات التشغيل..."
    )

    print(
        f"   BOT_TOKEN: "
        f"{'OK' if BOT_TOKEN else 'MISSING'}"
    )

    print(
        f"   GEMINI_API_KEY: "
        f"{'OK' if GEMINI_KEY else 'MISSING'}"
    )

    print(
        f"   SUPABASE_URL: "
        f"{'OK' if SUPABASE_URL else 'MISSING'}"
    )

    print(
        f"   SUPABASE_KEY: "
        f"{'OK' if SUPABASE_KEY else 'MISSING'}"
    )

    print(
        f"   CHANNEL_ID: "
        f"{CHANNEL_ID}"
    )

    if not BOT_TOKEN:
        print(
            "❌ لا يمكن تشغيل البوت بدون BOT_TOKEN"
        )
        return False

    if not SUPABASE_URL:
        print(
            "⚠️ SUPABASE_URL غير موجود"
        )

    if not SUPABASE_KEY:
        print(
            "⚠️ SUPABASE_KEY غير موجود"
        )

    if not GEMINI_KEY:
        print(
            "⚠️ GEMINI_API_KEY غير موجود "
            "— وضع الأخبار سيعمل، "
            "لكن Digest لن يستطيع استخدام Gemini."
        )

    return True


# ══════════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ══════════════════════════════════════════════════════════════════

def run():

    print(
        "\n"
        "══════════════════════════════════════════\n"
        "🛡 رادار المخاطر المصري\n"
        "══════════════════════════════════════════"
    )

    mode = os.environ.get(
        "RUN_MODE",
        "news"
    ).strip().lower()

    print(
        f"⚙️ RUN_MODE = {mode}"
    )

    if not configuration_check():
        return

    # --------------------------------------------------------------
    # Digest / PDF
    # --------------------------------------------------------------

    if mode == "digest":

        print(
            "📊 وضع الموجز اليومي"
        )

        if not telegram_health_check():
            print(
                "❌ تم إيقاف Digest بسبب مشكلة Telegram"
            )
            return

        run_daily_digest()

        return

    if mode == "pdf":

        print(
            "📋 وضع PDF"
        )

        if not telegram_health_check():
            print(
                "❌ تم إيقاف PDF بسبب مشكلة Telegram"
            )
            return

        run_pdf_report()

        return

    # --------------------------------------------------------------
    # News
    # --------------------------------------------------------------

    print(
        "🛡 وضع الأخبار — يعمل..."
    )

    # --------------------------------------------------------------
    # Telegram health check
    # --------------------------------------------------------------

    if not telegram_health_check():

        print(
            "\n"
            "❌ فشل فحص Telegram.\n"
            "لن يبدأ جلب الأخبار حتى لا يتم تشغيل "
            "الدورة بالكامل بدون إمكانية نشرها."
        )

        return

    print(
        "\n📦 جاري تحميل الأخبار "
        "المرسلة من Supabase..."
    )

    # --------------------------------------------------------------
    # Supabase memory
    # --------------------------------------------------------------

    sent_hashes = (
        supabase_get_hashes()
    )

    recent_news = (
        supabase_get_recent_news_for_dedupe()
    )

    print(
        f"   {len(sent_hashes)} hash محفوظ مسبقاً"
    )

    print(
        f"   {len(recent_news)} خبر في "
        f"ذاكرة منع التكرار"
    )

    new_count = 0

    # --------------------------------------------------------------
    # RSS
    # --------------------------------------------------------------

    print(
        "\n"
        "════════ RSS SOURCES ════════"
    )

    for src in RSS_SOURCES:

        print(
            f"\n  📡 RSS: "
            f"{src['name']}..."
        )

        try:

            count, sent_hashes, recent_news = (
                fetch_rss(
                    src,
                    sent_hashes,
                    recent_news
                )
            )

            new_count += count

            print(
                f"     → تم نشر {count} خبر"
            )

        except Exception as e:

            print(
                f"     ❌ خطأ غير متوقع في "
                f"{src['name']}: {e}"
            )

    # --------------------------------------------------------------
    # Scraping
    # --------------------------------------------------------------

    print(
        "\n"
        "════════ SCRAPING SOURCES ════════"
    )

    for src in SCRAPE_SOURCES:

        print(
            f"\n  🕷️ Scraping: "
            f"{src['name']}..."
        )

        try:

            count, sent_hashes, recent_news = (
                fetch_scrape(
                    src,
                    sent_hashes,
                    recent_news
                )
            )

            new_count += count

            print(
                f"     → تم نشر {count} خبر"
            )

        except Exception as e:

            print(
                f"     ❌ خطأ غير متوقع في "
                f"{src['name']}: {e}"
            )

    # --------------------------------------------------------------
    # Final
    # --------------------------------------------------------------

    print(
        "\n"
        "══════════════════════════════════════════"
    )

    print(
        f"✅ تم نشر {new_count} خبر جديد"
    )

    print(
        "🛡 انتهى تشغيل رادار المخاطر"
    )

    print(
        "══════════════════════════════════════════\n"
    )


if __name__ == "__main__":
    try:

        run()

    except KeyboardInterrupt:

        print(
            "\n⛔ تم إيقاف التشغيل يدويًا"
        )

    except Exception as e:

        print(
            "\n"
            "❌ خطأ رئيسي غير متوقع:\n"
            f"{type(e).__name__}: {e}"
        )

        raise
