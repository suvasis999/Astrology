# engine.py
from datetime import datetime, timezone, timedelta
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

RASHI_LIST_EN = list(RASHI_TRANSLATIONS.keys())
NAKSHATRA_LIST_EN = list(NAKSHATRA_TRANSLATIONS.keys())
TITHI_LIST_EN = list(TITHI_TRANSLATIONS.keys())

DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}

AYANAMSHA_MAP = {
    "LAHIRI": swe.SIDM_LAHIRI,
    "RAMAN": swe.SIDM_RAMAN,
    "KRISHNAMURTI": swe.SIDM_KRISHNAMURTI
}

PLANETS_MAP = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE
}

SPECIAL_ASPECTS = {
    "Sun": [7], "Moon": [7], "Mercury": [7], "Venus": [7],
    "Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10],
    "Rahu": [5, 7, 9], "Ketu": [5, 7, 9]
}

# =====================================================================
# TRANSLATION HELPERS
# =====================================================================

def tr_rashi(name_en: str, lang: str) -> str:
    if lang == "en": return name_en
    return RASHI_TRANSLATIONS.get(name_en, {}).get(lang, name_en)

def tr_planet(name_en: str, lang: str) -> str:
    if lang == "en": return name_en
    return PLANET_TRANSLATIONS.get(name_en, {}).get(lang, name_en)

def tr_nakshatra(name_en: str, lang: str) -> str:
    if lang == "en": return name_en
    return NAKSHATRA_TRANSLATIONS.get(name_en, {}).get(lang, name_en)

def tr_tithi(name_en: str, lang: str) -> str:
    if lang == "en": return name_en
    return TITHI_TRANSLATIONS.get(name_en, {}).get(lang, name_en)

def tr_weekday(name_en: str, lang: str) -> str:
    if lang == "en": return name_en
    return WEEKDAY_TRANSLATIONS.get(name_en, {}).get(lang, name_en)

def deg_to_dms(deg: float) -> str:
    d = int(deg)
    mins = (deg - d) * 60.0
    m = int(mins)
    s = round((mins - m) * 60.0)
    if s == 60: s = 0; m += 1
    if m == 60: m = 0; d += 1
    return f"{d:02d}° {m:02d}' {s:02d}\""

