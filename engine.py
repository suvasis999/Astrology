import math
from datetime import datetime, timedelta
import swisseph as swe

# =====================================================================
# CONSTANTS & LOOKUPS
# =====================================================================

ZODIAC_SIGNS = [
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

WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

RASHIFAL_PREDICTIONS = {
    "Aries": "Focus on leadership and energetic pursuits today. Financial opportunities may arise.",
    "Taurus": "Stability and patience will serve you well. Good day for long-term investments.",
    "Gemini": "Communication is key today. Expect favorable developments in business networking.",
    "Cancer": "Trust your intuition in financial decisions. Family support brings emotional strength.",
    "Leo": "Your charisma shines today. Great time for presentations and launching new ventures.",
    "Virgo": "Attention to detail brings success. Review contracts and financial plans carefully.",
    "Libra": "Harmonious planetary placements favor partnerships and balanced negotiations.",
    "Scorpio": "Deep analytical focus will help solve complex trading or financial puzzles.",
    "Sagittarius": "Optimism brings positive results. Be cautious with speculative investments.",
    "Capricorn": "Discipline and hard work yield substantial rewards in career and finance.",
    "Aquarius": "Innovative thinking opens new income streams. Stay open to fresh ideas.",
    "Pisces": "Spiritual clarity and intuitive insights guide your major financial choices today."
}

PLANET_MAP = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE, "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
}

AYANAMSHA_MAP = {
    "LAHIRI": swe.SIDM_LAHIRI,
    "RAMAN": swe.SIDM_RAMAN,
    "KRISHNAMURTI": swe.SIDM_KRISHNAMURTI
}

# =====================================================================
# 1. DAILY RASHIFAL FUNCTION
# =====================================================================

def get_daily_rashifal(sign_name: str) -> dict:
    """Returns daily rashifal/horoscope predictions for a zodiac sign."""
    clean_sign = str(sign_name).capitalize() if sign_name else "Aries"
    prediction = RASHIFAL_PREDICTIONS.get(
        clean_sign, 
        "A favorable day overall with promising opportunities across financial and personal endeavors."
    )
    return {
        "sign": clean_sign,
        "prediction": prediction,
        "financial_score": 85,
        "lucky_number": 7
    }

# =====================================================================
# 2. CORE ASTROLOGY CALCULATION ENGINE
# =====================================================================

