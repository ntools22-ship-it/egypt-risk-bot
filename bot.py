import feedparser, requests, hashlib, time, os, json, sys, cloudscraper
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ══════════════════════════════════════════════════════════════════
# 1. إعداد المحرك الجديد لتجاوز الحماية
# ══════════════════════════════════════════════════════════════════
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'android', 'desktop': False}
)

# ══════════════════════════════════════════════════════════════════
# 2. الإعدادات والـ Secrets
# ══════════════════════════════════════════════════════════════════
BOT_TOKEN     = os.environ.get("BOT_TOKEN", "")
GROQ_KEY      = os.environ.get("GROQ_API_KEY", "")
SUPABASE_URL  = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY", "")
CHANNEL_ID    = "@egypt_risk_radar"
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", CHANNEL_ID)
API_URL       = f"https://api.telegram.org/bot{BOT_TOKEN}"
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = "llama-3.3-70b-versatile"

# تتبع معدل الإرسال (Rate Limit)
_msg_times = []

# ══════════════════════════════════════════════════════════════════
# 3. قوائم المصادر والكلمات المفتاحية
# ══════════════════════════════════════════════════════════════════

RSS_SOURCES = [
    {
        "name": "أموال الغد - بنوك",
        "url": "https://amwalalghad.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-%d9%85%d8%a7%d9%84%d9%8a%d8%a9/feed/",
        "tab": "بنوك",
        "exclude": ["سعر", "أسعار", "تحديث", "الذهب", "الدولار اليوم", "الريال", "اليورو"],
    },
    {"name": "حابي - تمويل", "url": "https://hapijournal.com/category/%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/", "tab": "تمويل"},
    {"name": "المطور - تمويل", "url": "https://almotawwer.com/tag/%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%a7%d8%aa-%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%a1/feed/", "tab": "تمويل"},
    {"name": "سكاي نيوز - اقتصاد", "url": "https://www.skynewsarabia.com/rss/business.xml", "tab": "اقتصاد"},
    {"name": "بلوم - بنوك وتمويل", "url": "https://bloom-gate.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%86%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/", "tab": "تمويل"}
]

SCRAPE_SOURCES = [
    {"name": "المصرفيون", "url": "https://masrafeyoun.ebi.gov.eg/category/banksnews/", "tab": "بنوك", "base": "https://masrafeyoun.ebi.gov.eg"},
    {"name": "المال - مركزي", "url": "https://almalnews.com/tag/%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B3%D8%B1%D9%8A/", "tab": "مركزي", "base": "https://almalnews.com"},
    {
        "name": "مصراوي - اقتصاد",
        "url": "https://www.masrawy.com/news/news_economy/section/206/%d8%a7%d9%82%d8%aa%d8%b5%d8%a7%d8%af",
        "tab": "اقتصاد", "base": "https://www.masrawy.com",
        "exclude": ["سعر", "الذهب", "أسعار", "الأرز", "الحديد", "الدواجن", "البصل", "الخضروات", "الفاكهة", "السلع"],
        "exclude_except": ["أسعار النفط", "أسعار الفائدة"],
    },
    {"name": "فيرست بنك", "url": "https://www.firstbankeg.com/List/10", "tab": "بنوك", "base": "https://www.firstbankeg.com", "clean_prefix": ["بنك", "البنك"]}
]

KW = ["مركزي", "فائدة", "تضخم", "قرض", "تمويل", "استحواذ", "دمج", "سيولة", "دولار", "احتياطي", "ائتمان", "مخاطر", "تعثر", "ديون", "صندوق النقد", "شطب", "إفلاس", "تصنيف ائتماني", "رقابة"]
TAB_LABELS = {"بنوك": "🏦 أخبار البنوك", "تمويل": "💰 التمويل والشركات", "مركزي": "🏛️ البنك المركزي", "اقتصاد": "📈 اقتصاد كلي"}

# ══════════════════════════════════════════════════════════════════
# 4. الدوال الأساسية
# ══════════════════════════════════════════════════════════════════

def make_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def is_arabic(text):
    arabic_chars = [c for c in text if '\u0600' <= c <= '\u06FF']
    return len(arabic_chars) > (len(text) * 0.3)

