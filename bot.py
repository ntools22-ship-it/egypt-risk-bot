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
        "id": "shorouk_economy",
        "name": "الشروق - اقتصاد",
        "url": "https://www.shorouknews.com/mobile/news/section.aspx?id=6514de51-b725-4610-817e-1a19f3f0755d",
        "tab": "warning",
        "base": "https://www.shorouknews.com",
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
    {
        "id": "borsaa_special",
        "name": "البورصة نيوز - خاص",
        "url": "https://www.alborsaanews.com/latestnews",
        "tab": "warning",
        "base": "https://www.alborsaanews.com",
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
    {
        "id": "firstbank_banks",
        "name": "Firstbank - قوائم",
        "url": "https://www.firstbankeg.com/List/11",
        "tab": "banks",
        "base": "https://www.firstbankeg.com",
        "exclude": [],
    },
    {
        "id": "fallahalyoum_agri",
        "name": "الفلاح اليوم - زراعة",
        "url": "https://alfallahalyoum.news/category/akhbaralzra/",
        "tab": "sector_agri",
        "base": "https://alfallahalyoum.news",
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
                print(f"Supabase recent HTTP {r.status_code}: {r.text[:250]}")
                return None
            data = r.json()
            if not data:
                break
            all_items.extend(data)
            if len(data) < page_size or len(all_items) >= 20000:
                break
            offset += page_size
    except Exception as e:
        print(f"Supabase recent error: {e}")
        return None
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


def supabase_get_news_between(start_utc, end_utc, select_fields=None):
    """Paginated range query: None = DB error, [] = valid empty result."""
    if not supabase_ready():
        return []
    select_fields = select_fields or "title,url,source_name,tabs,created_at"
    all_items, offset, page_size = [], 0, 1000
    try:
        while True:
            params = [
                ("select", select_fields),
                ("created_at", f"gte.{start_utc.isoformat()}"),
                ("created_at", f"lt.{end_utc.isoformat()}"),
                ("order", "created_at.asc"),
                ("limit", str(page_size)),
                ("offset", str(offset)),
            ]
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/news",
                params=params,
                headers=sb_headers(), timeout=20,
            )
            if r.status_code != 200:
                print(f"Supabase range HTTP {r.status_code}: {r.text[:300]}")
                return None
            data = r.json()
            all_items.extend(data)
            if len(data) < page_size:
                break
            offset += page_size
            if offset >= 100000:
                print("⚠️ Supabase range capped at 100,000 rows")
                break
        return all_items
    except Exception as e:
        print(f"Supabase range error: {e}")
        return None


def supabase_get_last_24h():
    now = datetime.now(timezone.utc)
    return supabase_get_news_between(
        now - timedelta(hours=24), now,
        "title,tabs,created_at"
    )


def supabase_get_news_for_pdf():
    now = datetime.now(timezone.utc)
    return supabase_get_news_between(
        now - timedelta(hours=24), now,
        "title,url,source_name,tabs,created_at"
    )


def get_previous_completed_week_bounds():
    """الأسبوع المكتمل السابق: الأحد 00:00 إلى السبت 23:59 بتوقيت القاهرة."""
    now = datetime.now(timezone.utc).astimezone(CAIRO_TZ)
    today = now.date()
    days_since_sunday = (today.weekday() + 1) % 7
    this_sunday = today - timedelta(days=days_since_sunday)
    prev_sunday = this_sunday - timedelta(days=7)

    start_cairo = datetime.combine(prev_sunday, datetime.min.time(), tzinfo=CAIRO_TZ)
    end_cairo = datetime.combine(this_sunday, datetime.min.time(), tzinfo=CAIRO_TZ)
    return (
        start_cairo.astimezone(timezone.utc),
        end_cairo.astimezone(timezone.utc),
        prev_sunday,
        this_sunday - timedelta(days=1),
    )


def supabase_get_last_7days():
    start_utc, end_utc, _, _ = get_previous_completed_week_bounds()
    return supabase_get_news_between(
        start_utc, end_utc,
        "title,url,source_name,tabs,created_at"
    )


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
    n = normalize_arabic(title)
    return all(normalize_arabic(kw) in n for kw in require_kw)


CBE_TITLE_KW = [
    "البنك المركزي",
    "المركزي",
    "محافظ البنك المركزي",
    "محافظ المركزي",
    "البنك المركزى",
    "محافظ البنك المركزى",
]


def is_cbe_title(title):
    n = normalize_arabic(title)
    return any(normalize_arabic(k) in n for k in CBE_TITLE_KW)


def get_tabs_for_title(primary_tab, title):
    return ["cbe"] if is_cbe_title(title) else ([primary_tab] if primary_tab else ["breaking"])


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
    url = canonical_url(url)

    if not is_arabic(title):
        return False, sent_hashes, recent_news

    # أولوية مطلقة للمركزي: لا تبويب آخر ولا فلتر مصدر يمنع الخبر.
    cbe_override = is_cbe_title(title)

    if not cbe_override and is_excluded(title, exclude):
        print(f"    ⛔ مستبعد: {title[:80]}")
        return False, sent_hashes, recent_news

    if not cbe_override and not passes_require_kw(title, require_kw or []):
        return False, sent_hashes, recent_news

    if published_at is not None and not is_recent(published_at):
        print(f"    ⏳ قديم: {title[:70]}")
        return False, sent_hashes, recent_news

    h = make_hash(title)
    if h in sent_hashes:
        print(f"    ♻️ Hash مكرر: {title[:70]}")
        return False, sent_hashes, recent_news

    dup, reason = is_duplicate(title, url, source_name, recent_news)
    if dup:
        print(f"    ♻️ مكرر ({reason}): {title[:70]}")
        return False, sent_hashes, recent_news

    tabs = get_tabs_for_title(primary_tab, title)
    msg = format_msg(title, url, source_name, tabs)

    if send(msg, parse_mode="HTML"):
        sent_hashes.add(h)
        saved = supabase_save_news(title, url, source_name, tabs, h)
        if not saved:
            print("    ⚠️ أُرسل لكن فشل حفظه في Supabase")
        recent_news.insert(0, {
            "title": title, "url": url, "source_name": source_name,
            "tabs": tabs,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"    {'🏛️ CBE override: ' if cbe_override else ''}✅ {title[:80]}")
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


def normalize_tabs_field(value):
    if isinstance(value, list):
        return [str(x) for x in value if x]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def item_cairo_dt(item):
    try:
        dt = datetime.fromisoformat(str(item.get("created_at", "")).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(CAIRO_TZ)
    except Exception:
        return None


def download_font():
    if os.path.exists(FONT_PATH):
        return True
    try:
        print("⬇️ جاري تحميل الخط العربي...")
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


def clean_pdf_text(text):
    return re.sub(r"[*_`#]+", "", str(text or "")).strip()


def pdf_write_wrapped(pdf, text, size=10, align="R", link=None, fill=False):
    pdf.set_font("Amiri", size=size)
    pdf.multi_cell(
        0, 6.5, ar(clean_pdf_text(text)),
        align=align, link=link or "", fill=fill
    )


def add_pdf_ai_analysis(pdf, analysis, heading):
    if not analysis:
        return
    pdf.set_text_color(26, 60, 94)
    pdf.set_font("Amiri", size=14)
    pdf.cell(0, 10, ar(heading), ln=True, align="R")
    for line in str(analysis).splitlines():
        line = clean_pdf_text(line)
        if not line:
            pdf.ln(2)
            continue
        pdf.set_text_color(40, 40, 40)
        pdf_write_wrapped(pdf, line, size=9)
        pdf.ln(0.5)
    pdf.ln(4)


def make_pdf_base(title, subtitle):
    from fpdf import FPDF
    if not download_font():
        raise RuntimeError("تعذر تحميل خط Amiri")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_font("Amiri", "", FONT_PATH, uni=True)
    pdf.add_page()

    pdf.set_fill_color(26, 60, 94)
    pdf.rect(0, 0, 210, 31, "F")
    pdf.set_font("Amiri", size=17)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(6)
    pdf.cell(0, 9, ar("رادار المخاطر المصري"), ln=True, align="C")
    pdf.set_font("Amiri", size=12)
    pdf.cell(0, 8, ar(title), ln=True, align="C")
    pdf.set_text_color(80, 80, 80)
    pdf.ln(8)
    pdf.set_font("Amiri", size=9)
    pdf.multi_cell(0, 6, ar(subtitle), align="R")
    pdf.ln(3)
    return pdf


def add_pdf_news_item(pdf, item, index=0):
    title = item.get("title", "")
    url = item.get("url", "")
    source = item.get("source_name", "")
    dt = item_cairo_dt(item)
    date_time = dt.strftime("%d/%m/%Y %H:%M") if dt else ""

    pdf.set_fill_color(245, 249, 252) if index % 2 == 0 else pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(26, 60, 94)
    pdf_write_wrapped(pdf, title, size=10, link=url, fill=True)
    pdf.set_text_color(110, 110, 110)
    pdf.set_font("Amiri", size=8.5)
    pdf.multi_cell(0, 5.5, ar(f"📰 {source}   |   🕒 {date_time}"), align="R")

    if url:
        pdf.set_text_color(70, 70, 120)
        pdf.set_font("Amiri", size=7.5)
        # الرابط ظاهر وقابل للنقر.
        pdf.multi_cell(0, 5, url, align="L", link=url)
    pdf.ln(2)


def finish_pdf(pdf, footer_text):
    pdf.set_y(-14)
    pdf.set_font("Amiri", size=7.5)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 7, ar(footer_text), align="C")
    return bytes(pdf.output())


def generate_daily_pdf(news_list, now_cairo, ai_analysis=None, title="تقرير الأخبار اليومي"):
    grouped = {}
    for item in news_list:
        for tab in normalize_tabs_field(item.get("tabs")):
            grouped.setdefault(tab, []).append(item)

    ordered = sorted(grouped, key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99)
    subtitle = (
        f"الفترة: آخر 24 ساعة حتى {now_cairo.strftime('%d/%m/%Y %H:%M')} بتوقيت القاهرة"
        f" | إجمالي الأخبار: {len(news_list)} | {len(grouped)} تبويبات"
    )
    pdf = make_pdf_base(title, subtitle)
    add_pdf_ai_analysis(pdf, ai_analysis, "التحليل المهني اليومي")

    for tab in ordered:
        items = sorted(
            grouped[tab],
            key=lambda x: item_cairo_dt(x) or datetime.min.replace(tzinfo=CAIRO_TZ)
        )
        pdf.set_fill_color(26, 60, 94)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Amiri", size=12)
        pdf.cell(0, 9, ar(f"{TAB_LABELS.get(tab, tab)} ({len(items)} خبر)"), ln=True, align="R", fill=True)
        pdf.ln(1)
        for i, item in enumerate(items):
            add_pdf_news_item(pdf, item, i)
        pdf.ln(3)

    return finish_pdf(
        pdf,
        f"رادار المخاطر — @egypt_risk_radar — {now_cairo.strftime('%d/%m/%Y')}"
    )


def generate_weekly_pdf(news_list, week_start, week_end, ai_analysis=None):
    from collections import defaultdict
    days = defaultdict(list)
    for item in news_list:
        dt = item_cairo_dt(item)
        days[dt.date() if dt else week_start].append(item)

    pdf = make_pdf_base(
        "تقرير الأخبار الأسبوعي",
        f"الأسبوع المكتمل: {week_start.strftime('%d/%m/%Y')} — "
        f"{week_end.strftime('%d/%m/%Y')} | إجمالي الأخبار: {len(news_list)}"
    )
    add_pdf_ai_analysis(pdf, ai_analysis, "التحليل المهني الأسبوعي")

    for day in sorted(days):
        day_items = sorted(
            days[day],
            key=lambda x: item_cairo_dt(x) or datetime.min.replace(tzinfo=CAIRO_TZ)
        )
        pdf.set_fill_color(70, 70, 70)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Amiri", size=13)
        pdf.cell(0, 10, ar(f"📅 {day.strftime('%d/%m/%Y')} — {len(day_items)} خبر"), ln=True, align="R", fill=True)
        pdf.ln(1)

        grouped = {}
        for item in day_items:
            for tab in normalize_tabs_field(item.get("tabs")):
                grouped.setdefault(tab, []).append(item)
        ordered = sorted(grouped, key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99)
        for tab in ordered:
            pdf.set_text_color(26, 60, 94)
            pdf.set_font("Amiri", size=10.5)
            pdf.cell(0, 7, ar(f"{TAB_LABELS.get(tab, tab)} ({len(grouped[tab])})"), ln=True, align="R")
            for i, item in enumerate(grouped[tab]):
                add_pdf_news_item(pdf, item, i)
        pdf.ln(4)

    return finish_pdf(
        pdf,
        f"رادار المخاطر — @egypt_risk_radar — "
        f"{week_start.strftime('%d/%m/%Y')} إلى {week_end.strftime('%d/%m/%Y')}"
    )


def send_pdf_to_chat(pdf_bytes, chat_id, filename, caption):
    if not BOT_TOKEN:
        return False
    try:
        r = requests.post(
            f"{API_URL}/sendDocument",
            files={"document": (filename, io.BytesIO(pdf_bytes), "application/pdf")},
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"},
            timeout=60,
        )
        if r.status_code == 200:
            print(f"✅ PDF اتبعت إلى {chat_id}")
            return True
        print(f"❌ PDF Telegram {r.status_code}: {r.text[:300]}")
    except Exception as e:
        print(f"❌ PDF send error: {e}")
    return False


def send_pdf(pdf_bytes, date_str):
    return send_pdf_to_chat(
        pdf_bytes, CHANNEL_ID,
        f"رادار_المخاطر_{date_str.replace('/', '-')}.pdf",
        f"📋 *تقرير أخبار اليوم — {escape_md(date_str)}*\n"
        f"_جميع أخبار الـ24 ساعة الماضية، بدون استثناء، مصنفة بالتبويبات._\n\n"
        f"🛡 @egypt\\_risk\\_radar"
    )


def run_pdf_report():
    print("📋 جاري إعداد التقرير اليومي PDF...")
    news = supabase_get_news_for_pdf()
    if news is None:
        print("❌ تعذر قراءة الأخبار من Supabase")
        return
    if not news:
        print("لا توجد أخبار في الـ24 ساعة الماضية")
        return
    now = datetime.now(timezone.utc).astimezone(CAIRO_TZ)
    try:
        pdf_bytes = generate_daily_pdf(news, now)
        send_pdf(pdf_bytes, now.strftime("%d/%m/%Y"))
    except Exception as e:
        print(f"❌ PDF error: {e}")


def run_weekly_pdf_report():
    print("📅 جاري إعداد PDF الأسبوعي...")
    news = supabase_get_last_7days()
    if news is None:
        print("❌ تعذر قراءة الأخبار من Supabase")
        return
    if not news:
        print("لا توجد أخبار في الأسبوع المكتمل")
        return
    _, _, start_date, end_date = get_previous_completed_week_bounds()
    try:
        pdf_bytes = generate_weekly_pdf(news, start_date, end_date)
        filename = f"رادار_المخاطر_أسبوع_{start_date.strftime('%Y-%m-%d')}.pdf"
        caption = (
            f"📅 *التقرير الأسبوعي — {escape_md(start_date.strftime('%d/%m/%Y'))}"
            f" — {escape_md(end_date.strftime('%d/%m/%Y'))}*\n"
            f"_جميع أخبار الأسبوع، بدون استثناء._\n\n🛡 @egypt\\_risk\\_radar"
        )
        send_pdf_to_chat(pdf_bytes, CHANNEL_ID, filename, caption)
    except Exception as e:
        print(f"❌ Weekly PDF error: {e}")


RISK_KW = {
    "المركزي": 8, "فائدة": 7, "سيولة": 8, "احتياطي": 8, "دولار": 6,
    "تعثر": 9, "متعث": 9, "npl": 10, "ديون": 7, "إفلاس": 10, "إعسار": 10,
    "تخلف عن السداد": 10, "مخصصات": 8, "اضمحلال": 8, "ائتمان": 6,
    "قرض": 5, "تمويل": 5, "احتيال": 10, "تزوير": 10, "نصب": 9, "اختلاس": 10,
    "غسل الأموال": 10, "aml": 10, "عقوبات": 8, "امتثال": 7, "اختراق": 10,
    "هجوم سيبراني": 10, "تسريب بيانات": 10, "تعطل": 7, "انقطاع": 7,
    "استمرارية الأعمال": 8, "إغلاق": 7, "حريق": 8, "تضخم": 7, "وقود": 6,
    "ركود": 8, "انكماش": 8, "استيراد": 5, "تصدير": 5, "سعر الصرف": 7,
    "خفض التصنيف": 9, "خسائر": 8, "تصفية": 9,
}


def group_by_tab(news_list):
    grouped = {}
    for item in news_list:
        for tab in normalize_tabs_field(item.get("tabs")):
            grouped.setdefault(tab, []).append(item.get("title", ""))
    return grouped


def risk_score(title):
    n = normalize_arabic(title)
    return sum(w for kw, w in RISK_KW.items() if normalize_arabic(kw) in n)


def select_ai_news(news_list, limit=70):
    selected, seen_tabs = [], set()
    for item in sorted(
        news_list,
        key=lambda x: item_cairo_dt(x) or datetime.min.replace(tzinfo=CAIRO_TZ),
        reverse=True,
    ):
        tabs = normalize_tabs_field(item.get("tabs"))
        if tabs and tabs[0] not in seen_tabs:
            selected.append(item)
            seen_tabs.add(tabs[0])

    remaining = [x for x in news_list if x not in selected]
    remaining.sort(
        key=lambda x: (
            risk_score(x.get("title", "")),
            item_cairo_dt(x) or datetime.min.replace(tzinfo=CAIRO_TZ),
        ),
        reverse=True,
    )
    selected.extend(remaining[:max(0, limit - len(selected))])
    return selected[:limit]


def build_ai_prompt(period_label, period_text, news_list, weekly=False):
    selected = select_ai_news(news_list)
    lines = []
    for item in selected:
        dt = item_cairo_dt(item)
        dt_text = dt.strftime("%d/%m %H:%M") if dt else ""
        tabs = normalize_tabs_field(item.get("tabs"))
        tab = TAB_LABELS.get(tabs[0], tabs[0]) if tabs else "غير مصنف"
        lines.append(
            f"[{dt_text}] [{tab}] [{item.get('source_name','')}] {item.get('title','')}"
        )

    weekly_extra = """
للتقرير الأسبوعي أضف:
- الاتجاهات المتكررة خلال الأسبوع.
- الإشارات التي تصاعدت أو تراجعت.
- القطاعات ذات الضغوط المتكررة.
- Watchlist للأسبوع القادم.
- هل توجد إشارات تستدعي Scenario Analysis أو RCSA Review أو Portfolio Review؟
""" if weekly else ""

    return (
        f"أنت Senior Risk Analyst في بنك مصري كبير.\n"
        f"الفترة: {period_label} — {period_text}\n"
        f"إجمالي الأخبار المسجلة: {len(news_list)}. تم تمرير عينة عالية القيمة فقط وعددها {len(selected)}.\n\n"
        "الأخبار:\n" + "\n".join(lines) + "\n\n"
        "حلّلها عملياً من منظور:\n"
        "- Banking Investigations / CPV / Inquiries\n"
        "- Credit Risk / Underwriting\n"
        "- Fraud Prevention / Fraud Risk\n"
        "- Operational Risk / RCSA / KRI / KCI\n"
        "- Portfolio Risk / Concentration\n"
        "- Collections / NPL\n"
        "- Compliance / AML\n"
        "- Treasury / FX / Liquidity\n"
        "- Sector Risk\n"
        "- Business Continuity / IT / Cyber Risk\n\n"
        "قواعد التحليل:\n"
        "1. ميّز بين ما تدل عليه الأخبار مباشرة وبين الاستنتاج المحتمل.\n"
        "2. لا تخترع أرقاماً أو وقائع غير موجودة.\n"
        "3. إذا كانت الإشارة ضعيفة، قل إنها تحتاج تحققاً.\n"
        "4. لا تكرر الأخبار؛ استخرج الإشارات المشتركة.\n"
        "5. أعطِ إجراءات قابلة للتنفيذ داخل بنك.\n"
        "6. صنّف Early Warning Signals إلى High / Medium / Low عند وجود أساس.\n"
        + weekly_extra +
        "\nاكتب بالعربية المهنية وابدأ مباشرة.\n"
        "هيكل الإخراج:\n"
        "1. الصورة التنفيذية للمخاطر\n"
        "2. أبرز الإشارات المباشرة\n"
        "3. Early Warning Signals — High / Medium / Low\n"
        "4. CBE / Monetary / FX / Liquidity implications\n"
        "5. Credit / Portfolio / NPL implications\n"
        "6. CPV / Banking Investigations / Inquiries implications\n"
        "7. Fraud / AML / Compliance implications\n"
        "8. Operational / RCSA / BCM / IT implications\n"
        "9. Sector Risk\n"
        "10. Recommended Actions حسب الوظيفة\n"
        "11. Escalation & Watchlist\n"
        + ("12. Weekly Trends & Next-Week Outlook\n" if weekly else "")
    )


def ask_gemini(prompt):
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY غير موجود")
        return None
    for attempt in range(1, 3):
        try:
            r = requests.post(
                GEMINI_ENDPOINT,
                params={"key": GEMINI_KEY},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 3500},
                },
                timeout=90,
            )
            if r.status_code == 200:
                candidates = r.json().get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    answer = "".join(p.get("text", "") for p in parts if p.get("text"))
                    if answer.strip():
                        return answer.strip()
                print("Gemini: لا يوجد محتوى")
                return None
            print(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            print(f"Gemini error attempt {attempt}: {e}")
        if attempt < 2:
            time.sleep(2)
    return None


def send_report_to_telegram(title, analysis, date_str, period_icon="📊"):
    if not analysis:
        return False
    header = (
        f"{period_icon} *{escape_md(title)}*\n"
        f"{'━'*20}\n📅 {escape_md(date_str)}\n{'━'*20}\n\n"
    )
    footer = f"\n\n{'━'*20}\n🛡 @egypt\\_risk\\_radar"
    return send(header + escape_md(str(analysis).replace("**", "")) + footer, parse_mode="Markdown")


def scheduled_run():
    return os.environ.get("GITHUB_EVENT_NAME", "").strip().lower() == "schedule"


def report_already_done(tab_key, digest_date):
    if not supabase_ready():
        return False
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/digest",
            params={"select": "tab_key", "tab_key": f"eq.{tab_key}",
                    "digest_date": f"eq.{digest_date}", "limit": "1"},
            headers=sb_headers(), timeout=10,
        )
        if r.status_code == 200:
            return bool(r.json())
        print(f"⚠️ report marker HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"⚠️ report marker error: {e}")
    return False


def run_daily_digest():
    """موجز 10 مساءً: Gemini واحد فقط."""
    print("📊 جاري إعداد الموجز اليومي...")
    news = supabase_get_last_24h()
    if news is None:
        print("❌ تعذر قراءة Supabase")
        return
    if not news:
        print("لا توجد أخبار في الـ24 ساعة الماضية")
        return

    grouped = group_by_tab(news)
    now = datetime.now(timezone.utc).astimezone(CAIRO_TZ)
    date_str = now.strftime("%d/%m/%Y")

    send(
        f"🗞️ *موجز أنباء وتحليلات — {escape_md(date_str)}*\n"
        f"_تقرير يومي لمتخصصي الائتمان والمخاطر_\n\n"
        f"رصدنا *{len(news)}* خبراً في *{len(grouped)}* تبويبات.\n"
        f"🛡 @egypt\\_risk\\_radar",
        parse_mode="Markdown",
    )

    ordered = sorted(grouped, key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99)
    blocks = []
    for tab in ordered:
        blocks.append(
            f"*{escape_md(TAB_LABELS.get(tab, tab))}* — {len(grouped[tab])} خبر\n" +
            "\n".join(f"• {escape_md(h)}" for h in grouped[tab][:12])
        )
    send("\n\n".join(blocks) + "\n\n🛡 @egypt\\_risk\\_radar", parse_mode="Markdown")

    print("  🤖 Gemini: تحليل يومي موحد (1 call)...")
    analysis = ask_gemini(
        build_ai_prompt("الموجز اليومي", f"{date_str} — آخر 24 ساعة", news, weekly=False)
    )
    if analysis:
        send_report_to_telegram("تحليل المخاطر اليومي", analysis, date_str, "🔍")
        supabase_save_digest("daily_digest", "الموجز اليومي", analysis, len(news), now.strftime("%Y-%m-%d"))

    send(
        f"✅ *انتهى موجز {escape_md(date_str)}*\n"
        f"عدد الأخبار: {len(news)}\n\n🛡 @egypt\\_risk\\_radar",
        parse_mode="Markdown",
    )


def run_daily_report():
    print("📊 جاري إعداد التقرير اليومي الشامل...")
    now = datetime.now(timezone.utc).astimezone(CAIRO_TZ)
    date_key = now.strftime("%Y-%m-%d")

    if scheduled_run() and report_already_done("report_daily", date_key):
        print(f"⏭️ التقرير اليومي {date_key} تم إرساله مسبقاً")
        return

    news = supabase_get_news_for_pdf()
    if news is None:
        print("❌ تعذر قراءة الأخبار من Supabase")
        return
    if not news:
        print("لا توجد أخبار في آخر 24 ساعة")
        return

    grouped = group_by_tab(news)
    warning_count = len(grouped.get("warning", []))
    credit_count = len(grouped.get("credit", [])) + len(grouped.get("banks", []))
    top_sector = max(
        ((k, v) for k, v in grouped.items() if k.startswith("sector_")),
        key=lambda x: len(x[1]), default=("—", [])
    )
    date_str = now.strftime("%d/%m/%Y %H:%M")

    send(
        f"📊 *التقرير اليومي — {escape_md(date_str)}*\n{'━'*20}\n"
        f"📰 إجمالي الأخبار: *{len(news)}*\n"
        f"⚠️ إنذار مبكر: *{warning_count}*\n"
        f"💰 ائتمان + بنوك: *{credit_count}*\n"
        f"🏭 الأكثر نشاطاً: *{escape_md(TAB_LABELS.get(top_sector[0], top_sector[0]))}* ({len(top_sector[1])})\n"
        f"{'━'*20}\n🛡 @egypt\\_risk\\_radar",
        parse_mode="Markdown",
    )

    print("  🤖 Gemini: التقرير اليومي الموحد (1 call)...")
    analysis = ask_gemini(
        build_ai_prompt("تقرير يومي شامل", f"آخر 24 ساعة حتى {date_str}", news, weekly=False)
    )
    if analysis:
        send_report_to_telegram("التحليل والتوصيات اليومية", analysis, date_str, "🔍")

    try:
        pdf_bytes = generate_daily_pdf(news, now, ai_analysis=analysis)
        pdf_ok = send_pdf(pdf_bytes, now.strftime("%d/%m/%Y"))
    except Exception as e:
        print(f"❌ Daily report PDF error: {e}")
        pdf_ok = False

    if pdf_ok and scheduled_run():
        supabase_save_digest("report_daily", "التقرير اليومي الآلي", "sent", len(news), date_key)
    print("✅ انتهى التقرير اليومي")


def run_weekly_report():
    print("📅 جاري إعداد التقرير الأسبوعي...")
    start_utc, end_utc, start_date, end_date = get_previous_completed_week_bounds()
    marker = start_date.strftime("%Y-%m-%d")

    if scheduled_run() and report_already_done("report_weekly", marker):
        print(f"⏭️ التقرير الأسبوعي الذي يبدأ {marker} تم إرساله مسبقاً")
        return

    news = supabase_get_news_between(start_utc, end_utc, "title,url,source_name,tabs,created_at")
    if news is None:
        print("❌ تعذر قراءة الأخبار من Supabase")
        return
    if not news:
        print("لا توجد أخبار في الأسبوع المكتمل")
        return

    grouped = group_by_tab(news)
    daily_counts = {}
    for item in news:
        dt = item_cairo_dt(item)
        if dt:
            key = dt.strftime("%d/%m")
            daily_counts[key] = daily_counts.get(key, 0) + 1

    period = f"{start_date.strftime('%d/%m/%Y')} — {end_date.strftime('%d/%m/%Y')}"
    daily_summary = " | ".join(f"{d}: {c}" for d, c in sorted(daily_counts.items()))

    send(
        f"📅 *التقرير الأسبوعي — {escape_md(period)}*\n{'━'*20}\n"
        f"📰 إجمالي الأخبار: *{len(news)}*\n"
        f"📊 التوزيع اليومي: {escape_md(daily_summary)}\n"
        f"⚠️ إنذارات: *{len(grouped.get('warning', []))}*\n"
        f"{'━'*20}\n🛡 @egypt\\_risk\\_radar",
        parse_mode="Markdown",
    )

    print("  🤖 Gemini: التقرير الأسبوعي الموحد (1 call)...")
    analysis = ask_gemini(
        build_ai_prompt("تقرير أسبوعي شامل", period, news, weekly=True)
    )
    if analysis:
        send_report_to_telegram("التحليل والتوقعات الأسبوعية", analysis, period, "📅")

    try:
        pdf_bytes = generate_weekly_pdf(news, start_date, end_date, ai_analysis=analysis)
        filename = f"رادار_المخاطر_أسبوع_{start_date.strftime('%Y-%m-%d')}.pdf"
        caption = (
            f"📅 *التقرير الأسبوعي — {escape_md(period)}*\n"
            f"_جميع أخبار الأسبوع، بدون استثناء، مرتبة يومياً ومصنفة._\n\n"
            f"🛡 @egypt\\_risk\\_radar"
        )
        pdf_ok = send_pdf_to_chat(pdf_bytes, CHANNEL_ID, filename, caption)
    except Exception as e:
        print(f"❌ Weekly report PDF error: {e}")
        pdf_ok = False

    if pdf_ok and scheduled_run():
        supabase_save_digest("report_weekly", "التقرير الأسبوعي الآلي", "sent", len(news), marker)
    print("✅ انتهى التقرير الأسبوعي")


def supabase_get_digest_content(tab_key, digest_date):
    if not supabase_ready():
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/digest",
            params={"select": "content", "tab_key": f"eq.{tab_key}",
                    "digest_date": f"eq.{digest_date}", "limit": "1"},
            headers=sb_headers(), timeout=10,
        )
        if r.status_code == 200:
            rows = r.json()
            return rows[0].get("content") if rows else None
    except Exception as e:
        print(f"Supabase digest content error: {e}")
    return None


