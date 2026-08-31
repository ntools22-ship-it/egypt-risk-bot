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
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
CHANNEL_ID   = "@egypt_risk_radar"

API_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
)

FONT_PATH = "/tmp/Amiri-Regular.ttf"
FONT_URL  = "https://github.com/aliftype/amiri/raw/main/fonts/Amiri-Regular.ttf"

# الأخبار التي لا نريد نشرها
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

# كلمات تحديثات حقيقية.
# إذا ظهر تحديث لنفس الحادث، لا نعتبره تكرارًا تلقائيًا.
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
        "url": "https://amwalalghad.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-%d9%85%d8%a7%d9%84%d9%8a%d8%a9/feed/",
        "tab": "banks",
        "exclude": ["سعر"]
    },
    {
        "id": "masrafeyoun_banks",
        "name": "المصرفيون",
        "url": "https://masrafeyoun.ebi.gov.eg/category/banksnews/feed/",
        "tab": "banks",
        "exclude": []
    },
    {
        "id": "hapi_credit",
        "name": "حابي - تمويل",
        "url": "https://hapijournal.com/category/%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/",
        "tab": "credit",
        "exclude": []
    },
    {
        "id": "motawwer_credit",
        "name": "المطور - تمويل",
        "url": "https://almotawwer.com/tag/%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%b9%d8%a7%d8%aa-%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%b1%d8%a9/feed/",
        "tab": "credit",
        "exclude": []
    },
    {
        "id": "amwal_micro",
        "name": "أموال الغد - تمويل",
        "url": "https://amwalalghad.com/tag/%d9%85%d8%aa%d9%86%d8%a7%d9%87%d9%8a-%d8%a7%d9%84%d8%b5%d8%ba%d8%b1/feed/",
        "tab": "credit",
        "exclude": []
    },
    {
        "id": "hapi_fx",
        "name": "حابي - دولار",
        "url": "https://hapijournal.com/tag/%d8%a3%d8%b3%d8%b9%d8%a7%d8%b1-%d8%a7%d9%84%d8%af%d9%88%d9%84%d8%a7%d8%b1/feed/",
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
    {
        "id": "borsaa_agri",
        "name": "البورصة نيوز - زراعة",
        "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b2%d8%b1%d8%a7%d8%b9%d8%a9/feed/",
        "tab": "sector_agri",
        "exclude": []
    },
    {
        "id": "borsaa_industry",
        "name": "البورصة نيوز - صناعة",
        "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d8%a9/feed/",
        "tab": "sector_industry",
        "exclude": []
    },
    {
        "id": "borsaa_realestate",
        "name": "البورصة نيوز - عقارات",
        "url": "https://www.alborsaanews.com/category/%d8%a7%d9%84%d8%b9%d9%82%d8%a7%d8%b1%d8%a7%d8%aa/feed/",
        "tab": "sector_realestate",
        "exclude": []
    },
    {
        "id": "amwal_energy",
        "name": "أموال الغد - طاقة",
        "url": "https://amwalalghad.com/category/%d8%b7%d8%a7%d9%82%d8%a9/feed/",
        "tab": "sector_energy",
        "exclude": []
    },
    {
        "id": "amwal_transport",
        "name": "أموال الغد - نقل",
        "url": "https://amwalalghad.com/category/%d9%86%d9%82%d9%84-%d9%88-%d9%85%d9%84%d8%a7%d8%ad%d8%a9/feed/",
        "tab": "sector_transport",
        "exclude": []
    },
    {
        "id": "amwal_tech",
        "name": "أموال الغد - تكنولوجيا",
        "url": "https://amwalalghad.com/category/%d8%aa%d9%83%d9%86%d9%88%d9%84%d9%88%d8%ac%d9%8a%d8%a7-%d9%88%d8%a7%d8%aa%d8%b5%d8%a7%d9%84%d8%a7%d8%aa/feed/",
        "tab": "sector_tech",
        "exclude": []
    },
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
        "id": "borsaa_all",
        "name": "البورصة نيوز",
        "url": "https://www.alborsaanews.com/feed/",
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
        "url": "https://www.independentarabia.com/tags/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A",
        "tab": "breaking",
        "base": "https://www.independentarabia.com",
        "exclude": []
    },
    {
        "id": "almal_cbe",
        "name": "المال - مركزي",
        "url": "https://almalnews.com/tag/%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A/",
        "tab": "cbe",
        "base": "https://almalnews.com",
        "exclude": []
    },

    # ──────────────────────────────────────────────────────────────
    # جديد: Economy Plus → عاجل
    # ──────────────────────────────────────────────────────────────
    {
        "id": "economyplus_breaking",
        "name": "Economy Plus - أخبار",
        "url": "https://economyplusme.com/category/%d8%a3%d8%ae%d8%a8%d8%a7%d8%b1/",
        "tab": "breaking",
        "base": "https://economyplusme.com",
        "exclude": []
    },

    # ──────────────────────────────────────────────────────────────
    # جديد: مصراوي → بحث حريق مصنع
    # ──────────────────────────────────────────────────────────────
    {
        "id": "masrawy_factory_fire",
        "name": "مصراوي - حريق مصنع",
        "url": "https://www.masrawy.com/search/0/%D8%AD%D8%B1%D9%8A%D9%82%20%D9%85%D8%B5%D9%86%D8%B9",
        "tab": "breaking",
        "base": "https://www.masrawy.com",
        "exclude": []
    },

    # ──────────────────────────────────────────────────────────────
    # جديد: Google News → بوابة الأهرام → حريق مصنع
    # ──────────────────────────────────────────────────────────────
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
        "allowed_domains": ["gate.ahram.org.eg"]
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


