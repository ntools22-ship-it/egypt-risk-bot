import feedparser, requests, hashlib, time, os, json, sys
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════════════════
# إعدادات
# ══════════════════════════════════════════════════════════════════
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
GROQ_KEY     = os.environ.get("GROQ_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
CHANNEL_ID   = "@egypt_risk_radar"
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", CHANNEL_ID)
API_URL      = f"https://api.telegram.org/bot{BOT_TOKEN}"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"

# ══════════════════════════════════════════════════════════════════
# Telegram rate limit tracker (max 18 msg/دقيقة للأمان)
# ══════════════════════════════════════════════════════════════════
_msg_times: list = []  # timestamps للرسائل المبعوتة

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ar,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

# ══════════════════════════════════════════════════════════════════
# المصادر — RSS
# ══════════════════════════════════════════════════════════════════
RSS_SOURCES = [
    # 🏦 البنوك
    {"id": "amwal_banks",       "name": "أموال الغد - بنوك",      "url": "https://amwalalghad.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-%d9%85%d8%a7%d9%84%d9%8a%d8%a9/feed/",     "tab": "banks",  "exclude": ["سعر"]},
    # 💰 تمويل
    {"id": "hapi_credit",       "name": "حابي - تمويل",           "url": "https://hapijournal.com/category/%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/",                                                                           "tab": "credit", "exclude": []},
    {"id": "motawwer_credit",   "name": "المطور - تمويل",         "url": "https://almotawwer.com/tag/%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%b9%d8%a7%d8%aa-%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%b1%d8%a9/feed/", "tab": "credit", "exclude": []},
    {"id": "amwal_micro",       "name": "أموال الغد - تمويل",     "url": "https://amwalalghad.com/tag/%d9%85%d8%aa%d9%86%d8%a7%d9%87%d9%8a-%d8%a7%d9%84%d8%b5%d8%ba%d8%b1/feed/",                                         "tab": "credit", "exclude": []},
    # 💵 الدولار
    {"id": "hapi_fx",           "name": "حابي - دولار",           "url": "https://hapijournal.com/tag/%d8%a3%d8%b3%d8%b9%d8%a7%d8%b1-%d8%a7%d9%84%d8%af%d9%88%d9%84%d8%a7%d8%b1/feed/",                                   "tab": "fx",     "exclude": []},
    # 🌍 عالمي — سكاي نيوز بدل BBC
    {"id": "skynews_business",  "name": "سكاي نيوز - اقتصاد",    "url": "https://www.skynewsarabia.com/rss/business.xml",                                                                                                  "tab": "global", "exclude": []},
    # 🌾 زراعة
    {"id": "borsaa_agri",       "name": "البورصة نيوز - زراعة",   "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b2%d8%b1%d8%a7%d8%b9%d8%a9/feed/",                                                              "tab": "sector_agri",       "exclude": []},
    # 🏭 صناعة
    {"id": "borsaa_industry",   "name": "البورصة نيوز - صناعة",   "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d8%a9/feed/",                                                              "tab": "sector_industry",   "exclude": []},
    # 🏗️ عقارات
    {"id": "borsaa_realestate", "name": "البورصة نيوز - عقارات",  "url": "https://www.alborsaanews.com/category/%d8%a7%d9%84%d8%b9%d9%82%d8%a7%d8%b1%d8%a7%d8%aa/feed/",                                                   "tab": "sector_realestate", "exclude": []},
    # ⚡ طاقة
    {"id": "amwal_energy",      "name": "أموال الغد - طاقة",      "url": "https://amwalalghad.com/category/%d8%b7%d8%a7%d9%82%d8%a9/feed/",                                                                                 "tab": "sector_energy",     "exclude": []},
    # 🚢 نقل
    {"id": "amwal_transport",   "name": "أموال الغد - نقل",       "url": "https://amwalalghad.com/category/%d9%86%d9%82%d9%84-%d9%88-%d9%85%d9%84%d8%a7%d8%ad%d8%a9/feed/",                                                "tab": "sector_transport",  "exclude": []},
    # 💻 تكنولوجيا
    {"id": "amwal_tech",        "name": "أموال الغد - تكنولوجيا", "url": "https://amwalalghad.com/category/%d8%aa%d9%83%d9%86%d9%88%d9%84%d9%88%d8%ac%d9%8a%d8%a7-%d9%88%d8%a7%d8%aa%d8%b5%d8%a7%d9%84%d8%a7%d8%aa/feed/", "tab": "sector_tech",       "exclude": []},
    # 💼 استثمار — كلمات مفتاحية
    {"id": "hapi_all",          "name": "حابي",          "url": "https://hapijournal.com/feed/",                       "tab": None, "exclude": []},
    # 💰 تمويل — بلوم
    {"id": "bloom_banks",       "name": "بلوم - بنوك وتمويل", "url": "https://bloom-gate.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/", "tab": "credit", "exclude": []},
]

# ══════════════════════════════════════════════════════════════════
# المصادر — Scraping
# ══════════════════════════════════════════════════════════════════
SCRAPE_SOURCES = [
    {
        "id":      "masrafeyoun_banks",
        "name":    "المصرفيون",
        "url":     "https://masrafeyoun.ebi.gov.eg/category/banksnews/",
        "tab":     "banks",
        "base":    "https://masrafeyoun.ebi.gov.eg",
        "selector": "h2",
        "exclude": [],
    },
    {
        "id":      "independent_breaking",
        "name":    "Independent عربي",
        "url":     "https://www.independentarabia.com/tags/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A",
        "tab":     "breaking",
        "base":    "https://www.independentarabia.com",
        "exclude": [],
    },
    {
        "id":      "almal_cbe",
        "name":    "المال - مركزي",
        "url":     "https://almalnews.com/tag/%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A/",
        "tab":     "cbe",
        "base":    "https://almalnews.com",
        "exclude": [],
    },
]

# ══════════════════════════════════════════════════════════════════
# التصنيفات والكلمات المفتاحية
# ══════════════════════════════════════════════════════════════════
TAB_LABELS = {
    "breaking":          "⚡ عاجل",
    "banks":             "🏦 أخبار البنوك",
    "credit":            "💰 تمويل وائتمان",
    "warning":           "⚠️ إنذار مبكر",
    "fx":                "💵 أسعار الدولار",
    "cbe":               "🏛️ أخبار المركزي",
    "global":            "🌍 اقتصاد الشرق والعالم",
    "sector_invest":     "💼 استثمار",
    "sector_agri":       "🌾 زراعة",
    "sector_industry":   "🏭 صناعة",
    "sector_realestate": "🏗️ عقارات",
    "sector_energy":     "⚡ طاقة",
    "sector_transport":  "🚢 نقل وملاحة",
    "sector_tech":       "💻 تكنولوجيا واتصالات",
}

CBE_KW = [
    "البنك المركزي", "المركزي المصري", "لجنة السياسة النقدية",
    "سعر الفائدة", "الاحتياطي النقدي", "السياسة النقدية",
]

WARNING_KW = [
    "تعثر", "عجز عن السداد", "توقف عن السداد", "ديون متعثرة",
    "قروض متعثرة", "محفظة متعثرة", "ديون رديئة", "مخصصات",
    "شطب ديون", "استرداد ديون", "NPL", "إفلاس", "شهر إفلاس",
    "إعسار", "تصفية", "حراسة قضائية", "إدارة قضائية",
    "تعليق النشاط", "وقف الأعمال", "بيع أصول قسري",
    "حجز على أصول", "حجز على أموال", "دعوى قضائية",
    "غرامة مالية", "خفض تصنيف", "تخفيض تصنيف",
    "جدولة ديون", "إعادة جدولة", "أزمة سيولة",
    "خسائر متراكمة", "مخالفة مالية", "انهيار", "أزمة مالية",
]

CREDIT_KW = [
    "تسهيل ائتماني", "تسهيلات ائتمانية", "قرض", "تمويل",
    "خط ائتماني", "توريق", "سندات", "صكوك", "قرض مشترك",
    "تمويل مشترك", "اتفاقية تمويل", "اتفاقية قرض", "ائتمان",
    "حصلت على تمويل", "وقعت اتفاقية", "منحة قرض",
    "اعتماد مستندي", "ضمانات بنكية", "رسملة",
    "بروتوكول تمويل", "مذكرة تفاهم", "تمويل مشروع",
    "متناهي الصغر", "قرض ميسر",
]

DIGEST_PRIORITY = [
    "warning", "credit", "cbe", "banks", "fx", "global",
    "breaking", "sector_invest", "sector_agri", "sector_industry",
    "sector_realestate", "sector_energy", "sector_transport", "sector_tech",
]


# ══════════════════════════════════════════════════════════════════
# Supabase
# ══════════════════════════════════════════════════════════════════
def sb_headers():
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
    }

