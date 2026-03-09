import feedparser, requests, hashlib, time, os, json
from datetime import datetime, timezone, timedelta

BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY  = os.environ.get("GEMINI_API_KEY", "")
CHANNEL_ID  = "@egypt_risk_radar"
API_URL     = f"https://api.telegram.org/bot{BOT_TOKEN}"
GEMINI_URL  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

SOURCES = [
    {"id": "youm7_breaking",    "name": "اليوم السابع",           "url": "https://www.youm7.com/rss/Section/65",                                                                                                              "tab": "breaking"},
    {"id": "amwal_banks",       "name": "أموال الغد - بنوك",      "url": "https://amwalalghad.com/category/%d8%a8%d9%86%d9%88%d9%83-%d9%88%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-%d9%85%d8%a7%d9%84%d9%8a%d8%a9/feed/",     "tab": "banks"},
    {"id": "amwal_micro",       "name": "أموال الغد - تمويل",     "url": "https://amwalalghad.com/tag/%d9%85%d8%aa%d9%86%d8%a7%d9%87%d9%8a-%d8%a7%d9%84%d8%b5%d8%ba%d8%b1/feed/",                                           "tab": "credit"},
    {"id": "hapi_credit",       "name": "حابي - تمويل",           "url": "https://hapijournal.com/category/%d8%aa%d9%85%d9%88%d9%8a%d9%84/feed/",                                                                             "tab": "credit"},
    {"id": "motawwer_credit",   "name": "المطور - تمويل",         "url": "https://almotawwer.com/tag/%d8%aa%d9%85%d9%88%d9%8a%d9%84-%d8%a7%d9%84%d9%85%d8%b4%d8%b1%d9%88%d8%b9%d8%a7%d8%aa-%d8%a7%d9%84%d8%b5%d8%ba%d9%8a%d8%b1%d8%a9/feed/", "tab": "credit"},
    {"id": "hapi_fx",           "name": "حابي - دولار",           "url": "https://hapijournal.com/tag/%d8%a3%d8%b3%d8%b9%d8%a7%d8%b1-%d8%a7%d9%84%d8%af%d9%88%d9%84%d8%a7%d8%b1/feed/",                                     "tab": "fx"},
    {"id": "almal_cbe",         "name": "المال - مركزي",          "url": "https://almalnews.com/tag/%D8%A7%D9%84%D8%A8%D9%86%D9%83-%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A-%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A/feed/", "tab": "cbe"},
    {"id": "alarabiya_economy", "name": "العربية - اقتصاد",       "url": "https://www.alarabiya.net/aswaq/economy.rss",                                                                                                       "tab": "global"},
    {"id": "borsaa_agri",       "name": "البورصة نيوز - زراعة",   "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b2%d8%b1%d8%a7%d8%b9%d8%a9/feed/",                                                                "tab": "sector_agri"},
    {"id": "borsaa_industry",   "name": "البورصة نيوز - صناعة",   "url": "https://www.alborsaanews.com/tag/%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d8%a9/feed/",                                                                "tab": "sector_industry"},
    {"id": "borsaa_realestate", "name": "البورصة نيوز - عقارات",  "url": "https://www.alborsaanews.com/category/%d8%a7%d9%84%d8%b9%d9%82%d8%a7%d8%b1%d8%a7%d8%aa/feed/",                                                     "tab": "sector_realestate"},
    {"id": "amwal_energy",      "name": "أموال الغد - طاقة",      "url": "https://amwalalghad.com/category/%d8%b7%d8%a7%d9%82%d8%a9/feed/",                                                                                   "tab": "sector_energy"},
    {"id": "amwal_transport",   "name": "أموال الغد - نقل",       "url": "https://amwalalghad.com/category/%d9%86%d9%82%d9%84-%d9%88-%d9%85%d9%84%d8%a7%d8%ad%d8%a9/feed/",                                                  "tab": "sector_transport"},
    {"id": "amwal_tech",        "name": "أموال الغد - تكنولوجيا", "url": "https://amwalalghad.com/category/%d8%aa%d9%83%d9%86%d9%88%d9%84%d9%88%d8%ac%d9%8a%d8%a7-%d9%88%d8%a7%d8%aa%d8%b5%d8%a7%d9%84%d8%a7%d8%aa/feed/",  "tab": "sector_tech"},
    {"id": "amwal_all",         "name": "أموال الغد",             "url": "https://amwalalghad.com/feed/",              "tab": None},
    {"id": "hapi_all",          "name": "حابي",                   "url": "https://hapijournal.com/feed/",              "tab": None},
    {"id": "almal_all",         "name": "المال",                  "url": "https://almalnews.com/feed/",                "tab": None},
    {"id": "febanks_all",       "name": "في البنوك",              "url": "https://febanks.com/feed/",                  "tab": None},
    {"id": "sahm_all",          "name": "سهم نيوز",               "url": "https://sahmnews.com/feed/",                 "tab": None},
    {"id": "borsaa_all",        "name": "البورصة نيوز",           "url": "https://www.alborsaanews.com/feed/",         "tab": None},
    {"id": "mubasher_all",      "name": "مباشر",                  "url": "https://www.mubasher.info/feed/",            "tab": None},
    {"id": "elborsa_all",       "name": "البورصة",                "url": "https://www.elborsa.com/feed/",              "tab": None},
    {"id": "masrawy_econ",      "name": "مصراوي اقتصاد",         "url": "https://www.masrawy.com/news/economy/rss",    "tab": None},
    {"id": "youm7_econ",        "name": "اليوم السابع اقتصاد",   "url": "https://www.youm7.com/rss/Section/97",        "tab": None},
]

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
    "تعثر", "تعثر في السداد", "عجز عن السداد", "توقف عن السداد",
    "ديون متعثرة", "قروض متعثرة", "محفظة متعثرة", "ديون رديئة",
    "مخصصات", "شطب ديون", "استرداد ديون", "NPL",
    "إفلاس", "شهر إفلاس", "إعسار", "تصفية", "حراسة قضائية",
    "إدارة قضائية", "تعليق النشاط", "وقف الأعمال",
    "بيع أصول قسري", "تنازل عن أصول",
    "حجز على أصول", "حجز على أموال", "دعوى قضائية", "نزاع مالي",
    "غرامة مالية", "خفض تصنيف", "تخفيض تصنيف", "جدولة ديون",
    "إعادة جدولة", "أزمة سيولة", "خسائر متراكمة", "مخالفة مالية",
    "انهيار", "أزمة مالية", "إغلاق شركة",
]

