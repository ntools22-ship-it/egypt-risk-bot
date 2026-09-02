import feedparser
import requests
import hashlib
import time
import os
import io
import re
import difflib

from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse, parse_qs, unquote

from bs4 import BeautifulSoup


# ══════════════════════════════════════════════════════════════════
# إعدادات
# ══════════════════════════════════════════════════════════════════
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
CHANNEL_ID   = "@egypt_risk_radar"
API_URL      = f"https://api.telegram.org/bot{BOT_TOKEN}"
GEMINI_URL   = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
)
FONT_PATH = "/tmp/Amiri-Regular.ttf"
FONT_URL  = "https://github.com/aliftype/amiri/raw/main/fonts/Amiri-Regular.ttf"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}


# ══════════════════════════════════════════════════════════════════
# كلمات مستبعدة عالمياً
# ══════════════════════════════════════════════════════════════════
EXCLUDE_KW = [
    "مواعيد قطارات", "مواعيد القطار", "مواعيد القطارات",
    "جدول قطارات", "جدول القطارات", "أسعار تذاكر القطارات",
    "اسعار تذاكر القطارات", "حجز تذاكر القطارات",
    "حجز تذاكر القطار", "محطات القطارات", "محطة القطار",
    "قطارات اليوم", "القطار اليوم", "قطار اليوم",
    "حركة القطارات", "تأخيرات القطارات", "تأخير القطارات",
    "مواعيد المترو", "مواعيد الأتوبيسات", "مواعيد الاتوبيسات",
    "جدول المترو", "مواعيد وسائل النقل",
]