def send_to_chat(chat_id, text, parse_mode="HTML", max_retries=3):
    if not BOT_TOKEN or not text:
        return False
    chunks, t = [], str(text)
    while len(t) > MAX_TG_MSG:
        cut = t.rfind("\n", 0, MAX_TG_MSG)
        if cut < MAX_TG_MSG * 0.5:
            cut = MAX_TG_MSG
        chunks.append(t[:cut])
        t = t[cut:].lstrip()
    if t:
        chunks.append(t)

    for chunk in chunks:
        sent = False
        for attempt in range(1, max_retries + 1):
            payload = {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            try:
                r = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=TELEGRAM_TIMEOUT)
                if r.status_code == 200:
                    sent = True
                    break
                if r.status_code == 429:
                    try:
                        wait = int(r.json().get("parameters", {}).get("retry_after", 5))
                    except Exception:
                        wait = 5
                    time.sleep(min(max(wait, 2), 60))
                    continue
                if r.status_code == 400 and parse_mode:
                    r2 = requests.post(
                        f"{API_URL}/sendMessage",
                        json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                        timeout=TELEGRAM_TIMEOUT,
                    )
                    if r2.status_code == 200:
                        sent = True
                        break
            except Exception as e:
                print(f"⚠️ private Telegram error attempt {attempt}: {e}")
            time.sleep(min(attempt * 2, 10))
        if not sent:
            return False
    return True


