import feedparser, requests, hashlib, time, os, json
from datetime import datetime, timezone, timedelta
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
GEMINI_URL   = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

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
    {"id": "amwal_banks",       "name": "أموال الغد - بنوك",      "url": "https://amwalalghad.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-%d9%85%d8%a7%d9%84%d9%8a%d8%a9/feed/",     "tab": "banks"},
    {"id": "masrafeyoun_banks", "name": "المصرفيون",               "url": "https://masrafeyoun.ebi.gov.eg/category/banksnews/feed/",                                                                                         "tab": "banks"},
    # 💰 تمويل
    {"id": "hapi_credit",       "name": "حابي - تمويل",           "url": "https://hapijournal.com/category/%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/",                                                                           "tab": "credit"},
    {"id": "motawwer_credit",   "name": "المطور - تمويل",         "url": "https://almotawwer.com/tag/%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%b9%d8%a7%d8%aa-%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%b1%d8%a9/feed/", "tab": "credit"},
    {"id": "amwal_micro",       "name": "أموال الغد - تمويل",     "url": "https://amwalalghad.com/tag/%d9%85%d8%aa%d9%86%d8%a7%d9%87%d9%8a-%d8%a7%d9%84%d8%b5%d8%ba%d8%b1/feed/",                                         "tab": "credit"},
    # 💵 الدولار
    {"id": "hapi_fx",           "name": "حابي - دولار",           "url": "https://hapijournal.com/tag/%d8%a3%d8%b3%d8%b9%d8%a7%d8%b1-%d8%a7%d9%84%d8%af%d9%88%d9%84%d8%a7%d8%b1/feed/",                                   "tab": "fx"},
    # 🌍 عالمي
    {"id": "bbc_ar",            "name": "BBC عربي - اقتصاد",      "url": "https://feeds.bbci.co.uk/arabic/business/rss.xml",                                                                                                "tab": "global"},
    # 🌾 زراعة
    {"id": "borsaa_agri",       "name": "البورصة نيوز - زراعة",   "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b2%d8%b1%d8%a7%d8%b9%d8%a9/feed/",                                                              "tab": "sector_agri"},
    # 🏭 صناعة
    {"id": "borsaa_industry",   "name": "البورصة نيوز - صناعة",   "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d8%a9/feed/",                                                              "tab": "sector_industry"},
    # 🏗️ عقارات
    {"id": "borsaa_realestate", "name": "البورصة نيوز - عقارات",  "url": "https://www.alborsaanews.com/category/%d8%a7%d9%84%d8%b9%d9%82%d8%a7%d8%b1%d8%a7%d8%aa/feed/",                                                   "tab": "sector_realestate"},
    # ⚡ طاقة
    {"id": "amwal_energy",      "name": "أموال الغد - طاقة",      "url": "https://amwalalghad.com/category/%d8%b7%d8%a7%d9%82%d8%a9/feed/",                                                                                 "tab": "sector_energy"},
    # 🚢 نقل
    {"id": "amwal_transport",   "name": "أموال الغد - نقل",       "url": "https://amwalalghad.com/category/%d9%86%d9%82%d9%84-%d9%88-%d9%85%d9%84%d8%a7%d8%ad%d8%a9/feed/",                                                "tab": "sector_transport"},
    # 💻 تكنولوجيا
    {"id": "amwal_tech",        "name": "أموال الغد - تكنولوجيا", "url": "https://amwalalghad.com/category/%d8%aa%d9%83%d9%86%d9%88%d9%84%d9%88%d8%ac%d9%8a%d8%a7-%d9%88%d8%a7%d8%aa%d8%b5%d8%a7%d9%84%d8%a7%d8%aa/feed/", "tab": "sector_tech"},
    # ⚠️ كلمات مفتاحية
    {"id": "hapi_all",          "name": "حابي",          "url": "https://hapijournal.com/feed/",                        "tab": None},
    {"id": "febanks_all",       "name": "في البنوك",     "url": "https://febanks.com/feed/",                            "tab": None},
    {"id": "borsaa_all",        "name": "البورصة نيوز",  "url": "https://www.alborsaanews.com/feed/",                    "tab": None},
    {"id": "masrafeyoun_all",   "name": "المصرفيون",     "url": "https://masrafeyoun.ebi.gov.eg/feed/",                  "tab": None},
]