CBE_KW = [
    "البنك المركزي",
    "المركزي المصري",
    "لجنة السياسة النقدية",
    "سعر الفائدة",
    "الاحتياطي النقدي",
    "السياسة النقدية"
]

WARNING_KW = [
    "تعثر",
    "عجز عن السداد",
    "توقف عن السداد",
    "ديون متعثرة",
    "قروض متعثرة",
    "محفظة متعثرة",
    "ديون رديئة",
    "مخصصات",
    "شطب ديون",
    "استرداد ديون",
    "NPL",
    "إفلاس",
    "شهر إفلاس",
    "إعسار",
    "تصفية",
    "حراسة قضائية",
    "إدارة قضائية",
    "تعليق النشاط",
    "وقف الأعمال",
    "بيع أصول قسري",
    "حجز على أصول",
    "حجز على أموال",
    "دعوى قضائية",
    "غرامة مالية",
    "خفض تصنيف",
    "تخفيض تصنيف",
    "جدولة ديون",
    "إعادة جدولة",
    "أزمة سيولة",
    "خسائر متراكمة",
    "مخالفة مالية",
    "انهيار",
    "أزمة مالية"
]

CREDIT_KW = [
    "تسهيل ائتماني",
    "تسهيلات ائتمانية",
    "قرض",
    "تمويل",
    "خط ائتماني",
    "توريق",
    "سندات",
    "صكوك",
    "قرض مشترك",
    "تمويل مشترك",
    "اتفاقية تمويل",
    "اتفاقية قرض",
    "ائتمان",
    "حصلت على تمويل",
    "وقعت اتفاقية",
    "منحة قرض",
    "اعتماد مستندي",
    "ضمانات بنكية",
    "رسملة",
    "بروتوكول تمويل",
    "مذكرة تفاهم",
    "تمويل مشروع",
    "متناهي الصغر",
    "قرض ميسر"
]

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
# Supabase
# ══════════════════════════════════════════════════════════════════
def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


def supabase_get_hashes():
    try:
        since = (
            datetime.now(timezone.utc) - timedelta(days=7)
        ).isoformat()

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news"
            f"?select=hash&created_at=gte.{since}",
            headers=sb_headers(),
            timeout=10
        )

        if r.status_code == 200:
            return {
                item["hash"]
                for item in r.json()
                if item.get("hash")
            }

    except Exception as e:
        print(f"Supabase get_hashes error: {e}")

    return set()


def supabase_get_recent_news_for_dedupe():
    """
    تحميل آخر 7 أيام من الأخبار.
    نستخدم العنوان والرابط لمنع التكرار بين المصادر المختلفة.
    لا نحتاج إلى تغيير بنية جدول Supabase.
    """
    try:
        since = (
            datetime.now(timezone.utc) - timedelta(days=7)
        ).isoformat()

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news"
            f"?select=title,url,source_name,created_at"
            f"&created_at=gte.{since}"
            f"&order=created_at.desc"
            f"&limit=1000",
            headers=sb_headers(),
            timeout=15
        )

        if r.status_code == 200:
            return r.json()

        print(
            f"Supabase recent news HTTP {r.status_code}: "
            f"{r.text[:200]}"
        )

    except Exception as e:
        print(f"Supabase recent news error: {e}")

    return []