def supabase_get_hashes():
    try:
        url = f"{SUPABASE_URL}/rest/v1/sent_news?select=hash"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            return {item["hash"] for item in r.json()}
        return set()
    except: return None

def supabase_insert_hash(h, title):
    try:
        url = f"{SUPABASE_URL}/rest/v1/sent_news"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
        requests.post(url, headers=headers, json={"hash": h, "title": title[:200]}, timeout=20)
    except: pass

def analyze_risk_with_groq(title, summary):
    if not GROQ_KEY: return "تعذر التحليل: مفتاح GROQ مفقود."
    prompt = f"حلل مخاطر الائتمان للخبر التالي باختصار شديد جدا (نقاط):\nالعنوان: {title}\nالتفاصيل: {summary}\nالرد بالعربية فقط."
    try:
        data = {"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
        r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_KEY}"}, json=data, timeout=30)
        return r.json()["choices"][0]["message"]["content"]
    except: return "فشل تحليل المخاطر آلياً."

def send_telegram(text):
    global _msg_times
    now = time.time()
    _msg_times = [t for t in _msg_times if now - t < 60]
    if len(_msg_times) >= 18: time.sleep(5)
    
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": False}, timeout=25)
        if r.status_code == 200: _msg_times.append(time.time())
    except: pass

def process_item(title, url, source_name, tab, summary="", exclude_list=None, sent_hashes=None, exclude_except=None):
    if not is_arabic(title): return False, sent_hashes
    
    # فلترة الكلمات المستبعدة
    if exclude_list:
        for ex in exclude_list:
            if ex in title:
                is_safe = False
                if exclude_except:
                    for excp in exclude_except:
                        if excp in title: is_safe = True; break
                if not is_safe: return False, sent_hashes

    h = make_hash(title)
    if sent_hashes is not None and h in sent_hashes: return False, sent_hashes

    # التحليل والإرسال
    risk = analyze_risk_with_groq(title, summary)
    label = TAB_LABELS.get(tab, "📢 أخبار")
    msg = f"{label}\n\n📌 *{title}*\n\n🔍 *تحليل المخاطر:*\n{risk}\n\n🔗 [المصدر: {source_name}]({url})"
    
    send_telegram(msg)
    supabase_insert_hash(h, title)
    if sent_hashes is not None: sent_hashes.add(h)
    return True, sent_hashes

# ══════════════════════════════════════════════════════════════════
# 5. دوال الجلب (المحرك الجديد)
# ══════════════════════════════════════════════════════════════════

def fetch_rss(src, sent_hashes):
    count = 0
    try:
        response = scraper.get(src["url"], timeout=15)
        feed = feedparser.parse(response.text)
        for entry in feed.entries[:15]:
            title = entry.get("title", "").strip()
            url = entry.get("link", "")
            summary = entry.get("summary", "")[:400]
            ok, sent_hashes = process_item(title, url, src["name"], src["tab"], summary, src.get("exclude", []), sent_hashes)
            if ok: count += 1
    except: pass
    return count, sent_hashes

def fetch_scrape(src, sent_hashes):
    count = 0
    try:
        r = scraper.get(src["url"], timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        elements = [a for a in soup.find_all("a", href=True) if len(a.get_text(strip=True)) > 30]
        for el in elements[:20]:
            title = el.get_text(strip=True)
            link = el['href']
            if not link.startswith("http"): link = src["base"] + link
            for prefix in src.get("clean_prefix", []):
                if title.startswith(prefix): title = title[len(prefix):].strip()
            ok, sent_hashes = process_item(title, link, src["name"], src["tab"], "", src.get("exclude", []), sent_hashes, src.get("exclude_except"))
            if ok: count += 1
    except: pass
    return count, sent_hashes

# ══════════════════════════════════════════════════════════════════
# 6. التشغيل الرئيسي
# ══════════════════════════════════════════════════════════════════

def run():
    print("🛡 رادار المخاطر — يعمل بالمحرك الجديد...")
    sent_hashes = supabase_get_hashes()
    if sent_hashes is None: sys.exit(1)

    for src in RSS_SOURCES:
        _, sent_hashes = fetch_rss(src, sent_hashes)
        time.sleep(2)
    
    for src in SCRAPE_SOURCES:
        _, sent_hashes = fetch_scrape(src, sent_hashes)
        time.sleep(2)

if __name__ == "__main__":
    run()
