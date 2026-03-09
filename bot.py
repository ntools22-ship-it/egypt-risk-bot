import feedparser, requests, hashlib, time, os

BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = "@egypt_risk_radar"
API_URL    = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ─── المصادر ───────────────────────────────────────────────────────────────
# tab = None → ينشر فقط لو مطابق كلمات مفتاحية (إنذار مبكر أو تمويل)
SOURCES = [

    # ⚡ عاجل
    {"id": "youm7_breaking",    "name": "اليوم السابع",          "url": "https://www.youm7.com/rss/Section/65",                                                                          "tab": "breaking"},

    # 🏦 أخبار البنوك
    {"id": "amwal_banks",       "name": "أموال الغد - بنوك",     "url": "https://amwalalghad.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-%d9%85%d8%a7%d9%84%d9%8a%d8%a9/feed/", "tab": "banks"},

    # 💰 تمويل وائتمان (مصادر ثابتة)
    {"id": "amwal_micro",       "name": "أموال الغد - تمويل",    "url": "https://amwalalghad.com/tag/%d9%85%d8%aa%d9%86%d8%a7%d9%87%d9%8a-%d8%a7%d9%84%d8%b5%d8%ba%d8%b1/feed/",       "tab": "credit"},
    {"id": "hapi_credit",       "name": "حابي - تمويل",          "url": "https://hapijournal.com/category/%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/",                                       "tab": "credit"},
    {"id": "motawwer_credit",   "name": "المطور - تمويل",        "url": "https://almotawwer.com/tag/%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%b9%d8%a7%d8%aa-%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%b1%d8%a9/feed/", "tab": "credit"},

    # 💵 أسعار الدولار
    {"id": "hapi_fx",           "name": "حابي - دولار",          "url": "https://hapijournal.com/tag/%d8%a3%d8%b3%d8%b9%d8%a7%d8%b1-%d8%a7%d9%84%d8%af%d9%88%d9%84%d8%a7%d8%b1/feed/", "tab": "fx"},

    # 🏛️ أخبار المركزي
    {"id": "almal_cbe",         "name": "المال - مركزي",         "url": "https://almalnews.com/tag/%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A/feed/", "tab": "cbe"},

    # 🌍 اقتصاد الشرق والعالم
    {"id": "alarabiya_economy", "name": "العربية - اقتصاد",      "url": "https://www.alarabiya.net/aswaq/economy.rss",                                                                   "tab": "global"},

    # 🏗️ القطاعات الفرعية
    {"id": "borsaa_agri",       "name": "البورصة نيوز - زراعة",  "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b2%d8%b1%d8%a7%d8%b9%d8%a9/feed/",                           "tab": "sector_agri"},
    {"id": "borsaa_industry",   "name": "البورصة نيوز - صناعة",  "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d8%a9/feed/",                           "tab": "sector_industry"},
    {"id": "borsaa_realestate", "name": "البورصة نيوز - عقارات", "url": "https://www.alborsaanews.com/category/%d8%a7%d9%84%d8%b9%d9%82%d8%a7%d8%b1%d8%a7%d8%aa/feed/",                "tab": "sector_realestate"},
    {"id": "amwal_energy",      "name": "أموال الغد - طاقة",     "url": "https://amwalalghad.com/category/%d8%b7%d8%a7%d9%82%d8%a9/feed/",                                             "tab": "sector_energy"},
    {"id": "amwal_transport",   "name": "أموال الغد - نقل",      "url": "https://amwalalghad.com/category/%d9%86%d9%82%d9%84-%d9%88-%d9%85%d9%84%d8%a7%d8%ad%d8%a9/feed/",             "tab": "sector_transport"},
    {"id": "amwal_tech",        "name": "أموال الغد - تكنولوجيا","url": "https://amwalalghad.com/category/%d8%aa%d9%83%d9%86%d9%88%d9%84%d9%88%d8%ac%d9%8a%d8%a7-%d9%88%d8%a7%d8%aa%d8%b5%d8%a7%d9%84%d8%a7%d8%aa/feed/", "tab": "sector_tech"},

    # ⚠️ إنذار مبكر — مسح بكلمات مفتاحية (tab=None)
    {"id": "amwal_all",         "name": "أموال الغد",            "url": "https://amwalalghad.com/feed/",                  "tab": None},
    {"id": "hapi_all",          "name": "حابي",                  "url": "https://hapijournal.com/feed/",                  "tab": None},
    {"id": "almal_all",         "name": "المال",                 "url": "https://almalnews.com/feed/",                    "tab": None},
    {"id": "febanks_all",       "name": "في البنوك",             "url": "https://febanks.com/feed/",                      "tab": None},
    {"id": "sahm_all",          "name": "سهم نيوز",              "url": "https://sahmnews.com/feed/",                     "tab": None},
    {"id": "borsaa_all",        "name": "البورصة نيوز",          "url": "https://www.alborsaanews.com/feed/",             "tab": None},
    {"id": "mubasher_all",      "name": "مباشر",                 "url": "https://www.mubasher.info/feed/",                "tab": None},
    {"id": "elborsa_all",       "name": "البورصة",               "url": "https://www.elborsa.com/feed/",                  "tab": None},
    {"id": "masrawy_econ",      "name": "مصراوي اقتصاد",        "url": "https://www.masrawy.com/news/economy/rss",        "tab": None},
    {"id": "youm7_econ",        "name": "اليوم السابع اقتصاد",  "url": "https://www.youm7.com/rss/Section/97",            "tab": None},
]

