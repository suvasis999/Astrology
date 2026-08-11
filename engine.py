# engine.py
from datetime import datetime, timezone, timedelta
import swisseph as swe

# =====================================================================
# CONSTANTS & VEDIC DATA DICTIONARIES
# =====================================================================

RASHI_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shasthi", "Saptami",
    "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi",
    "Purnima / Amavasya"
]

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Sobhana", "Atiganda", "Sukarma",
    "Dhriti", "Soola", "Ganda", "Vriddhi", "Dhruva", "Vyaghat", "Harshana", "Vajra",
    "Siddhi", "Vatayana", "Variyan", "Parigha", "Shiva", "Siddha", "Sadhya", "Subha",
    "Sukla", "Brahma", "Aindra", "Vaidhriti"
]

KARANA_NAMES = [
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti (Bhadra)",
    "Sakuni", "Chatushpada", "Naga", "Kintughna"
]

DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10,
    "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17
}

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
# MATHEMATICAL & CONVERSION HELPERS
# =====================================================================

def deg_to_dms(deg: float) -> str:
    d = int(deg)
    mins = (deg - d) * 60.0
    m = int(mins)
    s = round((mins - m) * 60.0)
    if s == 60: s = 0; m += 1
    if m == 60: m = 0; d += 1
    return f"{d:02d}° {m:02d}' {s:02d}\""