# ══════════════════════════════════════════════════════════════════
# المصادر — Scraping
# ══════════════════════════════════════════════════════════════════
SCRAPE_SOURCES = [
    {
        "id":   "independent_breaking",
        "name": "Independent عربي",
        "url":  "https://www.independentarabia.com/tags/%D8%A7%D9%84%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A",
        "tab":  "breaking",
        "base": "https://www.independentarabia.com",
    },
    {
        "id":   "almal_cbe",
        "name": "المال - مركزي",
        "url":  "https://almalnews.com/tag/%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A/",
        "tab":  "cbe",
        "base": "https://almalnews.com",
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
    "sector_agri":       "🌾 زراعة",
    "sector_industry":   "🏭 صناعة",
    "sector_realestate": "🏗️ عقارات",
    "sector_energy":     "⚡ طاقة",
    "sector_transport":  "🚢 نقل وملاحة",
    "sector_tech":       "💻 تكنولوجيا واتصالات",
}

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

DAILY_LOG = "daily_news.json"


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
    """جيب الـ hashes من آخر 7 أيام لضمان عدم التكرار"""
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/news?select=hash&created_at=gte.{since}",
            headers=sb_headers(),
            timeout=10,
        )
        if r.status_code == 200:
            return {item["hash"] for item in r.json()}
    except Exception as e:
        print(f"Supabase get_hashes error: {e}")
    return set()

def supabase_save(title, url, source_name, tabs, h):
    """حفظ الخبر في Supabase"""
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/news",
            headers={**sb_headers(), "Prefer": "resolution=ignore-duplicates"},
            json={
                "title":       title,
                "url":         url,
                "source_name": source_name,
                "tabs":        tabs,
                "hash":        h,
            },
            timeout=10,
        )
        return r.status_code in (200, 201, 204)
    except Exception as e:
        print(f"Supabase save error: {e}")
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
    if primary_tab:
        tabs.append(primary_tab)
    if any(k in text for k in WARNING_KW) and "warning" not in tabs:
        tabs.append("warning")
    if any(k in text for k in CREDIT_KW) and "credit" not in tabs:
        tabs.append("credit")
    return tabs

def make_hash(title):
    return hashlib.md5(title.strip().encode()).hexdigest()