def supabase_get_hashes():
    """
    جلب هاشات الأخبار آخر 7 أيام مع Pagination.
    بترجع None لو فشل الاتصال — عشان البوت يوقف ومش يعيد نشر كل حاجة.
    """
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        all_hashes = set()
        page_size   = 1000
        offset      = 0

        while True:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/news",
                params={
                    "select":     "hash",
                    "created_at": f"gte.{since}",
                    "limit":      page_size,
                    "offset":     offset,
                },
                headers=sb_headers(), timeout=15,
            )
            if r.status_code != 200:
                print(f"Supabase get_hashes HTTP {r.status_code}: {r.text[:200]}")
                return None

            batch = r.json()
            all_hashes.update(item["hash"] for item in batch)

            if len(batch) < page_size:
                break
            offset += page_size

        print(f"   {len(all_hashes)} خبر محفوظ مسبقاً")
        return all_hashes

    except Exception as e:
        print(f"Supabase get_hashes error: {e}")
        return None

def supabase_save_news(title, url, source_name, tabs, h):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/news",
            headers={**sb_headers(), "Prefer": "resolution=ignore-duplicates"},
            json={"title": title, "url": url, "source_name": source_name, "tabs": tabs, "hash": h},
            timeout=10,
        )
        if r.status_code not in (200, 201, 409):
            print(f"⚠️ save_news HTTP {r.status_code}: {r.text[:100]}")
        return r.status_code in (200, 201, 204)
    except Exception as e:
        print(f"Supabase save error: {e}")
        return False

