import math
from datetime import datetime, timedelta
import swisseph as swe

# Set Swiss Ephemeris sidereal mode to Lahiri
swe.set_sid_mode(swe.SIDM_LAHIRI)

# =====================================================================
# ODIA DICTIONARIES & LOOKUPS (KOHINOOR CALENDAR)
# =====================================================================

ODIA_WEEKDAYS = {
    0: {"en": "Monday", "or": "ସୋମବାର"},
    1: {"en": "Tuesday", "or": "ମଙ୍ଗଳବାର"},
    2: {"en": "Wednesday", "or": "ବୁଧବାର"},
    3: {"en": "Thursday", "or": "ଗୁରୁବାର"},
    4: {"en": "Friday", "or": "ଶୁକ୍ରବାର"},
    5: {"en": "Saturday", "or": "ଶନିବାର"},
    6: {"en": "Sunday", "or": "ରବିବାର"},
}

ODIA_SOLAR_MONTHS = [
    "ମେଷ (Mesha)",
    "ବୃଷ (Vrisha)",
    "ମିଥୁନ (Mithuna)",
    "କର୍କଟ (Karkata)",
    "ସିଂହ (Simha)",
    "କନ୍ୟା (Kanya)",
    "ତୁଳା (Tula)",
    "ବିଛା (Bicha)",
    "ଧନୁ (Dhanu)",
    "ମକର (Makara)",
    "କୁମ୍ଭ (Kumbha)",
    "ମୀନ (Mina)",
]

ODIA_LUNAR_MONTHS = [
    "ବୈଶାଖ (Baisakha)",
    "ଜ୍ୟେଷ୍ଠ (Jyestha)",
    "ଆଷାଢ଼ (Asadha)",
    "ଶ୍ରାବଣ (Sravana)",
    "ଭାଦ୍ରବ (Bhadrava)",
    "ଆଶ୍ୱିନ (Aswina)",
    "କାର୍ତ୍ତିକ (Kartika)",
    "ମାର୍ଗଶିର (Margasira)",
    "ପୌଷ (Pausha)",
    "ମାଘ (Magha)",
    "ଫାଲ୍ଗୁନ (Phalguna)",
    "ଚୈତ୍ର (Chaitra)",
]

TITHI_NAMES = [
    "ପ୍ରତିପଦା (Pratipada)",
    "ଦ୍ୱିତୀୟା (Dwitiya)",
    "ତୃତୀୟା (Tritiya)",
    "ଚତୁର୍ଥୀ (Chaturthi)",
    "ପଞ୍ଚମୀ (Panchami)",
    "ଷଷ୍ଠୀ (Shasthi)",
    "ସପ୍ତମୀ (Saptami)",
    "ଅଷ୍ଟମୀ (Ashtami)",
    "ନବମୀ (Navami)",
    "ଦଶମୀ (Dashami)",
    "ଏକାଦଶୀ (Ekadashi)",
    "ଦ୍ୱାଦଶୀ (Dwadashi)",
    "ତ୍ରୟୋଦଶୀ (Trayodashi)",
    "ଚତୁର୍ଦ୍ଦଶୀ (Chaturdashi)",
    "ପୂର୍ଣ୍ଣିମା (Purnima)",
    "ପ୍ରତିପଦା (Pratipada)",
    "ଦ୍ୱିତୀୟା (Dwitiya)",
    "ତୃତୀୟା (Tritiya)",
    "ଚତୁର୍ଥୀ (Chaturthi)",
    "ପଞ୍ଚମୀ (Panchami)",
    "ଷଷ୍ଠୀ (Shasthi)",
    "ସପ୍ତମୀ (Saptami)",
    "ଅଷ୍ଟମୀ (Ashtami)",
    "ନବମୀ (Navami)",
    "ଦଶମୀ (Dashami)",
    "ଏକାଦଶୀ (Ekadashi)",
    "ଦ୍ୱାଦଶୀ (Dwadashi)",
    "ତ୍ରୟୋଦଶୀ (Trayodashi)",
    "ଚତୁର୍ଦ୍ଦଶୀ (Chaturdashi)",
    "ଅମାବାସ୍ୟା (Amavasya)",
]

