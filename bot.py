import feedparser
import requests
import hashlib
import time
import os
import io
import re
import difflib
import html

from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


# ══════════════════════════════════════════════════════════════════
# إعدادات
# ══════════════════════════════════════════════════════════════════
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "").strip()
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
CHANNEL_ID   = "@egypt_risk_radar"
API_URL      = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip()
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    if GEMINI_KEY else ""
)
FONT_PATH         = "/tmp/Amiri-Regular.ttf"
FONT_URL          = "https://github.com/aliftype/amiri/raw/main/fonts/Amiri-Regular.ttf"
HTTP_TIMEOUT      = 20
TELEGRAM_TIMEOUT  = 30
MAX_TG_MSG        = 4000
CAIRO_TZ          = ZoneInfo("Africa/Cairo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}


# ══════════════════════════════════════════════════════════════════
# كلمات مستبعدة وكلمات التحديث
# ══════════════════════════════════════════════════════════════════
EXCLUDE_KW = [
    "مواعيد قطارات", "مواعيد القطار", "مواعيد القطارات",
    "جدول قطارات", "جدول القطارات", "أسعار تذاكر القطارات",
    "اسعار تذاكر القطارات", "حجز تذاكر القطارات", "حجز تذاكر القطار",
    "محطات القطارات", "محطة القطار", "قطارات اليوم", "القطار اليوم",
    "قطار اليوم", "حركة القطارات", "حركة القطارات اليوم",
    "تأخيرات القطارات", "تأخير القطارات", "مواعيد المترو",
    "مواعيد الأتوبيسات", "مواعيد الاتوبيسات", "جدول المترو",
    "مواعيد وسائل النقل",
]

UPDATE_KW = [
    "ارتفاع عدد", "حصيلة", "حصيلة جديدة", "تطورات", "آخر التطورات",
    "تحديث", "تفاصيل جديدة", "كشف سبب", "كشفت التحقيقات", "التحقيقات",
    "النيابة", "ضبط", "القبض على", "إصابة", "إصابات", "وفاة", "وفيات",
    "انتشال", "إخماد", "السيطرة على", "استمرار", "استكمال",
    "فتح تحقيق", "إحالة", "قرار جديد", "بيان جديد",
]


# ══════════════════════════════════════════════════════════════════
# المصادر — RSS
# ══════════════════════════════════════════════════════════════════
RSS_SOURCES = [
    {
        "id": "amwal_banks", "name": "أموال الغد - بنوك",
        "url": "https://amwalalghad.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-%d9%85%d8%a7%d9%84%d9%8a%d8%a9/feed/",
        "tab": "banks", "exclude": ["سعر"],
    },
    {
        "id": "masrafeyoun_banks", "name": "المصرفيون",
        "url": "https://masrafeyoun.ebi.gov.eg/category/banksnews/feed/",
        "tab": "banks", "exclude": [],
    },
    {
        "id": "borsaa_banks", "name": "البورصة نيوز - بنوك",
        "url": "https://www.alborsaanews.com/category/%d8%a7%d9%84%d8%a8%d9%86%d9%88%d9%83/feed/",
        "tab": "banks", "exclude": [],
    },
    {
        "id": "hapi_credit", "name": "حابي - تمويل",
        "url": "https://hapijournal.com/category/%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/",
        "tab": "credit", "exclude": [],
    },
    {
        "id": "motawwer_credit", "name": "المطور - تمويل",
        "url": "https://almotawwer.com/tag/%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%b9%d8%a7%d8%aa-%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%b1%d8%a9/feed/",
        "tab": "credit", "exclude": [],
    },
    {
        "id": "amwal_micro", "name": "أموال الغد - تمويل",
        "url": "https://amwalalghad.com/tag/%d9%85%d8%aa%d9%86%d8%a7%d9%87%d9%8a-%d8%a7%d9%84%d8%b5%d8%ba%d8%b1/feed/",
        "tab": "credit", "exclude": [],
    },
    {
        "id": "hapi_fx", "name": "حابي - دولار",
        "url": "https://hapijournal.com/tag/%d8%a3%d8%b3%d8%b9%d8%a7%d8%b1-%d8%a7%d9%84%d8%af%d9%88%d9%84%d8%a7%d8%b1/feed/",
        "tab": "fx", "exclude": [],
    },
    {
        "id": "skynews_business", "name": "سكاي نيوز - اقتصاد",
        "url": "https://www.skynewsarabia.com/rss/business.xml",
        "tab": "global", "exclude": [],
    },
    {
        "id": "borsaa_agri", "name": "البورصة نيوز - زراعة",
        "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b2%d8%b1%d8%a7%d8%b9%d8%a9/feed/",
        "tab": "sector_agri", "exclude": [],
    },
    {
        "id": "borsaa_industry", "name": "البورصة نيوز - صناعة",
        "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d8%a9/feed/",
        "tab": "sector_industry", "exclude": [],
    },
    {
        "id": "borsaa_realestate", "name": "البورصة نيوز - عقارات",
        "url": "https://www.alborsaanews.com/category/%d8%a7%d9%84%d8%b9%d9%82%d8%a7%d8%b1%d8%a7%d8%aa/feed/",
        "tab": "sector_realestate", "exclude": [],
    },
    {
        "id": "amwal_energy", "name": "أموال الغد - طاقة",
        "url": "https://amwalalghad.com/category/%d8%b7%d8%a7%d9%82%d8%a9/feed/",
        "tab": "sector_energy", "exclude": [],
    },
    {
        "id": "amwal_transport", "name": "أموال الغد - نقل",
        "url": "https://amwalalghad.com/category/%d9%86%d9%82%d9%84-%d9%88-%d9%85%d9%84%d8%a7%d8%ad%d8%a9/feed/",
        "tab": "sector_transport", "exclude": [],
    },
    {
        "id": "amwal_tech", "name": "أموال الغد - تكنولوجيا",
        "url": "https://amwalalghad.com/category/%d8%aa%d9%83%d9%86%d9%88%d9%84%d9%88%d8%ac%d9%8a%d8%a7-%d9%88%d8%a7%d8%aa%d8%b5%d8%a7%d9%84%d8%a7%d8%aa/feed/",
        "tab": "sector_tech", "exclude": [],
    },
    # مصادر عامة → عاجل
    {"id": "hapi_all",        "name": "حابي",        "url": "https://hapijournal.com/feed/",                "tab": None, "exclude": []},
    {"id": "febanks_all",     "name": "في البنوك",   "url": "https://febanks.com/feed/",                   "tab": None, "exclude": []},
    {"id": "masrafeyoun_all", "name": "المصرفيون",   "url": "https://masrafeyoun.ebi.gov.eg/feed/",         "tab": None, "exclude": []},
]


# ══════════════════════════════════════════════════════════════════
# المصادر — Scraping
# ══════════════════════════════════════════════════════════════════
SCRAPE_SOURCES = [
    # ── عاجل ──────────────────────────────────────────────────────
    {
        "id": "alarabiya_egypt_economy",
        "name": "العربية - اقتصاد مصر",
        "url": "https://www.alarabiya.net/aswaq/egypt-economy",
        "tab": "breaking",
        "base": "https://www.alarabiya.net",
        "exclude": [],
    },
    {
        "id": "economyplus_breaking",
        "name": "Economy Plus - أخبار",
        "url": "https://economyplusme.com/category/%d8%a3%d8%ae%d8%a8%d8%a7%d8%b1/",
        "tab": "breaking",
        "base": "https://economyplusme.com",
        "exclude": [],
    },
    {
        "id": "hapi_important_breaking",
        "name": "حابي - أهم الأخبار",
        "url": "https://hapijournal.com/tag/%d8%a3%d9%87%d9%85-%d8%a7%d9%84%d8%a3%d8%ae%d8%a8%d8%a7%d8%b1/",
        "tab": "breaking",
        "base": "https://hapijournal.com",
        "exclude": [],
    },
    # ── إنذار مبكر ────────────────────────────────────────────────
    {
        "id": "ahram_economy",
        "name": "الأهرام - اقتصاد",
        "url": "https://gate.ahram.org.eg/Portal/14/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF.aspx",
        "tab": "warning",
        "base": "https://gate.ahram.org.eg",
        "exclude": [],
    },
    {
        "id": "youm7_economy",
        "name": "اليوم السابع - اقتصاد",
        "url": "https://m.youm7.com/Section/%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D9%88%D8%A8%D9%88%D8%B1%D8%B5%D8%A9/297/1",
        "tab": "warning",
        "base": "https://m.youm7.com",
        "exclude": ["سعر", "أسعار"],
    },
    {
        "id": "elbalad_factory_fire",
        "name": "صدى البلد - حريق مصنع",
        "url": "https://www.elbalad.news/search/term?search=%D8%AD%D8%B1%D9%8A%D9%82-%D9%85%D8%B5%D9%86%D8%B9&pageIndex=1",
        "tab": "warning",
        "base": "https://www.elbalad.news",
        "exclude": [],
        "require_kw": ["حريق", "مصنع"],
    },
    {
        "id": "almal_investment",
        "name": "المال - استثمار",
        "url": "https://almalnews.com/category/investment/1/",
        "tab": "warning",
        "base": "https://almalnews.com",
        "exclude": [],
    },
    {
        "id": "enterprise_ma",
        "name": "انتربرايز - دمج واستحواذ",
        "url": "https://enterpriseam.com/egypt-ar/category/%d8%a3%d8%b9%d9%85%d8%a7%d9%84/%d8%af%d9%85%d8%ac-%d9%88%d8%a7%d8%b3%d8%aa%d8%ad%d9%88%d8%a7%d8%b0/",
        "tab": "warning",
        "base": "https://enterpriseam.com",
        "exclude": [],
    },
    {
        "id": "enterprise_debt",
        "name": "انتربرايز - ديون",
        "url": "https://enterpriseam.com/egypt-ar/category/%d8%a3%d8%b9%d9%85%d8%a7%d9%84/%d8%af%d9%8a%d9%88%d9%86/",
        "tab": "warning",
        "base": "https://enterpriseam.com",
        "exclude": [],
    },
    # ── البنوك ────────────────────────────────────────────────────
    {
        "id": "masrawy_banks",
        "name": "مصراوي - البنوك",
        "url": "https://www.masrawy.com/news/news-banking/section/847/%d8%a3%d8%ae%d8%a8%d8%a7%d8%b1-%d8%a7%d9%84%d8%a8%d9%86%d9%88%d9%83-",
        "tab": "banks",
        "base": "https://www.masrawy.com",
        "exclude": ["سعر", "أسعار"],
    },
    {
        "id": "egyptbanks_banks",
        "name": "مباشر بنوك مصر",
        "url": "https://egyptbanks.info/news",
        "tab": "banks",
        "base": "https://egyptbanks.info",
        "exclude": [],
    },
    # ── المركزي ───────────────────────────────────────────────────
    {
        "id": "almal_cbe",
        "name": "المال - مركزي",
        "url": "https://almalnews.com/tag/%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A/",
        "tab": "cbe",
        "base": "https://almalnews.com",
        "exclude": [],
        "require_kw": ["المركزي", "البنك المركزي"],
    },
]


# ══════════════════════════════════════════════════════════════════
# تصنيفات وأولويات
# ══════════════════════════════════════════════════════════════════
TAB_LABELS = {
    "breaking":          "⚡ عاجل",
    "banks":             "🏦 البنوك",
    "credit":            "💰 تمويل وائتمان",
    "warning":           "⚠️ إنذار مبكر",
    "fx":                "💵 أسعار الدولار",
    "cbe":               "🏛️ المركزي",
    "global":            "🌍 اقتصاد الشرق والعالم",
    "sector_agri":       "🌾 زراعة",
    "sector_industry":   "🏭 صناعة",
    "sector_realestate": "🏗️ عقارات",
    "sector_energy":     "⚡ طاقة",
    "sector_transport":  "🚢 نقل وملاحة",
    "sector_tech":       "💻 تكنولوجيا واتصالات",
}

DIGEST_PRIORITY = [
    "warning", "credit", "cbe", "banks", "fx", "global",
    "breaking", "sector_agri", "sector_industry",
    "sector_realestate", "sector_energy", "sector_transport", "sector_tech",
]


# ══════════════════════════════════════════════════════════════════
# Telegram
# ══════════════════════════════════════════════════════════════════
def escape_html(text):
    return html.escape("" if text is None else str(text), quote=True)

def escape_md(text):
    return (str(text or "")
            .replace("\\", "\\\\").replace("_", "\\_")
            .replace("*", "\\*").replace("[", "\\[")
            .replace("]", "\\]").replace("`", "\\`"))

def send(text, parse_mode="HTML", max_retries=3):
    if not BOT_TOKEN:
        print("    ❌ BOT_TOKEN غير موجود")
        return False
    if not text:
        return False

    # تقسيم الرسائل الطويلة
    chunks = []
    t = str(text)
    while len(t) > MAX_TG_MSG:
        cut = t.rfind("\n", 0, MAX_TG_MSG)
        if cut < MAX_TG_MSG * 0.5:
            cut = MAX_TG_MSG
        chunks.append(t[:cut])
        t = t[cut:].lstrip()
    if t:
        chunks.append(t)

    for idx, chunk in enumerate(chunks, 1):
        sent = False
        for attempt in range(1, max_retries + 1):
            payload = {"chat_id": CHANNEL_ID, "text": chunk, "disable_web_page_preview": True}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            try:
                r = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=TELEGRAM_TIMEOUT)
                if r.status_code == 200:
                    sent = True
                    break
                # Rate limit
                if r.status_code == 429:
                    try:
                        wait = int(r.json().get("parameters", {}).get("retry_after", 5))
                    except Exception:
                        wait = 5
                    time.sleep(min(max(wait, 2), 60))
                    continue
                # Markdown/HTML error → retry without parse_mode
                if r.status_code == 400 and parse_mode:
                    r2 = requests.post(
                        f"{API_URL}/sendMessage",
                        json={"chat_id": CHANNEL_ID, "text": chunk, "disable_web_page_preview": True},
                        timeout=TELEGRAM_TIMEOUT,
                    )
                    if r2.status_code == 200:
                        print("    📤 تم الإرسال بدون parse_mode")
                        sent = True
                        break
                print(f"    ⚠️ Telegram {r.status_code}: {r.text[:200]}")
                time.sleep(min(attempt * 2, 10))
            except Exception as e:
                print(f"    ❌ Telegram error attempt {attempt}: {e}")
                time.sleep(min(attempt * 2, 10))
        if not sent:
            return False
        if idx < len(chunks):
            time.sleep(1)
    return True


