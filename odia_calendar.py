import math
from datetime import datetime, timedelta
import calendar
import swisseph as swe

swe.set_sid_mode(swe.SIDM_LAHIRI)

ODIA_DIGITS = {'0': '୦', '1': '୧', '2': '୨', '3': '୩', '4': '୪', '5': '୫', '6': '୬', '7': '୭', '8': '୮', '9': '୯'}

def to_odia_num(num) -> str:
    return "".join(ODIA_DIGITS.get(ch, ch) for ch in str(num))

ODIA_WEEKDAYS = {
    0: {"en": "Monday", "or": "ସୋମବାର"},
    1: {"en": "Tuesday", "or": "ମଙ୍ଗଳବାର"},
    2: {"en": "Wednesday", "or": "ବୁଧବାର"},
    3: {"en": "Thursday", "or": "ଗୁରୁବାର"},
    4: {"en": "Friday", "or": "ଶୁକ୍ରବାର"},
    5: {"en": "Saturday", "or": "ଶନିବାର"},
    6: {"en": "Sunday", "or": "ରବିବାର"},
}

ODIA_SOLAR_MONTHS = ["ମେଷ", "ବୃଷ", "ମିଥୁନ", "କର୍କଟ", "ସିଂହ", "କନ୍ୟା", "ତୁଳା", "ବିଛା", "ଧନୁ", "ମକର", "କୁମ୍ଭ", "ମୀନ"]

SHORT_TITHI_NAMES = [
    "ପ୍ରତିପଦ", "ଦ୍ୱିତୀୟା", "ତୃତୀୟା", "ଚତୁର୍ଥୀ", "ପଞ୍ଚମୀ", "ଷଷ୍ଠୀ", "ସପ୍ତମୀ", "ଅଷ୍ଟମୀ",
    "ନବମୀ", "ଦଶମୀ", "ଏକାଦଶୀ", "ଦ୍ୱାଦଶୀ", "ତ୍ରୟୋଦଶୀ", "ଚତୁର୍ଦ୍ଦଶୀ", "ପୂର୍ଣ୍ଣିମା",
    "ପ୍ରତିପଦ", "ଦ୍ୱିତୀୟା", "ତୃତୀୟା", "ଚତୁର୍ଥୀ", "ପଞ୍ଚମୀ", "ଷଷ୍ଠୀ", "ସପ୍ତମୀ", "ଅଷ୍ଟମୀ",
    "ନବମୀ", "ଦଶମୀ", "ଏକାଦଶୀ", "ଦ୍ୱାଦଶୀ", "ତ୍ରୟୋଦଶୀ", "ଚତୁର୍ଦ୍ଦଶୀ", "ଅମାବାସ୍ୟା"
]

TITHI_NAMES = SHORT_TITHI_NAMES  # Full mapping alias

NAKSHATRA_NAMES = [
    "ଅଶ୍ୱିନୀ", "ଭରଣୀ", "କୃତ୍ତିକା", "ରୋହିଣୀ", "ମୃଗଶିରା", "ଆର୍ଦ୍ରା", "ପୁନର୍ବସୁ", "ପୁଷ୍ୟା", "ଅଶ୍ଳେଷା",
    "ମଘା", "ପୂର୍ବଫାଲ୍ଗୁନୀ", "ଉତ୍ତରଫାଲ୍ଗୁନୀ", "ହସ୍ତା", "ଚିତ୍ରା", "ସ୍ୱାତୀ", "ବିଶାଖା", "ଅନୁରାଧା",
    "ଜ୍ୟେଷ୍ଠା", "ମୂଳା", "ପୂର୍ବାଷାଢ଼ା", "ଉତ୍ତରାଷାଢ଼ା", "ଶ୍ରବଣା", "ଧନିଷ୍ଠା", "ଶତଭିଷା", "ପୂର୍ବଭାଦ୍ରପଦ",
    "ଉତ୍ତରଭାଦ୍ରପଦ", "ରେବତୀ"
]

YOGA_NAMES = ["ବିଷ୍କମ୍ଭ", "ପ୍ରୀତି", "ଆୟୁଷ୍କାନ୍", "ସୌଭାଗ୍ୟ", "ଶୋଭନ", "ଅତିଗଣ୍ଡ", "ସୁକର୍ମା", "ଧୃତି", "ଶୂଳ", "ଗଣ୍ଡ", "ବୃଦ୍ଧି", "ଧ୍ରୁବ", "ବ୍ୟାଘାତ", "ହର୍ଷଣ", "ବଜ୍ର", "ସିଦ୍ଧି", "ବ୍ୟତୀପାତ", "ବରୀୟାନ୍", "ପରିଘ", "ଶିବ", "ସିଦ୍ଧ", "ସାଧ୍ୟ", "ଶୁଭ", "ଶୁକ୍ଳ", "ବ୍ରହ୍ମ", "ଐନ୍ଦ୍ର", "ବୈଧୃତି"]
KARANA_NAMES = ["ବବ", "ବାଲବ", "କୌଲବ", "ତୈତିଳ", "ଗର", "ବଣିଜ", "ବିଷ୍ଟି/ଭଦ୍ରା", "ଶକୁନି", "ଚତୁଷ୍କଦ", "ନାଗ", "କିଂସ୍ତୁଘ୍ନ"]