NAKSHATRA_NAMES = [
    "ଅଶ୍ୱିନୀ (Ashwini)",
    "ଭରଣୀ (Bharani)",
    "କୃତ୍ତିକା (Krittika)",
    "ରୋହିଣୀ (Rohini)",
    "ମୃଗଶିରା (Mrigasira)",
    "ଆର୍ଦ୍ରା (Ardra)",
    "ପୁନର୍ବସୁ (Punarvasu)",
    "ପୁଷ୍ୟା (Pushya)",
    "ଅଶ୍ଳେଷା (Ashlesha)",
    "ମଘା (Magha)",
    "ପୂର୍ବଫାଲ୍ଗୁନୀ (Purva Phalguni)",
    "ଉତ୍ତରଫାଲ୍ଗୁନୀ (Uttara Phalguni)",
    "ହସ୍ତା (Hasta)",
    "ଚିତ୍ରା (Chitra)",
    "ସ୍ୱାତୀ (Swati)",
    "ବିଶାଖା (Vishakha)",
    "ଅନୁରାଧା (Anuradha)",
    "ଜ୍ୟେଷ୍ଠା (Jyestha)",
    "ମୂଳା (Mula)",
    "ପୂର୍ବାଷାଢ଼ା (Purvashada)",
    "ଉତ୍ତରାଷାଢ଼ା (Uttarashada)",
    "ଶ୍ରବଣା (Shravana)",
    "ଧନିଷ୍ଠା (Dhanishta)",
    "ଶତଭିଷା (Shatabhisha)",
    "ପୂର୍ବଭାଦ୍ରପଦ (Purva Bhadrapada)",
    "ଉତ୍ତରଭାଦ୍ରପଦ (Uttara Bhadrapada)",
    "ରେବତୀ (Revati)",
]

YOGA_NAMES = [
    "ବିଷ୍କମ୍ଭ (Vishkambha)",
    "ପ୍ରୀତି (Priti)",
    "ଆୟୁଷ୍କାନ୍ (Ayushman)",
    "ସୌଭାଗ୍ୟ (Saubhagya)",
    "ଶୋଭନ (Shobhana)",
    "ଅତିଗଣ୍ଡ (Atiganda)",
    "ସୁକର୍ମା (Sukarma)",
    "ଧୃତି (Dhriti)",
    "ଶୂଳ (Shula)",
    "ଗଣ୍ଡ (Ganda)",
    "ବୃଦ୍ଧି (Vriddhi)",
    "ଧ୍ରୁବ (Dhruva)",
    "ବ୍ୟାଘାତ (Vyaghata)",
    "ହର୍ଷଣ (Harshana)",
    "ବଜ୍ର (Vajra)",
    "ସିଦ୍ଧି (Siddhi)",
    "ବ୍ୟତୀପାତ (Vyatipata)",
    "ବରୀୟାନ୍ (Variyan)",
    "ପରିଘ (Parigha)",
    "ଶିବ (Shiva)",
    "ସିଦ୍ଧ (Siddha)",
    "ସାଧ୍ୟ (Sadhya)",
    "ଶୁଭ (Shubha)",
    "ଶୁକ୍ଳ (Shukla)",
    "ବ୍ରହ୍ମ (Brahma)",
    "ଐନ୍ଦ୍ର (Aindra)",
    "ବୈଧୃତି (Vaidhriti)",
]

KARANA_NAMES = [
    "ବବ (Bava)",
    "ବାଲବ (Balava)",
    "କୌଲବ (Kaulava)",
    "ତୈତିଳ (Taitila)",
    "ଗର (Gara)",
    "ବଣିଜ (Vanija)",
    "ବିଷ୍ଟି / ଭଦ୍ରା (Vishti/Bhadra)",
    "ଶକୁନି (Shakuni)",
    "ଚତୁଷ୍କଦ (Chatushpada)",
    "ନାଗ (Naga)",
    "କିଂସ୍ତୁଘ୍ନ (Kinstughna)",
]