def get_nakshatra_and_pada(deg: float):
    tot_min = (deg % 360.0) * 60.0
    nak_idx = int(tot_min // 800.0)
    pada = int((tot_min % 800.0) // 200.0) + 1
    return NAKSHATRAS[nak_idx], pada, nak_idx

def get_navamsa_rashi(longitude: float) -> int:
    rashi_idx = int(longitude // 30.0)
    deg_in_rashi = longitude % 30.0
    nav_step = int(deg_in_rashi // (30.0 / 9.0))
    element_start = {0: 0, 1: 9, 2: 6, 3: 3}
    start_rashi = element_start[rashi_idx % 4]
    return (start_rashi + nav_step) % 12

def calculate_panchanga(sun_long: float, moon_long: float, birth_dt: datetime):
    diff = (moon_long - sun_long) % 360.0
    tithi_num = int(diff // 12.0) + 1
    paksha = "Shukla Paksha" if tithi_num <= 15 else "Krishna Paksha"
    tithi_idx = (tithi_num - 1) % 15
    tithi_name = f"{paksha} {TITHI_NAMES[tithi_idx]}"

    yoga_sum = (sun_long + moon_long) % 360.0
    yoga_idx = int((yoga_sum * 60.0) // 800.0)
    yoga_name = YOGA_NAMES[yoga_idx % 27]

    karana_num = int(diff // 6.0) + 1
    if karana_num == 1:
        karana_name = "Kintughna"
    elif karana_num >= 58:
        karana_name = KARANA_NAMES[karana_num - 51]
    else:
        karana_name = KARANA_NAMES[(karana_num - 2) % 7]

    vara_name = birth_dt.strftime("%A")
    nak_name, pada, _ = get_nakshatra_and_pada(moon_long)

    return {
        "tithi": tithi_name,
        "vara": vara_name,
        "nakshatra": f"{nak_name} (Pada {pada})",
        "yoga": yoga_name,
        "karana": karana_name
    }

def calculate_dasha(moon_long: float, birth_dt: datetime):
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
        lord = DASHA_ORDER[curr_idx]
        full_years = DASHA_YEARS[lord]
        duration = balance_years if is_first else full_years
        curr_end = curr_start + timedelta(days=duration * 365.25)

        is_active = curr_start <= today <= curr_end

        mahadashas.append({
            "lord": lord,
            "duration": round(duration, 1),
            "start_date": curr_start.strftime("%Y-%m-%d"),
            "end_date": curr_end.strftime("%Y-%m-%d"),
            "is_active": is_active
        })

        curr_start = curr_end
        curr_idx = (curr_idx + 1) % 9
        is_first = False

    return mahadashas

def get_daily_rashifal(moon_rashi: str):
    rashifal_database = {
        "Aries": {
            "overall": "High energy and enthusiasm will drive your day. Great day for initiating new projects.",
            "career": "Your leadership skills will be recognized at work. A good time to pitch new ideas.",
            "finance": "Financial gains through past investments. Avoid impulsive buying today.",
            "love": "Harmonious day for relationships. Single Aries might meet someone through work.",
            "health": "Vitality is high, but stay hydrated and watch out for minor headaches.",
            "lucky_number": "9", "lucky_color": "Red"
        },
        "Taurus": {
            "overall": "Patience and stability will be your guiding light today. Steady progress expected.",
            "career": "Focus on routine tasks and pending administrative work. Avoid office politics.",
            "finance": "Good day for long-term financial planning and savings discussions.",
            "love": "Comfort and warmth in family life. Express your appreciation to your partner.",
            "health": "Pay attention to neck and throat hygiene. Gentle yoga will help.",
            "lucky_number": "6", "lucky_color": "White"
        },
        "Gemini": {
            "overall": "Communication channels are bright open. Excellent day for networking and learning.",
            "career": "Collaborative efforts will yield great results. Contracts and emails favor you.",
            "finance": "Multiple minor income avenues may open up. Recheck budget numbers.",
            "love": "Charming interactions ahead. Clear up any minor past misunderstandings.",
            "health": "Mental restlessness might occur. Practice deep breathing exercises.",
            "lucky_number": "5", "lucky_color": "Green"
        },
        "Cancer": {
            "overall": "Emotional clarity will help you make key family and career decisions today.",
            "career": "Work from home or creative problem solving will flourish. Trust your intuition.",
            "finance": "Expenses on home or family needs are indicated. Handle finances prudently.",
            "love": "Deep emotional bonding with your partner. Deep conversations bring closeness.",
            "health": "Digestion needs care. Opt for light, freshly cooked meals.",
            "lucky_number": "2", "lucky_color": "Silver"
        },
        "Leo": {
            "overall": "Your natural charisma shines bright. Confidence levels are peaking today.",
            "career": "Senior authorities will be supportive. Takes center stage in presentations.",
            "finance": "Speculative gains are possible, but maintain a realistic risk buffer.",
            "love": "Passionate and romantic evening ahead. Great time for a date night.",
            "health": "Cardio or moderate exercise will boost your stamina and mood.",
            "lucky_number": "1", "lucky_color": "Gold / Amber"
        },
        "Virgo": {
            "overall": "Attention to detail will save the day. Methodical approach wins everywhere.",
            "career": "Analytical tasks, coding, or auditing will yield flawless results.",
            "finance": "Good time to organize accounts, tax planning, and clear pending bills.",
            "love": "Constructive advice will strengthen your relationship. Avoid micro-analyzing your partner.",
            "health": "Gut health is crucial today. Include probiotics in your diet.",
            "lucky_number": "5", "lucky_color": "Emerald Green"
        },
        "Libra": {
            "overall": "Balance and harmony in all spheres. Social connections bring happiness.",
            "career": "Partnerships and team agreements progress smoothly today.",
            "finance": "Inflow and outflow stay balanced. A good day for luxury purchases.",
            "love": "Romantic vibes are strong. Ideal day for proposals or commitments.",
            "health": "Ensure proper kidney hydration by drinking adequate water.",
            "lucky_number": "7", "lucky_color": "Pink / Sky Blue"
        },
        "Scorpio": {
            "overall": "Deep focus and intense willpower will help you conquer difficult obstacles.",
            "career": "Research work, investigation, or strategy planning will succeed today.",
            "finance": "Secret or hidden gains are possible. Avoid lending money today.",
            "love": "Intense emotional connections. Transparency will build deeper trust.",
            "health": "Detoxify your diet. Avoid heavy or oily late-night food.",
            "lucky_number": "8", "lucky_color": "Maroon"
        },
        "Sagittarius": {
            "overall": "Optimism and expansion guide your actions. High spiritual energy today.",
            "career": "Travel for work or foreign communications will bring positive news.",
            "finance": "Good day for investment in learning, courses, or wealth growth plans.",
            "love": "Fun-loving and cheerful atmosphere with your companion.",
            "health": "Thighs and lower back need stretching. Take active walking breaks.",
            "lucky_number": "3", "lucky_color": "Yellow"
        },
        "Capricorn": {
            "overall": "Disciplined execution brings success. Perseverance will pay off.",
            "career": "Long-term goals receive a major boost. Supervisors value your dedication.",
            "finance": "Real estate or steady asset investments look promising.",
            "love": "Show love through practical care and support rather than empty words.",
            "health": "Bone and joint health care needed. Ensure adequate Calcium intake.",
            "lucky_number": "4", "lucky_color": "Dark Blue"
        },
        "Aquarius": {
            "overall": "Innovative thoughts and social causes will inspire you today.",
            "career": "Out-of-the-box ideas will impress team members and clients.",
            "finance": "Gains through network circles, friends, or digital projects.",
            "love": "Intellectual connection with your partner creates strong bonding.",
            "health": "Ankles and blood circulation need movement. Avoid prolonged sitting.",
            "lucky_number": "11", "lucky_color": "Cyan / Electric Blue"
        },
        "Pisces": {
            "overall": "Intuitive, artistic, and peaceful mindset will guide your interactions.",
            "career": "Creative arts, healing, and design projects receive positive momentum.",
            "finance": "Charity or spiritual spending brings peace. Keep track of small expenses.",
            "love": "Soulful connection with your partner. Romantic imagination is high.",
            "health": "Relaxation and good sleep are key. Meditation before sleep helps.",
            "lucky_number": "3", "lucky_color": "Sea Green"
        }
    }
    return rashifal_database.get(moon_rashi, rashifal_database["Aries"])

def calculate_astrology(date_str: str, time_str: str, latitude: float, longitude: float, tz_offset: float, ayanamsha_mode: str = "LAHIRI"):
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
    nak_l, pada_l, _ = get_nakshatra_and_pada(sidereal_lagna)
    nav_lagna_idx = get_navamsa_rashi(sidereal_lagna)

    lagna_data = {
        "sign": RASHI_NAMES[lagna_r_idx],
        "sign_index": lagna_r_idx + 1,
        "degree": deg_to_dms(sidereal_lagna % 30.0),
        "nakshatra": nak_l,
        "pada": pada_l,
        "house": 1,
        "navamsa_sign": RASHI_NAMES[nav_lagna_idx]
    }

    planets_out = {}
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED

    for name, pid in PLANETS_MAP.items():
        res, _ = swe.calc_ut(jd_ut, pid, flags)
        sid_lon = (res[0] - ayanamsa_val) % 360.0
        r_idx = int(sid_lon // 30.0)
        house_num = ((r_idx - lagna_r_idx) % 12) + 1
        nak, pada, _ = get_nakshatra_and_pada(sid_lon)
        nav_r_idx = get_navamsa_rashi(sid_lon)

        planets_out[name] = {
            "longitude_raw": sid_lon,
            "sign": RASHI_NAMES[r_idx],
            "sign_index": r_idx + 1,
            "degree": deg_to_dms(sid_lon % 30.0),
            "nakshatra": nak,
            "pada": pada,
            "house": house_num,
            "is_retrograde": res[3] < 0 if name not in ["Sun", "Moon"] else False,
            "navamsa_sign": RASHI_NAMES[nav_r_idx],
            "navamsa_sign_index": nav_r_idx + 1,
            "navamsa_house": ((nav_r_idx - nav_lagna_idx) % 12) + 1
        }

    rahu_lon = planets_out["Rahu"]["longitude_raw"]
    ketu_lon = (rahu_lon + 180.0) % 360.0
    ketu_r_idx = int(ketu_lon // 30.0)
    ketu_nak, ketu_pada, _ = get_nakshatra_and_pada(ketu_lon)
    ketu_nav_idx = get_navamsa_rashi(ketu_lon)

    planets_out["Ketu"] = {
        "longitude_raw": ketu_lon,
        "sign": RASHI_NAMES[ketu_r_idx],
        "sign_index": ketu_r_idx + 1,
        "degree": deg_to_dms(ketu_lon % 30.0),
        "nakshatra": ketu_nak,
        "pada": ketu_pada,
        "house": ((ketu_r_idx - lagna_r_idx) % 12) + 1,
        "is_retrograde": True,
        "navamsa_sign": RASHI_NAMES[ketu_nav_idx],
        "navamsa_sign_index": ketu_nav_idx + 1,
        "navamsa_house": ((ketu_nav_idx - nav_lagna_idx) % 12) + 1
    }

    houses_out = {}
    navamsa_houses_out = {}

    for h in range(1, 13):
        r_i = (lagna_r_idx + h - 1) % 12
        houses_out[h] = {
            "sign": RASHI_NAMES[r_i],
            "sign_index": r_i + 1,
            "planets": [p for p, d in planets_out.items() if d["house"] == h]
        }

        nav_r_i = (nav_lagna_idx + h - 1) % 12
        navamsa_houses_out[h] = {
            "sign": RASHI_NAMES[nav_r_i],
            "sign_index": nav_r_i + 1,
            "planets": [p for p, d in planets_out.items() if d["navamsa_house"] == h]
        }

    aspects = []
    for p_name, p_data in planets_out.items():
        s_house = p_data["house"]
        for offset in SPECIAL_ASPECTS.get(p_name, [7]):
            t_house = ((s_house - 1 + offset - 1) % 12) + 1
            t_planets = houses_out[t_house]["planets"]
            aspects.append({
                "source": p_name,
                "type": f"{offset}th House Aspect",
                "target_house": t_house,
                "target_sign": houses_out[t_house]["sign"],
                "aspected_planets": t_planets
            })

    panchanga = calculate_panchanga(planets_out["Sun"]["longitude_raw"], planets_out["Moon"]["longitude_raw"], dt)
    dasha = calculate_dasha(planets_out["Moon"]["longitude_raw"], dt)

    return {
        "julian_day": jd_ut,
        "ayanamsha_value": deg_to_dms(ayanamsa_val),
        "lagna": lagna_data,
        "planets": planets_out,
        "houses": houses_out,
        "navamsa_houses": navamsa_houses_out,
        "panchanga": panchanga,
        "dasha": dasha,
        "aspects": aspects
    }