def supabase_save_news(title, url, source_name, tabs, h):
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
            timeout=10
        )

        return r.status_code in (200, 201, 204)

    except Exception as e:
        print(f"Supabase save error: {e}")
        return False


def supabase_get_last_24h():
    try:
        since = (
            datetime.now(timezone.utc) - timedelta(hours=24)
        ).isoformat()

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news"
            f"?select=title,tabs"
            f"&created_at=gte.{since}"
            f"&order=created_at.asc",
            headers=sb_headers(),
            timeout=15
        )

        if r.status_code == 200:
            return r.json()

    except Exception as e:
        print(f"Supabase get_last_24h error: {e}")

    return []


def supabase_get_news_for_pdf():
    """أخبار آخر 24 ساعة مع كل الحقول للـ PDF"""
    try:
        since = (
            datetime.now(timezone.utc) - timedelta(hours=24)
        ).isoformat()

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news"
            f"?select=title,url,source_name,tabs,created_at"
            f"&created_at=gte.{since}"
            f"&order=created_at.asc",
            headers=sb_headers(),
            timeout=15
        )

        if r.status_code == 200:
            return r.json()

    except Exception as e:
        print(f"Supabase get_news_for_pdf error: {e}")

    return []


def supabase_save_digest(
    tab_key,
    tab_label,
    content,
    news_count,
    digest_date
):
    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/digest"
            f"?tab_key=eq.{tab_key}"
            f"&digest_date=eq.{digest_date}",
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

        return r.status_code in (200, 201, 204)

    except Exception as e:
        print(f"Supabase save_digest error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# دوال تنظيف ومقارنة الأخبار
# ══════════════════════════════════════════════════════════════════
def normalize_arabic_text(text):
    """
    توحيد العنوان قبل المقارنة.
    الهدف منع اختلافات بسيطة في الكتابة من إنتاج خبر مكرر.
    """
    if not text:
        return ""

    text = str(text).lower().strip()

    # إزالة التشكيل
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)

    # توحيد الحروف العربية
    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # إزالة علامات الترقيم والرموز
    text = re.sub(
        r"[^\w\u0600-\u06FF]+",
        " ",
        text,
        flags=re.UNICODE
    )

    # مسافات زائدة
    text = re.sub(r"\s+", " ", text).strip()

    return text


def title_tokens(text):
    normalized = normalize_arabic_text(text)

    # كلمات شائعة جدًا لا تفيد في مقارنة الخبر
    stop_words = {
        "مصر",
        "اليوم",
        "غدا",
        "اليوم",
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
        if len(word) >= 2 and word not in stop_words
    }


def is_update_title(title):
    normalized = normalize_arabic_text(title)

    return any(
        normalize_arabic_text(k) in normalized
        for k in UPDATE_KW
    )


def titles_are_probable_duplicate(title1, title2):
    """
    مقارنة محافظة نسبيًا.
    لا نحاول إثبات أن حادثين مختلفين هما نفس الخبر.
    نعتبرهما تكرارًا فقط عندما تكون درجة التشابه مرتفعة.
    """

    n1 = normalize_arabic_text(title1)
    n2 = normalize_arabic_text(title2)

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
    smaller = min(len(t1), len(t2))

    overlap = len(common) / smaller

    # تطابق قوي في الكلمات الأساسية + تشابه نصي معقول
    if overlap >= 0.80 and ratio >= 0.58:
        return True

    return False


def is_excluded_title(title, extra_exclude=None):
    """
    استبعاد الأخبار غير المرغوبة مركزيًا.
    """
    text = normalize_arabic_text(title)

    keywords = list(EXCLUDE_KW)

    if extra_exclude:
        keywords.extend(extra_exclude)

    for kw in keywords:
        if normalize_arabic_text(kw) in text:
            return True

    return False


def is_recent_datetime(dt, max_age_hours=24):
    if not dt:
        return False

    now = datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    age = now - dt

    # لا نقبل الأخبار المستقبلية بشكل غير طبيعي
    if age < timedelta(minutes=-10):
        return False

    return age <= timedelta(hours=max_age_hours)