def get_nakshatra_and_pada(deg: float, lang: str = "en"):
    tot_min = (deg % 360.0) * 60.0
    nak_idx = int(tot_min // 800.0)
    pada = int((tot_min % 800.0) // 200.0) + 1
    nak_en = NAKSHATRA_LIST_EN[nak_idx]
    nak_translated = tr_nakshatra(nak_en, lang)
    return nak_translated, pada, nak_idx, nak_en

def get_navamsa_rashi(longitude: float) -> int:
    rashi_idx = int(longitude // 30.0)
    deg_in_rashi = longitude % 30.0
    nav_step = int(deg_in_rashi // (30.0 / 9.0))
    element_start = {0: 0, 1: 9, 2: 6, 3: 3}
    start_rashi = element_start[rashi_idx % 4]
    return (start_rashi + nav_step) % 12

def calculate_panchanga(sun_long: float, moon_long: float, birth_dt: datetime, lang: str = "en"):
    diff = (moon_long - sun_long) % 360.0
    tithi_num = int(diff // 12.0) + 1
    
    # Paksha text
    if lang == "hi":
        paksha = "शुक्ल पक्ष" if tithi_num <= 15 else "कृष्ण पक्ष"
    elif lang == "or":
        paksha = "ଶୁକ୍ଳ ପକ୍ଷ" if tithi_num <= 15 else "କୃଷ୍ଣ ପକ୍ଷ"
    else:
        paksha = "Shukla Paksha" if tithi_num <= 15 else "Krishna Paksha"

    tithi_idx = (tithi_num - 1) % 15
    tithi_en = TITHI_LIST_EN[tithi_idx]
    tithi_tr = tr_tithi(tithi_en, lang)
    tithi_name = f"{paksha} {tithi_tr}"

    vara_en = birth_dt.strftime("%A")
    vara_name = tr_weekday(vara_en, lang)

    nak_tr, pada, _, _ = get_nakshatra_and_pada(moon_long, lang)
    pada_label = "चरण" if lang == "hi" else ("ପାଦ" if lang == "or" else "Pada")

    return {
        "tithi": tithi_name,
        "vara": vara_name,
        "nakshatra": f"{nak_tr} ({pada_label} {pada})",
        "yoga": f"Yoga #{int(((sun_long + moon_long) % 360.0) // 13.333) + 1}",
        "karana": f"Karana #{int(diff // 6.0) + 1}"
    }

def calculate_dasha(moon_long: float, birth_dt: datetime, lang: str = "en"):
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
    is_first = True
    today = datetime.now()

    for _ in range(9):
        lord_en = DASHA_ORDER[curr_idx]
        lord_tr = tr_planet(lord_en, lang)
        full_years = DASHA_YEARS[lord_en]
        duration = balance_years if is_first else full_years
        curr_end = curr_start + timedelta(days=duration * 365.25)

        is_active = curr_start <= today <= curr_end

        mahadashas.append({
            "lord": lord_tr,
            "lord_en": lord_en,
            "duration": round(duration, 1),
            "start_date": curr_start.strftime("%Y-%m-%d"),
            "end_date": curr_end.strftime("%Y-%m-%d"),
            "is_active": is_active
        })

        curr_start = curr_end
        curr_idx = (curr_idx + 1) % 9
        is_first = False

    return mahadashas

def get_daily_rashifal(moon_rashi_en: str, lang: str = "en"):
    db = {
        "Aries": {
            "en": {"overall": "High energy driving your day.", "career": "Leadership recognized.", "finance": "Gains from past investments.", "love": "Harmonious relationships.", "health": "High vitality.", "lucky_number": "9", "lucky_color": "Red"},
            "hi": {"overall": "आज आपका ऊर्जा स्तर उच्च रहेगा।", "career": "कार्यक्षेत्र में नेतृत्व क्षमता की सराहना होगी।", "finance": "पुराने निवेश से लाभ संभव।", "love": "संबंधों में मधुरता बनी रहेगी।", "health": "स्वास्थ्य उत्तम रहेगा।", "lucky_number": "9", "lucky_color": "लाल"},
            "or": {"overall": "ଆଜି ଆପଣଙ୍କର ଉତ୍ସାହ ବୃଦ୍ଧି ପାଇବ।", "career": "କର୍ମକ୍ଷେତ୍ରରେ ନେତୃତ୍ୱ ପ୍ରଶଂସିତ ହେବ।", "finance": "ପୁରୁଣା ବିନିଯୋଗରୁ ଲାଭ ମିଳିବ।", "love": "ସମ୍ପର୍କରେ ମଧୁରତା ରହିବ।", "health": "ସ୍ୱାସ୍ଥ୍ୟ ଭଲ ରହିବ।", "lucky_number": "9", "lucky_color": "ଲାଲ୍"}
        },
        "Taurus": {
            "en": {"overall": "Patience and stability will guide you.", "career": "Focus on routine tasks.", "finance": "Good for long-term planning.", "love": "Comfort and warmth at home.", "health": "Take care of throat.", "lucky_number": "6", "lucky_color": "White"},
            "hi": {"overall": "धैर्य और स्थिरता आपको सफलता दिलाएगी।", "career": "नियमित कार्यों पर ध्यान केंद्रित करें।", "finance": "दीर्घकालिक वित्तीय योजना बनाएं।", "love": "पारिवारिक जीवन में शांति रहेगी।", "health": "गले का ध्यान रखें।", "lucky_number": "6", "lucky_color": "सफेद"},
            "or": {"overall": "ଧୈର୍ଯ୍ୟ ଏବଂ ସ୍ଥିରତା ଆପଣଙ୍କୁ ସଫଳତା ଦେବ।", "career": "ନିୟମିତ କାର୍ଯ୍ୟରେ ମନ ଦିଅନ୍ତୁ।", "finance": "ଦୀର୍ଘକାଳୀନ ଯୋଜନା ପାଇଁ ଭଲ ଦିନ।", "love": "ପରିବାରରେ ଶାନ୍ତି ବଜାୟ ରହିବ।", "health": "ଗଳାର ଯତ୍ନ ନିଅନ୍ତୁ।", "lucky_number": "6", "lucky_color": "ଧଳା"}
        }
    }
    
    r_data = db.get(moon_rashi_en, db["Aries"])
    return r_data.get(lang, r_data["en"])

def calculate_astrology(date_str: str, time_str: str, latitude: float, longitude: float, tz_offset: float, ayanamsha_mode: str = "LAHIRI", lang: str = "en"):
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    tz = timezone(timedelta(hours=tz_offset))
    utc_dt = dt.replace(tzinfo=tz).astimezone(timezone.utc)

    jd_ut = swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )

    mode_code = AYANAMSHA_MAP.get(ayanamsha_mode.upper(), swe.SIDM_LAHIRI)
    swe.set_sid_mode(mode_code, 0, 0)
    ayanamsa_val = swe.get_ayanamsa_ut(jd_ut)

    cusps, ascmc = swe.houses(jd_ut, latitude, longitude, b'P')
    sidereal_lagna = (ascmc[0] - ayanamsa_val) % 360.0
    lagna_r_idx = int(sidereal_lagna // 30.0)
    nak_l, pada_l, _, _ = get_nakshatra_and_pada(sidereal_lagna, lang)
    nav_lagna_idx = get_navamsa_rashi(sidereal_lagna)

    lagna_rashi_en = RASHI_LIST_EN[lagna_r_idx]
    nav_lagna_en = RASHI_LIST_EN[nav_lagna_idx]

    lagna_data = {
        "sign": tr_rashi(lagna_rashi_en, lang),
        "sign_en": lagna_rashi_en,
        "sign_index": lagna_r_idx + 1,
        "degree": deg_to_dms(sidereal_lagna % 30.0),
        "nakshatra": nak_l,
        "pada": pada_l,
        "house": 1,
        "navamsa_sign": tr_rashi(nav_lagna_en, lang)
    }

    planets_out = {}
    planets_en = {}
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED

    for name_en, pid in PLANETS_MAP.items():
        res, _ = swe.calc_ut(jd_ut, pid, flags)
        sid_lon = (res[0] - ayanamsa_val) % 360.0
        r_idx = int(sid_lon // 30.0)
        house_num = ((r_idx - lagna_r_idx) % 12) + 1
        nak, pada, _, _ = get_nakshatra_and_pada(sid_lon, lang)
        nav_r_idx = get_navamsa_rashi(sid_lon)

        rashi_en = RASHI_LIST_EN[r_idx]
        nav_rashi_en = RASHI_LIST_EN[nav_r_idx]
        p_name_tr = tr_planet(name_en, lang)

        p_info = {
            "longitude_raw": sid_lon,
            "sign": tr_rashi(rashi_en, lang),
            "sign_en": rashi_en,
            "sign_index": r_idx + 1,
            "degree": deg_to_dms(sid_lon % 30.0),
            "nakshatra": nak,
            "pada": pada,
            "house": house_num,
            "is_retrograde": res[3] < 0 if name_en not in ["Sun", "Moon"] else False,
            "navamsa_sign": tr_rashi(nav_rashi_en, lang),
            "navamsa_house": ((nav_r_idx - nav_lagna_idx) % 12) + 1
        }
        
        planets_out[p_name_tr] = p_info
        planets_en[name_en] = p_info

    # Ketu
    rahu_lon = planets_en["Rahu"]["longitude_raw"]
    ketu_lon = (rahu_lon + 180.0) % 360.0
    ketu_r_idx = int(ketu_lon // 30.0)
    ketu_nak, ketu_pada, _, _ = get_nakshatra_and_pada(ketu_lon, lang)
    ketu_nav_idx = get_navamsa_rashi(ketu_lon)

    ketu_rashi_en = RASHI_LIST_EN[ketu_r_idx]
    ketu_nav_en = RASHI_LIST_EN[ketu_nav_idx]
    ketu_name_tr = tr_planet("Ketu", lang)

    ketu_info = {
        "longitude_raw": ketu_lon,
        "sign": tr_rashi(ketu_rashi_en, lang),
        "sign_en": ketu_rashi_en,
        "sign_index": ketu_r_idx + 1,
        "degree": deg_to_dms(ketu_lon % 30.0),
        "nakshatra": ketu_nak,
        "pada": ketu_pada,
        "house": ((ketu_r_idx - lagna_r_idx) % 12) + 1,
        "is_retrograde": True,
        "navamsa_sign": tr_rashi(ketu_nav_en, lang),
        "navamsa_house": ((ketu_nav_idx - nav_lagna_idx) % 12) + 1
    }
    
    planets_out[ketu_name_tr] = ketu_info
    planets_en["Ketu"] = ketu_info

    houses_out = {}
    navamsa_houses_out = {}

    for h in range(1, 13):
        r_i = (lagna_r_idx + h - 1) % 12
        r_en = RASHI_LIST_EN[r_i]
        houses_out[h] = {
            "sign": tr_rashi(r_en, lang),
            "sign_en": r_en,
            "planets": [p for p, d in planets_out.items() if d["house"] == h]
        }

        nav_r_i = (nav_lagna_idx + h - 1) % 12
        nav_r_en = RASHI_LIST_EN[nav_r_i]
        navamsa_houses_out[h] = {
            "sign": tr_rashi(nav_r_en, lang),
            "sign_en": nav_r_en,
            "planets": [p for p, d in planets_out.items() if d["navamsa_house"] == h]
        }

    aspects = []
    for p_name_en, p_data in planets_en.items():
        s_house = p_data["house"]
        p_name_tr = tr_planet(p_name_en, lang)
        for offset in SPECIAL_ASPECTS.get(p_name_en, [7]):
            t_house = ((s_house - 1 + offset - 1) % 12) + 1
            t_planets = houses_out[t_house]["planets"]
            aspects.append({
                "source": p_name_tr,
                "type": f"{offset}th House Aspect",
                "target_house": t_house,
                "target_sign": houses_out[t_house]["sign"],
                "aspected_planets": t_planets
            })

    panchanga = calculate_panchanga(planets_en["Sun"]["longitude_raw"], planets_en["Moon"]["longitude_raw"], dt, lang)
    dasha = calculate_dasha(planets_en["Moon"]["longitude_raw"], dt, lang)

    return {
        "julian_day": jd_ut,
        "ayanamsha_value": deg_to_dms(ayanamsa_val),
        "lagna": lagna_data,
        "planets": planets_out,
        "planets_en": planets_en,
        "houses": houses_out,
        "navamsa_houses": navamsa_houses_out,
        "panchanga": panchanga,
        "dasha": dasha,
        "aspects": aspects
    }