def telegram_prepare_polling():
    """GitHub Actions يستخدم getUpdates، لذلك أزل أي webhook قديم دون حذف الرسائل المعلقة."""
    try:
        r = requests.get(f"{API_URL}/getWebhookInfo", timeout=15)
        if r.status_code != 200:
            print(f"⚠️ getWebhookInfo {r.status_code}: {r.text[:250]}")
            return False
        info = r.json().get("result", {}) or {}
        webhook_url = info.get("url", "")
        if webhook_url:
            print(f"⚠️ Webhook موجود ({webhook_url}) — تحويل البوت إلى polling...")
            d = requests.post(
                f"{API_URL}/deleteWebhook",
                json={"drop_pending_updates": False},
                timeout=15,
            )
            if d.status_code == 200 and d.json().get("ok"):
                print("✅ تم حذف الـ webhook مع الاحتفاظ بالتحديثات المعلقة")
                return True
            print(f"❌ فشل deleteWebhook {d.status_code}: {d.text[:300]}")
            return False
        return True
    except Exception as e:
        print(f"⚠️ Telegram polling preparation error: {e}")
        return False


def telegram_get_updates(offset=None, limit=100):
    params = {
        "timeout": 1,
        "limit": limit,
        "allowed_updates": '["message","edited_message","channel_post","edited_channel_post"]',
    }
    if offset is not None:
        params["offset"] = offset
    try:
        r = requests.get(f"{API_URL}/getUpdates", params=params, timeout=10)
        if r.status_code == 409:
            print("⚠️ Telegram 409: webhook/another getUpdates consumer.")
            return None
        if r.status_code != 200:
            print(f"⚠️ getUpdates {r.status_code}: {r.text[:250]}")
            return None
        return r.json().get("result", [])
    except Exception as e:
        print(f"⚠️ getUpdates error: {e}")
        return None