# كلمات تُشير لتحديث جديد (يُسمح بنشره حتى لو العنوان مشابه)
UPDATE_KW = [
    "ارتفاع عدد", "حصيلة", "حصيلة جديدة", "تطورات",
    "آخر التطورات", "تحديث", "تفاصيل جديدة", "كشف سبب",
    "كشفت التحقيقات", "التحقيقات", "النيابة", "ضبط",
    "القبض على", "إصابة", "إصابات", "وفاة", "وفيات",
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
        "tab": "banks", "exclude": ["سعر"], "require_kw": [],
    },
    {
        "id": "masrafeyoun_banks", "name": "المصرفيون",
        "url": "https://masrafeyoun.ebi.gov.eg/category/banksnews/feed/",
        "tab": "banks", "exclude": [], "require_kw": [],
    },
    {
        "id": "hapi_credit", "name": "حابي - تمويل",
        "url": "https://hapijournal.com/category/%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/",
        "tab": "credit", "exclude": [], "require_kw": [],
    },
    {
        "id": "motawwer_credit", "name": "المطور - تمويل",
        "url": "https://almotawwer.com/tag/%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%b9%d8%a7%d8%aa-%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%b1%d8%a9/feed/",
        "tab": "credit", "exclude": [], "require_kw": [],
    },
    {
        "id": "amwal_micro", "name": "أموال الغد - تمويل",
        "url": "https://amwalalghad.com/tag/%d9%85%d8%aa%d9%86%d8%a7%d9%87%d9%8a-%d8%a7%d9%84%d8%b5%d8%ba%d8%b1/feed/",
        "tab": "credit", "exclude": [], "require_kw": [],
    },
    {
        "id": "hapi_fx", "name": "حابي - دولار",
        "url": "https://hapijournal.com/tag/%d8%a3%d8%b3%d8%b9%d8%a7%d8%b1-%d8%a7%d9%84%d8%af%d9%88%d9%84%d8%a7%d8%b1/feed/",
        "tab": "fx", "exclude": [], "require_kw": [],
    },
    {
        "id": "skynews_business", "name": "سكاي نيوز - اقتصاد",
        "url": "https://www.skynewsarabia.com/rss/business.xml",
        "tab": "global", "exclude": [], "require_kw": [],
    },
    {
        "id": "borsaa_agri", "name": "البورصة نيوز - زراعة",
        "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b2%d8%b1%d8%a7%d8%b9%d8%a9/feed/",
        "tab": "sector_agri", "exclude": [], "require_kw": [],
    },
    {
        "id": "borsaa_industry", "name": "البورصة نيوز - صناعة",
        "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d8%a9/feed/",
        "tab": "sector_industry", "exclude": [], "require_kw": [],
    },
    {
        "id": "borsaa_realestate", "name": "البورصة نيوز - عقارات",
        "url": "https://www.alborsaanews.com/category/%d8%a7%d9%84%d8%b9%d9%82%d8%a7%d8%b1%d8%a7%d8%aa/feed/",
        "tab": "sector_realestate", "exclude": [], "require_kw": [],
    },
    {
        "id": "amwal_energy", "name": "أموال الغد - طاقة",
        "url": "https://amwalalghad.com/category/%d8%b7%d8%a7%d9%82%d8%a9/feed/",
        "tab": "sector_energy", "exclude": [], "require_kw": [],
    },
    {
        "id": "amwal_transport", "name": "أموال الغد - نقل",
        "url": "https://amwalalghad.com/category/%d9%86%d9%82%d9%84-%d9%88-%d9%85%d9%84%d8%a7%d8%ad%d8%a9/feed/",
        "tab": "sector_transport", "exclude": [], "require_kw": [],
    },
    {
        "id": "amwal_tech", "name": "أموال الغد - تكنولوجيا",
        "url": "https://amwalalghad.com/category/%d8%aa%d9%83%d9%86%d9%88%d9%84%d9%88%d8%ac%d9%8a%d8%a7-%d9%88%d8%a7%d8%aa%d8%b5%d8%a7%d9%84%d8%a7%d8%aa/feed/",
        "tab": "sector_tech", "exclude": [], "require_kw": [],
    },
    # مصادر عامة
    {
        "id": "hapi_all", "name": "حابي",
        "url": "https://hapijournal.com/feed/",
        "tab": None, "exclude": [], "require_kw": [],
    },
    {
        "id": "febanks_all", "name": "في البنوك",
        "url": "https://febanks.com/feed/",
        "tab": None, "exclude": [], "require_kw": [],
    },
    {
        "id": "borsaa_all", "name": "البورصة نيوز",
        "url": "https://www.alborsaanews.com/feed/",
        "tab": None, "exclude": [], "require_kw": [],
    },
    {
        "id": "masrafeyoun_all", "name": "المصرفيون",
        "url": "https://masrafeyoun.ebi.gov.eg/feed/",
        "tab": None, "exclude": [], "require_kw": [],
    },
]


# ══════════════════════════════════════════════════════════════════
# المصادر — Scraping
# ══════════════════════════════════════════════════════════════════
SCRAPE_SOURCES = [
    {
        "id": "independent_breaking",
        "name": "Independent عربي",
        "url": "https://www.independentarabia.com/tags/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A",
        "tab": "breaking", "base": "https://www.independentarabia.com",
        "exclude": [], "require_kw": [],
    },
    {
        "id": "economyplus_breaking",
        "name": "Economy Plus - أخبار",
        "url": "https://economyplusme.com/category/%d8%a3%d8%ae%d8%a8%d8%a7%d8%b1/",
        "tab": "breaking", "base": "https://economyplusme.com",
        "exclude": [], "require_kw": [],
    },
    {
        "id": "almal_cbe",
        "name": "المال - مركزي",
        "url": "https://almalnews.com/tag/%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A/",
        "tab": "cbe", "base": "https://almalnews.com",
        "exclude": [], "require_kw": [],
    },
    {
        "id": "masrawy_factory_fire",
        "name": "مصراوي - حريق مصنع",
        "url": "https://www.masrawy.com/search/0/%D8%AD%D8%B1%D9%8A%D9%82%20%D9%85%D8%B5%D9%86%D8%B9",
        "tab": "warning", "base": "https://www.masrawy.com",
        "exclude": [], "require_kw": ["حريق", "مصنع"],
    },
    {
        "id": "elbalad_factory_fire",
        "name": "البلد - حريق مصنع",
        "url": "https://www.elbalad.news/search/term?search=%D8%AD%D8%B1%D9%8A%D9%82-%D9%85%D8%B5%D9%86%D8%B9&pageIndex=1",
        "tab": "warning", "base": "https://www.elbalad.news",
        "exclude": [], "require_kw": ["حريق", "مصنع"],
    },
    {
        "id": "hapi_important_breaking",
        "name": "حابي - أهم الأخبار",
        "url": "https://hapijournal.com/tag/%d8%a3%d9%87%d9%85-%d8%a7%d9%84%d8%a3%d8%ae%d8%a8%d8%a7%d8%b1/",
        "tab": "breaking", "base": "https://hapijournal.com",
        "exclude": [], "require_kw": [],
    },
]