# ─── تسميات التبويبات ───────────────────────────────────────────────────────
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

# ─── كلمات مفتاحية — إنذار مبكر ────────────────────────────────────────────
WARNING_KW = [
    # تعثر وسداد
    "تعثر", "تعثر في السداد", "عجز عن السداد", "توقف عن السداد",
    "ديون متعثرة", "قروض متعثرة", "محفظة متعثرة", "ديون رديئة",
    "مخصصات", "شطب ديون", "استرداد ديون", "NPL",
    # إفلاس وإعسار
    "إفلاس", "شهر إفلاس", "إعسار", "تصفية", "حراسة قضائية",
    "إدارة قضائية", "تعليق النشاط", "وقف الأعمال",
    "بيع أصول قسري", "تنازل عن أصول",
    # قانوني ومالي
    "حجز على أصول", "حجز على أموال", "دعوى قضائية", "نزاع مالي",
    "غرامة مالية", "خفض تصنيف", "تخفيض تصنيف", "جدولة ديون",
    "إعادة جدولة", "أزمة سيولة", "خسائر متراكمة", "مخالفة مالية",
    "انهيار", "أزمة مالية", "إغلاق شركة", "شركة في ورطة",
]

# ─── كلمات مفتاحية — تمويل وائتمان ────────────────────────────────────────
CREDIT_KW = [
    "تسهيل ائتماني", "تسهيلات ائتمانية", "قرض", "تمويل",
    "خط ائتماني", "توريق", "سندات", "صكوك", "قرض مشترك",
    "تمويل مشترك", "اتفاقية تمويل", "اتفاقية قرض", "ائتمان",
    "حصلت على تمويل", "وقعت اتفاقية", "منحة قرض", "موافقة ائتمانية",
    "اعتماد مستندي", "ضمانات بنكية", "رسملة", "بروتوكول تمويل",
    "مذكرة تفاهم", "تمويل مشروع", "تمويل المشروعات الصغيرة",
    "متناهي الصغر", "تمويل متناهي", "قرض ميسر",
]

# ─── دوال مساعدة ────────────────────────────────────────────────────────────
def is_arabic(text):
    count = sum(1 for c in text if '\u0600' <= c <= '\u06ff')
    return count / max(len(text), 1) > 0.3

def get_tabs(title, summary, primary_tab):
    text = title + " " + summary
    tabs = []

    # التبويب الأساسي للمصدر
    if primary_tab:
        tabs.append(primary_tab)

    # فحص كلمات إنذار مبكر
    if any(k in text for k in WARNING_KW) and "warning" not in tabs:
        tabs.append("warning")

    # فحص كلمات تمويل وائتمان
    if any(k in text for k in CREDIT_KW) and "credit" not in tabs:
        tabs.append("credit")

    return tabs

def format_msg(title, url, source_name, tabs):
    tabs_str = "  |  ".join(TAB_LABELS.get(t, t) for t in tabs)
    safe_title = title.replace("*","").replace("[","").replace("]","").replace("_","\\_")
    lines = [
        f"[{safe_title}]({url})",
        f"🗂  {tabs_str}",
        f"📰  {source_name}",
        "",
        "━━━━━━━━━━━━━━━━",
        "🛡 @egypt\\_risk\\_radar",
    ]
    return "\n".join(lines)

def send(text):
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Send error: {e}")
        return False

SENT_FILE = "sent_hashes.txt"

def load_sent():
    try:
        with open(SENT_FILE) as f:
            return set(f.read().splitlines())
    except:
        return set()

def save_hash(h):
    with open(SENT_FILE, "a") as f:
        f.write(h + "\n")

def make_hash(title):
    # hash على العنوان فقط لمنع التكرار من مصادر متعددة
    return hashlib.md5(title.strip().encode()).hexdigest()

# ─── التشغيل ─────────────────────────────────────────────────────────────────
def run():
    print("🛡 رادار المخاطر — يعمل...")
    sent = load_sent()
    new_count = 0

    for src in SOURCES:
        print(f"  📡 {src['name']}...")
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:10]:
                title   = entry.get("title", "").strip()
                url     = entry.get("link", "")
                summary = entry.get("summary", "")[:400]

                if not title or not url:
                    continue
                if not is_arabic(title):
                    continue

                h = make_hash(title)
                if h in sent:
                    continue

                tabs = get_tabs(title, summary, src["tab"])

                # مصادر إنذار مبكر (tab=None) — لا تنشر إلا لو فيه تطابق
                if not tabs:
                    continue

                msg = format_msg(title, url, src["name"], tabs)

                if send(msg):
                    sent.add(h)
                    save_hash(h)
                    new_count += 1
                    print(f"    ✅ {title[:60]}")
                    time.sleep(2)
                else:
                    print(f"    ❌ فشل: {title[:40]}")

        except Exception as e:
            print(f"    ⚠️ خطأ في {src['name']}: {e}")

    print(f"\n✅ تم نشر {new_count} خبر جديد")

if __name__ == "__main__":
    run()