def poll_dailyrep_commands():
    """dailyrep للخاص والقناة/الجروب، وبدون Gemini."""
    if not supabase_ready():
        print("⚠️ dailyrep متوقف: يحتاج Supabase لحفظ Telegram offset.")
        return

    state = supabase_get_digest_content("telegram_update_offset", "state")
    try:
        offset = int(state) if state else None
    except Exception:
        offset = None

    updates = telegram_get_updates(offset=offset)
    if updates is None or not updates:
        return

    admin_ids = {x.strip() for x in os.environ.get("ADMIN_CHAT_IDS", "").split(",") if x.strip()}
    max_update_id = max(u.get("update_id", 0) for u in updates)

    for update in updates:
        # دعم الأمر من الخاص ومن داخل القناة/الجروب.
        # Telegram يضع منشورات القناة في channel_post وليس message.
        message = (
            update.get("message")
            or update.get("edited_message")
            or update.get("channel_post")
            or update.get("edited_channel_post")
        )
        if not message:
            continue

        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        chat_type = chat.get("type")

        # ADMIN_CHAT_IDS يقيّد الرسائل الخاصة فقط؛ أما القناة التي ينشر فيها
        # البوت نفسه فيُسمح لها بتنفيذ dailyrep مباشرة.
        if chat_type == "private":
            if admin_ids and chat_id not in admin_ids:
                continue
        elif chat_type not in ("channel", "group", "supergroup"):
            continue

        text = str(message.get("text") or message.get("caption") or "").strip()
        if not text:
            continue
        first = text.split()[0].lower()
        command = "/dailyrep" if first.startswith("/dailyrep@") else first
        if command not in ("dailyrep", "/dailyrep"):
            continue

        print(f"📋 dailyrep requested by {chat_id}")
        send_to_chat(chat_id, "📋 جاري تجهيز تقرير أخبار اليوم حتى الآن — بدون Gemini...", parse_mode="Markdown")

        now = datetime.now(timezone.utc).astimezone(CAIRO_TZ)
        start_cairo = now.replace(hour=0, minute=0, second=0, microsecond=0)
        news = supabase_get_news_between(
            start_cairo.astimezone(timezone.utc),
            now.astimezone(timezone.utc),
            "title,url,source_name,tabs,created_at",
        )
        if news is None:
            send_to_chat(chat_id, "❌ تعذر قراءة الأخبار من Supabase.", parse_mode=None)
            continue
        if not news:
            send_to_chat(chat_id, "لا توجد أخبار مسجلة اليوم حتى الآن.", parse_mode=None)
            continue

        try:
            pdf_bytes = generate_daily_pdf(
                news, now, ai_analysis=None, title="تقرير أخبار اليوم حتى الآن"
            )
            filename = f"رادار_المخاطر_dailyrep_{now.strftime('%Y-%m-%d')}.pdf"
            caption = (
                f"📋 *dailyrep — {escape_md(now.strftime('%d/%m/%Y %H:%M'))}*\n"
                f"_كل الأخبار المسجلة من 00:00 حتى الآن، بدون Gemini._\n"
                f"📰 {len(news)} خبر\n\n🛡 @egypt\\_risk\\_radar"
            )
            if not send_pdf_to_chat(pdf_bytes, chat_id, filename, caption):
                send_to_chat(chat_id, "❌ تم تجهيز الـPDF لكن فشل إرساله إلى Telegram. راجع Log التشغيل.", parse_mode=None)
        except Exception as e:
            print(f"❌ dailyrep PDF error: {e}")
            send_to_chat(chat_id, f"❌ فشل إنشاء PDF: {e}", parse_mode=None)

    supabase_save_digest(
        "telegram_update_offset", "Telegram update offset",
        str(max_update_id + 1), 0, "state"
    )