RAHU_KALA_PARTS = {6: 7, 0: 1, 1: 6, 2: 4, 3: 5, 4: 3, 5: 2}

def get_julian_day(dt: datetime, tz_offset: float = 5.5) -> float:
    utc_dt = dt - timedelta(hours=tz_offset)
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)

def format_time_str(hours_float: float) -> str:
    if hours_float is None or math.isnan(hours_float):
        return "N/A"
    h = int(hours_float) % 24
    m = int((hours_float - int(hours_float)) * 60)
    ampm = "AM" if h < 12 else "PM"
    disp_h = h if h <= 12 else h - 12
    if disp_h == 0:
        disp_h = 12
    return f"{disp_h:02d}:{m:02d} {ampm}"

def get_sun_moon_longitudes(jd: float):
    sun_info = swe.calc_ut(jd, swe.SUN, swe.FLG_SIDEREAL)
    moon_info = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)
    return sun_info[0][0] % 360, moon_info[0][0] % 360

def get_kohinoor_odia_panchang(date_str: str, time_str: str = "06:00:00", lat: float = 20.2961, lon: float = 85.8245, tz_offset: float = 5.5) -> dict:
    dt_input = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    weekday_num = dt_input.weekday()
    weekday_info = ODIA_WEEKDAYS[weekday_num]
    jd = get_julian_day(dt_input, tz_offset)

    sun_long, moon_long = get_sun_moon_longitudes(jd)

    moon_sun_diff = (moon_long - sun_long) % 360
    tithi_idx = int(moon_sun_diff / 12)
    tithi_num = (tithi_idx % 15) + 1
    paksha_str = "ଶୁକ୍ଳ ପକ୍ଷ" if tithi_idx < 15 else "କୃଷ୍ଣ ପକ୍ଷ"
    tithi_name = TITHI_NAMES[tithi_idx]

    nakshatra_idx = int(moon_long / (360 / 27))
    nakshatra_name = NAKSHATRA_NAMES[nakshatra_idx]
    pada_num = int((moon_long % (360 / 27)) / (360 / 108)) + 1

    sum_long = (sun_long + moon_long) % 360
    yoga_idx = int(sum_long / (360 / 27))
    yoga_name = YOGA_NAMES[yoga_idx]

    karana_val = int(moon_sun_diff / 6)
    if karana_val == 0:
        karana_name = KARANA_NAMES[10]
    elif karana_val >= 57:
        karana_name = KARANA_NAMES[7 + (karana_val - 57)]
    else:
        karana_name = KARANA_NAMES[(karana_val - 1) % 7]

    solar_month_idx = int(sun_long / 30)
    solar_month_name = ODIA_SOLAR_MONTHS[solar_month_idx]
    solar_day = int((sun_long % 30)) + 1
    odia_sal = dt_input.year - 593 if dt_input.month >= 4 else dt_input.year - 594

    # Sun Timings
    res_sunrise = swe.rise_trans(jd, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_RISE | swe.BIT_DISC_CENTER)
    res_sunset = swe.rise_trans(jd, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_SET | swe.BIT_DISC_CENTER)

    sr_jd = res_sunrise[1][0] if res_sunrise[0] == 0 else jd
    ss_jd = res_sunset[1][0] if res_sunset[0] == 0 else jd + 0.5

    sr_time_local = ((sr_jd + 0.5 + (tz_offset / 24.0)) % 1) * 24.0
    ss_time_local = ((ss_jd + 0.5 + (tz_offset / 24.0)) % 1) * 24.0

    day_length = ss_time_local - sr_time_local
    part_length = day_length / 8.0

    rahu_part = RAHU_KALA_PARTS[weekday_num]
    rahu_start = sr_time_local + (rahu_part - 1) * part_length
    rahu_end = rahu_start + part_length

    abhijit_start = sr_time_local + (day_length * (11 / 15))
    abhijit_end = sr_time_local + (day_length * (12 / 15))

    festivals = []
    is_ekadashi = tithi_num == 11
    is_purnima = tithi_idx == 14
    is_amavasya = tithi_idx == 29
    is_sankranti = solar_day == 1

    if is_ekadashi:
        festivals.append("ପବିତ୍ର ଏକାଦଶୀ ବ୍ରତ")
    if is_purnima:
        festivals.append("ପୂର୍ଣ୍ଣିମା ବ୍ରତ")
    if is_amavasya:
        festivals.append("ଅମାବାସ୍ୟା")
    if is_sankranti:
        festivals.append(f"{solar_month_name} ସଂକ୍ରାନ୍ତି")

    if dt_input.month == 4 and 13 <= dt_input.day <= 15:
        festivals.append("ପଣା ସଂକ୍ରାନ୍ତି")
    elif dt_input.month == 6 and 14 <= dt_input.day <= 16:
        festivals.append("ରଜ ସଂକ୍ରାନ୍ତି")
    elif dt_input.month == 7 and tithi_idx == 1:
        festivals.append("ରଥଯାତ୍ରା")

    # Shubha Karma (Auspicious Marriage, Brata, Housewarming rules)
    is_vivaha = False
    is_brata = False
    is_gruhaprabesha = False

    # Auspicious Tithis for Vivaha: 2, 3, 5, 7, 10, 11, 12, 13
    if tithi_num in [2, 3, 5, 7, 10, 11, 12, 13] and nakshatra_idx in [3, 4, 9, 11, 12, 14, 16, 20, 25, 26]:
        if weekday_num in [0, 2, 3, 4]:  # Mon, Wed, Thu, Fri
            is_vivaha = True

    if tithi_num in [3, 5, 7, 10] and nakshatra_idx in [0, 3, 7, 12, 14, 16, 26]:
        is_brata = True

    if tithi_num in [2, 3, 5, 7, 10, 13] and nakshatra_idx in [3, 4, 11, 12, 20, 25, 26]:
        is_gruhaprabesha = True

    return {
        "gregorian_date": date_str,
        "day_number": dt_input.day,
        "weekday": weekday_info["or"],
        "weekday_en": weekday_info["en"],
        "odia_solar_month": solar_month_name,
        "odia_solar_day": solar_day,
        "odia_solar_day_str": to_odia_num(solar_day),
        "odia_date_summary": f"{solar_month_name} {to_odia_num(solar_day)} ଦିନ, ସାଲ {to_odia_num(odia_sal)}",
        "short_tithi": tithi_name,
        "is_ekadashi": is_ekadashi,
        "is_purnima": is_purnima,
        "is_amavasya": is_amavasya,
        "is_sankranti": is_sankranti,
        "shubha_karma": {
            "vivaha": is_vivaha,
            "brata": is_brata,
            "gruhaprabesha": is_gruhaprabesha
        },
        "panchanga": {
            "tithi": f"{tithi_name} ({paksha_str})",
            "nakshatra": nakshatra_name,
            "pada": pada_num,
            "yoga": yoga_name,
            "karana": karana_name,
        },
        "sun_timings": {
            "sunrise": format_time_str(sr_time_local),
            "sunset": format_time_str(ss_time_local),
        },
        "shubha_bela": {
            "abhijit_muhurta": f"{format_time_str(abhijit_start)} - {format_time_str(abhijit_end)}",
            "amrita_bela": f"{format_time_str(sr_time_local + 1.5)} - {format_time_str(sr_time_local + 3.2)}",
            "mahendra_bela": f"{format_time_str(sr_time_local + 4.0)} - {format_time_str(sr_time_local + 5.5)}",
        },
        "ashubha_bela": {
            "rahu_kala": f"{format_time_str(rahu_start)} - {format_time_str(rahu_end)}"
        },
        "festivals": festivals,
    }

def get_kohinoor_month_calendar(year: int, month: int, lat: float = 20.2961, lon: float = 85.8245, tz_offset: float = 5.5) -> dict:
    _, num_days = calendar.monthrange(year, month)
    days_data = []
    shubha_summary = {"vivaha": [], "brata": [], "gruhaprabesha": []}
    festivals_list = []

    for d in range(1, num_days + 1):
        d_str = f"{year}:{month:02d}:{d:02d}".replace(':', '-')
        p_data = get_kohinoor_odia_panchang(d_str, lat=lat, lon=lon, tz_offset=tz_offset)
        days_data.append(p_data)

        if p_data["shubha_karma"]["vivaha"]:
            shubha_summary["vivaha"].append(d)
        if p_data["shubha_karma"]["brata"]:
            shubha_summary["brata"].append(d)
        if p_data["shubha_karma"]["gruhaprabesha"]:
            shubha_summary["gruhaprabesha"].append(d)

        if p_data["festivals"]:
            festivals_list.append({"day": d, "festivals": p_data["festivals"]})

    return {
        "year": year,
        "month": month,
        "days": days_data,
        "shubha_summary": shubha_summary,
        "festivals_list": festivals_list
    }