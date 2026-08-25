# engine.py
from datetime import datetime, timezone, timedelta
import math
import swisseph as swe

# =====================================================================
# MULTILINGUAL DICTIONARIES (EN / HI / OR)
# =====================================================================

RASHI_TRANSLATIONS = {
    "Aries": {"hi": "मेष", "or": "ମେଷ"},
    "Taurus": {"hi": "वृषभ", "or": "ବୃଷ"},
    "Gemini": {"hi": "मिथुन", "or": "ମିଥୁନ"},
    "Cancer": {"hi": "कर्क", "or": "କର୍କଟ"},
    "Leo": {"hi": "सिंह", "or": "ସିଂହ"},
    "Virgo": {"hi": "कन्या", "or": "କନ୍ୟା"},
    "Libra": {"hi": "तुला", "or": "ତୁଳା"},
    "Scorpio": {"hi": "वृश्चिक", "or": "ବିଛା"},
    "Sagittarius": {"hi": "धनु", "or": "ଧନୁ"},
    "Capricorn": {"hi": "मकर", "or": "ମକର"},
    "Aquarius": {"hi": "कुंभ", "or": "କୁମ୍ଭ"},
    "Pisces": {"hi": "मीन", "or": "ମୀନ"},
}

PLANET_TRANSLATIONS = {
    "Lagna": {"hi": "लग्न", "or": "ଲଗ୍ନ"},
    "Sun": {"hi": "सूर्य", "or": "ସୂର୍ଯ୍ୟ"},
    "Moon": {"hi": "चंद्रमा", "or": "ଚନ୍ଦ୍ର"},
    "Mars": {"hi": "मंगल", "or": "ମଙ୍ଗଳ"},
    "Mercury": {"hi": "बुध", "or": "ବୁଧ"},
    "Jupiter": {"hi": "गुरु", "or": "ଗୁରୁ"},
    "Venus": {"hi": "शुक्र", "or": "ଶୁକ୍ର"},
    "Saturn": {"hi": "शनि", "or": "ଶନି"},
    "Rahu": {"hi": "राहु", "or": "ରାହୁ"},
    "Ketu": {"hi": "केतु", "or": "କେତୁ"},
}

NAKSHATRA_TRANSLATIONS = {
    "Ashwini": {"hi": "अश्विनी", "or": "ଅଶ୍ୱିନୀ"},
    "Bharani": {"hi": "भरणी", "or": "ଭରଣୀ"},
    "Krittika": {"hi": "कृत्तिका", "or": "କୃତ୍ତିକା"},
    "Rohini": {"hi": "रोहिणी", "or": "ରୋହିଣୀ"},
    "Mrigashira": {"hi": "मृगशिरा", "or": "ମୃଗଶିରା"},
    "Ardra": {"hi": "आर्द्रा", "or": "ଆର୍ଦ୍ରା"},
    "Punarvasu": {"hi": "पुनर्वसु", "or": "ପୁନର୍ବସୁ"},
    "Pushya": {"hi": "पुष्य", "or": "ପୁଷ୍ୟା"},
    "Ashlesha": {"hi": "अश्लेषा", "or": "ଅଶ୍ଳେଷା"},
    "Magha": {"hi": "मघा", "or": "ମଘା"},
    "Purva Phalguni": {"hi": "पूर्वाफाल्गुनी", "or": "ପୂର୍ବଫାଲ୍ଗୁନୀ"},
    "Uttara Phalguni": {"hi": "उत्तराफाल्गुनी", "or": "ଉତ୍ତରଫାଲ୍ଗୁନୀ"},
    "Hasta": {"hi": "हस्त", "or": "ହସ୍ତା"},
    "Chitra": {"hi": "चित्रा", "or": "ଚିତ୍ରା"},
    "Swati": {"hi": "स्वाति", "or": "ସ୍ୱାତୀ"},
    "Vishakha": {"hi": "विशाखा", "or": "ବିଶାଖା"},
    "Anuradha": {"hi": "अनुराधा", "or": "ଅନୁରାଧା"},
    "Jyeshtha": {"hi": "ज्येष्ठा", "or": "ଜ୍ୟେଷ୍ଠା"},
    "Mula": {"hi": "मूल", "or": "ମୂଳା"},
    "Purva Ashadha": {"hi": "पूर्वाषाढ़ा", "or": "ପୂର୍ବାଷାଢ଼ା"},
    "Uttara Ashadha": {"hi": "उत्तराषाढ़ा", "or": "ଉତ୍ତରାଷାଢ଼ା"},
    "Shravana": {"hi": "श्रवण", "or": "ଶ୍ରବଣା"},
    "Dhanishta": {"hi": "धनिष्ठा", "or": "ଧନିଷ୍ଠା"},
    "Shatabhisha": {"hi": "शतभिषा", "or": "ଶତଭିଷା"},
    "Purva Bhadrapada": {"hi": "पूर्वाभाद्रपद", "or": "ପୂର୍ବଭାଦ୍ରପଦ"},
    "Uttara Bhadrapada": {"hi": "उत्तराभाद्रपद", "or": "ଉତ୍ତରଭାଦ୍ରପଦ"},
    "Revati": {"hi": "रेवती", "or": "ରେବତୀ"},
}

TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shasthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima / Amavasya"
]

