from datetime import datetime, timedelta, timezone
import swisseph as swe

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE, "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
}

COMBUSTION_ORBS = {
    "Moon": 12.0, "Mars": 17.0, "Mercury": 14.0,
    "Jupiter": 11.0, "Venus": 10.0, "Saturn": 15.0
}

HORA_SEQUENCE = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]
WEEKDAY_FIRST_HORA = {0: "Sun", 1: "Moon", 2: "Mars", 3: "Mercury", 4: "Jupiter", 5: "Venus", 6: "Saturn"}

def check_vargottama(d1_rashi_idx: int, d9_rashi_idx: int) -> bool:
    return d1_rashi_idx == d9_rashi_idx

def check_combustion(planet_name: str, planet_long: float, sun_long: float, is_retro: bool = False) -> dict:
    if planet_name in ["Sun", "Rahu", "Ketu", "Uranus", "Neptune", "Pluto"]:
        return {"is_combust": False, "orb_degrees": 0.0}
    
    limit_orb = COMBUSTION_ORBS.get(planet_name, 12.0)
    if planet_name == "Mercury" and is_retro:
        limit_orb = 12.0
    if planet_name == "Venus" and is_retro:
        limit_orb = 8.0

    diff = abs((planet_long - sun_long + 180.0) % 360.0 - 180.0)
    return {
        "is_combust": diff <= limit_orb,
        "orb_degrees": round(diff, 2),
        "limit_orb": limit_orb
    }

def check_paap_kartari(target_house: int, house_planets: dict) -> bool:
    malefics = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}
    prev_house = 12 if target_house == 1 else target_house - 1
    next_house = 1 if target_house == 12 else target_house + 1

    prev_has_malefic = any(p in malefics for p in house_planets.get(prev_house, []))
    next_has_malefic = any(p in malefics for p in house_planets.get(next_house, []))

    return prev_has_malefic and next_has_malefic

def check_panchak(moon_longitude: float) -> dict:
    moon_lon = moon_longitude % 360.0
    is_panchak = moon_lon >= 300.0
    return {
        "is_panchak": is_panchak,
        "degree": round(moon_lon, 2)
    }

def calculate_hora_timings(jd_ut: float, lat: float, lon: float, tz_offset: float):
    # PySwisseph returns (status, (jd,...), err)
    _, res_rise, _ = swe.rise_trans(jd_ut, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_RISE)
    _, res_set, _ = swe.rise_trans(jd_ut, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_SET)
    _, res_next_rise, _ = swe.rise_trans(jd_ut + 1.0, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_RISE)

    sunrise = res_rise[0]
    sunset = res_set[0]
    next_sunrise = res_next_rise[0]

    day_hora_duration = (sunset - sunrise) / 12.0
    night_hora_duration = (next_sunrise - sunset) / 12.0

    weekday = int((jd_ut + 1.5) % 7)
    start_lord = WEEKDAY_FIRST_HORA[weekday]
    start_idx = HORA_SEQUENCE.index(start_lord)

    horas = []
    for i in range(12):
        h_start = sunrise + (i * day_hora_duration)
        h_end = h_start + day_hora_duration
        lord = HORA_SEQUENCE[(start_idx + i) % 7]
        horas.append({"number": i + 1, "lord": lord, "type": "Day", "start_jd": h_start, "end_jd": h_end})

    for i in range(12):
        h_start = sunset + (i * night_hora_duration)
        h_end = h_start + night_hora_duration
        lord = HORA_SEQUENCE[(start_idx + 12 + i) % 7]
        horas.append({"number": i + 13, "lord": lord, "type": "Night", "start_jd": h_start, "end_jd": h_end})

    return horas

def search_aspect_contacts(
    start_jd: float,
    days_range: int,
    p1_id: int,
    p2_id: int,
    target_aspect_deg: float,
    ayanamsha_mode: int = swe.SIDM_LAHIRI
):
    swe.set_sid_mode(ayanamsha_mode, 0, 0)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    
    contacts = []
    step_days = 0.5
    curr_jd = start_jd
    end_jd = start_jd + days_range

    while curr_jd < end_jd:
        res1, _ = swe.calc_ut(curr_jd, p1_id, flags)
        res2, _ = swe.calc_ut(curr_jd, p2_id, flags)
        
        # Access index [0][0] for position, [0][3] for speed
        lon1, speed1 = res1[0][0] % 360.0, res1[0][3]
        lon2, speed2 = res2[0][0] % 360.0, res2[0][3]

        diff = abs((lon1 - lon2 + 180.0) % 360.0 - 180.0)
        aspect_error = abs(diff - target_aspect_deg)

        if aspect_error < 0.5:
            contacts.append({
                "julian_day": curr_jd,
                "planet_1_lon": round(lon1, 2),
                "planet_2_lon": round(lon2, 2),
                "exact_angle": round(diff, 2),
                "is_p1_retro": speed1 < 0,
                "is_p2_retro": speed2 < 0
            })
            curr_jd += 2.0
        else:
            curr_jd += step_days

    return contacts