# Rahu Kala offsets from Sunrise (in hours into 8 parts of day)
RAHU_KALA_PARTS = {
    6: 7,  # Sunday: 8th part
    0: 1,  # Monday: 2nd part
    1: 6,  # Tuesday: 7th part
    2: 4,  # Wednesday: 5th part
    3: 5,  # Thursday: 6th part
    4: 3,  # Friday: 4th part
    5: 2,  # Saturday: 3rd part
}


# =====================================================================
# HELPER MATHEMATICAL FUNCTIONS
# =====================================================================


def get_julian_day(dt: datetime, tz_offset: float = 5.5) -> float:
  """Converts UTC/Local Datetime to Julian Day Number."""
  utc_dt = dt - timedelta(hours=tz_offset)
  return swe.julday(
      utc_dt.year,
      utc_dt.month,
      utc_dt.day,
      utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
  )


def format_time_str(hours_float: float) -> str:
  """Formats decimal hours (e.g. 6.25) to hh:mm AM/PM string."""
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
  """Returns Lahiri Sidereal Longitudes of Sun and Moon."""
  sun_info = swe.calc_ut(jd, swe.SUN, swe.FLG_SIDEREAL)
  moon_info = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)
  return sun_info[0][0] % 360, moon_info[0][0] % 360


# =====================================================================
# CORE PANCHANG GENERATOR FUNCTION
# =====================================================================