def supabase_get_last_24h():
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news?select=title,tabs&created_at=gte.{since}&order=created_at.asc&limit=1000",
            headers=sb_headers(), timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        print(f"Supabase get_last_24h HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"Supabase get_last_24h error: {e}")
    return []

def supabase_save_digest(tab_key, tab_label, content, news_count, digest_date):
    try:
        # احذف الموجز القديم لنفس اليوم ونفس التبويب
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/digest?tab_key=eq.{tab_key}&digest_date=eq.{digest_date}",
            headers=sb_headers(), timeout=10,
        )
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/digest",
            headers=sb_headers(),
            json={
                "tab_key":    tab_key,
                "tab_label":  tab_label,
                "content":    content,
                "news_count": news_count,
                "digest_date": digest_date,
            },
            timeout=10,
        )
        return r.status_code in (200, 201, 204)
    except Exception as e:
        print(f"Supabase save_digest error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# دوال مساعدة
# ══════════════════════════════════════════════════════════════════
def is_arabic(text):
    count = sum(1 for c in text if '\u0600' <= c <= '\u06ff')
    return count / max(len(text), 1) > 0.3

def get_tabs(title, summary, primary_tab):
    text = title + " " + summary
    tabs = []

    # لو تبويبه banks وفيه كلمات المركزي — يروح cbe بدل banks
    if primary_tab == "banks" and any(k in text for k in CBE_KW):
        tabs.append("cbe")
    elif primary_tab:
        tabs.append(primary_tab)

    if any(k in text for k in WARNING_KW) and "warning" not in tabs:
        tabs.append("warning")
    if any(k in text for k in CREDIT_KW) and "credit" not in tabs:
        tabs.append("credit")
    return tabs

def make_hash(title):
    # SHA-256 — متوافق مع الموقع (Web Crypto API)
    return hashlib.sha256(title.strip().encode()).hexdigest()

def send(text):
    """إرسال رسالة مع حماية من rate limit تيليجرام (18 msg/دقيقة)"""
    global _msg_times
    now = time.time()

    # امسح الـ timestamps الأقدم من دقيقة
    _msg_times = [t for t in _msg_times if now - t < 60]

    # لو وصلنا 18 رسالة في الدقيقة → نام الباقي
    if len(_msg_times) >= 18:
        oldest = _msg_times[0]
        sleep_sec = 61 - (now - oldest)
        if sleep_sec > 0:
            print(f"    ⏳ Rate limit: نايم {sleep_sec:.1f} ثانية...")
            time.sleep(sleep_sec)
        _msg_times = []

    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id":                  CHANNEL_ID,
            "text":                     text,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": False,
        }, timeout=15)
        if r.status_code == 200:
            _msg_times.append(time.time())
            return True
        print(f"    Telegram error: {r.status_code} {r.text[:100]}")
        return False
    except Exception as e:
        print(f"Send error: {e}")
        return False