TITHI_TRANSLATIONS = {
    "Pratipada": {"hi": "प्रतिपदा", "or": "ପ୍ରତିପଦା"},
    "Dwitiya": {"hi": "द्वितीया", "or": "ଦ୍ୱିତୀୟା"},
    "Tritiya": {"hi": "तृतीया", "or": "ତୃତୀୟା"},
    "Chaturthi": {"hi": "चतुर्थी", "or": "ଚତୁର୍ଥୀ"},
    "Panchami": {"hi": "पंचमी", "or": "ପଞ୍ଚମୀ"},
    "Shasthi": {"hi": "षष्ठी", "or": "ଷଷ୍ଠୀ"},
    "Saptami": {"hi": "सप्तमी", "or": "ସପ୍ତମୀ"},
    "Ashtami": {"hi": "अष्टमी", "or": "ଅଷ୍ଟମୀ"},
    "Navami": {"hi": "नवमी", "or": "ନବମୀ"},
    "Dashami": {"hi": "दशमी", "or": "ଦଶମୀ"},
    "Ekadashi": {"hi": "एकादशी", "or": "ଏକାଦଶୀ"},
    "Dwadashi": {"hi": "द्वादशी", "or": "ଦ୍ୱାଦଶୀ"},
    "Trayodashi": {"hi": "त्रयोदशी", "or": "ତ୍ରୟୋଦଶୀ"},
    "Chaturdashi": {"hi": "चतुर्दशी", "or": "ଚତୁର୍ଦ୍ଦଶୀ"},
    "Purnima / Amavasya": {"hi": "पूर्णिमा / अमावस्या", "or": "ପୂର୍ଣ୍ଣିମା / ଅମାବାସ୍ୟା"},
}

WEEKDAY_TRANSLATIONS = {
    "Monday": {"hi": "सोमवार", "or": "ସୋମବାର"},
    "Tuesday": {"hi": "मंगलवार", "or": "ମଙ୍ଗଳବାର"},
    "Wednesday": {"hi": "बुधवार", "or": "ବୁଧବାର"},
    "Thursday": {"hi": "गुरुवार", "or": "ଗୁରୁବାର"},
    "Friday": {"hi": "शुक्रवार", "or": "ଶୁକ୍ରବାର"},
    "Saturday": {"hi": "शनिवार", "or": "ଶନିବାର"},
    "Sunday": {"hi": "रविवार", "or": "ରବିବାର"},
}

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarma", "Dhriti", "Shoola", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti"
]

KARANA_SEQUENCE = [
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti"
]

RASHI_LIST_EN = list(RASHI_TRANSLATIONS.keys())
NAKSHATRA_LIST_EN = list(NAKSHATRA_TRANSLATIONS.keys())

DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}

AYANAMSHA_MAP = {
    "LAHIRI": swe.SIDM_LAHIRI,
    "RAMAN": swe.SIDM_RAMAN,
    "KRISHNAMURTI": swe.SIDM_KRISHNAMURTI,
}

PLANETS_MAP = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
}

SPECIAL_ASPECTS = {
    "Sun": [7],
    "Moon": [7],
    "Mercury": [7],
    "Venus": [7],
    "Mars": [4, 7, 8],
    "Jupiter": [5, 7, 9],
    "Saturn": [3, 7, 10],
    "Rahu": [5, 7, 9],
    "Ketu": [5, 7, 9],
}

HOUSE_LORDS = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

EXALTATION = {
    "Sun": "Aries",
    "Moon": "Taurus",
    "Mars": "Capricorn",
    "Mercury": "Virgo",
    "Jupiter": "Cancer",
    "Venus": "Pisces",
    "Saturn": "Libra",
}

DEBILITATION = {
    "Sun": "Libra",
    "Moon": "Scorpio",
    "Mars": "Cancer",
    "Mercury": "Pisces",
    "Jupiter": "Capricorn",
    "Venus": "Virgo",
    "Saturn": "Aries",
}

OWN_SIGNS = {
    "Sun": {"Leo"},
    "Moon": {"Cancer"},
    "Mars": {"Aries", "Scorpio"},
    "Mercury": {"Gemini", "Virgo"},
    "Jupiter": {"Sagittarius", "Pisces"},
    "Venus": {"Taurus", "Libra"},
    "Saturn": {"Capricorn", "Aquarius"},
}

COMBUST_ORBS = {
    "Moon": 12.0,
    "Mars": 17.0,
    "Mercury": 14.0,
    "Jupiter": 11.0,
    "Venus": 10.0,
    "Saturn": 15.0,
}

# =====================================================================
# TRANSLATION / FORMAT HELPERS
# =====================================================================

def tr_rashi(name_en: str, lang: str) -> str:
    if lang == "en":
        return name_en
    return RASHI_TRANSLATIONS.get(name_en, {}).get(lang, name_en)


def tr_planet(name_en: str, lang: str) -> str:
    if lang == "en":
        return name_en
    return PLANET_TRANSLATIONS.get(name_en, {}).get(lang, name_en)


def tr_nakshatra(name_en: str, lang: str) -> str:
    if lang == "en":
        return name_en
    return NAKSHATRA_TRANSLATIONS.get(name_en, {}).get(lang, name_en)


def tr_tithi(name_en: str, lang: str) -> str:
    if lang == "en":
        return name_en
    return TITHI_TRANSLATIONS.get(name_en, {}).get(lang, name_en)


def tr_weekday(name_en: str, lang: str) -> str:
    if lang == "en":
        return name_en
    return WEEKDAY_TRANSLATIONS.get(name_en, {}).get(lang, name_en)


def deg_to_dms(deg: float) -> str:
    d = int(deg)
    mins = (deg - d) * 60.0
    m = int(mins)
    s = round((mins - m) * 60.0)
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d:02d}° {m:02d}' {s:02d}\""