def load_daily_log():
    try:
        with open(DAILY_LOG, encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_to_daily_log(title, url, source_name, tabs):
    log = load_daily_log()
    log.append({
        "title":  title,
        "url":    url,
        "source": source_name,
        "tabs":   tabs,
        "time":   datetime.now(timezone.utc).isoformat(),
    })
    with open(DAILY_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def send(text):
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id":                  CHANNEL_ID,
            "text":                     text,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": False,
        }, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Send error: {e}")
        return False

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

def process_item(title, url, source_name, primary_tab, summary, sent_hashes):
    if not title or not url:
        return False, sent_hashes
    if not is_arabic(title):
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
        supabase_save(title, url, source_name, tabs, h)
        save_to_daily_log(title, url, source_name, tabs)
        print(f"    ✅ {title[:60]}")
        time.sleep(2)
        return True, sent_hashes

    print(f"    ❌ فشل إرسال: {title[:40]}")
    return False, sent_hashes


# ══════════════════════════════════════════════════════════════════
# جلب RSS
# ══════════════════════════════════════════════════════════════════
def fetch_rss(src, sent_hashes):
    count = 0
    try:
        feed = feedparser.parse(src["url"])
        for entry in feed.entries[:10]:
            title   = entry.get("title", "").strip()
            url     = entry.get("link", "")
            summary = entry.get("summary", "")[:400]
            ok, sent_hashes = process_item(title, url, src["name"], src["tab"], summary, sent_hashes)
            if ok:
                count += 1
    except Exception as e:
        print(f"    ⚠️ RSS error {src['name']}: {e}")
    return count, sent_hashes


# ══════════════════════════════════════════════════════════════════
# جلب Scraping
# ══════════════════════════════════════════════════════════════════
def fetch_scrape(src, sent_hashes):
    count = 0
    try:
        r = requests.get(src["url"], headers=HEADERS, timeout=10)
        if r.status_code != 200:
            print(f"    ⚠️ Scrape HTTP {r.status_code}: {src['name']}")
            return 0, sent_hashes

        soup  = BeautifulSoup(r.text, "html.parser")
        items = []

        for article in soup.find_all("article")[:15]:
            h = article.find(["h1","h2","h3","h4"])
            a = article.find("a", href=True)
            if h and a:
                title = h.get_text(strip=True)
                link  = a["href"]
                if not link.startswith("http"):
                    link = src["base"] + link
                if len(title) > 15:
                    items.append((title, link))

        if not items:
            for h in soup.find_all(["h2","h3"])[:20]:
                a = h.find("a", href=True)
                if a and len(h.get_text(strip=True)) > 15:
                    title = h.get_text(strip=True)
                    link  = a["href"]
                    if not link.startswith("http"):
                        link = src["base"] + link
                    items.append((title, link))

        for title, link in items[:10]:
            ok, sent_hashes = process_item(title, link, src["name"], src["tab"], "", sent_hashes)
            if ok:
                count += 1

    except Exception as e:
        print(f"    ⚠️ Scrape error {src['name']}: {e}")
    return count, sent_hashes


# ══════════════════════════════════════════════════════════════════
# الموجز اليومي
# ══════════════════════════════════════════════════════════════════
def ask_gemini(prompt):
    try:
        r = requests.post(GEMINI_URL, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=60)
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

def get_last_24h_news():
    log    = load_daily_log()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    return [
        item for item in log
        if datetime.fromisoformat(item["time"]) >= cutoff
    ]

def group_by_tab(news_list):
    grouped = {}
    for item in news_list:
        for tab in item["tabs"]:
            grouped.setdefault(tab, []).append(item["title"])
    return grouped

def build_prompt(tab_label, headlines):
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    return f"""أنت محلل أول في قسم المخاطر والائتمان في أحد البنوك المصرية الكبرى.
لديك الأخبار التالية من تبويب "{tab_label}" خلال الـ 24 ساعة الماضية:

{headlines_text}

المطلوب:
1. موجز سريع للأخبار الأبرز في نقاط مختصرة
2. تحليل دقيق: ما الذي يستوجب الانتباه من منظور مخاطر وائتمان؟
3. توصية أو تعليق مهني واحد للعاملين في القطاع

اكتب بأسلوب احترافي وموجز باللغة العربية، بدون مقدمات أو تحيات."""

def run_daily_digest():
    print("📊 جاري إعداد الموجز اليومي...")
    news = get_last_24h_news()
    if not news:
        print("لا توجد أخبار في الـ 24 ساعة الماضية")
        return

    grouped  = group_by_tab(news)
    now      = datetime.now(timezone.utc) + timedelta(hours=2)
    date_str = now.strftime("%d/%m/%Y")

    send(
        f"🗞️ *نشرة رادار المخاطر — {date_str}*\n"
        f"_تقرير يومي شامل لمتخصصي الائتمان والمخاطر_\n\n"
        f"رصدنا اليوم *{len(news)} خبراً* في *{len(grouped)} قطاعات*\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🛡 @egypt\\_risk\\_radar"
    )
    time.sleep(3)

    priority = [
        "warning","credit","cbe","banks","fx","global",
        "breaking","sector_agri","sector_industry",
        "sector_realestate","sector_energy","sector_transport","sector_tech"
    ]
    for tab in sorted(grouped.keys(), key=lambda x: priority.index(x) if x in priority else 99):
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
            f"{'━'*16}\n"
            f"*{tab_label}*  \\| {len(headlines)} خبر\n"
            f"{'━'*16}\n\n"
            f"{analysis}\n\n"
            f"🛡 @egypt\\_risk\\_radar"
        )
        if len(msg) > 4000:
            msg = msg[:3990] + "...\n\n🛡 @egypt\\_risk\\_radar"
        send(msg)
        time.sleep(5)

    send(
        "✅ *انتهى تقرير اليوم*\n\n"
        "تابع أخبار السوق لحظة بلحظة\n"
        "🛡 @egypt\\_risk\\_radar"
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

    print("🛡 رادار المخاطر — يعمل...")
    print("📦 جاري تحميل الأخبار المرسلة من Supabase...")
    sent_hashes = supabase_get_hashes()
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