def calculate_astrology(
    date_str: str,
    time_str: str,
    latitude: float,
    longitude: float,
    tz_offset: float = 5.5,
    ayanamsha_mode: str = "LAHIRI"
) -> dict:
    """Computes planetary longitudes, house cusps, D9 Navamsa, and Panchanga."""
    
    # 1. Convert Local DateTime to UTC
    dt_local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    dt_utc = dt_local - timedelta(hours=tz_offset)
    
    # 2. Calculate UTC Julian Day
    decimal_hour_utc = dt_utc.hour + (dt_utc.minute / 60.0) + (dt_utc.second / 3600.0)
    jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, decimal_hour_utc)

    # 3. Configure Ayanamsha (Sidereal Mode)
    mode_id = AYANAMSHA_MAP.get(str(ayanamsha_mode).upper(), swe.SIDM_LAHIRI)
    swe.set_sid_mode(mode_id, 0, 0)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL

    # 4. Lagna (Ascendant) Calculation
    _, ascmc = swe.houses_ex(jd_ut, latitude, longitude, b'E', swe.FLG_SIDEREAL)
    ascendant_lon = ascmc[0] % 360.0
    lagna_sign_idx = int(ascendant_lon // 30)

    # 5. Compute Planets
    planets_data = {}
    planets_in_d1_house = {h: [] for h in range(1, 13)}
    planets_in_d9_house = {h: [] for h in range(1, 13)}

    # Navamsa starting sign offsets by triplicity element (Fire/Earth/Air/Water)
    elem_start_offsets = [0, 8, 4, 0, 8, 4, 0, 8, 4, 0, 8, 4]

    # Pre-fetch Rahu for Ketu opposite calculation
    rahu_res, _ = swe.calc_ut(jd_ut, swe.MEAN_NODE, flags)
    rahu_lon = rahu_res[0][0] % 360.0

    all_targets = list(PLANET_MAP.items()) + [("Ketu", None)]

    for p_name, p_id in all_targets:
        if p_name == "Ketu":
            lon = (rahu_lon + 180.0) % 360.0
            speed = rahu_res[0][3]
        else:
            res, _ = swe.calc_ut(jd_ut, p_id, flags)
            lon = res[0][0] % 360.0
            speed = res[0][3]

        # Rashi / Sign
        sign_idx = int(lon // 30)
        sign_name = ZODIAC_SIGNS[sign_idx]
        deg_in_sign = lon % 30.0

        # Nakshatra & Pada
        nak_idx = int(lon // (360.0 / 27.0))
        nak_name = NAKSHATRAS[nak_idx]
        pada = int((lon % (360.0 / 27.0)) // (360.0 / 108.0)) + 1

        # D9 Navamsa Sign
        navamsa_part = int(deg_in_sign // (30.0 / 9.0))
        navamsa_sign_idx = (elem_start_offsets[sign_idx] + navamsa_part) % 12

        # House Placement (Whole Sign)
        d1_house = ((sign_idx - lagna_sign_idx) % 12) + 1
        planets_in_d1_house[d1_house].append(p_name)

        d9_lagna_sign_idx = (elem_start_offsets[lagna_sign_idx] + int((ascendant_lon % 30.0) // (30.0 / 9.0))) % 12
        d9_house = ((navamsa_sign_idx - d9_lagna_sign_idx) % 12) + 1
        planets_in_d9_house[d9_house].append(p_name)

        deg_int = int(deg_in_sign)
        min_int = int((deg_in_sign - deg_int) * 60)
        sec_int = int((((deg_in_sign - deg_int) * 60) - min_int) * 60)

        planets_data[p_name] = {
            "longitude_raw": round(lon, 4),
            "sign": sign_name,
            "sign_index": sign_idx,
            "degree": f"{deg_int}° {min_int}' {sec_int}\"",
            "nakshatra": nak_name,
            "pada": pada,
            "is_retrograde": speed < 0,
            "navamsa_sign": ZODIAC_SIGNS[navamsa_sign_idx],
            "navamsa_sign_index": navamsa_sign_idx,
            "house": d1_house
        }

    # 6. Build Houses Maps (D1 & D9)
    houses_data = {}
    for h in range(1, 13):
        h_sign_idx = (lagna_sign_idx + h - 1) % 12
        houses_data[h] = {
            "sign": ZODIAC_SIGNS[h_sign_idx],
            "planets": planets_in_d1_house[h]
        }

    navamsa_houses_data = {}
    d9_lagna_sign_idx = (elem_start_offsets[lagna_sign_idx] + int((ascendant_lon % 30.0) // (30.0 / 9.0))) % 12
    for h in range(1, 13):
        h_sign_idx = (d9_lagna_sign_idx + h - 1) % 12
        navamsa_houses_data[h] = {
            "sign": ZODIAC_SIGNS[h_sign_idx],
            "planets": planets_in_d9_house[h]
        }

    # 7. Compute Panchang
    sun_lon = planets_data["Sun"]["longitude_raw"]
    moon_lon = planets_data["Moon"]["longitude_raw"]

    tithi_num = int(((moon_lon - sun_lon) % 360.0) // 12.0) + 1
    vara_idx = int((jd_ut + 1.5) % 7)
    yoga_num = int(((sun_lon + moon_lon) % 360.0) // (360.0 / 27.0)) + 1
    karana_num = int(((moon_lon - sun_lon) % 360.0) // 6.0) + 1

    panchanga = {
        "tithi": f"Tithi {tithi_num}",
        "vara": WEEKDAYS[vara_idx],
        "nakshatra": planets_data["Moon"]["nakshatra"],
        "yoga": f"Yoga {yoga_num}",
        "karana": f"Karana {karana_num}"
    }

    return {
        "julian_day": jd_ut,
        "ascendant_longitude": round(ascendant_lon, 4),
        "lagna_sign": ZODIAC_SIGNS[lagna_sign_idx],
        "planets": planets_data,
        "houses": houses_data,
        "navamsa_houses": navamsa_houses_data,
        "panchanga": panchanga
    }
