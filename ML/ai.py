import joblib
import json
import pandas as pd
import re
import os

def normalize_arabic(text):
    text = str(text)
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ؤ", "و", text)
    text = re.sub(r"ئ", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\d+", " ", text)   
    text = re.sub(r"\s+", " ", text)  
    return text.strip()

base_dir = os.path.dirname(os.path.abspath(__file__))
model = joblib.load(os.path.join(base_dir, "model.pkl"))
vectorizer = joblib.load(os.path.join(base_dir, "vectorizer.pkl"))



CATEGORY_KEYWORDS = {
    "رياضة": [
        "الاهلي", "الزمالك", "مباراه", "كره", "ليفربول",
        "ريال مدريد", "برشلونه", "دوري", "كاس", "هدف",
        "بطوله", "رياضه", "لاعب", "منتخب", "فوز", "تعادل",
        "ملعب", "مصارعه", "خيول", "سباق", "تزلج", "جودو",
        "مانشستر", "باريس"
    ],
    "سياسه": [
        "الرييس", "الحكومه", "البرلمان", "انتخابات", "وزير",
        "سياسي", "الدوله", "وزاره", "ادان", "تدين", "ايران",
        "الخارجيه", "الداخليه", "الامن", "اعتداء", "ارهابي",
        "تضامن", "السعوديه", "البحرين", "الكويت", "قطر",
        "مسيره", "دفاع", "جوي", "عسكري", "صاروخ",
    "هجوم", "تفجير", "قتيل", "مسلح"
    ],
    "فن": [
        "فيلم", "مسلسل", "ممثل", "فنان", "اغنيه", "مهرجان",
        "وفاه", "مطرب", "مغني", "نجم", "نجمه", "موسيقي",
        "سينما", "مسرح", "اوركسترا"
    ],
    "اجتماعيه": [
        "حادث", "مدرسه", "جامعه", "اسره", "طفل", "مستشفي",
        "شركه", "اقتصاد", "تجاره", "سوق", "مبادره", "مجلس",
        "غرفه", "ابوظبي", "الشارقه", "عجمان", "اطلاق", "تعاون"
    ]
}



TEMPLATES = {
    "رياضة": "templates/sports.png",
    "سياسة": "templates/politics.png",
    "فن": "templates/art.png",
    "اجتماعية": "templates/social.png",
    "عام": "templates/default.png"
}



def classify_news(title, content=None):

    
    if content:
        text = title + " " + content
    else:
        text = title

    text = normalize_arabic(text)


    title = normalize_arabic(title)



    try:
        X = vectorizer.transform([title])

        probs = model.predict_proba(X)[0]
        classes = model.classes_

        best_index = probs.argmax()

        ml_category = classes[best_index]
        ml_confidence = float(probs[best_index])
        print(title)
        print("CATEGORY:", ml_category)
        print("CONFIDENCE:", ml_confidence)
    except Exception:
        ml_category = None
        ml_confidence = 0



    if ml_category and ml_confidence >= 0.40:   
        return ml_category, ml_confidence

    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title:
                scores[cat] += 1

    best = max(scores.items(), key=lambda kv: kv[1])[0]
    score = scores[best]

    if score >= 1:                              
        return best, 0.5


    if ml_category:
        return ml_category, ml_confidence

    return None, 0.0