def notify_admin(text):
    """إشعار المسؤول بأي خطأ — بيبعت لـ ADMIN_CHAT_ID"""
    try:
        requests.post(f"{API_URL}/sendMessage", json={
            "chat_id":    ADMIN_CHAT_ID,
            "text":       f"⚠️ *رادار المخاطر — تنبيه*\n\n{text}",
            "parse_mode": "Markdown",
        }, timeout=10)
    except Exception as e:
        print(f"notify_admin error: {e}")

def format_msg(title, url, source_name, tabs):
    tabs_str   = "  |  ".join(TAB_LABELS.get(t, t) for t in tabs)
    safe_title = title.replace("*","").replace("[","").replace("]","").replace("_","\\_")
    return "\n".join([
        f"[{safe_title}]({url})",
        f"🗂  {tabs_str}",
        f"📰  {source_name}",
        "",
        "━━━━━━━━━━━━━━━━",
        "🛡 @egypt\\_risk\\_radar",
    ])

def process_item(title, url, source_name, primary_tab, summary, exclude, sent_hashes):
    if not title or not url:
        return False, sent_hashes
    if not is_arabic(title):
        return False, sent_hashes
    # فلترة الكلمات المستثناة
    if any(kw in title for kw in exclude):
        return False, sent_hashes

    h = make_hash(title)
    if h in sent_hashes:
        return False, sent_hashes

    tabs = get_tabs(title, summary, primary_tab)
    if not tabs:
        return False, sent_hashes

    msg = format_msg(title, url, source_name, tabs)
    if send(msg):
        sent_hashes.add(h)
        supabase_save_news(title, url, source_name, tabs, h)
        print(f"    ✅ {title[:60]}")
        return True, sent_hashes

    print(f"    ❌ فشل: {title[:40]}")
    return False, sent_hashes


# ══════════════════════════════════════════════════════════════════
# جلب RSS
# ══════════════════════════════════════════════════════════════════
def is_recent(entry, hours=26):
    """هل الخبر نُشر في آخر {hours} ساعة؟ لو مفيش تاريخ → يعدي (نشره)."""
    pt = entry.get("published_parsed") or entry.get("updated_parsed")
    if not pt:
        return True  # مفيش تاريخ → متتجاهلش
    try:
        pub = datetime(*pt[:6], tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - pub
        if age > timedelta(hours=hours):
            return False
        return True
    except Exception:
        return True


def fetch_rss(src, sent_hashes):
    count = 0
    skipped_hash = 0
    try:
        feed = feedparser.parse(src["url"])
        for entry in feed.entries[:15]:
            title   = entry.get("title", "").strip()
            url     = entry.get("link", "")
            summary = entry.get("summary", "")[:400]
            h = make_hash(title)
            if sent_hashes is not None and h in sent_hashes:
                skipped_hash += 1
                continue
            ok, sent_hashes = process_item(title, url, src["name"], src["tab"], summary, src.get("exclude", []), sent_hashes)
            if ok:
                count += 1
        if skipped_hash or count:
            print(f"    ↩️  {src['name']}: {skipped_hash} مكرر | {count} جديد")
    except Exception as e:
        print(f"    ⚠️ RSS error {src['name']}: {e}")
    return count, sent_hashes


# ══════════════════════════════════════════════════════════════════
# جلب Scraping
# ══════════════════════════════════════════════════════════════════
def fetch_scrape(src, sent_hashes):
    count = 0
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ar,en;q=0.9",
            "Referer": "https://www.google.com/",
        }
        r = requests.get(src["url"], headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"    ⚠️ HTTP {r.status_code}: {src['name']}")
            return 0, sent_hashes

        soup  = BeautifulSoup(r.text, "html.parser")
        items = []

        # لو في selector مخصص (زي المصدر - استثمار)
        if src.get("selector"):
            for el in soup.find_all(src["selector"])[:20]:
                a = el.find("a", href=True) or el
                if a:
                    t = el.get_text(strip=True)
                    l = a.get("href", src["url"])
                    if not l.startswith("http"):
                        l = src["base"] + l
                    if len(t) > 15:
                        items.append((t, l))

        if not items:
            for article in soup.find_all("article")[:15]:
                h = article.find(["h1","h2","h3","h4"])
                a = article.find("a", href=True)
                if h and a:
                    t = h.get_text(strip=True)
                    l = a["href"]
                    if not l.startswith("http"):
                        l = src["base"] + l
                    if len(t) > 15:
                        items.append((t, l))

        if not items:
            for h in soup.find_all(["h2","h3"])[:20]:
                a = h.find("a", href=True)
                if a and len(h.get_text(strip=True)) > 15:
                    t = h.get_text(strip=True)
                    l = a["href"]
                    if not l.startswith("http"):
                        l = src["base"] + l
                    items.append((t, l))

        for title, link in items[:10]:
            ok, sent_hashes = process_item(title, link, src["name"], src["tab"], "", src.get("exclude", []), sent_hashes)
            if ok:
                count += 1

        skipped = len(items) - count if items else 0
        if items:
            print(f"    ↩️  {src['name']}: {len(items)} عنوان | {count} جديد | {skipped} مكرر")
        else:
            print(f"    ⚠️ {src['name']}: مفيش عناوين — selector ممكن اتغير")

    except Exception as e:
        print(f"    ⚠️ Scrape error {src['name']}: {e}")
    return count, sent_hashes