def parse_any_datetime(value):
    """
    محاولة قراءة التاريخ من أكثر من صيغة.
    """
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    value = str(value).strip()

    # ISO 8601
    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except Exception:
        pass

    # RFC / RSS
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except Exception:
        pass

    # صيغ مصرية شائعة
    formats = [
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


# ══════════════════════════════════════════════════════════════════
# استخراج تاريخ المقال من صفحة الخبر
# ══════════════════════════════════════════════════════════════════
def extract_article_date(url):
    """
    يزور صفحة المقال ويحاول الحصول على تاريخ النشر/التحديث.
    الأولوية:
    1. datePublished
    2. article:published_time
    3. meta date
    4. time datetime
    5. dateModified كحل أخير
    """

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
                data = json.loads(
                    script.get_text(strip=True)
                )

                objects = []

                if isinstance(data, dict):
                    objects.append(data)

                    if isinstance(data.get("@graph"), list):
                        objects.extend(data["@graph"])

                elif isinstance(data, list):
                    objects.extend(data)

                for obj in objects:
                    if not isinstance(obj, dict):
                        continue

                    published = (
                        obj.get("datePublished")
                        or obj.get("datepublished")
                    )

                    dt = parse_any_datetime(published)

                    if dt:
                        return dt

            except Exception:
                continue

        # OpenGraph
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
                attrs={attr: value}
            )

            if tag and tag.get("content"):
                dt = parse_any_datetime(
                    tag.get("content")
                )

                if dt:
                    return dt

        # time datetime
        for tag in soup.find_all("time"):
            value = (
                tag.get("datetime")
                or tag.get("content")
                or tag.get_text(" ", strip=True)
            )

            dt = parse_any_datetime(value)

            if dt:
                return dt

        # dateModified كحل أخير
        for script in soup.find_all(
            "script",
            type="application/ld+json"
        ):
            try:
                data = json.loads(
                    script.get_text(strip=True)
                )

                objects = []

                if isinstance(data, dict):
                    objects.append(data)

                    if isinstance(data.get("@graph"), list):
                        objects.extend(data["@graph"])

                elif isinstance(data, list):
                    objects.extend(data)

                for obj in objects:
                    if not isinstance(obj, dict):
                        continue

                    modified = obj.get("dateModified")

                    dt = parse_any_datetime(modified)

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
# دوال مساعدة
# ══════════════════════════════════════════════════════════════════
def is_arabic(text):
    count = sum(
        1
        for c in text
        if "\u0600" <= c <= "\u06ff"
    )

    return count / max(len(text), 1) > 0.3


def get_tabs(title, summary, primary_tab):
    text = title + " " + summary
    tabs = []

    if primary_tab == "banks" and any(
        k in text for k in CBE_KW
    ):
        tabs.append("cbe")

    elif primary_tab:
        tabs.append(primary_tab)

    if any(k in text for k in WARNING_KW):
        if "warning" not in tabs:
            tabs.append("warning")

    if any(k in text for k in CREDIT_KW):
        if "credit" not in tabs:
            tabs.append("credit")

    return tabs


def make_hash(title):
    normalized = normalize_arabic_text(title)

    return hashlib.md5(
        normalized.encode("utf-8")
    ).hexdigest()


def canonical_url(url):
    """
    توحيد الرابط قبل المقارنة.
    """
    if not url:
        return ""

    url = url.strip()

    # إزالة fragment
    parsed = urlparse(url)

    clean = parsed._replace(
        fragment=""
    ).geturl()

    # إزالة بعض بارامترات التتبع
    parsed = urlparse(clean)

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
            key.lower().startswith(prefix)
            for prefix in tracking_prefixes
        ):
            continue

        filtered[key] = values

    query_parts = []

    for key in sorted(filtered):
        for value in filtered[key]:
            query_parts.append(
                f"{key}={value}"
            )

    query_string = "&".join(query_parts)

    result = parsed._replace(
        query=query_string,
        fragment=""
    ).geturl()

    return result.rstrip("/")