# ══════════════════════════════════════════════════════════════════
# تصنيفات وأولويات
# ══════════════════════════════════════════════════════════════════
TAB_LABELS = {
    "breaking":          "⚡ عاجل",
    "banks":             "🏦 أخبار البنوك",
    "credit":            "💰 تمويل وائتمان",
    "warning":           "⚠️ إنذار مبكر",
    "fx":                "💵 أسعار الدولار",
    "cbe":               "🏛️ أخبار المركزي",
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
# Supabase
# ══════════════════════════════════════════════════════════════════
def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def supabase_get_hashes():
    """
    يرجع set() لو نجح (حتى لو فاضية — أول تشغيل)
    يرجع None لو فشل الاتصال — يوقف البوت منعاً للتكرار
    """
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news?select=hash&created_at=gte.{since}",
            headers=sb_headers(), timeout=10,
        )
        if r.status_code == 200:
            hashes = {item["hash"] for item in r.json() if item.get("hash")}
            print(f"   ✅ {len(hashes)} hash من Supabase")
            return hashes
        print(f"   ❌ Supabase HTTP {r.status_code}: {r.text[:150]}")
        return None
    except Exception as e:
        print(f"   ❌ Supabase connection failed: {e}")
        return None


def supabase_get_recent_news_for_dedupe():
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news"
            f"?select=title,url,source_name,created_at"
            f"&created_at=gte.{since}&order=created_at.desc&limit=1000",
            headers=sb_headers(), timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        print(f"Supabase recent news HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"Supabase recent news error: {e}")
    return []


def supabase_save_news(title, url, source_name, tabs, h):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/news",
            headers={**sb_headers(), "Prefer": "resolution=ignore-duplicates"},
            json={"title": title, "url": url, "source_name": source_name, "tabs": tabs, "hash": h},
            timeout=10,
        )
        return r.status_code in (200, 201, 204)
    except Exception as e:
        print(f"Supabase save error: {e}")
        return False


def supabase_get_last_24h():
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news?select=title,tabs"
            f"&created_at=gte.{since}&order=created_at.asc",
            headers=sb_headers(), timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Supabase get_last_24h error: {e}")
    return []


def supabase_get_news_for_pdf():
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news"
            f"?select=title,url,source_name,tabs,created_at"
            f"&created_at=gte.{since}&order=created_at.asc",
            headers=sb_headers(), timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Supabase get_news_for_pdf error: {e}")
    return []