# ══════════════════════════════════════════════════════════════════
# الموجز اليومي
# ══════════════════════════════════════════════════════════════════
def ask_groq(prompt):
    if not GROQ_KEY:
        print("GROQ_API_KEY مش موجود")
        return None
    try:
        r = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1500,
                "temperature": 0.3,
            },
            timeout=60,
        )
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq error: {e} | status: {getattr(r, 'status_code', '?')} | response: {getattr(r, 'text', '')[:200]}")
        return None

def group_by_tab(news_list):
    grouped = {}
    for item in news_list:
        for tab in item["tabs"]:
            grouped.setdefault(tab, []).append(item["title"])
    return grouped

def build_prompt(tab_label, headlines):
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    return f"""أنت محلل أول في قسم المخاطر والائتمان في أحد البنوك المصرية الكبرى.
لديك عناوين أخبار تبويب "{tab_label}" خلال الـ 24 ساعة الماضية:

{headlines_text}

المطلوب:
1. عناوين الأخبار الأبرز في نقاط مختصرة
2. تحليل: ما الذي يستوجب الانتباه من منظور مخاطر وائتمان؟
3. تعليق مهني واحد للعاملين في القطاع

اكتب بأسلوب احترافي وموجز باللغة العربية، بدون مقدمات أو تحيات."""

def run_daily_digest():
    print("📊 جاري إعداد الموجز اليومي...")

    # اقرأ من Supabase
    news = supabase_get_last_24h()
    if not news:
        print("لا توجد أخبار في الـ 24 ساعة الماضية")
        return

    grouped  = group_by_tab(news)
    now      = datetime.now(timezone.utc) + timedelta(hours=2)  # توقيت مصر
    date_str = now.strftime("%d/%m/%Y")

    # رسالة افتتاحية
    send(
        f"🗞️ *موجز أنباء وتحليلات — {date_str}*\n"
        f"_تقرير يومي لمتخصصي الائتمان والمخاطر_\n\n"
        f"رصدنا اليوم *{len(news)} خبراً* في *{len(grouped)} قطاعات*\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🛡 @egypt\\_risk\\_radar"
    )
    time.sleep(3)

    ordered_tabs = sorted(grouped.keys(), key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99)

    for tab in ordered_tabs:
        headlines = grouped[tab]
        if not headlines:
            continue
        tab_label = TAB_LABELS.get(tab, tab)
        print(f"  🤖 Gemini: {tab_label} ({len(headlines)} خبر)...")

        analysis = ask_groq(build_prompt(tab_label, headlines))
        if not analysis:
            # Gemini فشل — ابعت العناوين مباشرة
            analysis = "\n".join(f"• {h}" for h in headlines)

        analysis = analysis.replace("**", "*")

        msg = (
            f"{'━'*16}\n"
            f"*{tab_label}*  \\| {len(headlines)} خبر\n"
            f"{'━'*16}\n\n"
            f"{analysis}\n\n"
            f"🛡 @egypt\\_risk\\_radar"
        )
        if len(msg) > 4000:
            msg = msg[:3990] + "...\n\n🛡 @egypt\\_risk\\_radar"

        send(msg)

        # حفظ في Supabase للموقع
        supabase_save_digest(tab, tab_label, analysis, len(headlines), now.strftime("%Y-%m-%d"))

        time.sleep(5)

    send(
        f"✅ *انتهى موجز {date_str}*\n\n"
        "تابع أخبار السوق لحظة بلحظة\n"
        "🛡 @egypt\\_risk\\_radar"
    )
    print("✅ انتهى الموجز اليومي")

    # ── الموجز الصوتي ──────────────────────────────────────
    send_voice_digest(grouped, date_str)