def send(text):
    try:
        r = requests.post(
            f"{API_URL}/sendMessage",
            json={
                "chat_id": CHANNEL_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=15
        )

        return r.status_code == 200

    except Exception as e:
        print(f"Send error: {e}")
        return False


def format_msg(
    title,
    url,
    source_name,
    tabs
):
    tabs_str = "  |  ".join(
        TAB_LABELS.get(t, t)
        for t in tabs
    )

    safe_title = (
        title
        .replace("*", "")
        .replace("[", "")
        .replace("]", "")
        .replace("_", "\\_")
    )

    return "\n".join([
        f"[{safe_title}]({url})",
        f"🗂  {tabs_str}",
        f"📰  {source_name}",
        "",
        "━━━━━━━━━━━━━━━━",
        "🛡 @egypt\\_risk\\_radar"
    ])


# ══════════════════════════════════════════════════════════════════
# فحص التكرار المركزي
# ══════════════════════════════════════════════════════════════════
def is_duplicate_against_recent(
    title,
    url,
    recent_news
):
    current_url = canonical_url(url)

    current_norm = normalize_arabic_text(title)

    for item in recent_news:

        old_url = canonical_url(
            item.get("url", "")
        )

        old_title = item.get(
            "title",
            ""
        )

        # 1 — نفس الرابط
        if current_url and old_url:
            if current_url == old_url:
                return True, "نفس الرابط"

        # 2 — نفس العنوان بعد التطبيع
        old_norm = normalize_arabic_text(
            old_title
        )

        if current_norm and old_norm:
            if current_norm == old_norm:
                return True, "نفس العنوان"

        # 3 — تشابه قوي للعناوين
        # إذا كان الخبر الحالي تحديثًا، نسمح به.
        if not is_update_title(title):
            if titles_are_probable_duplicate(
                title,
                old_title
            ):
                return True, "عنوان مشابه جدًا"

    return False, ""


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
        return False, sent_hashes, recent_news

    title = title.strip()
    url = canonical_url(url)

    # 1 — عربي
    if not is_arabic(title):
        return False, sent_hashes, recent_news

    # 2 — استبعادات
    if is_excluded_title(
        title,
        exclude
    ):
        print(
            f"    ⛔ مستبعد: {title[:80]}"
        )

        return False, sent_hashes, recent_news

    # 3 — تاريخ الخبر
    if published_at is not None:
        if not is_recent_datetime(
            published_at,
            max_age_hours=24
        ):
            print(
                f"    ⏳ خبر قديم: "
                f"{title[:70]}"
            )

            return False, sent_hashes, recent_news

    # 4 — Hash
    h = make_hash(title)

    if h in sent_hashes:
        return False, sent_hashes, recent_news

    # 5 — مقارنة مع الأخبار المنشورة من جميع المصادر
    duplicate, reason = (
        is_duplicate_against_recent(
            title,
            url,
            recent_news
        )
    )

    if duplicate:
        print(
            f"    ♻️ مكرر ({reason}): "
            f"{title[:70]}"
        )

        return False, sent_hashes, recent_news

    # 6 — تصنيف
    tabs = get_tabs(
        title,
        summary,
        primary_tab
    )

    if not tabs:
        return False, sent_hashes, recent_news

    # 7 — النشر
    msg = format_msg(
        title,
        url,
        source_name,
        tabs
    )

    if send(msg):

        sent_hashes.add(h)

        supabase_save_news(
            title,
            url,
            source_name,
            tabs,
            h
        )

        # إضافة الخبر إلى الذاكرة الحالية
        # حتى لا يكرر مصدر آخر الخبر في نفس التشغيل
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
        f"    ❌ فشل: {title[:60]}"
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
        value = entry.get(field)

        if value:
            try:
                from calendar import timegm

                timestamp = timegm(value)

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
        value = entry.get(field)

        dt = parse_any_datetime(value)

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
        feed = feedparser.parse(
            src["url"]
        )

        for entry in feed.entries[:15]:

            published_at = get_feed_entry_date(
                entry
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
# أدوات Scraping عامة
# ══════════════════════════════════════════════════════════════════
def absolute_url(base, href):
    if not href:
        return ""

    href = href.strip()

    if href.startswith("//"):
        return "https:" + href

    return urljoin(
        base,
        href
    )


def extract_listing_items(
    soup,
    base,
    limit=15
):
    items = []

    seen_urls = set()

    # المقالات أولاً
    for article in soup.find_all("article"):

        heading = article.find(
            ["h1", "h2", "h3", "h4"]
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
            anchor.get("href")
        )

        if len(title) < 15 or not link:
            continue

        link = canonical_url(link)

        if link in seen_urls:
            continue

        seen_urls.add(link)

        items.append(
            (title, link)
        )

        if len(items) >= limit:
            break

    # fallback
    if len(items) < limit:

        for heading in soup.find_all(
            ["h1", "h2", "h3", "h4"]
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
                anchor.get("href")
            )

            if len(title) < 15 or not link:
                continue

            link = canonical_url(link)

            if link in seen_urls:
                continue

            seen_urls.add(link)

            items.append(
                (title, link)
            )

            if len(items) >= limit:
                break

    return items


# ══════════════════════════════════════════════════════════════════
# Google News
# ══════════════════════════════════════════════════════════════════
def google_news_real_url(href):
    """
    Google News قد يستخدم:
    /url?q=...
    أو رابطًا مباشرًا.
    """
    if not href:
        return ""

    href = unquote(href)

    parsed = urlparse(href)

    if parsed.path == "/url":
        qs = parse_qs(
            parsed.query
        )

        for key in (
            "q",
            "url"
        ):
            if qs.get(key):
                return qs[key][0]

    return href


def is_allowed_domain(
    url,
    allowed_domains
):
    try:
        host = (
            urlparse(url)
            .netloc
            .lower()
        )

        host = host.split("@")[-1]

        return any(
            host == domain
            or host.endswith("." + domain)
            for domain in allowed_domains
        )

    except Exception:
        return False


def extract_google_news_items(
    soup,
    allowed_domains,
    limit=20
):
    items = []

    seen = set()

    # Google News غالبًا يضع العنوان في h3
    for heading in soup.find_all("h3"):

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
            anchor.get("href")
        )

        if not href:
            continue

        if not is_allowed_domain(
            href,
            allowed_domains
        ):
            continue

        href = canonical_url(href)

        if href in seen:
            continue

        seen.add(href)

        if len(title) < 15:
            continue

        items.append(
            (title, href)
        )

        if len(items) >= limit:
            break

    # fallback للـ anchors
    if len(items) < limit:

        for anchor in soup.find_all(
            "a",
            href=True
        ):

            href = google_news_real_url(
                anchor.get("href")
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

            href = canonical_url(href)

            if href in seen:
                continue

            seen.add(href)

            items.append(
                (text, href)
            )

            if len(items) >= limit:
                break

    return items


# ══════════════════════════════════════════════════════════════════
# Scraping
# ══════════════════════════════════════════════════════════════════
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
            timeout=15
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

        # Google News
        if src.get("google_news"):

            items = extract_google_news_items(
                soup,
                src.get(
                    "allowed_domains",
                    []
                ),
                limit=20
            )

        else:

            items = extract_listing_items(
                soup,
                src["base"],
                limit=20
            )

        print(
            f"    🔎 تم العثور على "
            f"{len(items)} نتيجة في "
            f"{src['name']}"
        )

        for title, link in items:

            # Google News / مصادر البحث:
            # لا نعتمد على ترتيب الصفحة لإثبات حداثة الخبر.
            # نذهب للمقال نفسه للحصول على التاريخ.
            published_at = (
                extract_article_date(link)
            )

            if published_at is None:
                print(
                    f"    ⚠️ لا يوجد تاريخ موثوق: "
                    f"{title[:70]}"
                )

                # أمنيًا: لا ننشر خبرًا لا نستطيع
                # إثبات حداثته من مصادر البحث.
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
# PDF يومي
# ══════════════════════════════════════════════════════════════════
def download_font():
    if not os.path.exists(FONT_PATH):

        print(
            "⬇️  جاري تحميل الخط العربي..."
        )

        r = requests.get(
            FONT_URL,
            timeout=30
        )

        with open(
            FONT_PATH,
            "wb"
        ) as f:
            f.write(r.content)

        print(
            "✅ تم تحميل الخط"
        )


def ar(text):
    """تحويل النص العربي للعرض الصحيح في PDF"""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(
            arabic_reshaper.reshape(
                str(text)
            )
        )

    except:
        return str(text)


def generate_daily_pdf(
    news_list,
    now_egypt
):
    from fpdf import FPDF

    download_font()

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
            ).append(item)

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

    # رأس الصفحة
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

    pdf.set_y(6)

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

    pdf.ln(8)

    for tab in ordered_tabs:

        items = grouped[tab]

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
                f"{tab_label}  "
                f"({len(items)} خبر)"
            ),
            ln=True,
            align="R",
            fill=True
        )

        pdf.ln(1)

        for i, item in enumerate(items):

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
                    dt +
                    timedelta(hours=2)
                )

                time_str = dt.strftime(
                    "%H:%M"
                )

            except:
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

            pdf.ln(1)

        pdf.ln(5)

    pdf.set_y(-15)

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
                io.BytesIO(pdf_bytes),
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

        return r.status_code == 200

    except Exception as e:
        print(
            f"Send PDF error: {e}"
        )

        return False