# ══════════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ══════════════════════════════════════════════════════════════════
def run():
    print("\n══════════════════════════════════════════")
    print("🛡 رادار المخاطر المصري")
    print("══════════════════════════════════════════")

    mode = os.environ.get("RUN_MODE", "news").strip().lower()
    print(f"⚙️  RUN_MODE = {mode}")

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN غير موجود — إيقاف")
        return
    if not telegram_bot_ok():
        print("❌ BOT_TOKEN غير صالح — إيقاف")
        return

    # هذا البوت يعمل من GitHub Actions؛ يجب أن يكون Telegram في polling mode.
    telegram_prepare_polling()

    # افحص الأوامر أولاً حتى لا تنتظر نهاية جمع الأخبار.
    poll_dailyrep_commands()

    if mode == "digest":
        run_daily_digest()
        return
    if mode == "report_daily":
        run_daily_report()
        return
    if mode == "report_weekly":
        run_weekly_report()
        return
    if mode == "pdf":
        run_pdf_report()
        return
    if mode == "weekly_pdf":
        run_weekly_pdf_report()
        return

    print("\n📦 جاري تحميل الأخبار المرسلة من Supabase...")
    sent_hashes = supabase_get_hashes()
    if sent_hashes is None:
        print("❌ ABORT: Supabase غير متاح — وقف منعاً للتكرار")
        return

    recent_news = supabase_get_recent_news_for_dedupe()
    if recent_news is None:
        print("❌ ABORT: تعذر قراءة ذاكرة التكرار من Supabase")
        return

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
        print(f"\n  🕷️ Scraping: {src['name']}...")
        try:
            count, sent_hashes, recent_news = fetch_scrape(src, sent_hashes, recent_news)
            new_count += count
            print(f"     → {count} خبر جديد")
        except Exception as e:
            print(f"     ❌ خطأ غير متوقع: {e}")

    print("\n══════════════════════════════════════════")
    print(f"✅ تم نشر {new_count} خبر جديد")
    print("══════════════════════════════════════════\n")

    # تنفيذ /dailyrep بعد جمع أخبار الدورة الحالية.
    poll_dailyrep_commands()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n⛔ تم إيقاف التشغيل يدوياً")
    except Exception as e:
        print(f"\n❌ خطأ رئيسي: {type(e).__name__}: {e}")
        raise