CREDIT_KW = [
    "تسهيل ائتماني", "تسهيلات ائتمانية", "قرض", "تمويل",
    "خط ائتماني", "توريق", "سندات", "صكوك", "قرض مشترك",
    "تمويل مشترك", "اتفاقية تمويل", "اتفاقية قرض", "ائتمان",
    "حصلت على تمويل", "وقعت اتفاقية", "منحة قرض", "موافقة ائتمانية",
    "اعتماد مستندي", "ضمانات بنكية", "رسملة", "بروتوكول تمويل",
    "مذكرة تفاهم", "تمويل مشروع", "متناهي الصغر", "قرض ميسر",
]

DAILY_LOG = "daily_news.json"
SENT_FILE = "sent_hashes.txt"


# ─── دوال مساعدة ──────────────────────────────────────────────────────────────

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
        "time":   datetime.now(timezone.utc).isoformat()
    })
    with open(DAILY_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


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
    return hashlib.md5(title.strip().encode()).hexdigest()


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
    lines = [
        f"[{safe_title}]({url})",
        f"🗂  {tabs_str}",
        f"📰  {source_name}",
        "",
        "━━━━━━━━━━━━━━━━",
        "🛡 @egypt\\_risk\\_radar",
    ]
    return "\n".join(lines)


# ─── Gemini تحليل يومي ────────────────────────────────────────────────────────

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
    recent = []
    for item in log:
        try:
            t = datetime.fromisoformat(item["time"])
            if t >= cutoff:
                recent.append(item)
        except:
            pass
    return recent


def group_by_tab(news_list):
    grouped = {}
    for item in news_list:
        for tab in item["tabs"]:
            if tab not in grouped:
                grouped[tab] = []
            grouped[tab].append(item["title"])
    return grouped


def build_prompt(tab_label, headlines):
    headlines_text = "\n".join(f"- {h}" for h in headlines)
    return f"""أنت محلل أول في قسم المخاطر والائتمان والاستعلامات في أحد البنوك المصرية الكبرى.
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

    grouped    = group_by_tab(news)
    now        = datetime.now(timezone.utc) + timedelta(hours=2)  # توقيت مصر
    date_str   = now.strftime("%d/%m/%Y")
    total      = len(news)
    tabs_count = len(grouped)

    # رسالة افتتاحية جذابة
    intro = (
        f"🗞️ *نشرة رادار المخاطر — {date_str}*\n"
        f"_تقرير يومي شامل لمتخصصي الائتمان والمخاطر_\n\n"
        f"رصدنا اليوم *{total} خبراً* في *{tabs_count} قطاعات*\n"
        f"فيما يلي الموجز والتحليل المهني لكل قطاع 👇\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🛡 @egypt\\_risk\\_radar"
    )
    send(intro)
    time.sleep(3)

    # ترتيب التبويبات بالأولوية
    priority = [
        "warning", "credit", "cbe", "banks", "fx", "global",
        "breaking", "sector_agri", "sector_industry", "sector_realestate",
        "sector_energy", "sector_transport", "sector_tech"
    ]
    ordered_tabs = sorted(
        grouped.keys(),
        key=lambda x: priority.index(x) if x in priority else 99
    )

    for tab in ordered_tabs:
        headlines = grouped[tab]
        if not headlines:
            continue

        tab_label = TAB_LABELS.get(tab, tab)
        print(f"  🤖 Gemini يحلل: {tab_label} ({len(headlines)} خبر)...")

        prompt   = build_prompt(tab_label, headlines)
        analysis = ask_gemini(prompt)

        if not analysis:
            continue

        # تنظيف علامات Markdown من Gemini
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

    # رسالة ختامية
    outro = (
        f"✅ *انتهى تقرير اليوم*\n\n"
        f"تابع أخبار السوق لحظة بلحظة على قناة رادار المخاطر\n"
        f"🛡 @egypt\\_risk\\_radar"
    )
    send(outro)
    print("✅ انتهى الموجز اليومي")


# ─── التشغيل الرئيسي ──────────────────────────────────────────────────────────

def run():
    mode = os.environ.get("RUN_MODE", "news")

    if mode == "digest":
        run_daily_digest()
        return

    print("🛡 رادار المخاطر — يعمل...")
    sent      = load_sent()
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
                if not tabs:
                    continue

                msg = format_msg(title, url, src["name"], tabs)

                if send(msg):
                    sent.add(h)
                    save_hash(h)
                    save_to_daily_log(title, url, src["name"], tabs)
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