def run_pdf_report():

    print(
        "📋 جاري إعداد التقرير اليومي PDF..."
    )

    news = supabase_get_news_for_pdf()

    if not news:

        print(
            "لا توجد أخبار في "
            "الـ 24 ساعة الماضية"
        )

        return

    now_egypt = (
        datetime.now(timezone.utc)
        + timedelta(hours=2)
    )

    date_str = now_egypt.strftime(
        "%d/%m/%Y"
    )

    print(
        f"  {len(news)} خبر — "
        f"جاري توليد PDF..."
    )

    pdf_bytes = generate_daily_pdf(
        news,
        now_egypt
    )

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
# الموجز اليومي
# ══════════════════════════════════════════════════════════════════
def ask_gemini(prompt):

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

        data = r.json()

        return (
            data[
                "candidates"
            ][0][
                "content"
            ][
                "parts"
            ][0][
                "text"
            ]
        )

    except Exception as e:

        print(
            f"Gemini error: {e}"
        )

        return None


def group_by_tab(news_list):

    grouped = {}

    for item in news_list:

        for tab in item["tabs"]:

            grouped.setdefault(
                tab,
                []
            ).append(
                item["title"]
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

    news = supabase_get_last_24h()

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
        datetime.now(timezone.utc)
        + timedelta(hours=2)
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

    time.sleep(3)

    ordered_tabs = sorted(
        grouped.keys(),
        key=lambda x:
            DIGEST_PRIORITY.index(x)
            if x in DIGEST_PRIORITY
            else 99
    )

    for tab in ordered_tabs:

        headlines = grouped[tab]

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

        if len(msg) > 4000:
            msg = (
                msg[:3990]
                + "...\n\n"
                + "🛡 @egypt\\_risk\\_radar"
            )

        send(msg)

        supabase_save_digest(
            tab,
            tab_label,
            analysis,
            len(headlines),
            now.strftime(
                "%Y-%m-%d"
            )
        )

        time.sleep(5)

    send(
        f"✅ *انتهى موجز {date_str}*\n\n"
        f"تابع أخبار السوق لحظة بلحظة\n"
        f"🛡 @egypt\\_risk\\_radar"
    )

    print(
        "✅ انتهى الموجز اليومي"
    )


# ══════════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ══════════════════════════════════════════════════════════════════
def run():

    mode = os.environ.get(
        "RUN_MODE",
        "news"
    )

    if mode == "digest":
        run_daily_digest()
        return

    if mode == "pdf":
        run_pdf_report()
        return

    print(
        "🛡 رادار المخاطر — يعمل..."
    )

    print(
        "📦 جاري تحميل الأخبار "
        "المرسلة من Supabase..."
    )

    sent_hashes = (
        supabase_get_hashes()
    )

    recent_news = (
        supabase_get_recent_news_for_dedupe()
    )

    print(
        f"   {len(sent_hashes)} خبر محفوظ "
        f"مسبقاً"
    )

    print(
        f"   {len(recent_news)} خبر في "
        f"ذاكرة منع التكرار"
    )

    new_count = 0

    # ──────────────────────────────────────────────────────────────
    # RSS
    # ──────────────────────────────────────────────────────────────
    for src in RSS_SOURCES:

        print(
            f"  📡 RSS: "
            f"{src['name']}..."
        )

        count, sent_hashes, recent_news = (
            fetch_rss(
                src,
                sent_hashes,
                recent_news
            )
        )

        new_count += count

    # ──────────────────────────────────────────────────────────────
    # Scraping
    # ──────────────────────────────────────────────────────────────
    for src in SCRAPE_SOURCES:

        print(
            f"  🕷️ Scraping: "
            f"{src['name']}..."
        )

        count, sent_hashes, recent_news = (
            fetch_scrape(
                src,
                sent_hashes,
                recent_news
            )
        )

        new_count += count

    print(
        f"\n✅ تم نشر "
        f"{new_count} خبر جديد"
    )


if __name__ == "__main__":
    run()
