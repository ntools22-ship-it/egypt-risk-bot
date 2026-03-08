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

# الكلمات المفتاحية للتصنيف
RISK_KW    = ["تعثر","إفلاس","حجز","دعوى","غرامة","خسارة","ديون متعثرة","خفض تصنيف","مخالفة","تصفية","إعسار","حبس","انهيار","أزمة","تحقيق"]
BREAKING_KW= ["عاجل","الآن","للتو","مستجد"]
CBE_KW     = ["البنك المركزي","سعر الفائدة","لجنة السياسة النقدية","ريبو","سياسة نقدية","التضخم","قرار الفائدة"]
FX_KW      = ["سعر الدولار","سعر الصرف","الدولار اليوم","اليورو","احتياطي النقد","تعويم"]
CREDIT_KW  = ["تسهيل ائتماني","قرض مشترك","توريق","سندات","صكوك","تمويل","ائتمان","جدولة"]
WARNING_KW = ["تعثر","إفلاس","حجز","دعوى","غرامة","مخالفة","خفض تصنيف","إعسار"]

SECTOR_KW = {
    "عقارات":    ["عقارات","تطوير عقاري","إسكان","وحدات سكنية"],
    "صناعة":     ["صناعة","مصنع","تصنيع"],
    "طاقة":      ["طاقة","بترول","غاز","كهرباء","نفط"],
    "زراعة":     ["زراعة","محاصيل","أغذية"],
    "تكنولوجيا": ["تكنولوجيا","فنتك","رقمي","ذكاء اصطناعي"],
    "سياحة":     ["سياحة","فنادق","سياحي"],
    "بنوك":      ["بنك","مصرف","بنكي","مصرفي"],
    "تجارة":     ["تجارة","استيراد","تصدير"],
}

TAB_LABELS = {
    "breaking": "⚡ عاجل",
    "banks":    "🏦 أخبار البنوك",
    "credit":   "💰 تمويل وائتمان",
    "warning":  "⚠️ إنذار مبكر",
    "sectors":  "🏗️ أخبار القطاعات",
    "fx":       "💵 أسعار الصرف",
    "cbe":      "🏛️ أخبار المركزي",
    "global":   "🌍 اقتصاد الشرق والعالم",
}

def is_arabic(text):
    arabic = sum(1 for c in text if '\u0600' <= c <= '\u06ff')
    return arabic / max(len(text), 1) > 0.3

def classify(title, summary, source_cat):
    text = (title + " " + summary).lower()
    tabs = [source_cat] if source_cat != "breaking" else []

    risk_score  = sum(1 for k in RISK_KW if k in text)
    is_breaking = any(k in text for k in BREAKING_KW) or source_cat == "breaking"
    is_warning  = any(k in text for k in WARNING_KW) or risk_score >= 2

    if any(k in text for k in CBE_KW)    and "cbe"     not in tabs: tabs.append("cbe")
    if any(k in text for k in FX_KW)     and "fx"      not in tabs: tabs.append("fx")
    if any(k in text for k in CREDIT_KW) and "credit"  not in tabs: tabs.append("credit")
    if any(k in text for k in ["بنك","مصرف"]) and "banks" not in tabs: tabs.append("banks")
    if is_warning and "warning" not in tabs: tabs.append("warning")
    if not tabs: tabs.append("global")

    industry = "عام"
    for sector, kws in SECTOR_KW.items():
        if any(k in text for k in kws):
            industry = sector
            break

    if   risk_score >= 3: risk_level = "حرج 🔴"
    elif risk_score == 2: risk_level = "مرتفع 🟠"
    elif risk_score == 1: risk_level = "متوسط 🟡"
    else:                 risk_level = "منخفض 🟢"

    return {"tabs": tabs, "risk_level": risk_level, "industry": industry,
            "is_breaking": is_breaking, "is_warning": is_warning}

def format_msg(title, url, source_name, cl):
    tabs_str = "  |  ".join(TAB_LABELS.get(t, t) for t in cl["tabs"])
    lines = []
    if cl["is_breaking"]: lines.append("⚡ *عاجل*\n")
    if cl["is_warning"]:  lines.append("🚨 *تحذير مبكر*\n")
    lines.append(f"*{title}*\n")
    lines.append(f"🗂  {tabs_str}")
    lines.append(f"🏭  القطاع: {cl['industry']}")
    lines.append(f"📊  مستوى الخطر: {cl['risk_level']}")
    lines.append(f"📰  المصدر: {source_name}\n")
    lines.append(f"[📎 اقرأ الخبر كاملًا]({url})\n")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("🛡 @egypt_risk_radar")
    return "\n".join(lines)

def send(text):
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHANNEL_ID, "text": text,
            "parse_mode": "Markdown", "disable_web_page_preview": False,
        }, timeout=15)
        return r.status_
