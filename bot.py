# رادار المخاطر — نسخة GitHub Actions النهائية
import feedparser
import requests
import hashlib
import time

# إعدادات البوت والقناة
BOT_TOKEN  = "8676198122:AAHYs5AWT-vnCv8fTNloDvtAjbz6-chMVlk"
CHANNEL_ID = "@egypt_risk_radar"
API_URL    = f"https://api.telegram.org/bot{BOT_TOKEN}"

# المصادر الإخبارية
SOURCES = [
    {"id": "youm7",        "name": "اليوم السابع",        "url": "https://www.youm7.com/rss/Section/22", "cat": "breaking"},
    {"id": "febanks_cbe",  "name": "في البنوك - المركزي", "url": "https://febanks.com/feed/",            "cat": "cbe"},
    {"id": "amwal_cbe",    "name": "أموال الغد - مركزي",  "url": "https://www.amwalalghad.com/feed/",    "cat": "cbe"},
    {"id": "eleqtisad_fx", "name": "الاقتصاد نيوز",       "url": "https://www.eliqtisadi.com/feed/",     "cat": "fx"},
    {"id": "amwal_fx",     "name": "أموال الغد - صرف",    "url": "https://www.amwalalghad.com/feed/",    "cat": "fx"},
    {"id": "febanks",      "name": "في البنوك",            "url": "https://febanks.com/feed/",            "cat": "banks"},
    {"id": "amwal_banks",  "name": "أموال الغد - بنوك",   "url": "https://www.amwalalghad.com/feed/",    "cat": "banks"},
    {"id": "sahm_news",    "name": "سهم نيوز",             "url": "https://sahmnews.com/feed/",           "cat": "banks"},
    {"id": "hapi",         "name": "حابي",                 "url": "https://hapi.ps/feed/",                "cat": "credit"},
    {"id": "almal",        "name": "المال",                "url": "https://almalnews.com/feed/",          "cat": "credit"},
    {"id": "amwal_main",   "name": "أموال الغد",           "url": "https://www.amwalalghad.com/feed/",    "cat": "sectors"},
    {"id": "masrawy",      "name": "مصراوي",               "url": "https://www.masrawy.com/news/rss",     "cat": "sectors"},
    {"id": "skynews_ar",   "name": "سكاي نيوز عربية",     "url": "https://www.skynewsarabia.com/rss",    "cat": "global"},
    {"id": "mubasher",     "name": "مباشر",                "url": "https://www.mubasher.info/feed",       "cat": "global"},
    {"id": "alaraby",      "name": "العربي الجديد",        "url": "https://www.alaraby.co.uk/feed",       "cat": "global"},
]

# الكلمات المفتاحية
RISK_KW = ["تعثر","إفلاس","حجز","دعوى","غرامة","خسارة","ديون متعثرة","خفض تصنيف","مخالفة","تصفية","إعسار","انهيار"]
SECTOR_KW = {
    "عقارات": ["عقارات","تطوير عقاري","إسكان"],
    "بنوك": ["بنك","مصرف","بنكي","مصرفي"],
    "طاقة": ["طاقة","بترول","غاز","كهرباء"],
    "تكنولوجيا": ["تكنولوجيا","فنتك","ذكاء اصطناعي"]
}

def is_arabic(text):
    arabic = sum(1 for c in text if '\u0600' <= c <= '\u06ff')
    return arabic / max(len(text), 1) > 0.3

def classify(title, summary, source_cat):
    text = (title + " " + summary).lower()
    risk_score = sum(1 for k in RISK_KW if k in text)
    industry = "عام"
    for sector, kws in SECTOR_KW.items():
        if any(k in text for k in kws):
            industry = sector
            break
    
    if risk_score >= 2: risk_level = "حرج 🔴"
    elif risk_score == 1: risk_level = "متوسط 🟡"
    else: risk_level = "منخفض 🟢"
    
    return {"risk_level": risk_level, "industry": industry}

def send(text):
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHANNEL_ID, "text": text,
            "parse_mode": "Markdown", "disable_web_page_preview": False,
        }, timeout=10)
        return r.status_code == 200
    except:
        return False

def run():
    print("🛡 رادار المخاطر بدأ العمل...")
    new_count = 0
    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:2]: # فحص آخر خبرين فقط لتجنب التكرار
                title = entry.get("title", "").strip()
                url = entry.get("link", "")
                if not title or not is_arabic(title): continue
                
                cl = classify(title, entry.get("summary", ""), src["cat"])
                msg = (f"🔔 *{title}*\n\n"
                       f"📊 مستوى الخطر: {cl['risk_level']}\n"
                       f"🏭 القطاع: {cl['industry']}\n"
                       f"📰 المصدر: {src['name']}\n\n"
                       f"[📎 رابط الخبر]({url})")
                
                if send(msg):
                    new_count += 1
                    print(f"✅ تم نشر: {title[:30]}")
                    time.sleep(2)
        except Exception as e:
            print(f"❌ خطأ في {src['name']}: {e}")
    print(f"\n✅ اكتملت المهمة بنجاح.")

if __name__ == "__main__":
    run()
