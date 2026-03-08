import feedparser, requests, hashlib, time

BOT_TOKEN  = "8676198122:AAHYs5AWT-vnCv8fTNloDvtAjbz6-chMVlk"
CHANNEL_ID = "@egypt_risk_radar"
API_URL    = f"https://api.telegram.org/bot{BOT_TOKEN}"

SOURCES = [
    {"id": "youm7", "name": "اليوم السابع", "url": "https://www.youm7.com/rss/Section/22", "cat": "breaking"},
    {"id": "febanks_cbe", "name": "في البنوك - المركزي", "url": "https://febanks.com/feed/", "cat": "cbe"},
    {"id": "amwal_cbe", "name": "أموال الغد - مركزي", "url": "https://www.amwalalghad.com/feed/", "cat": "cbe"},
    {"id": "eleqtisad_fx", "name": "الاقتصاد نيوز", "url": "https://www.eliqtisadi.com/feed/", "cat": "fx"},
    {"id": "febanks", "name": "في البنوك", "url": "https://febanks.com/feed/", "cat": "banks"},
    {"id": "hapi", "name": "حابي", "url": "https://hapi.ps/feed/", "cat": "credit"},
    {"id": "masrawy", "name": "مصراوي", "url": "https://www.masrawy.com/news/rss", "cat": "sectors"}
]

RISK_KW = ["تعثر","إفلاس","حجز","دعوى","غرامة","خسارة","ديون","تصفية","إعسار","انهيار"]

def is_arabic(text):
    arabic = sum(1 for c in text if '\u0600' <= c <= '\u06ff')
    return arabic / max(len(text), 1) > 0.3

def classify(title, summary, cat):
    text = (title + " " + summary).lower()
    risk_score = sum(1 for k in RISK_KW if k in text)
    lvl = "حرج 🔴" if risk_score >= 2 else "متوسط 🟡" if risk_score == 1 else "منخفض 🟢"
    return {"risk_level": lvl}

def send(text):
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHANNEL_ID, "text": text,
            "parse_mode": "Markdown", "disable_web_page_preview": False,
        }, timeout=10)
        return r.status_code == 200
    except: return False

def run():
    print("🛡 رادار المخاطر يعمل...")
    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:2]: # نكتفي بآخر خبرين لتجنب تكرار النشر
                title = entry.get("title", "").strip()
                url = entry.get("link", "")
                if not title or not is_arabic(title): continue
                
                cl = classify(title, entry.get("summary", ""), src["cat"])
                msg = f"🔔 *{title}*\n\n📊 الخطر: {cl['risk_level']}\n📰 المصدر: {src['name']}\n\n[📎 الرابط]({url})"
                if send(msg):
                    print(f"✅ تم نشر: {title[:30]}")
                    time.sleep(2)
        except Exception as e: print(f"❌ خطأ: {e}")

if __name__ == "__main__":
    run() # هذه الإزاحة (4 مسافات) هي أهم تعديل