def build_voice_script(grouped, date_str):
    """بناء النص الصوتي المختصر للموجز"""
    ordered = sorted(grouped.keys(), key=lambda x: DIGEST_PRIORITY.index(x) if x in DIGEST_PRIORITY else 99)

    lines = [f"موجز رادار المخاطر — {date_str}."]
    total = sum(len(v) for v in grouped.values())
    lines.append(f"رصدنا اليوم {total} خبراً في {len(grouped)} قطاعات.")
    lines.append("أبرز ما رصدناه:")

    for tab in ordered[:6]:  # أهم 6 تبويبات بس عشان النص ما يطولش
        headlines = grouped[tab]
        tab_label = TAB_LABELS.get(tab, tab)
        # خد أبرز خبرين بس من كل تبويب
        for h in headlines[:2]:
            lines.append(h.rstrip(".") + ".")

    lines.append("تابع أخبار السوق لحظة بلحظة مع رادار المخاطر.")
    return "\n".join(lines)


def send_voice_digest(grouped, date_str):
    """توليد الموجز الصوتي وإرساله على التيليجرام"""
    if not GROQ_KEY:
        print("⚠️ GROQ_API_KEY مش موجود — الموجز الصوتي متوقف")
        return

    print("🎙️ جاري توليد الموجز الصوتي...")
    script = build_voice_script(grouped, date_str)

    try:
        # توليد الصوت
        r = requests.post(
            "https://api.groq.com/openai/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {GROQ_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "canopylabs/orpheus-arabic-saudi",
                "input": script,
                "voice": "noura",
                "response_format": "wav",
            },
            timeout=120,
        )

        if r.status_code != 200:
            print(f"⚠️ TTS error HTTP {r.status_code}: {r.text[:200]}")
            return

        # إرسال على التيليجرام كـ voice message
        voice_r = requests.post(
            f"{API_URL}/sendVoice",
            data={
                "chat_id": CHANNEL_ID,
                "caption": f"🎙️ *الموجز الصوتي — {date_str}*\n🛡 @egypt\\_risk\\_radar",
                "parse_mode": "Markdown",
            },
            files={"voice": ("digest.wav", r.content, "audio/wav")},
            timeout=60,
        )

        if voice_r.status_code == 200:
            print("✅ تم إرسال الموجز الصوتي")
        else:
            print(f"⚠️ Telegram voice error: {voice_r.text[:200]}")

    except Exception as e:
        print(f"⚠️ Voice digest error: {e}")


# ══════════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ══════════════════════════════════════════════════════════════════
def run():
    mode = os.environ.get("RUN_MODE", "news")

    if mode == "digest":
        run_daily_digest()
        return

    print("🛡 رادار المخاطر — يعمل...")
    print("📦 جاري تحميل الأخبار المرسلة من Supabase...")
    sent_hashes = supabase_get_hashes()

    if sent_hashes is None:
        msg = "فشل الاتصال بـ Supabase — توقف التشغيل لمنع تكرار الأخبار.\nتحقق من الـ secrets في GitHub."
        print(f"❌ {msg}")
        notify_admin(msg)
        sys.exit(1)

    print(f"   {len(sent_hashes)} خبر محفوظ مسبقاً")

    new_count = 0

    for src in RSS_SOURCES:
        print(f"  📡 RSS: {src['name']}...")
        count, sent_hashes = fetch_rss(src, sent_hashes)
        new_count += count

    for src in SCRAPE_SOURCES:
        print(f"  🕷️  Scraping: {src['name']}...")
        count, sent_hashes = fetch_scrape(src, sent_hashes)
        new_count += count

    print(f"\n✅ تم نشر {new_count} خبر جديد")


if __name__ == "__main__":
    run()