def angular_distance(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def get_nakshatra_and_pada(deg: float, lang: str = "en"):
    tot_min = (deg % 360.0) * 60.0
    nak_idx = int(tot_min // 800.0)
    pada = int((tot_min % 800.0) // 200.0) + 1
    nak_en = NAKSHATRA_LIST_EN[nak_idx]
    return tr_nakshatra(nak_en, lang), pada, nak_idx, nak_en


def get_navamsa_rashi(longitude: float) -> int:
    rashi_idx = int(longitude // 30.0)
    deg_in_rashi = longitude % 30.0
    nav_step = int(deg_in_rashi // (30.0 / 9.0))
    element_start = {0: 0, 1: 9, 2: 6, 3: 3}
    start_rashi = element_start[rashi_idx % 4]
    return (start_rashi + nav_step) % 12


def sign_name(index: int) -> str:
    return RASHI_LIST_EN[index % 12]


# =====================================================================
# PANCHANGA
# =====================================================================

def calculate_panchanga(sun_long: float, moon_long: float, birth_dt: datetime, lang: str = "en"):
    diff = (moon_long - sun_long) % 360.0
    tithi_num = int(diff // 12.0) + 1

    if lang == "hi":
        paksha = "शुक्ल पक्ष" if tithi_num <= 15 else "कृष्ण पक्ष"
    elif lang == "or":
        paksha = "ଶୁକ୍ଳ ପକ୍ଷ" if tithi_num <= 15 else "କୃଷ୍ଣ ପକ୍ଷ"
    else:
        paksha = "Shukla Paksha" if tithi_num <= 15 else "Krishna Paksha"

    tithi_idx = (tithi_num - 1) % 15
    tithi_en = TITHI_NAMES[tithi_idx]
    tithi_name = f"{paksha} {tr_tithi(tithi_en, lang)}"

    vara_en = birth_dt.strftime("%A")
    vara_name = tr_weekday(vara_en, lang)

    nak_tr, pada, _, nak_en = get_nakshatra_and_pada(moon_long, lang)
    pada_label = "चरण" if lang == "hi" else ("ପାଦ" if lang == "or" else "Pada")

    yoga_idx = int(((sun_long + moon_long) % 360.0) // (360.0 / 27.0))
    yoga_name = YOGA_NAMES[yoga_idx]

    half_tithi = int(diff // 6.0) + 1
    if half_tithi == 1:
        karana_name = "Kimstughna"
    elif half_tithi >= 58:
        karana_name = ["Shakuni", "Chatushpada", "Naga"][min(half_tithi - 58, 2)]
    else:
        karana_name = KARANA_SEQUENCE[(half_tithi - 2) % 7]

    return {
        "tithi": tithi_name,
        "tithi_number": tithi_num,
        "paksha": paksha,
        "vara": vara_name,
        "vara_en": vara_en,
        "nakshatra": f"{nak_tr} ({pada_label} {pada})",
        "nakshatra_en": nak_en,
        "nakshatra_pada": pada,
        "yoga": yoga_name,
        "yoga_number": yoga_idx + 1,
        "karana": karana_name,
        "karana_number": half_tithi,
    }


# =====================================================================
# VIMSHOTTARI DASHA
# =====================================================================

def _period_entry(lord_en, start_dt, duration_years, lang):
    end_dt = start_dt + timedelta(days=duration_years * 365.25)
    now = datetime.now()
    return {
        "lord": tr_planet(lord_en, lang),
        "lord_en": lord_en,
        "duration": round(duration_years, 4),
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "end_date": end_dt.strftime("%Y-%m-%d"),
        "is_active": start_dt <= now <= end_dt,
        "_start": start_dt,
        "_end": end_dt,
    }


def calculate_vimshottari(moon_long: float, birth_dt: datetime, lang: str = "en"):
    tot_min = (moon_long % 360.0) * 60.0
    nak_idx = int(tot_min // 800.0)
    first_lord_idx = nak_idx % 9
    first_lord_name = DASHA_ORDER[first_lord_idx]

    rem_min = 800.0 - (tot_min % 800.0)
    fraction_remaining = rem_min / 800.0
    balance_years = DASHA_YEARS[first_lord_name] * fraction_remaining

    mahadashas = []
    curr_start = birth_dt
    curr_idx = first_lord_idx

    for i in range(9):
        lord_en = DASHA_ORDER[curr_idx]
        duration = balance_years if i == 0 else DASHA_YEARS[lord_en]
        md = _period_entry(lord_en, curr_start, duration, lang)

        antardashas = []
        ad_start = md["_start"]
        for offset in range(9):
            ad_lord_idx = (curr_idx + offset) % 9
            ad_lord = DASHA_ORDER[ad_lord_idx]
            ad_duration = duration * DASHA_YEARS[ad_lord] / 120.0
            ad = _period_entry(ad_lord, ad_start, ad_duration, lang)

            pratyantardashas = []
            pd_start = ad["_start"]
            for p_offset in range(9):
                pd_lord_idx = (ad_lord_idx + p_offset) % 9
                pd_lord = DASHA_ORDER[pd_lord_idx]
                pd_duration = ad_duration * DASHA_YEARS[pd_lord] / 120.0
                pd = _period_entry(pd_lord, pd_start, pd_duration, lang)
                pratyantardashas.append({k: v for k, v in pd.items() if not k.startswith("_")})
                pd_start = pd["_end"]

            ad_clean = {k: v for k, v in ad.items() if not k.startswith("_")}
            ad_clean["pratyantardasha"] = pratyantardashas
            antardashas.append(ad_clean)
            ad_start = ad["_end"]

        md_clean = {k: v for k, v in md.items() if not k.startswith("_")}
        md_clean["antardasha"] = antardashas
        mahadashas.append(md_clean)

        curr_start = md["_end"]
        curr_idx = (curr_idx + 1) % 9

    current_md = next((d for d in mahadashas if d["is_active"]), None)
    current_ad = None
    current_pd = None
    if current_md:
        current_ad = next((d for d in current_md["antardasha"] if d["is_active"]), None)
        if current_ad:
            current_pd = next((d for d in current_ad["pratyantardasha"] if d["is_active"]), None)

    return {
        "mahadasha": mahadashas,
        "current_mahadasha": current_md,
        "current_antardasha": current_ad,
        "current_pratyantardasha": current_pd,
    }


def calculate_dasha(moon_long: float, birth_dt: datetime, lang: str = "en"):
    # Backward-compatible old key.
    return calculate_vimshottari(moon_long, birth_dt, lang)["mahadasha"]


# =====================================================================
# DIVISIONAL CHARTS
# =====================================================================

def _uniform_varga(longitude: float, division: int, start_rule: str = "same") -> int:
    sign_idx = int(longitude // 30.0)
    deg = longitude % 30.0
    part = int(deg // (30.0 / division))

    if start_rule == "same":
        start = sign_idx
    elif start_rule == "movable_fixed_dual":
        modality = sign_idx % 3
        start = sign_idx if modality == 0 else ((sign_idx + 8) % 12 if modality == 1 else (sign_idx + 4) % 12)
    else:
        start = sign_idx

    return (start + part) % 12


def divisional_sign(longitude: float, division: int) -> int:
    sign_idx = int(longitude // 30.0)
    deg = longitude % 30.0
    odd_sign = sign_idx % 2 == 0  # Aries is index 0.

    if division == 1:
        return sign_idx

    if division == 2:  # Hora
        first_half = deg < 15.0
        if odd_sign:
            return 4 if first_half else 3  # Leo / Cancer
        return 3 if first_half else 4

    if division == 3:  # Drekkana
        part = int(deg // 10.0)
        return (sign_idx + [0, 4, 8][part]) % 12

    if division == 4:  # Chaturthamsha
        part = int(deg // 7.5)
        return (sign_idx + [0, 3, 6, 9][part]) % 12

    if division == 7:  # Saptamsha
        part = int(deg // (30.0 / 7.0))
        start = sign_idx if odd_sign else (sign_idx + 6) % 12
        return (start + part) % 12

    if division == 9:
        return get_navamsa_rashi(longitude)

    if division == 10:  # Dashamsha
        part = int(deg // 3.0)
        start = sign_idx if odd_sign else (sign_idx + 8) % 12
        return (start + part) % 12

    if division == 12:  # Dwadashamsha
        part = int(deg // 2.5)
        return (sign_idx + part) % 12

    if division == 16:
        return _uniform_varga(longitude, 16)

    if division == 20:
        return _uniform_varga(longitude, 20)

    if division == 24:
        return _uniform_varga(longitude, 24)

    if division == 27:
        return _uniform_varga(longitude, 27)

    if division == 30:  # Simplified Parashara Trimshamsha sign mapping
        x = deg
        if odd_sign:
            if x < 5: return 0
            if x < 10: return 10
            if x < 18: return 8
            if x < 25: return 2
            return 6
        else:
            if x < 5: return 1
            if x < 12: return 5
            if x < 20: return 11
            if x < 25: return 9
            return 7

    if division in (40, 45, 60):
        return _uniform_varga(longitude, division)

    return _uniform_varga(longitude, division)


def build_divisional_chart(planets_en: dict, lagna_longitude: float, division: int, lang: str):
    lagna_idx = divisional_sign(lagna_longitude, division)
    houses = {}

    for h in range(1, 13):
        s_idx = (lagna_idx + h - 1) % 12
        houses[h] = {
            "sign": tr_rashi(sign_name(s_idx), lang),
            "sign_en": sign_name(s_idx),
            "planets": [],
        }

    planets = {}
    for name_en, p in planets_en.items():
        s_idx = divisional_sign(p["longitude_raw"], division)
        h = ((s_idx - lagna_idx) % 12) + 1
        planets[name_en] = {
            "sign": tr_rashi(sign_name(s_idx), lang),
            "sign_en": sign_name(s_idx),
            "sign_index": s_idx + 1,
            "house": h,
        }
        houses[h]["planets"].append(tr_planet(name_en, lang))

    return {
        "division": division,
        "lagna_sign": tr_rashi(sign_name(lagna_idx), lang),
        "lagna_sign_en": sign_name(lagna_idx),
        "lagna_sign_index": lagna_idx + 1,
        "houses": houses,
        "planets": planets,
    }


# =====================================================================
# DIGNITY / COMBUSTION / HOUSE LORDS
# =====================================================================

def calculate_dignity(name_en: str, sign_en: str) -> str:
    if name_en in ("Rahu", "Ketu"):
        return "Node"
    if EXALTATION.get(name_en) == sign_en:
        return "Exalted"
    if DEBILITATION.get(name_en) == sign_en:
        return "Debilitated"
    if sign_en in OWN_SIGNS.get(name_en, set()):
        return "Own Sign"
    return "Neutral"


def calculate_combustion(planets_en: dict):
    sun_lon = planets_en["Sun"]["longitude_raw"]
    result = {}
    for name, p in planets_en.items():
        if name in ("Sun", "Rahu", "Ketu"):
            result[name] = False
            continue
        orb = COMBUST_ORBS.get(name)
        result[name] = angular_distance(p["longitude_raw"], sun_lon) <= orb if orb else False
    return result


def calculate_house_lords(lagna_r_idx: int, planets_en: dict, lang: str):
    out = {}
    for house in range(1, 13):
        sign_idx = (lagna_r_idx + house - 1) % 12
        sign_en = sign_name(sign_idx)
        lord_en = HOUSE_LORDS[sign_en]
        lord_house = planets_en.get(lord_en, {}).get("house")
        out[house] = {
            "sign": tr_rashi(sign_en, lang),
            "sign_en": sign_en,
            "lord": tr_planet(lord_en, lang),
            "lord_en": lord_en,
            "lord_house": lord_house,
        }
    return out


# =====================================================================
# YOGAS / DOSHAS
# =====================================================================

def _house_distance(from_house: int, to_house: int) -> int:
    return ((to_house - from_house) % 12) + 1


def calculate_yogas(planets_en: dict, house_lords: dict, lang: str):
    yogas = []

    sun = planets_en["Sun"]
    moon = planets_en["Moon"]
    mars = planets_en["Mars"]
    mercury = planets_en["Mercury"]
    jupiter = planets_en["Jupiter"]
    venus = planets_en["Venus"]
    saturn = planets_en["Saturn"]

    # Budha-Aditya
    if sun["sign_index"] == mercury["sign_index"]:
        yogas.append({
            "code": "BUDHA_ADITYA",
            "name": "Budha-Aditya Yoga",
            "present": True,
            "basis": "Sun and Mercury occupy the same sign."
        })

    # Chandra-Mangala
    if moon["sign_index"] == mars["sign_index"] or _house_distance(moon["house"], mars["house"]) == 7:
        yogas.append({
            "code": "CHANDRA_MANGALA",
            "name": "Chandra-Mangala Yoga",
            "present": True,
            "basis": "Moon and Mars are conjunct or mutually opposite."
        })

    # Gaja-Kesari - Jupiter in kendra from Moon
    if _house_distance(moon["house"], jupiter["house"]) in (1, 4, 7, 10):
        yogas.append({
            "code": "GAJA_KESARI",
            "name": "Gaja-Kesari Yoga",
            "present": True,
            "basis": "Jupiter is in a Kendra from Moon."
        })

    # Panch Mahapurusha - planet in Kendra and own/exalted sign
    for p_name in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        p = planets_en[p_name]
        dignity = calculate_dignity(p_name, p["sign_en"])
        if p["house"] in (1, 4, 7, 10) and dignity in ("Own Sign", "Exalted"):
            yogas.append({
                "code": f"MAHAPURUSHA_{p_name.upper()}",
                "name": f"{p_name} Mahapurusha Yoga",
                "present": True,
                "basis": f"{p_name} is in a Kendra in {dignity.lower()}."
            })

    # Simple Dhana-yoga indicator: 2nd/11th lords connected to 5th/9th lords by same house.
    wealth_lords = {house_lords[2]["lord_en"], house_lords[11]["lord_en"]}
    trinal_lords = {house_lords[5]["lord_en"], house_lords[9]["lord_en"]}
    found = False
    for w in wealth_lords:
        for t in trinal_lords:
            if w in planets_en and t in planets_en and planets_en[w]["house"] == planets_en[t]["house"]:
                found = True
    if found:
        yogas.append({
            "code": "DHANA_SIMPLE",
            "name": "Dhana Yoga Indicator",
            "present": True,
            "basis": "A wealth-house lord is associated with a trinal-house lord."
        })

    return yogas


def calculate_manglik(planets_en: dict):
    mars_house = planets_en["Mars"]["house"]
    manglik_houses = {1, 2, 4, 7, 8, 12}
    return {
        "present": mars_house in manglik_houses,
        "mars_house": mars_house,
        "rule": "Mars in 1, 2, 4, 7, 8 or 12 from Lagna.",
    }


def calculate_kaal_sarp(planets_en: dict):
    rahu = planets_en["Rahu"]["longitude_raw"]
    ketu = planets_en["Ketu"]["longitude_raw"]
    classical = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

    def arc_contains(start, end, x):
        start %= 360
        end %= 360
        x %= 360
        if start <= end:
            return start <= x <= end
        return x >= start or x <= end

    side1 = all(arc_contains(rahu, ketu, planets_en[p]["longitude_raw"]) for p in classical)
    side2 = all(arc_contains(ketu, rahu, planets_en[p]["longitude_raw"]) for p in classical)

    return {
        "present": side1 or side2,
        "basis": "All seven classical planets lie between the Rahu-Ketu axis on one side."
    }


def calculate_pitru_indicator(planets_en: dict):
    sun = planets_en["Sun"]
    rahu = planets_en["Rahu"]
    ketu = planets_en["Ketu"]
    conjunction_rahu = angular_distance(sun["longitude_raw"], rahu["longitude_raw"]) <= 10
    conjunction_ketu = angular_distance(sun["longitude_raw"], ketu["longitude_raw"]) <= 10
    ninth_affliction = sun["house"] == 9 and (rahu["house"] == 9 or ketu["house"] == 9)

    return {
        "present": conjunction_rahu or conjunction_ketu or ninth_affliction,
        "basis": "Simplified indicator using Sun-node conjunction or node involvement in the 9th house.",
        "note": "Pitru Dosha traditions vary; treat this as an indicator, not a definitive judgment."
    }


# =====================================================================
# TRANSITS / SADE SATI / DHAIYA
# =====================================================================

def get_current_sidereal_positions(ayanamsha_mode: str = "LAHIRI"):
    now = datetime.now(timezone.utc)
    jd = swe.julday(
        now.year, now.month, now.day,
        now.hour + now.minute / 60.0 + now.second / 3600.0
    )
    mode_code = AYANAMSHA_MAP.get(ayanamsha_mode.upper(), swe.SIDM_LAHIRI)
    swe.set_sid_mode(mode_code, 0, 0)
    ay = swe.get_ayanamsa_ut(jd)

    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    out = {}
    for name, pid in PLANETS_MAP.items():
        res, _ = swe.calc_ut(jd, pid, flags)
        lon = (res[0] - ay) % 360.0
        out[name] = {
            "longitude_raw": lon,
            "sign_en": sign_name(int(lon // 30)),
            "sign_index": int(lon // 30) + 1,
            "is_retrograde": res[3] < 0 if name not in ("Sun", "Moon") else False,
        }

    out["Ketu"] = {
        "longitude_raw": (out["Rahu"]["longitude_raw"] + 180.0) % 360.0,
    }
    out["Ketu"]["sign_en"] = sign_name(int(out["Ketu"]["longitude_raw"] // 30))
    out["Ketu"]["sign_index"] = int(out["Ketu"]["longitude_raw"] // 30) + 1
    out["Ketu"]["is_retrograde"] = True
    return out


def calculate_saturn_phases(natal_moon_sign_idx: int, transits: dict):
    saturn_idx = transits["Saturn"]["sign_index"] - 1
    prev_sign = (natal_moon_sign_idx - 1) % 12
    same_sign = natal_moon_sign_idx
    next_sign = (natal_moon_sign_idx + 1) % 12

    sade_sati = saturn_idx in {prev_sign, same_sign, next_sign}
    phase = None
    if saturn_idx == prev_sign:
        phase = "Rising / First Phase"
    elif saturn_idx == same_sign:
        phase = "Peak / Second Phase"
    elif saturn_idx == next_sign:
        phase = "Setting / Third Phase"

    distance_from_moon = ((saturn_idx - natal_moon_sign_idx) % 12) + 1
    dhaiya = distance_from_moon in (4, 8)

    return {
        "sade_sati": {
            "present": sade_sati,
            "phase": phase,
            "saturn_sign": transits["Saturn"]["sign_en"],
        },
        "dhaiya": {
            "present": dhaiya,
            "saturn_from_moon_house": distance_from_moon,
            "saturn_sign": transits["Saturn"]["sign_en"],
        },
    }


# =====================================================================
# STRENGTH SUMMARY
# =====================================================================

def calculate_strength_summary(planets_en: dict, combustion: dict):
    """
    This is a transparent practical strength summary, NOT a full classical
    Shadbala calculation. Full Shadbala requires more sub-components and
    tradition-specific handling.
    """
    out = {}
    for name, p in planets_en.items():
        if name in ("Rahu", "Ketu"):
            continue

        score = 50
        dignity = calculate_dignity(name, p["sign_en"])

        if dignity == "Exalted":
            score += 30
        elif dignity == "Own Sign":
            score += 20
        elif dignity == "Debilitated":
            score -= 25

        if p["house"] in (1, 4, 7, 10):
            score += 10
        elif p["house"] in (5, 9):
            score += 8

        if p.get("is_retrograde"):
            score += 5

        if combustion.get(name):
            score -= 15

        score = max(0, min(100, score))
        label = "Very Strong" if score >= 80 else "Strong" if score >= 65 else "Average" if score >= 45 else "Weak"

        out[name] = {
            "score": score,
            "label": label,
            "dignity": dignity,
            "combust": bool(combustion.get(name)),
            "retrograde": bool(p.get("is_retrograde")),
        }

    return {
        "method": "practical_summary_v1",
        "is_classical_shadbala": False,
        "note": "This score is a practical summary, not full classical Shadbala.",
        "planets": out,
    }


# =====================================================================
# DAILY RASHIFAL
# =====================================================================

def get_daily_rashifal(moon_rashi_en: str, lang: str = "en"):
    db = {
        "Aries": {
            "en": {"overall": "High energy driving your day.", "career": "Leadership recognized.", "finance": "Gains from past investments.", "love": "Harmonious relationships.", "health": "High vitality.", "lucky_number": "9", "lucky_color": "Red"},
            "hi": {"overall": "आज आपका ऊर्जा स्तर उच्च रहेगा।", "career": "कार्यक्षेत्र में नेतृत्व क्षमता की सराहना होगी।", "finance": "पुराने निवेश से लाभ संभव।", "love": "संबंधों में मधुरता बनी रहेगी।", "health": "स्वास्थ्य उत्तम रहेगा।", "lucky_number": "9", "lucky_color": "लाल"},
            "or": {"overall": "ଆଜି ଆପଣଙ୍କର ଉତ୍ସାହ ବୃଦ୍ଧି ପାଇବ।", "career": "କର୍ମକ୍ଷେତ୍ରରେ ନେତୃତ୍ୱ ପ୍ରଶଂସିତ ହେବ।", "finance": "ପୁରୁଣା ବିନିଯୋଗରୁ ଲାଭ ମିଳିବ।", "love": "ସମ୍ପର୍କରେ ମଧୁରତା ରହିବ।", "health": "ସ୍ୱାସ୍ଥ୍ୟ ଭଲ ରହିବ।", "lucky_number": "9", "lucky_color": "ଲାଲ୍"},
        },
        "Taurus": {
            "en": {"overall": "Patience and stability will guide you.", "career": "Focus on routine tasks.", "finance": "Good for long-term planning.", "love": "Comfort and warmth at home.", "health": "Take care of throat.", "lucky_number": "6", "lucky_color": "White"},
            "hi": {"overall": "धैर्य और स्थिरता आपको सफलता दिलाएगी।", "career": "नियमित कार्यों पर ध्यान केंद्रित करें।", "finance": "दीर्घकालिक वित्तीय योजना बनाएं।", "love": "पारिवारिक जीवन में शांति रहेगी।", "health": "गले का ध्यान रखें।", "lucky_number": "6", "lucky_color": "सफेद"},
            "or": {"overall": "ଧୈର୍ଯ୍ୟ ଏବଂ ସ୍ଥିରତା ଆପଣଙ୍କୁ ସଫଳତା ଦେବ।", "career": "ନିୟମିତ କାର୍ଯ୍ୟରେ ମନ ଦିଅନ୍ତୁ।", "finance": "ଦୀର୍ଘକାଳୀନ ଯୋଜନା ପାଇଁ ଭଲ ଦିନ।", "love": "ପରିବାରରେ ଶାନ୍ତି ବଜାୟ ରହିବ।", "health": "ଗଳାର ଯତ୍ନ ନିଅନ୍ତୁ।", "lucky_number": "6", "lucky_color": "ଧଳା"},
        },
    }
    r_data = db.get(moon_rashi_en, db["Aries"])
    return r_data.get(lang, r_data["en"])


# =====================================================================
# MAIN ASTROLOGY ENGINE
# =====================================================================

def calculate_astrology(
    date_str: str,
    time_str: str,
    latitude: float,
    longitude: float,
    tz_offset: float,
    ayanamsha_mode: str = "LAHIRI",
    lang: str = "en",
    node_type: str = "MEAN",
):
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    tz = timezone(timedelta(hours=tz_offset))
    utc_dt = dt.replace(tzinfo=tz).astimezone(timezone.utc)

    jd_ut = swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
    )

    mode_code = AYANAMSHA_MAP.get(ayanamsha_mode.upper(), swe.SIDM_LAHIRI)
    swe.set_sid_mode(mode_code, 0, 0)
    ayanamsa_val = swe.get_ayanamsa_ut(jd_ut)

    cusps, ascmc = swe.houses(jd_ut, latitude, longitude, b'P')
    sidereal_lagna = (ascmc[0] - ayanamsa_val) % 360.0
    lagna_r_idx = int(sidereal_lagna // 30.0)
    nak_l, pada_l, _, _ = get_nakshatra_and_pada(sidereal_lagna, lang)
    nav_lagna_idx = get_navamsa_rashi(sidereal_lagna)

    lagna_rashi_en = sign_name(lagna_r_idx)
    nav_lagna_en = sign_name(nav_lagna_idx)

    lagna_data = {
        "longitude_raw": sidereal_lagna,
        "sign": tr_rashi(lagna_rashi_en, lang),
        "sign_en": lagna_rashi_en,
        "sign_index": lagna_r_idx + 1,
        "degree": deg_to_dms(sidereal_lagna % 30.0),
        "nakshatra": nak_l,
        "pada": pada_l,
        "house": 1,
        "navamsa_sign": tr_rashi(nav_lagna_en, lang),
    }

    # Optional mean/true node
    node_pid = swe.TRUE_NODE if str(node_type).upper() == "TRUE" else swe.MEAN_NODE
    planets_map = dict(PLANETS_MAP)
    planets_map["Rahu"] = node_pid

    planets_out = {}
    planets_en = {}
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED

    for name_en, pid in planets_map.items():
        res, _ = swe.calc_ut(jd_ut, pid, flags)
        sid_lon = (res[0] - ayanamsa_val) % 360.0
        r_idx = int(sid_lon // 30.0)
        house_num = ((r_idx - lagna_r_idx) % 12) + 1
        nak, pada, _, nak_en = get_nakshatra_and_pada(sid_lon, lang)
        nav_r_idx = get_navamsa_rashi(sid_lon)

        rashi_en = sign_name(r_idx)
        nav_rashi_en = sign_name(nav_r_idx)
        p_name_tr = tr_planet(name_en, lang)

        p_info = {
            "longitude_raw": sid_lon,
            "latitude_raw": res[1],
            "distance_au": res[2],
            "speed_longitude": res[3],
            "sign": tr_rashi(rashi_en, lang),
            "sign_en": rashi_en,
            "sign_index": r_idx + 1,
            "degree": deg_to_dms(sid_lon % 30.0),
            "nakshatra": nak,
            "nakshatra_en": nak_en,
            "pada": pada,
            "house": house_num,
            "is_retrograde": res[3] < 0 if name_en not in ["Sun", "Moon"] else False,
            "navamsa_sign": tr_rashi(nav_rashi_en, lang),
            "navamsa_sign_en": nav_rashi_en,
            "navamsa_house": ((nav_r_idx - nav_lagna_idx) % 12) + 1,
            "dignity": calculate_dignity(name_en, rashi_en),
        }

        planets_out[p_name_tr] = p_info
        planets_en[name_en] = dict(p_info)

    # Ketu
    rahu_lon = planets_en["Rahu"]["longitude_raw"]
    ketu_lon = (rahu_lon + 180.0) % 360.0
    ketu_r_idx = int(ketu_lon // 30.0)
    ketu_nak, ketu_pada, _, ketu_nak_en = get_nakshatra_and_pada(ketu_lon, lang)
    ketu_nav_idx = get_navamsa_rashi(ketu_lon)

    ketu_rashi_en = sign_name(ketu_r_idx)
    ketu_nav_en = sign_name(ketu_nav_idx)
    ketu_name_tr = tr_planet("Ketu", lang)

    ketu_info = {
        "longitude_raw": ketu_lon,
        "latitude_raw": -planets_en["Rahu"].get("latitude_raw", 0),
        "distance_au": planets_en["Rahu"].get("distance_au", 0),
        "speed_longitude": planets_en["Rahu"].get("speed_longitude", 0),
        "sign": tr_rashi(ketu_rashi_en, lang),
        "sign_en": ketu_rashi_en,
        "sign_index": ketu_r_idx + 1,
        "degree": deg_to_dms(ketu_lon % 30.0),
        "nakshatra": ketu_nak,
        "nakshatra_en": ketu_nak_en,
        "pada": ketu_pada,
        "house": ((ketu_r_idx - lagna_r_idx) % 12) + 1,
        "is_retrograde": True,
        "navamsa_sign": tr_rashi(ketu_nav_en, lang),
        "navamsa_sign_en": ketu_nav_en,
        "navamsa_house": ((ketu_nav_idx - nav_lagna_idx) % 12) + 1,
        "dignity": "Node",
    }

    planets_out[ketu_name_tr] = ketu_info
    planets_en["Ketu"] = dict(ketu_info)

    # Combustion
    combustion = calculate_combustion(planets_en)
    for name_en, p in planets_en.items():
        p["is_combust"] = bool(combustion.get(name_en))
        translated_name = tr_planet(name_en, lang)
        if translated_name in planets_out:
            planets_out[translated_name]["is_combust"] = bool(combustion.get(name_en))

    # Houses D1 / D9
    houses_out = {}
    navamsa_houses_out = {}

    for h in range(1, 13):
        r_i = (lagna_r_idx + h - 1) % 12
        r_en = sign_name(r_i)
        houses_out[h] = {
            "sign": tr_rashi(r_en, lang),
            "sign_en": r_en,
            "lord": tr_planet(HOUSE_LORDS[r_en], lang),
            "lord_en": HOUSE_LORDS[r_en],
            "planets": [p for p, d in planets_out.items() if d["house"] == h],
        }

        nav_r_i = (nav_lagna_idx + h - 1) % 12
        nav_r_en = sign_name(nav_r_i)
        navamsa_houses_out[h] = {
            "sign": tr_rashi(nav_r_en, lang),
            "sign_en": nav_r_en,
            "planets": [p for p, d in planets_out.items() if d["navamsa_house"] == h],
        }

    # Aspects
    aspects = []
    for p_name_en, p_data in planets_en.items():
        s_house = p_data["house"]
        p_name_tr = tr_planet(p_name_en, lang)
        for offset in SPECIAL_ASPECTS.get(p_name_en, [7]):
            t_house = ((s_house - 1 + offset - 1) % 12) + 1
            t_planets = houses_out[t_house]["planets"]
            aspects.append({
                "source": p_name_tr,
                "source_en": p_name_en,
                "type": f"{offset}th House Aspect",
                "target_house": t_house,
                "target_sign": houses_out[t_house]["sign"],
                "target_sign_en": houses_out[t_house]["sign_en"],
                "aspected_planets": t_planets,
            })

    # Core calculations
    panchanga = calculate_panchanga(
        planets_en["Sun"]["longitude_raw"],
        planets_en["Moon"]["longitude_raw"],
        dt,
        lang,
    )

    vimshottari = calculate_vimshottari(
        planets_en["Moon"]["longitude_raw"],
        dt,
        lang,
    )

    dasha = vimshottari["mahadasha"]  # backward-compatible

    # Divisional charts
    divisions = [1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60]
    charts = {}
    for division in divisions:
        charts[f"D{division}"] = build_divisional_chart(
            planets_en,
            sidereal_lagna,
            division,
            lang,
        )

    # House lords, yogas, doshas
    house_lords = calculate_house_lords(lagna_r_idx, planets_en, lang)
    yogas = calculate_yogas(planets_en, house_lords, lang)

    manglik = calculate_manglik(planets_en)
    kaal_sarp = calculate_kaal_sarp(planets_en)
    pitru = calculate_pitru_indicator(planets_en)

    # Current transits + Saturn phases
    transits_en = get_current_sidereal_positions(ayanamsha_mode)
    transits = {}
    for name_en, p in transits_en.items():
        transits[tr_planet(name_en, lang)] = {
            **p,
            "sign": tr_rashi(p["sign_en"], lang),
        }

    natal_moon_idx = planets_en["Moon"]["sign_index"] - 1
    saturn_phases = calculate_saturn_phases(natal_moon_idx, transits_en)

    # Strength summary (transparent non-classical Shadbala placeholder)
    strength = calculate_strength_summary(planets_en, combustion)

    return {
        "julian_day": jd_ut,
        "ayanamsha_mode": ayanamsha_mode.upper(),
        "ayanamsha_value": deg_to_dms(ayanamsa_val),
        "node_type": str(node_type).upper(),

        # Existing keys - keep React Native compatible
        "lagna": lagna_data,
        "planets": planets_out,
        "planets_en": planets_en,
        "houses": houses_out,
        "navamsa_houses": navamsa_houses_out,
        "panchanga": panchanga,
        "dasha": dasha,
        "aspects": aspects,

        # New keys
        "charts": charts,
        "vimshottari": vimshottari,
        "house_lords": house_lords,
        "yogas": yogas,
        "doshas": {
            "manglik": manglik,
            "kaal_sarp": kaal_sarp,
            "pitru_indicator": pitru,
            "sade_sati": saturn_phases["sade_sati"],
            "dhaiya": saturn_phases["dhaiya"],
        },
        "strength": strength,
        "transits": transits,
        "calculation_notes": [
            "Planetary longitudes, Lagna and transits are based on Swiss Ephemeris.",
            "Divisional chart rules can vary between Vedic traditions; verify the selected tradition before production use.",
            "The strength section is a practical summary and is not full classical Shadbala.",
            "Pitru Dosha is returned only as a simplified indicator because traditions use different rules.",
        ],
    }