def supabase_save_digest(tab_key, tab_label, content, news_count, digest_date):
    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/digest"
            f"?tab_key=eq.{tab_key}&digest_date=eq.{digest_date}",
            headers=sb_headers(), timeout=10,
        )
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/digest",
            headers=sb_headers(),
            json={"tab_key": tab_key, "tab_label": tab_label,
                  "content": content, "news_count": news_count,
                  "digest_date": digest_date},
            timeout=10,
        )
        return r.status_code in (200, 201, 204)
    except Exception as e:
        print(f"Supabase save_digest error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# تنظيف ومقارنة النصوص
# ══════════════════════════════════════════════════════════════════
def normalize_arabic_text(text):
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    for old, new in {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"}.items():
        text = text.replace(old, new)
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def title_tokens(text):
    normalized = normalize_arabic_text(text)
    stop_words = {
        "مصر", "اليوم", "غدا", "المصري", "المصرية",
        "في", "من", "على", "عن", "بعد", "قبل", "مع",
        "الى", "إلى", "هذا", "هذه", "التي", "الذي", "و", "ب", "ل", "ا",
    }
    return {w for w in normalized.split() if len(w) >= 2 and w not in stop_words}


def is_update_title(title):
    normalized = normalize_arabic_text(title)
    return any(normalize_arabic_text(k) in normalized for k in UPDATE_KW)


def titles_are_probable_duplicate(title1, title2):
    n1 = normalize_arabic_text(title1)
    n2 = normalize_arabic_text(title2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    if ratio >= 0.88:
        return True
    t1, t2 = title_tokens(title1), title_tokens(title2)
    if not t1 or not t2:
        return False
    common = t1 & t2
    overlap = len(common) / min(len(t1), len(t2))
    return overlap >= 0.80 and ratio >= 0.58


def is_excluded_title(title, extra_exclude=None):
    text = normalize_arabic_text(title)
    keywords = list(EXCLUDE_KW) + (extra_exclude or [])
    return any(normalize_arabic_text(kw) in text for kw in keywords)


def passes_require_kw(title, require_kw):
    if not require_kw:
        return True
    return all(kw in title for kw in require_kw)


def is_recent_datetime(dt, max_age_hours=24):
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = now - dt
    return timedelta(minutes=-10) < age <= timedelta(hours=max_age_hours)


def parse_any_datetime(value):
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
    for fmt in ["%d/%m/%Y %I:%M %p", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


# ══════════════════════════════════════════════════════════════════
# دوال مساعدة
# ══════════════════════════════════════════════════════════════════
def is_arabic(text):
    count = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    return count / max(len(text), 1) > 0.3


def get_tabs(title, summary, primary_tab):
    """التصنيف بناءً على المصدر فقط — tab=None يعني عاجل"""
    if primary_tab:
        return [primary_tab]
    return ["breaking"]


def make_hash(title):
    return hashlib.md5(normalize_arabic_text(title).encode("utf-8")).hexdigest()


def canonical_url(url):
    if not url:
        return ""
    url = url.strip()
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    tracking = ("utm_", "fbclid", "gclid", "ved", "ei")
    filtered = {k: v for k, v in query.items()
                if not any(k.lower().startswith(p) for p in tracking)}
    qs = "&".join(f"{k}={v}" for k in sorted(filtered) for v in filtered[k])
    return parsed._replace(query=qs, fragment="").geturl().rstrip("/")


def send(text):
    try:
        r = requests.post(
            f"{API_URL}/sendMessage",
            json={"chat_id": CHANNEL_ID, "text": text,
                  "parse_mode": "Markdown", "disable_web_page_preview": False},
            timeout=15,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"Send error: {e}")
        return False


def format_msg(title, url, source_name, tabs):
    tabs_str = "  |  ".join(TAB_LABELS.get(t, t) for t in tabs)
    safe = title.replace("*", "").replace("[", "").replace("]", "").replace("_", "\\_")
    return "\n".join([
        f"[{safe}]({url})",
        f"🗂  {tabs_str}",
        f"📰  {source_name}",
        "",
        "━━━━━━━━━━━━━━━━",
        "🛡 @egypt\\_risk\\_radar",
    ])


# ══════════════════════════════════════════════════════════════════
# منع التكرار
# ══════════════════════════════════════════════════════════════════
def is_duplicate_against_recent(title, url, recent_news):
    cur_url  = canonical_url(url)
    cur_norm = normalize_arabic_text(title)
    for item in recent_news:
        old_url  = canonical_url(item.get("url", ""))
        old_title = item.get("title", "")
        if cur_url and old_url and cur_url == old_url:
            return True, "نفس الرابط"
        old_norm = normalize_arabic_text(old_title)
        if cur_norm and old_norm and cur_norm == old_norm:
            return True, "نفس العنوان"
        if not is_update_title(title) and titles_are_probable_duplicate(title, old_title):
            return True, "عنوان مشابه جداً"
    return False, ""


# ══════════════════════════════════════════════════════════════════
# معالجة الخبر
# ══════════════════════════════════════════════════════════════════
def process_item(
    title, url, source_name, primary_tab,
    summary, exclude, sent_hashes, recent_news,
    published_at=None, require_kw=None,
):
    if not title or not url:
        return False, sent_hashes, recent_news

    title = title.strip()
    url   = canonical_url(url)

    if not is_arabic(title):
        return False, sent_hashes, recent_news

    if is_excluded_title(title, exclude):
        print(f"    ⛔ مستبعد: {title[:80]}")
        return False, sent_hashes, recent_news

    if not passes_require_kw(title, require_kw or []):
        return False, sent_hashes, recent_news

    # فلتر التاريخ — فقط لو published_at موجود
    if published_at is not None and not is_recent_datetime(published_at):
        print(f"    ⏳ خبر قديم: {title[:70]}")
        return False, sent_hashes, recent_news

    h = make_hash(title)
    if h in sent_hashes:
        print(f"    ♻️ مكرر Hash: {title[:70]}")
        return False, sent_hashes, recent_news

    duplicate, reason = is_duplicate_against_recent(title, url, recent_news)
    if duplicate:
        print(f"    ♻️ مكرر ({reason}): {title[:70]}")
        return False, sent_hashes, recent_news

    tabs = get_tabs(title, summary, primary_tab)
    if not tabs:
        return False, sent_hashes, recent_news

    if send(format_msg(title, url, source_name, tabs)):
        sent_hashes.add(h)
        supabase_save_news(title, url, source_name, tabs, h)
        recent_news.insert(0, {
            "title": title, "url": url,
            "source_name": source_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"    ✅ {title[:80]}")
        time.sleep(2)
        return True, sent_hashes, recent_news

    print(f"    ❌ فشل: {title[:60]}")
    return False, sent_hashes, recent_news


# ══════════════════════════════════════════════════════════════════
# RSS
# ══════════════════════════════════════════════════════════════════
def get_feed_entry_date(entry):
    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            try:
                from calendar import timegm
                return datetime.fromtimestamp(timegm(value), timezone.utc)
            except Exception:
                pass
    for field in ("published", "updated", "created"):
        dt = parse_any_datetime(entry.get(field))
        if dt:
            return dt
    return None


def fetch_rss(src, sent_hashes, recent_news):
    count = 0
    try:
        feed = feedparser.parse(src["url"])
        for entry in feed.entries[:15]:
            published_at = get_feed_entry_date(entry)
            ok, sent_hashes, recent_news = process_item(
                entry.get("title", "").strip(),
                entry.get("link", ""),
                src["name"], src["tab"],
                entry.get("summary", "")[:400],
                src.get("exclude", []),
                sent_hashes, recent_news,
                published_at=published_at,
                require_kw=src.get("require_kw", []),
            )
            if ok:
                count += 1
    except Exception as e:
        print(f"    ⚠️ RSS error {src['name']}: {e}")
    return count, sent_hashes, recent_news


# ══════════════════════════════════════════════════════════════════
# Scraping
# ══════════════════════════════════════════════════════════════════
def absolute_url(base, href):
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base, href)


def extract_listing_items(soup, base, limit=20):
    items = []
    seen  = set()

    for article in soup.find_all("article"):
        heading = article.find(["h1", "h2", "h3", "h4"])
        if not heading:
            continue
        anchor = heading.find("a", href=True) or article.find("a", href=True)
        if not anchor:
            continue
        title = heading.get_text(" ", strip=True)
        link  = canonical_url(absolute_url(base, anchor.get("href")))
        if len(title) < 15 or not link or link in seen:
            continue
        seen.add(link)
        items.append((title, link))
        if len(items) >= limit:
            break

    if len(items) < limit:
        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            anchor = heading.find("a", href=True)
            if not anchor:
                continue
            title = heading.get_text(" ", strip=True)
            link  = canonical_url(absolute_url(base, anchor.get("href")))
            if len(title) < 15 or not link or link in seen:
                continue
            seen.add(link)
            items.append((title, link))
            if len(items) >= limit:
                break

    return items


def fetch_scrape(src, sent_hashes, recent_news):
    """
    لا يطلب تاريخ المقال — يعتمد على hash + title dedup كضمان وحيد
    """
    count = 0
    try:
        r = requests.get(src["url"], headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"    ⚠️ HTTP {r.status_code}: {src['name']}")
            return 0, sent_hashes, recent_news

        soup  = BeautifulSoup(r.text, "html.parser")
        items = extract_listing_items(soup, src["base"], limit=20)

        print(f"    🔎 {len(items)} نتيجة في {src['name']}")

        for title, link in items:
            ok, sent_hashes, recent_news = process_item(
                title, link, src["name"], src["tab"],
                "",
                src.get("exclude", []),
                sent_hashes, recent_news,
                published_at=None,          # ← تجاهل فلتر التاريخ
                require_kw=src.get("require_kw", []),
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
    if not os.path.exists(FONT_PATH):
        print("⬇️  جاري تحميل الخط العربي...")
        r = requests.get(FONT_URL, timeout=30)
        with open(FONT_PATH, "wb") as f:
            f.write(r.content)
        print("✅ تم تحميل الخط")


def ar(text):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def generate_daily_pdf(news_list, now_egypt):
    from fpdf import FPDF
    download_font()

    date_str = now_egypt.strftime("%d/%m/%Y")
    grouped  = {}
    for item in news_list:
        for tab in item.get("tabs", []):
            grouped.setdefault(tab, []).append(item)
    ordered_tabs = sorted(
        grouped.keys(),
        key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99,
    )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("Amiri", "", FONT_PATH, uni=True)
    pdf.add_page()

    # رأس الصفحة
    pdf.set_fill_color(26, 60, 94)
    pdf.rect(0, 0, 210, 30, "F")
    pdf.set_font("Amiri", size=18)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(6)
    pdf.cell(0, 9, ar("رادار المخاطر — تقرير الأخبار اليومي"), ln=True, align="C")
    pdf.set_font("Amiri", size=11)
    pdf.cell(
        0, 8,
        ar(f"{date_str}  |  إجمالي: {len(news_list)} خبر في {len(grouped)} تبويبات"),
        ln=True, align="C",
    )
    pdf.ln(8)

    for tab in ordered_tabs:
        items     = grouped[tab]
        tab_label = TAB_LABELS.get(tab, tab)

        pdf.set_fill_color(26, 60, 94)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Amiri", size=13)
        pdf.cell(0, 10, ar(f"{tab_label} ({len(items)} خبر)"),
                 ln=True, align="R", fill=True)
        pdf.ln(1)

        for i, item in enumerate(items):
            title  = item.get("title", "")
            url    = item.get("url", "")
            source = item.get("source_name", "")
            try:
                dt = datetime.fromisoformat(
                    item["created_at"].replace("Z", "+00:00")
                ) + timedelta(hours=2)
                time_str = dt.strftime("%H:%M")
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


def send_pdf_to_telegram(pdf_bytes, date_str):
    try:
        filename = f"رادار_المخاطر_{date_str.replace('/', '-')}.pdf"
        caption  = (
            f"📋 *تقرير أخبار اليوم — {date_str}*\n"
            f"_جميع أخبار الـ 24 ساعة الماضية مصنفة بالتبويبات_\n\n"
            f"🛡 @egypt\\_risk\\_radar"
        )
        files = {"document": (filename, io.BytesIO(pdf_bytes), "application/pdf")}
        data  = {"chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "Markdown"}
        r = requests.post(f"{API_URL}/sendDocument", files=files, data=data, timeout=60)
        if r.status_code == 200:
            print("   ✅ PDF اتبعت على تليجرام")
            return True
        print(f"   ❌ Telegram PDF error {r.status_code}: {r.text[:300]}")
        return False
    except Exception as e:
        print(f"   ❌ Send PDF exception: {e}")
        return False


def run_pdf_report():
    print("📋 جاري إعداد التقرير اليومي PDF...")
    news = supabase_get_news_for_pdf()
    if not news:
        print("لا توجد أخبار في الـ 24 ساعة الماضية")
        return
    now_egypt = datetime.now(timezone.utc) + timedelta(hours=2)
    date_str  = now_egypt.strftime("%d/%m/%Y")
    print(f"  {len(news)} خبر — جاري توليد PDF...")
    pdf_bytes = generate_daily_pdf(news, now_egypt)
    send_pdf_to_telegram(pdf_bytes, date_str)


# ══════════════════════════════════════════════════════════════════
# الموجز اليومي
# ══════════════════════════════════════════════════════════════════
def ask_gemini(prompt):
    try:
        r = requests.post(
            GEMINI_URL,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


def group_by_tab(news_list):
    grouped = {}
    for item in news_list:
        for tab in item["tabs"]:
            grouped.setdefault(tab, []).append(item["title"])
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
    now      = datetime.now(timezone.utc) + timedelta(hours=2)
    date_str = now.strftime("%d/%m/%Y")

    send(
        f"🗞️ *موجز أنباء وتحليلات — {date_str}*\n"
        f"_تقرير يومي لمتخصصي الائتمان والمخاطر_\n\n"
        f"رصدنا اليوم *{len(news)} خبراً* في *{len(grouped)} قطاعات*\n\n"
        f"━━━━━━━━━━━━━━━━\n🛡 @egypt\\_risk\\_radar"
    )
    time.sleep(3)

    ordered_tabs = sorted(
        grouped.keys(),
        key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99,
    )
    for tab in ordered_tabs:
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
            f"{'━' * 16}\n*{tab_label}*  \\| {len(headlines)} خبر\n"
            f"{'━' * 16}\n\n{analysis}\n\n🛡 @egypt\\_risk\\_radar"
        )
        if len(msg) > 4000:
            msg = msg[:3990] + "...\n\n🛡 @egypt\\_risk\\_radar"
        send(msg)
        supabase_save_digest(tab, tab_label, analysis, len(headlines), now.strftime("%Y-%m-%d"))
        time.sleep(5)

    send(
        f"✅ *انتهى موجز {date_str}*\n\n"
        f"تابع أخبار السوق لحظة بلحظة\n🛡 @egypt\\_risk\\_radar"
    )
    print("✅ انتهى الموجز اليومي")


# ══════════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ══════════════════════════════════════════════════════════════════
def run():
    mode = os.environ.get("RUN_MODE", "news")

    if mode == "digest":
        run_daily_digest()
        return

    if mode == "pdf":
        run_pdf_report()
        return

    print("🛡 رادار المخاطر — يعمل...")
    print("📦 جاري تحميل الأخبار المرسلة من Supabase...")

    sent_hashes = supabase_get_hashes()

    # وقف فوري لو Supabase مش شغال — منعاً للتكرار
    if sent_hashes is None:
        print("❌ ABORT: Supabase غير متاح — وقف منعاً للتكرار")
        return

    recent_news = supabase_get_recent_news_for_dedupe()
    print(f"   {len(sent_hashes)} hash | {len(recent_news)} خبر في ذاكرة التكرار")

    new_count = 0

    for src in RSS_SOURCES:
        print(f"  📡 RSS: {src['name']}...")
        count, sent_hashes, recent_news = fetch_rss(src, sent_hashes, recent_news)
        new_count += count

    for src in SCRAPE_SOURCES:
        print(f"  🕷️ Scraping: {src['name']}...")
        count, sent_hashes, recent_news = fetch_scrape(src, sent_hashes, recent_news)
        new_count += count

    print(f"\n✅ تم نشر {new_count} خبر جديد")


if __name__ == "__main__":
    run()