def telegram_bot_ok():
    """تحقق بسيط: هل الـ BOT_TOKEN صحيح؟"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN غير موجود")
        return False
    try:
        r = requests.get(f"{API_URL}/getMe", timeout=15)
        if r.status_code == 200 and r.json().get("ok"):
            bot = r.json().get("result", {})
            print(f"✅ Telegram Bot: @{bot.get('username', 'unknown')}")
            return True
        print(f"❌ Telegram getMe {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"❌ Telegram check error: {e}")
        return False


def format_msg(title, url, source_name, tabs):
    labels = " | ".join(TAB_LABELS.get(t, t) for t in tabs)
    return (
        f"<b>{labels}</b>\n\n"
        f'<a href="{escape_html(url)}"><b>{escape_html(title)}</b></a>\n\n'
        f"📰 {escape_html(source_name)}\n\n"
        f"🛡 @egypt_risk_radar"
    )


# ══════════════════════════════════════════════════════════════════
# Supabase
# ══════════════════════════════════════════════════════════════════
def supabase_ready():
    return bool(SUPABASE_URL and SUPABASE_KEY)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

def supabase_get_hashes():
    """
    ✅ نجح الاتصال + بيانات  → set(hashes)
    ✅ نجح الاتصال + فاضية   → set()  (أول تشغيل — طبيعي)
    ❌ فشل الاتصال           → None   (يوقف البوت)
    """
    if not supabase_ready():
        print("⚠️ Supabase غير مُعد — سيعمل بدون حماية تكرار")
        return set()
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news",
            params={"select": "hash", "created_at": f"gte.{since}"},
            headers=sb_headers(), timeout=15,
        )
        if r.status_code == 200:
            hashes = {item["hash"] for item in r.json() if item.get("hash")}
            print(f"   ✅ {len(hashes)} hash من Supabase")
            return hashes
        print(f"   ❌ Supabase HTTP {r.status_code}: {r.text[:200]}")
        return None   # ← فشل حقيقي = يوقف البوت
    except Exception as e:
        print(f"   ❌ Supabase connection failed: {e}")
        return None   # ← فشل حقيقي = يوقف البوت


def supabase_get_recent_news_for_dedupe():
    if not supabase_ready():
        return []
    all_items, offset, page_size = [], 0, 1000
    try:
        while True:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/news",
                params={"select": "title,url,source_name,created_at",
                        "order": "created_at.desc",
                        "limit": page_size, "offset": offset},
                headers=sb_headers(), timeout=20,
            )
            if r.status_code != 200:
                print(f"Supabase recent HTTP {r.status_code}")
                break
            data = r.json()
            if not data:
                break
            all_items.extend(data)
            if len(data) < page_size or len(all_items) >= 20000:
                break
            offset += page_size
    except Exception as e:
        print(f"Supabase recent error: {e}")
    return all_items


def supabase_save_news(title, url, source_name, tabs, h):
    if not supabase_ready():
        return False
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/news",
            headers={**sb_headers(), "Prefer": "resolution=ignore-duplicates"},
            json={"title": title, "url": url, "source_name": source_name, "tabs": tabs, "hash": h},
            timeout=15,
        )
        if r.status_code not in (200, 201, 204):
            print(f"    ⚠️ Supabase save {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"    ⚠️ Supabase save error: {e}")
        return False


def supabase_get_last_24h():
    if not supabase_ready():
        return []
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news",
            params={"select": "title,tabs", "created_at": f"gte.{since}", "order": "created_at.asc"},
            headers=sb_headers(), timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Supabase last24h error: {e}")
    return []


def supabase_get_news_for_pdf():
    if not supabase_ready():
        return []
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news",
            params={"select": "title,url,source_name,tabs,created_at",
                    "created_at": f"gte.{since}", "order": "created_at.asc"},
            headers=sb_headers(), timeout=20,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Supabase PDF error: {e}")
    return []


def supabase_save_digest(tab_key, tab_label, content, news_count, digest_date):
    if not supabase_ready():
        return False
    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/digest",
            params={"tab_key": f"eq.{tab_key}", "digest_date": f"eq.{digest_date}"},
            headers=sb_headers(), timeout=10,
        )
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/digest",
            headers=sb_headers(),
            json={"tab_key": tab_key, "tab_label": tab_label, "content": content,
                  "news_count": news_count, "digest_date": digest_date},
            timeout=10,
        )
        return r.status_code in (200, 201, 204)
    except Exception as e:
        print(f"Supabase save_digest error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# تنظيف ومقارنة النصوص
# ══════════════════════════════════════════════════════════════════
def normalize_arabic(text):
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    for old, new in {"أ":"ا","إ":"ا","آ":"ا","ٱ":"ا","ى":"ي","ة":"ه"}.items():
        text = text.replace(old, new)
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def title_tokens(text):
    stop = {"مصر","اليوم","غدا","المصري","المصرية","في","من","على","عن",
            "بعد","قبل","مع","الى","إلى","هذا","هذه","التي","الذي","و","ب","ل","ا"}
    return {w for w in normalize_arabic(text).split() if len(w) >= 2 and w not in stop}


def is_update_title(title):
    n = normalize_arabic(title)
    return any(normalize_arabic(k) in n for k in UPDATE_KW)


def titles_are_probable_duplicate(t1, t2):
    n1, n2 = normalize_arabic(t1), normalize_arabic(t2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    if ratio >= 0.88:
        return True
    tok1, tok2 = title_tokens(t1), title_tokens(t2)
    if not tok1 or not tok2:
        return False
    overlap = len(tok1 & tok2) / min(len(tok1), len(tok2))
    return overlap >= 0.80 and ratio >= 0.58


def is_excluded(title, extra=None):
    n = normalize_arabic(title)
    return any(normalize_arabic(k) in n for k in (EXCLUDE_KW + (extra or [])))


def passes_require_kw(title, require_kw):
    if not require_kw:
        return True
    return all(kw in title for kw in require_kw)


def is_recent(dt, max_hours=24):
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = now - dt
    return timedelta(minutes=-10) < age <= timedelta(hours=max_hours)


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    value = str(value).strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    for fmt in ["%d/%m/%Y %I:%M %p", "%d/%m/%Y %H:%M",
                "%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


# ══════════════════════════════════════════════════════════════════
# دوال مساعدة
# ══════════════════════════════════════════════════════════════════
def is_arabic(text):
    if not text:
        return False
    c = sum(1 for ch in str(text) if "\u0600" <= ch <= "\u06ff")
    return c / max(len(str(text)), 1) > 0.3


def get_tabs(primary_tab):
    return [primary_tab] if primary_tab else ["breaking"]


def make_hash(title):
    return hashlib.md5(normalize_arabic(title).encode("utf-8")).hexdigest()


def canonical_url(url):
    if not url:
        return ""
    url = str(url).strip()
    parsed = urlparse(url)
    q = parse_qs(parsed.query, keep_blank_values=True)
    tracking = ("utm_", "fbclid", "gclid", "ved", "ei")
    filtered = {k: v for k, v in q.items()
                if not any(k.lower().startswith(p) for p in tracking)}
    qs = "&".join(f"{k}={v}" for k in sorted(filtered) for v in filtered[k])
    return parsed._replace(query=qs, fragment="").geturl().rstrip("/")


def source_domain(url):
    try:
        h = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════
# منع التكرار — نفس المصدر فقط
# ══════════════════════════════════════════════════════════════════
def is_duplicate(title, url, source_name, recent_news):
    cur_url    = canonical_url(url)
    cur_norm   = normalize_arabic(title)
    cur_domain = source_domain(cur_url) or normalize_arabic(source_name)

    for item in recent_news:
        old_url    = canonical_url(item.get("url", ""))
        old_domain = source_domain(old_url) or normalize_arabic(item.get("source_name", ""))

        # مصادر مختلفة → مسموح
        if cur_domain and old_domain and cur_domain != old_domain:
            continue

        if cur_url and old_url and cur_url == old_url:
            return True, "نفس الرابط"

        old_norm = normalize_arabic(item.get("title", ""))
        if cur_norm and old_norm and cur_norm == old_norm:
            return True, "نفس العنوان"

        if not is_update_title(title) and titles_are_probable_duplicate(title, item.get("title", "")):
            return True, "عنوان مشابه جداً"

    return False, ""


# ══════════════════════════════════════════════════════════════════
# معالجة الخبر
# ══════════════════════════════════════════════════════════════════
def process_item(title, url, source_name, primary_tab, summary,
                 exclude, sent_hashes, recent_news,
                 published_at=None, require_kw=None):

    if not title or not url:
        return False, sent_hashes, recent_news

    title = str(title).strip()
    url   = canonical_url(url)

    if not is_arabic(title):
        return False, sent_hashes, recent_news

    if is_excluded(title, exclude):
        print(f"    ⛔ مستبعد: {title[:80]}")
        return False, sent_hashes, recent_news

    if not passes_require_kw(title, require_kw or []):
        return False, sent_hashes, recent_news

    # فلتر التاريخ — فقط لو موجود (RSS)
    if published_at is not None and not is_recent(published_at):
        print(f"    ⏳ قديم: {title[:70]}")
        return False, sent_hashes, recent_news

    # ← فحص Hash أولاً (سريع)
    h = make_hash(title)
    if h in sent_hashes:
        print(f"    ♻️ Hash مكرر: {title[:70]}")
        return False, sent_hashes, recent_news

    # فحص التشابه مع الأخبار السابقة
    dup, reason = is_duplicate(title, url, source_name, recent_news)
    if dup:
        print(f"    ♻️ مكرر ({reason}): {title[:70]}")
        return False, sent_hashes, recent_news

    tabs = get_tabs(primary_tab)
    msg  = format_msg(title, url, source_name, tabs)

    if send(msg, parse_mode="HTML"):
        sent_hashes.add(h)
        saved = supabase_save_news(title, url, source_name, tabs, h)
        if not saved:
            print("    ⚠️ أُرسل لكن فشل حفظه في Supabase")
        recent_news.insert(0, {
            "title": title, "url": url, "source_name": source_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"    ✅ {title[:80]}")
        time.sleep(2)
        return True, sent_hashes, recent_news

    print(f"    ❌ فشل إرسال: {title[:60]}")
    return False, sent_hashes, recent_news


# ══════════════════════════════════════════════════════════════════
# RSS
# ══════════════════════════════════════════════════════════════════
def get_entry_date(entry):
    for field in ("published_parsed", "updated_parsed"):
        v = entry.get(field)
        if v:
            try:
                from calendar import timegm
                return datetime.fromtimestamp(timegm(v), timezone.utc)
            except Exception:
                pass
    for field in ("published", "updated", "created"):
        dt = parse_dt(entry.get(field))
        if dt:
            return dt
    return None


def fetch_rss(src, sent_hashes, recent_news):
    count = 0
    try:
        r = requests.get(src["url"], headers=HEADERS, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            print(f"    ⚠️ RSS HTTP {r.status_code}: {src['name']}")
            return 0, sent_hashes, recent_news
        feed    = feedparser.parse(r.content)
        entries = getattr(feed, "entries", [])
        print(f"    📥 {len(entries)} خبر في RSS")
        for entry in entries[:100]:
            ok, sent_hashes, recent_news = process_item(
                entry.get("title", "").strip(),
                entry.get("link", ""),
                src["name"], src["tab"],
                entry.get("summary", "")[:400],
                src.get("exclude", []),
                sent_hashes, recent_news,
                published_at=get_entry_date(entry),
            )
            if ok:
                count += 1
    except Exception as e:
        print(f"    ⚠️ RSS error {src['name']}: {e}")
    return count, sent_hashes, recent_news


# ══════════════════════════════════════════════════════════════════
# Scraping — بدون طلب تاريخ المقال
# ══════════════════════════════════════════════════════════════════
def abs_url(base, href):
    if not href:
        return ""
    href = href.strip()
    return "https:" + href if href.startswith("//") else urljoin(base, href)


def extract_items(soup, base, limit=50):
    items, seen = [], set()
    for article in soup.find_all("article"):
        heading = article.find(["h1","h2","h3","h4"])
        if not heading:
            continue
        anchor = heading.find("a", href=True) or article.find("a", href=True)
        if not anchor:
            continue
        title = heading.get_text(" ", strip=True)
        link  = canonical_url(abs_url(base, anchor.get("href")))
        if len(title) < 15 or not link or link in seen:
            continue
        seen.add(link)
        items.append((title, link))
        if len(items) >= limit:
            break

    if len(items) < limit:
        for h in soup.find_all(["h1","h2","h3","h4"]):
            a = h.find("a", href=True)
            if not a:
                continue
            title = h.get_text(" ", strip=True)
            link  = canonical_url(abs_url(base, a.get("href")))
            if len(title) < 15 or not link or link in seen:
                continue
            seen.add(link)
            items.append((title, link))
            if len(items) >= limit:
                break
    return items


def fetch_scrape(src, sent_hashes, recent_news):
    count = 0
    try:
        r = requests.get(src["url"], headers=HEADERS, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            print(f"    ⚠️ HTTP {r.status_code}: {src['name']}")
            return 0, sent_hashes, recent_news

        soup  = BeautifulSoup(r.text, "html.parser")
        items = extract_items(soup, src["base"], limit=50)
        print(f"    🔎 {len(items)} نتيجة في {src['name']}")

        for title, link in items:
            # ← لا نطلب تاريخ المقال — hash + title dedup هو الضمان
            ok, sent_hashes, recent_news = process_item(
                title, link, src["name"], src["tab"],
                "",
                src.get("exclude", []),
                sent_hashes, recent_news,
                published_at=None,           # ← تجاهل فلتر التاريخ
                require_kw=src.get("require_kw"),
            )
            if ok:
                count += 1
    except Exception as e:
        print(f"    ⚠️ Scrape error {src['name']}: {e}")
    return count, sent_hashes, recent_news


# ══════════════════════════════════════════════════════════════════
# PDF يومي
# ══════════════════════════════════════════════════════════════════
def download_font():
    if os.path.exists(FONT_PATH):
        return True
    try:
        print("⬇️  جاري تحميل الخط العربي...")
        r = requests.get(FONT_URL, timeout=30)
        if r.status_code == 200 and len(r.content) > 10000:
            with open(FONT_PATH, "wb") as f:
                f.write(r.content)
            print("✅ تم تحميل الخط")
            return True
        print(f"❌ فشل تحميل الخط: HTTP {r.status_code}")
    except Exception as e:
        print(f"❌ Font error: {e}")
    return False


def ar(text):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def generate_daily_pdf(news_list, now_cairo):
    from fpdf import FPDF
    if not download_font():
        raise RuntimeError("تعذر تحميل خط Amiri")

    date_str = now_cairo.strftime("%d/%m/%Y")
    grouped  = {}
    for item in news_list:
        for tab in item.get("tabs", []):
            grouped.setdefault(tab, []).append(item)
    ordered = sorted(grouped, key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("Amiri", "", FONT_PATH, uni=True)
    pdf.add_page()

    # رأس
    pdf.set_fill_color(26, 60, 94)
    pdf.rect(0, 0, 210, 30, "F")
    pdf.set_font("Amiri", size=18)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(6)
    pdf.cell(0, 9, ar("رادار المخاطر — تقرير الأخبار اليومي"), ln=True, align="C")
    pdf.set_font("Amiri", size=11)
    pdf.cell(0, 8, ar(f"{date_str}  |  {len(news_list)} خبر في {len(grouped)} تبويبات"), ln=True, align="C")
    pdf.ln(8)

    for tab in ordered:
        items     = grouped[tab]
        tab_label = TAB_LABELS.get(tab, tab)
        pdf.set_fill_color(26, 60, 94)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Amiri", size=13)
        pdf.cell(0, 10, ar(f"{tab_label} ({len(items)} خبر)"), ln=True, align="R", fill=True)
        pdf.ln(1)

        for i, item in enumerate(items):
            title  = item.get("title", "")
            url    = item.get("url", "")
            source = item.get("source_name", "")
            try:
                dt = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                time_str = dt.astimezone(CAIRO_TZ).strftime("%H:%M")
            except Exception:
                time_str = ""

            pdf.set_fill_color(245, 249, 252) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.set_font("Amiri", size=10)
            pdf.set_text_color(26, 60, 94)
            pdf.multi_cell(0, 7, f"  {ar(title)}", align="R", fill=True, link=url or "")
            pdf.set_font("Amiri", size=9)
            pdf.set_text_color(130, 130, 130)
            pdf.cell(0, 6, f"  {ar(source)} | {time_str}", ln=True, align="R")
            pdf.ln(1)
        pdf.ln(5)

    pdf.set_y(-15)
    pdf.set_font("Amiri", size=8)
    pdf.set_text_color(170, 170, 170)
    pdf.cell(0, 8, ar(f"رادار المخاطر — @egypt_risk_radar — {date_str}"), align="C")
    return bytes(pdf.output())


def send_pdf(pdf_bytes, date_str):
    if not BOT_TOKEN:
        print("❌ PDF: BOT_TOKEN غير موجود")
        return False
    try:
        filename = f"رادار_المخاطر_{date_str.replace('/', '-')}.pdf"
        caption  = (
            f"📋 *تقرير أخبار اليوم — {escape_md(date_str)}*\n"
            f"_جميع أخبار الـ 24 ساعة الماضية مصنفة بالتبويبات_\n\n"
            f"🛡 @egypt\\_risk\\_radar"
        )
        r = requests.post(
            f"{API_URL}/sendDocument",
            files={"document": (filename, io.BytesIO(pdf_bytes), "application/pdf")},
            data={"chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "Markdown"},
            timeout=60,
        )
        if r.status_code == 200:
            print("✅ PDF اتبعت على تليجرام")
            return True
        print(f"❌ PDF Telegram {r.status_code}: {r.text[:300]}")
        return False
    except Exception as e:
        print(f"❌ PDF send error: {e}")
        return False


def run_pdf_report():
    print("📋 جاري إعداد التقرير اليومي PDF...")
    news = supabase_get_news_for_pdf()
    if not news:
        print("لا توجد أخبار في الـ 24 ساعة الماضية")
        return
    now_cairo = datetime.now(timezone.utc).astimezone(CAIRO_TZ)
    date_str  = now_cairo.strftime("%d/%m/%Y")
    print(f"  {len(news)} خبر — جاري توليد PDF...")
    try:
        pdf_bytes = generate_daily_pdf(news, now_cairo)
        send_pdf(pdf_bytes, date_str)
    except Exception as e:
        print(f"❌ PDF error: {e}")


# ══════════════════════════════════════════════════════════════════
# الموجز اليومي
# ══════════════════════════════════════════════════════════════════
def ask_gemini(prompt):
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY غير موجود")
        return None
    try:
        r = requests.post(
            GEMINI_ENDPOINT,
            params={"key": GEMINI_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        if r.status_code != 200:
            print(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
            return None
        candidates = r.json().get("candidates", [])
        if not candidates:
            return None
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text")
        return text.strip() if text else None
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


def group_by_tab(news_list):
    grouped = {}
    for item in news_list:
        for tab in item.get("tabs", []):
            grouped.setdefault(tab, []).append(item.get("title", ""))
    return grouped


def build_prompt(tab_label, headlines):
    hl = "\n".join(f"- {h}" for h in headlines)
    return (
        f"أنت محلل أول في قسم المخاطر والائتمان في أحد البنوك المصرية الكبرى.\n"
        f'لديك عناوين أخبار تبويب "{tab_label}" خلال الـ 24 ساعة الماضية:\n\n'
        f"{hl}\n\n"
        f"المطلوب:\n"
        f"1. عناوين الأخبار الأبرز في نقاط مختصرة\n"
        f"2. تحليل: ما الذي يستوجب الانتباه من منظور مخاطر وائتمان؟\n"
        f"3. تعليق مهني واحد للعاملين في القطاع\n\n"
        f"اكتب بأسلوب احترافي وموجز باللغة العربية، بدون مقدمات أو تحيات."
    )


def run_daily_digest():
    print("📊 جاري إعداد الموجز اليومي...")
    news = supabase_get_last_24h()
    if not news:
        print("لا توجد أخبار في الـ 24 ساعة الماضية")
        return
    grouped  = group_by_tab(news)
    now      = datetime.now(timezone.utc).astimezone(CAIRO_TZ)
    date_str = now.strftime("%d/%m/%Y")
    send(
        f"🗞️ *موجز أنباء وتحليلات — {escape_md(date_str)}*\n"
        f"_تقرير يومي لمتخصصي الائتمان والمخاطر_\n\n"
        f"رصدنا اليوم *{len(news)} خبراً* في *{len(grouped)} قطاعات*\n\n"
        f"━━━━━━━━━━━━━━━━\n🛡 @egypt\\_risk\\_radar",
        parse_mode="Markdown",
    )
    time.sleep(3)
    ordered = sorted(grouped, key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99)
    for tab in ordered:
        headlines = grouped[tab]
        if not headlines:
            continue
        tab_label = TAB_LABELS.get(tab, tab)
        print(f"  🤖 Gemini: {tab_label} ({len(headlines)} خبر)...")
        analysis = ask_gemini(build_prompt(tab_label, headlines))
        if not analysis:
            continue
        analysis = analysis.replace("**", "*")
        msg = (
            f"{'━'*16}\n*{escape_md(tab_label)}*  \\| {len(headlines)} خبر\n"
            f"{'━'*16}\n\n{analysis}\n\n🛡 @egypt\\_risk\\_radar"
        )
        send(msg, parse_mode="Markdown")
        supabase_save_digest(tab, tab_label, analysis, len(headlines), now.strftime("%Y-%m-%d"))
        time.sleep(5)
    send(
        f"✅ *انتهى موجز {escape_md(date_str)}*\n\n"
        f"تابع أخبار السوق لحظة بلحظة\n🛡 @egypt\\_risk\\_radar",
        parse_mode="Markdown",
    )
    print("✅ انتهى الموجز اليومي")


# ══════════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ══════════════════════════════════════════════════════════════════
def run():
    print("\n══════════════════════════════════════════")
    print("🛡 رادار المخاطر المصري")
    print("══════════════════════════════════════════")

    mode = os.environ.get("RUN_MODE", "news").strip().lower()
    print(f"⚙️  RUN_MODE = {mode}")

    # فحص BOT_TOKEN
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN غير موجود — إيقاف")
        return

    # فحص الـ token صحيح
    if not telegram_bot_ok():
        print("❌ BOT_TOKEN غير صالح — إيقاف")
        return

    if mode == "digest":
        run_daily_digest()
        return

    if mode == "pdf":
        run_pdf_report()
        return

    # ── وضع الأخبار ──
    print("\n📦 جاري تحميل الأخبار المرسلة من Supabase...")
    sent_hashes = supabase_get_hashes()

    # ← وقف فوري لو Supabase فشل (None = خطأ اتصال)
    if sent_hashes is None:
        print("❌ ABORT: Supabase غير متاح — وقف منعاً للتكرار")
        return

    recent_news = supabase_get_recent_news_for_dedupe()
    print(f"   {len(sent_hashes)} hash | {len(recent_news)} خبر في ذاكرة التكرار")

    new_count = 0

    print("\n════════ RSS SOURCES ════════")
    for src in RSS_SOURCES:
        print(f"\n  📡 RSS: {src['name']}...")
        try:
            count, sent_hashes, recent_news = fetch_rss(src, sent_hashes, recent_news)
            new_count += count
            print(f"     → {count} خبر جديد")
        except Exception as e:
            print(f"     ❌ خطأ غير متوقع: {e}")

    print("\n════════ SCRAPING SOURCES ════════")
    for src in SCRAPE_SOURCES:
        print(f"\n  🕷️  Scraping: {src['name']}...")
        try:
            count, sent_hashes, recent_news = fetch_scrape(src, sent_hashes, recent_news)
            new_count += count
            print(f"     → {count} خبر جديد")
        except Exception as e:
            print(f"     ❌ خطأ غير متوقع: {e}")

    print("\n══════════════════════════════════════════")
    print(f"✅ تم نشر {new_count} خبر جديد")
    print("══════════════════════════════════════════\n")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n⛔ تم إيقاف التشغيل يدوياً")
    except Exception as e:
        print(f"\n❌ خطأ رئيسي: {type(e).__name__}: {e}")
        raise