def get_kohinoor_odia_panchang(
    date_str: str,
    time_str: str = "06:00:00",
    lat: float = 20.2961,  # Default Bhubaneswar, Odisha
    lon: float = 85.8245,
    tz_offset: float = 5.5,
) -> dict:
  """Calculates full Kohinoor Odia Calendar Panchang dataset for a given date."""

  # Parse datetime
  dt_input = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
  weekday_num = dt_input.weekday()  # Monday=0, Sunday=6
  weekday_info = ODIA_WEEKDAYS[weekday_num]

  # Julian Day calculation
  jd = get_julian_day(dt_input, tz_offset)

  # Sidereal Longitudes
  sun_long, moon_long = get_sun_moon_longitudes(jd)

  # 1. Tithi Calculation
  moon_sun_diff = (moon_long - sun_long) % 360
  tithi_idx = int(moon_sun_diff / 12)
  tithi_num = (tithi_idx % 15) + 1
  paksha_str = "ଶୁକ୍ଳ ପକ୍ଷ (Shukla Paksha)" if tithi_idx < 15 else "କୃଷ୍ଣ ପକ୍ଷ (Krishna Paksha)"
  tithi_name = TITHI_NAMES[tithi_idx]

  # 2. Nakshatra Calculation
  nakshatra_idx = int(moon_long / (360 / 27))
  nakshatra_name = NAKSHATRA_NAMES[nakshatra_idx]
  pada_num = int((moon_long % (360 / 27)) / (360 / 108)) + 1

  # 3. Yoga Calculation
  sum_long = (sun_long + moon_long) % 360
  yoga_idx = int(sum_long / (360 / 27))
  yoga_name = YOGA_NAMES[yoga_idx]

  # 4. Karana Calculation
  karana_val = int(moon_sun_diff / 6)
  if karana_val == 0:
    karana_name = KARANA_NAMES[10]  # Kinstughna
  elif karana_val >= 57:
    karana_name = KARANA_NAMES[7 + (karana_val - 57)]  # Shakuni, Chatushpada, Naga
  else:
    karana_name = KARANA_NAMES[(karana_val - 1) % 7]

  # 5. Solar Month (ସୌର ମାସ) & Odia Date Estimation
  solar_month_idx = int(sun_long / 30)
  solar_month_name = ODIA_SOLAR_MONTHS[solar_month_idx]
  solar_day = int((sun_long % 30)) + 1  # Approximate Solar Day of Month

  # Odia Sanwat / Sal Calculation
  odia_sal = dt_input.year - 593 if dt_input.month >= 4 else dt_input.year - 594

  # 6. Sunrise & Sunset Calculations
  # Swiss Ephemeris sunrise/sunset calculation
  res_sunrise = swe.rise_trans(
      jd, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_RISE | swe.BIT_DISC_CENTER
  )
  res_sunset = swe.rise_trans(
      jd, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_SET | swe.BIT_DISC_CENTER
  )

  # Convert Julian sunrise/sunset to local hours
  sr_jd = res_sunrise[1][0] if res_sunrise[0] == 0 else jd
  ss_jd = res_sunset[1][0] if res_sunset[0] == 0 else jd + 0.5

  # Convert JD back to local hour
  sr_time_local = ((sr_jd + 0.5 + (tz_offset / 24.0)) % 1) * 24.0
  ss_time_local = ((ss_jd + 0.5 + (tz_offset / 24.0)) % 1) * 24.0

  day_length = ss_time_local - sr_time_local
  part_length = day_length / 8.0

  # 7. Rahu Kala, Gulika, Yamaganda
  rahu_part = RAHU_KALA_PARTS[weekday_num]
  rahu_start = sr_time_local + (rahu_part - 1) * part_length
  rahu_end = rahu_start + part_length

  # 8. Auspicious Timings (Amrita Bela, Mahendra Bela, Abhijit)
  abhijit_start = sr_time_local + (day_length * (11 / 15))
  abhijit_end = sr_time_local + (day_length * (12 / 15))

  amrita_bela_start = sr_time_local + 1.5
  amrita_bela_end = sr_time_local + 3.2

  mahendra_bela_start = sr_time_local + 4.0
  mahendra_bela_end = sr_time_local + 5.5

  # 9. Festivals Engine ( Kohinoor Parba Parbani Rules )
  festivals = []
  if tithi_num == 11:
    festivals.append("ପବିତ୍ର ଏକାଦଶୀ ବ୍ରତ (Ekadashi Vrata)")
  if tithi_idx == 14:
    festivals.append("ପୂର୍ଣ୍ଣିମା ବ୍ରତ / ସତ୍ୟନାରାୟଣ ପୂଜା (Purnima Vrata)")
  if tithi_idx == 29:
    festivals.append("ଅମାବାସ୍ୟା (Amavasya / Pitru Tarpana)")
  if solar_day == 1:
    festivals.append(f"ସଂକ୍ରାନ୍ତି - {solar_month_name} ସଂକ୍ରାନ୍ତି")

  # Special Odia Festival Rule Highlights
  if dt_input.month == 4 and 13 <= dt_input.day <= 15:
    festivals.append(
        "ମହାବିଷୁବ ସଂକ୍ରାନ୍ତି / ପଣା ସଂକ୍ରାନ୍ତି (Pana Sankranti - Odia New Year)"
    )
  elif dt_input.month == 6 and 14 <= dt_input.day <= 16:
    festivals.append("ରଜ ସଂକ୍ରାନ୍ତି / ପହଲି ରଜ (Raja Parba)")
  elif dt_input.month == 7 and tithi_idx == 1:
    festivals.append("ଶ୍ରୀଗୁଣ୍ଡିଚା ରଥଯାତ୍ରା (Ratha Yatra)")

  # Return Complete Kohinoor Odia Panchang JSON Payload
  return {
      "gregorian_date": date_str,
      "weekday": weekday_info["or"],
      "weekday_en": weekday_info["en"],
      "odia_date_summary": (
          f"{solar_month_name} {solar_day} ଦିନ, ସାଲ {odia_sal}"
      ),
      "solar_month": solar_month_name,
      "solar_day": solar_day,
      "odia_sal": odia_sal,
      "panchanga": {
          "tithi": tithi_name,
          "tithi_number": tithi_num,
          "paksha": paksha_str,
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
          "abhijit_muhurta": (
              f"{format_time_str(abhijit_start)} - {format_time_str(abhijit_end)}"
          ),
          "amrita_bela": (
              f"{format_time_str(amrita_bela_start)} -"
              f" {format_time_str(amrita_bela_end)}"
          ),
          "mahendra_bela": (
              f"{format_time_str(mahendra_bela_start)} -"
              f" {format_time_str(mahendra_bela_end)}"
          ),
      },
      "ashubha_bela": {
          "rahu_kala": (
              f"{format_time_str(rahu_start)} - {format_time_str(rahu_end)}"
          )
      },
      "festivals": festivals,
  }