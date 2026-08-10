# engine.py
"""
Complete Vedic Astrology (Jyotish) Astronomical Calculation Engine
Driven by Swiss Ephemeris (pyswisseph)
"""

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

# Special Vedic Drishti Offsets (House steps receiving 100% aspect)
SPECIAL_ASPECTS = {
    "Sun": [7], "Moon": [7], "Mercury": [7], "Venus": [7],
    "Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10],
    "Rahu": [5, 7, 9], "Ketu": [5, 7, 9]
}

# =====================================================================
# HELPER MATHEMATICAL & CONVERSION FUNCTIONS
# =====================================================================

def deg_to_dms(deg: float) -> str:
    """Converts decimal degrees to DD° MM' SS" string format."""
    d = int(deg)
    mins = (deg - d) * 60.0
    m = int(mins)
    s = round((mins - m) * 60.0)
    if s == 60:
        s = 0; m += 1
    if m == 60:
        m = 0; d += 1
    return f"{d:02d}° {m:02d}' {s:02d}\""


def get_nakshatra_and_pada(deg: float):
    """Calculates Nakshatra name, Pada (1-4), and Nakshatra Index (0-26)."""
    tot_min = (deg % 360.0) * 60.0
    nak_idx = int(tot_min // 800.0)  # 13°20' = 800 arcminutes
    pada = int((tot_min % 800.0) // 200.0) + 1  # 3°20' = 200 arcminutes
    return NAKSHATRAS[nak_idx], pada, nak_idx


def get_navamsa_rashi(longitude: float) -> int:
    """Calculates Navamsa (D9) Rashi Index (0 to 11) for any given longitude."""
    rashi_idx = int(longitude // 30.0)
    deg_in_rashi = longitude % 30.0
    nav_step = int(deg_in_rashi // (30.0 / 9.0))  # 3°20' = 3.33333° per Navamsa
    
    # Elemental start rules for D9:
    # Fiery signs (Aries, Leo, Sag) -> Start at Aries (0)
    # Earthy signs (Taurus, Vir, Cap) -> Start at Capricorn (9)
    # Airy signs (Gemini, Lib, Aqu) -> Start at Libra (6)
    # Watery signs (Cancer, Sco, Pis) -> Start at Cancer (3)
    element_start = {0: 0, 1: 9, 2: 6, 3: 3}
    start_rashi = element_start[rashi_idx % 4]
    return (start_rashi + nav_step) % 12


# =====================================================================
# ALMANAC & TIMELINE ENGINE (PANCHANGA & VIMSHOTTARI DASHA)
# =====================================================================

def calculate_panchanga(sun_long: float, moon_long: float, birth_dt: datetime):
    """Calculates traditional 5 Panchanga elements at birth time."""
    # 1. Tithi (Moon - Sun longitude difference / 12°)
    diff = (moon_long - sun_long) % 360.0
    tithi_num = int(diff // 12.0) + 1
    paksha = "Shukla Paksha" if tithi_num <= 15 else "Krishna Paksha"
    tithi_idx = (tithi_num - 1) % 15
    tithi_name = f"{paksha} {TITHI_NAMES[tithi_idx]}"

    # 2. Yoga (Sun + Moon longitude sum / 13°20')
    yoga_sum = (sun_long + moon_long) % 360.0
    yoga_idx = int((yoga_sum * 60.0) // 800.0)
    yoga_name = YOGA_NAMES[yoga_idx % 27]

    # 3. Karana (Half Tithi = 6° segments)
    karana_num = int(diff // 6.0) + 1
    if karana_num == 1:
        karana_name = "Kintughna"
    elif karana_num >= 58:
        karana_name = KARANA_NAMES[karana_num - 51]
    else:
        karana_name = KARANA_NAMES[(karana_num - 2) % 7]

    # 4. Vara (Weekday)
    vara_name = birth_dt.strftime("%A")

    # 5. Moon Nakshatra
    nak_name, pada, _ = get_nakshatra_and_pada(moon_long)

    return {
        "tithi": tithi_name,
        "vara": vara_name,
        "nakshatra": f"{nak_name} (Pada {pada})",
        "yoga": yoga_name,
        "karana": karana_name
    }


def calculate_dasha(moon_long: float, birth_dt: datetime):
    """Calculates Vimshottari Mahadasha timeline starting from birth Moon Nakshatra."""
    tot_min = (moon_long % 360.0) * 60.0
    nak_idx = int(tot_min // 800.0)
    first_lord_idx = nak_idx % 9
    first_lord_name = DASHA_ORDER[first_lord_idx]

    # Calculate remaining balance of the first Mahadasha
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


# =====================================================================
# MAIN CALCULATION FUNCTION
# =====================================================================

def calculate_astrology(
    date_str: str,
    time_str: str,
    latitude: float,
    longitude: float,
    tz_offset: float,
    ayanamsha_mode: str = "LAHIRI"
):
    """
    Core pipeline: Converts input birth datetime to Julian Day UT,
    applies Sidereal Ayanamsha, computes Lagna, 9 Planets, D1 & D9 Charts,
    Bhavas, Panchanga, Aspects, and Vimshottari Dasha.
    """
    # 1. Parse UTC Datetime
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    tz = timezone(timedelta(hours=tz_offset))
    utc_dt = dt.replace(tzinfo=tz).astimezone(timezone.utc)

    # 2. Convert to Julian Day (UT)
    jd_ut = swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    )

    # 3. Set Sidereal Ayanamsha
    mode_code = AYANAMSHA_MAP.get(ayanamsha_mode.upper(), swe.SIDM_LAHIRI)
    swe.set_sid_mode(mode_code, 0, 0)
    ayanamsa_val = swe.get_ayanamsa_ut(jd_ut)

    # 4. Compute Ascendant (Lagna)
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

    # 5. Compute Planetary Positions
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

    # Compute Ketu (180° opposite Rahu)
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

    # 6. Map 12 Houses (D1 Rashi Chart & D9 Navamsa Chart Mapping)
    houses_out = {}
    navamsa_houses_out = {}

    for h in range(1, 13):
        # D1 Rashi House mapping
        r_i = (lagna_r_idx + h - 1) % 12
        houses_out[h] = {
            "sign": RASHI_NAMES[r_i],
            "sign_index": r_i + 1,
            "planets": [p for p, d in planets_out.items() if d["house"] == h]
        }

        # D9 Navamsa House mapping
        nav_r_i = (nav_lagna_idx + h - 1) % 12
        navamsa_houses_out[h] = {
            "sign": RASHI_NAMES[nav_r_i],
            "sign_index": nav_r_i + 1,
            "planets": [p for p, d in planets_out.items() if d["navamsa_house"] == h]
        }

    # 7. Planetary Aspects (Drishti)
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

    # 8. Panchanga & Dasha Calculations
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