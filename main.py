# main.py
import base64
import io
import os
import re
import requests
import traceback
import unicodedata
import html
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from weasyprint import HTML
import swisseph as swe
import fitz  # PyMuPDF

# =====================================================================
# PDF FONT CONFIGURATION
# =====================================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

FONT_DIR = os.path.join(
    BASE_DIR,
    "fonts"
)

ODIA_FONT_PATH = os.path.join(
    FONT_DIR,
    "NotoSansOriya-Regular.ttf"
)

DEVANAGARI_FONT_PATH = os.path.join(
    FONT_DIR,
    "NotoSansDevanagari-Regular.ttf"
)

ENGLISH_FONT_PATH = os.path.join(
    FONT_DIR,
    "NotoSans-Regular.ttf"
)


def get_pdf_font(lang: str):
    lang = (lang or "en").lower()

    if lang == "or":
        return (
            "OdiaFont",
            ODIA_FONT_PATH
        )

    if lang == "hi":
        return (
            "HindiFont",
            DEVANAGARI_FONT_PATH
        )

    return (
        "EnglishFont",
        ENGLISH_FONT_PATH
    )

try:
    from engine import calculate_astrology, get_daily_rashifal
    from odia_calendar import get_kohinoor_odia_panchang, get_kohinoor_month_calendar
    ASTRO_ENGINE_LOADED = True
    print("✅ Astrology & Odia Calendar Engines loaded successfully!")
except Exception as e:
    ASTRO_ENGINE_LOADED = False
    print(f"❌ Engine Load Error: {e}")
    traceback.print_exc()


# =====================================================================
# SAFE RESPONSE HELPERS
# =====================================================================

def sanitize_response(data):
    if isinstance(data, dict):
        return {k: sanitize_response(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_response(i) for i in data]
    if isinstance(data, bytes):
        return base64.b64encode(data).decode("utf-8")
    return data


def needs_ocr_fallback(text: str) -> bool:
    if not text:
        return True

    clean = unicodedata.normalize("NFC", text).strip()
    if len(clean) < 15:
        return True

    odia_char_count = sum(1 for ch in clean if 0x0B00 <= ord(ch) <= 0x0B7F)
    total_alpha = sum(1 for ch in clean if ch.isalpha())

    if odia_char_count < 5 and total_alpha > 10:
        return True

    weird_symbols = sum(1 for ch in clean if ch in '^~_`{}|\\<>#$@\uFFFD')
    return weird_symbols > 5


def clean_unicode_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    return "".join(
        ch for ch in text
        if ch in ("\n", "\r", "\t", " ")
        or unicodedata.category(ch)[0] != "C"
    )



# =====================================================================
# KP (KRISHNAMURTI PADDHATI) HELPERS
# =====================================================================

KP_DASHA_ORDER = [
    ("Ketu", 7),
    ("Venus", 20),
    ("Sun", 6),
    ("Moon", 10),
    ("Mars", 7),
    ("Rahu", 18),
    ("Jupiter", 16),
    ("Saturn", 19),
    ("Mercury", 17),
]

KP_NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira",
    "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
    "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

KP_SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

KP_SIGN_LORDS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}


def _norm360(value: float) -> float:
    return float(value) % 360.0


def _kp_sign(longitude: float):
    lon = _norm360(longitude)
    sign_index = int(lon // 30)
    return KP_SIGN_NAMES[sign_index], lon % 30.0, sign_index + 1


def _kp_sequence_from(lord: str):
    names = [x[0] for x in KP_DASHA_ORDER]
    try:
        start = names.index(lord)
    except ValueError:
        start = 0
    return KP_DASHA_ORDER[start:] + KP_DASHA_ORDER[:start]


def _kp_lords_for_longitude(longitude: float):
    """Return KP Nakshatra/Star lord, Sub lord and Sub-Sub lord."""
    lon = _norm360(longitude)
    nak_len = 360.0 / 27.0
    nak_index = int(lon // nak_len)
    nak_start = nak_index * nak_len
    offset = lon - nak_start

    star_lord = KP_DASHA_ORDER[nak_index % 9][0]
    star_seq = _kp_sequence_from(star_lord)

    sub_lord = star_lord
    sub_start = 0.0
    sub_end = nak_len
    cursor = 0.0

    for lord, years in star_seq:
        span = nak_len * (years / 120.0)
        if offset <= cursor + span + 1e-12:
            sub_lord = lord
            sub_start = cursor
            sub_end = cursor + span
            break
        cursor += span

    sub_span = max(sub_end - sub_start, 1e-12)
    sub_offset = max(0.0, offset - sub_start)
    subsub_lord = sub_lord
    cursor = 0.0

    for lord, years in _kp_sequence_from(sub_lord):
        span = sub_span * (years / 120.0)
        if sub_offset <= cursor + span + 1e-12:
            subsub_lord = lord
            break
        cursor += span

    pada = int((offset % nak_len) // (nak_len / 4.0)) + 1

    return {
        "nakshatra": KP_NAKSHATRAS[nak_index],
        "nakshatra_number": nak_index + 1,
        "pada": min(4, pada),
        "star_lord": star_lord,
        "sub_lord": sub_lord,
        "sub_sub_lord": subsub_lord,
    }


def _extract_planet_longitude(planet_data: dict):
    if not isinstance(planet_data, dict):
        return None

    for key in ("longitude_raw", "longitude", "lon", "absolute_longitude"):
        value = planet_data.get(key)
        try:
            if value is not None:
                return _norm360(float(value))
        except Exception:
            pass

    return None


def _birth_julian_day_ut(data: "BirthDataRequest") -> float:
    local_dt = datetime.strptime(
        f"{data.date} {data.time}",
        "%Y-%m-%d %H:%M:%S",
    )

    utc_dt = local_dt - timedelta(hours=float(data.tz_offset))

    hour = (
        utc_dt.hour
        + utc_dt.minute / 60.0
        + utc_dt.second / 3600.0
        + utc_dt.microsecond / 3_600_000_000.0
    )

    return swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        hour,
    )


def calculate_kp_details(result: dict, data: "BirthDataRequest") -> dict:
    """
    KP calculation layer.

    Uses:
    - Swiss Ephemeris Krishnamurti sidereal mode
    - Placidus cusps
    - Vimshottari proportional Star/Sub/Sub-Sub divisions

    This supplies calculation data, not a full predictive judgement engine.
    """
    try:
        jd_ut = _birth_julian_day_ut(data)

        swe.set_sid_mode(
            swe.SIDM_KRISHNAMURTI,
            0,
            0,
        )

        ayanamsha_value = float(
            swe.get_ayanamsa_ut(jd_ut)
        )

        try:
            cusps, ascmc = swe.houses_ex(
                jd_ut,
                float(data.latitude),
                float(data.longitude),
                b"P",
                swe.FLG_SIDEREAL,
            )
        except TypeError:
            cusps, ascmc = swe.houses_ex(
                jd_ut,
                float(data.latitude),
                float(data.longitude),
                b"P",
                flags=swe.FLG_SIDEREAL,
            )

        cusp_values = list(cusps)
        if len(cusp_values) > 12:
            cusp_values = cusp_values[-12:]

        kp_cusps = {}

        for idx, cusp_lon in enumerate(
            cusp_values[:12],
            start=1,
        ):
            cusp_lon = _norm360(cusp_lon)
            sign, degree_in_sign, sign_no = _kp_sign(cusp_lon)
            lords = _kp_lords_for_longitude(cusp_lon)

            kp_cusps[str(idx)] = {
                "cusp": idx,
                "longitude": round(cusp_lon, 6),
                "sign": sign,
                "sign_number": sign_no,
                "degree_in_sign": round(degree_in_sign, 6),
                "sign_lord": KP_SIGN_LORDS.get(sign),
                **lords,
            }

        planets_source = (
            result.get("planets_en")
            or result.get("planets")
            or {}
        )

        kp_planets = {}

        for planet_name, pdata in planets_source.items():
            lon = _extract_planet_longitude(pdata)

            if lon is None:
                continue

            sign, degree_in_sign, sign_no = _kp_sign(lon)
            lords = _kp_lords_for_longitude(lon)

            kp_planets[str(planet_name)] = {
                "longitude": round(lon, 6),
                "sign": sign,
                "sign_number": sign_no,
                "degree_in_sign": round(degree_in_sign, 6),
                "sign_lord": KP_SIGN_LORDS.get(sign),
                **lords,
            }

        asc_lon = _norm360(ascmc[0]) if ascmc else None
        asc_info = (
            _kp_lords_for_longitude(asc_lon)
            if asc_lon is not None
            else {}
        )
        asc_sign = (
            _kp_sign(asc_lon)[0]
            if asc_lon is not None
            else None
        )

        moon = kp_planets.get("Moon") or {}

        weekday_lords = [
            "Moon",
            "Mars",
            "Mercury",
            "Jupiter",
            "Venus",
            "Saturn",
            "Sun",
        ]

        local_dt = datetime.strptime(
            f"{data.date} {data.time}",
            "%Y-%m-%d %H:%M:%S",
        )

        ruling_planets = {
            "day_lord": weekday_lords[local_dt.weekday()],
            "ascendant_sign_lord": (
                KP_SIGN_LORDS.get(asc_sign)
                if asc_sign
                else None
            ),
            "ascendant_star_lord": asc_info.get("star_lord"),
            "ascendant_sub_lord": asc_info.get("sub_lord"),
            "moon_sign_lord": moon.get("sign_lord"),
            "moon_star_lord": moon.get("star_lord"),
            "moon_sub_lord": moon.get("sub_lord"),
        }

        return {
            "status": "success",
            "system": "Krishnamurti Paddhati (KP)",
            "house_system": "Placidus",
            "ayanamsha": "KRISHNAMURTI",
            "ayanamsha_value": round(ayanamsha_value, 8),
            "planets": kp_planets,
            "cusps": kp_cusps,
            "ruling_planets": ruling_planets,
            "note": (
                "KP Star/Sub/Sub-Sub divisions use Vimshottari proportions. "
                "Cusps are sidereal Placidus cusps calculated with Swiss Ephemeris."
            ),
        }

    except Exception as exc:
        traceback.print_exc()

        return {
            "status": "error",
            "system": "Krishnamurti Paddhati (KP)",
            "message": str(exc),
            "planets": {},
            "cusps": {},
            "ruling_planets": {},
        }


# =====================================================================
# ODIA DICTIONARY
# =====================================================================

ODIA_DICT = {}


def load_odianlp_dictionary():
    global ODIA_DICT

    github_urls = [
        "https://raw.githubusercontent.com/OdiaNLP/dictionary/master/OdiaToEnglish.json",
        "https://raw.githubusercontent.com/OdiaNLP/dictionary/main/OdiaToEnglish.json",
        "https://raw.githubusercontent.com/OdiaNLP/dictionary/master/dictionary.json",
        "https://raw.githubusercontent.com/OdiaNLP/dictionary/main/dictionary.json",
    ]

    for url in github_urls:
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                continue

            data = res.json()

            if isinstance(data, dict):
                ODIA_DICT.update(data)

            elif isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    w = item.get("word") or item.get("odia")
                    m = item.get("meaning") or item.get("english")
                    if w and m:
                        ODIA_DICT[w.strip()] = m

            print(f"✅ Loaded {len(ODIA_DICT)} entries into OdiaNLP dictionary.")
            return

        except Exception:
            continue

    print("⚠️ OdiaNLP dictionary fallback mode active.")


# =====================================================================
# FASTAPI
# =====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        load_odianlp_dictionary()
    except Exception as e:
        print(f"⚠️ Dictionary startup warning: {e}")
    yield


app = FastAPI(
    title="Vedic Astro Engine & Kohinoor Odia Reader Server",
    version="2.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    def clean_errors(errors):
        if isinstance(errors, list):
            return [clean_errors(e) for e in errors]
        if isinstance(errors, dict):
            return {k: clean_errors(v) for k, v in errors.items()}
        if isinstance(errors, bytes):
            return errors.decode("utf-8", errors="ignore")
        return errors

    safe_errors = clean_errors(exc.errors())
    return JSONResponse(status_code=422, content={"detail": safe_errors})


# =====================================================================
# REQUEST MODEL
# =====================================================================

class BirthDataRequest(BaseModel):
    name: str = Field("Rahul Sharma", example="Rahul Sharma")
    date: str = Field(..., example="1995-10-16")
    time: str = Field(..., example="07:30:00")
    latitude: float = Field(..., example=22.66)
    longitude: float = Field(..., example=70.3455)
    tz_offset: float = Field(..., example=4.5)
    ayanamsha: str = Field("LAHIRI", example="LAHIRI")
    lang: str = Field("en", example="or")
    node_type: str = Field("MEAN", example="MEAN")
    chart_style: str = Field("ODIA", example="ODIA")


# =====================================================================
# HEALTH
# =====================================================================

@app.get("/")
def health_check():

    try:
        import swisseph  # noqa
        swe_ok = True
    except Exception:
        swe_ok = False

    try:
        import fitz  # noqa
        fitz_ok = True
    except Exception:
        fitz_ok = False

    return {
        "status": "ok",
        "version": "2.2.0",

        "astro_engine_loaded":
            ASTRO_ENGINE_LOADED,

        "swisseph_installed":
            swe_ok,

        "fitz_installed":
            fitz_ok,

        "weasyprint_installed":
            True,

        "kp_enabled":
            True,

        "dictionary_entries":
            len(ODIA_DICT),

        "fonts": {
            "odia": os.path.exists(
                ODIA_FONT_PATH
            ),

            "hindi": os.path.exists(
                DEVANAGARI_FONT_PATH
            ),

            "english": os.path.exists(
                ENGLISH_FONT_PATH
            ),
        },

        "message":
            "Vedic Astro Engine & Odia Reader Active",
    }


# =====================================================================
# ASTROLOGY CALCULATION
# =====================================================================

@app.post("/api/calculate")
def calculate_kundli(data: BirthDataRequest):
    try:
        if not ASTRO_ENGINE_LOADED:
            raise Exception("Astrology calculation engine is not loaded on server.")

        result = calculate_astrology(
            date_str=data.date,
            time_str=data.time,
            latitude=data.latitude,
            longitude=data.longitude,
            tz_offset=data.tz_offset,
            ayanamsha_mode=data.ayanamsha,
            lang=data.lang,
            node_type=data.node_type,
        )

        result["name"] = data.name

        moon_rashi_en = (
            result.get("planets_en", {})
            .get("Moon", {})
            .get("sign_en", "Aries")
        )

        result["rashifal"] = get_daily_rashifal(
            moon_rashi_en,
            lang=data.lang,
        )

        # KP calculation is kept independent and always uses
        # Krishnamurti ayanamsha + Placidus cusps.
        result["kp"] = calculate_kp_details(
            result,
            data,
        )

        return sanitize_response(result)

    except Exception as e:
        print("❌ Error inside /api/calculate:")
        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail=f"Calculation Error: {str(e)}"
        )



# =====================================================================
# KP ENDPOINT
# =====================================================================

@app.post("/api/kp")
def calculate_kp(data: BirthDataRequest):
    try:
        if not ASTRO_ENGINE_LOADED:
            raise Exception(
                "Astrology calculation engine is not loaded on server."
            )

        result = calculate_astrology(
            date_str=data.date,
            time_str=data.time,
            latitude=data.latitude,
            longitude=data.longitude,
            tz_offset=data.tz_offset,
            ayanamsha_mode="KRISHNAMURTI",
            lang="en",
            node_type=data.node_type,
        )

        return sanitize_response({
            "status": "success",
            "name": data.name,
            "kp": calculate_kp_details(
                result,
                data,
            ),
        })

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail=f"KP Calculation Error: {str(e)}",
        )


# =====================================================================
# PDF HTML
# =====================================================================

def build_pdf_html(result: dict, data: BirthDataRequest) -> str:
    pdf_font_name, pdf_font_path = get_pdf_font(data.lang)

    if not os.path.exists(pdf_font_path):
        raise Exception(
            f"PDF font not found: {pdf_font_path}"
        )

    pdf_font_uri = Path(
        pdf_font_path
    ).resolve().as_uri()

    def safe(value, default="-"):
        if value is None or value == "":
            return default

        return html.escape(
            str(value)
        )

    def safe_join(values, default="-"):
        if not values:
            return default

        return ", ".join(
            safe(v)
            for v in values
        )

    def yes_no(value):
        if data.lang == "or":
            return "ହଁ" if value else "ନା"

        if data.lang == "hi":
            return "हाँ" if value else "नहीं"

        return "Yes" if value else "No"

    # ---------------------------------------------------------
    # Chart helpers
    # ---------------------------------------------------------

    odia_digits = {
        1: "୧", 2: "୨", 3: "୩", 4: "୪",
        5: "୫", 6: "୬", 7: "୭", 8: "୮",
        9: "୯", 10: "୧୦", 11: "୧୧", 12: "୧୨",
    }

    odia_planets = {
        "Sun": "ର",
        "Ravi": "ର",
        "ସୂର୍ଯ୍ୟ": "ର",

        "Moon": "ଚ",
        "Chandra": "ଚ",
        "ଚନ୍ଦ୍ର": "ଚ",

        "Mars": "ମ",
        "Mangala": "ମ",
        "ମଙ୍ଗଳ": "ମ",

        "Mercury": "ବୁ",
        "Budha": "ବୁ",
        "ବୁଧ": "ବୁ",

        "Jupiter": "ଗୁ",
        "Guru": "ଗୁ",
        "ଗୁରୁ": "ଗୁ",

        "Venus": "ଶୁ",
        "Shukra": "ଶୁ",
        "ଶୁକ୍ର": "ଶୁ",

        "Saturn": "ଶ",
        "Shani": "ଶ",
        "ଶନି": "ଶ",

        "Rahu": "ରା",
        "ରାହୁ": "ରା",

        "Ketu": "କେ",
        "କେତୁ": "କେ",

        "Lagna": "ଲ",
        "Ascendant": "ଲ",
        "ଲଗ୍ନ": "ଲ",
    }

    def sign_number_from_house(house_data):
        house_data = house_data or {}

        sign_en = str(
            house_data.get("sign_en")
            or ""
        )

        if sign_en in KP_SIGN_NAMES:
            return (
                KP_SIGN_NAMES.index(
                    sign_en
                )
                + 1
            )

        sign = str(
            house_data.get("sign")
            or ""
        ).lower()

        tests = [
            (1, ("ari", "mesh", "ମେଷ", "मेष")),
            (2, ("tau", "vrish", "ବୃଷ", "वृष")),
            (3, ("gem", "mith", "ମିଥୁନ", "मिथुन")),
            (4, ("can", "kark", "କର୍କ", "कर्क")),
            (5, ("leo", "simh", "ସିଂହ", "सिंह")),
            (6, ("vir", "kany", "କନ୍ୟା", "कन्या")),
            (7, ("lib", "tula", "ତୁଳା", "तुला")),
            (8, ("sco", "vrisch", "ବୃଶ୍ଚିକ", "वृश्चिक")),
            (9, ("sag", "dhan", "ଧନୁ", "धनु")),
            (10, ("cap", "maka", "ମକର", "मकर")),
            (11, ("aqu", "kumb", "କୁମ୍ଭ", "कुंभ")),
            (12, ("pis", "meen", "ମୀନ", "मीन")),
        ]

        for sign_number, tokens in tests:
            if any(
                token in sign
                for token in tokens
            ):
                return sign_number

        return 1

    def chart_sign_map(chart):
        sign_map = {
            i: []
            for i in range(1, 13)
        }

        houses = (
            (chart or {}).get(
                "houses",
                {}
            )
            or {}
        )

        for house_no, h in houses.items():
            sign_no = sign_number_from_house(
                h
            )

            try:
                if int(house_no) == 1:
                    sign_map[
                        sign_no
                    ].append(
                        "Lagna"
                    )
            except Exception:
                pass

            for planet in (
                h.get(
                    "planets",
                    []
                )
                or []
            ):
                sign_map[
                    sign_no
                ].append(
                    str(planet)
                )

        return sign_map

    def odia_occupants(items):
        converted = []

        for planet in items:
            planet_name = str(
                planet
            )

            converted.append(
                odia_planets.get(
                    planet_name,
                    planet_name[:2],
                )
            )

        return " ".join(
            converted
        )

    # ---------------------------------------------------------
    # Traditional Odia / East Indian chart
    # ---------------------------------------------------------

    def build_odia_chart(
        chart_name,
        chart,
    ):
        sign_map = chart_sign_map(
            chart
        )

        positions = {
            1: (180, 295),
            2: (295, 315),
            3: (315, 265),
            4: (295, 180),
            5: (315, 95),
            6: (295, 45),
            7: (180, 65),
            8: (65, 45),
            9: (45, 95),
            10: (65, 180),
            11: (45, 265),
            12: (65, 320),
        }

        sign_text = ""

        for sign_no in range(
            1,
            13
        ):
            x, y = positions[
                sign_no
            ]

            label = (
                f"{odia_digits[sign_no]} "
                f"{odia_occupants(sign_map[sign_no])}"
            ).strip()

            sign_text += f'''
            <text
                x="{x}"
                y="{y}"
                fill="#0d7880"
                font-family="{pdf_font_name}"
                font-size="13"
                text-anchor="middle"
            >
                {safe(label)}
            </text>
            '''

        lagna = safe(
            (chart or {}).get(
                "lagna_sign"
            )
            or "-"
        )

        return f'''
        <div class="chart-block">

            <div class="chart-title">
                {safe(chart_name)}
                · ଲଗ୍ନ: {lagna}
            </div>

            <svg
                viewBox="0 0 360 360"
                class="chart-svg"
                xmlns="http://www.w3.org/2000/svg"
            >

                <rect
                    x="5"
                    y="5"
                    width="350"
                    height="350"
                    fill="#ffffff"
                    stroke="#0d7880"
                    stroke-width="3"
                />

                <line x1="120" y1="5" x2="120" y2="355" stroke="#0d7880" stroke-width="2"/>
                <line x1="240" y1="5" x2="240" y2="355" stroke="#0d7880" stroke-width="2"/>

                <line x1="5" y1="120" x2="355" y2="120" stroke="#0d7880" stroke-width="2"/>
                <line x1="5" y1="240" x2="355" y2="240" stroke="#0d7880" stroke-width="2"/>

                <line x1="5" y1="5" x2="120" y2="120" stroke="#0d7880" stroke-width="2"/>
                <line x1="355" y1="5" x2="240" y2="120" stroke="#0d7880" stroke-width="2"/>
                <line x1="120" y1="240" x2="5" y2="355" stroke="#0d7880" stroke-width="2"/>
                <line x1="240" y1="240" x2="355" y2="355" stroke="#0d7880" stroke-width="2"/>

                <text
                    x="180"
                    y="170"
                    fill="#0d7880"
                    font-family="{pdf_font_name}"
                    font-size="15"
                    text-anchor="middle"
                >
                    ରାଶି ଚକ୍ର
                </text>

                <text
                    x="180"
                    y="195"
                    fill="#64748b"
                    font-family="{pdf_font_name}"
                    font-size="10"
                    text-anchor="middle"
                >
                    {safe(chart_name)}
                </text>

                {sign_text}

            </svg>

        </div>
        '''

    # ---------------------------------------------------------
    # North Indian chart
    # ---------------------------------------------------------

    def build_north_chart(
        chart_name,
        chart,
    ):
        houses = (
            (chart or {}).get(
                "houses",
                {}
            )
            or {}
        )

        positions = {
            1: (200, 100),
            2: (100, 50),
            3: (50, 100),
            4: (100, 200),
            5: (50, 300),
            6: (100, 350),
            7: (200, 300),
            8: (300, 350),
            9: (350, 300),
            10: (300, 200),
            11: (350, 100),
            12: (300, 50),
        }

        labels = ""

        for house_no in range(
            1,
            13
        ):
            h = (
                houses.get(
                    str(house_no)
                )
                or
                houses.get(
                    house_no
                )
                or {}
            )

            sign = safe(
                h.get("sign")
                or
                h.get("sign_en")
                or house_no
            )

            planets = safe_join(
                h.get(
                    "planets"
                )
                or []
            )

            x, y = positions[
                house_no
            ]

            labels += f'''
            <text
                x="{x}"
                y="{y - 9}"
                fill="#0d7880"
                font-family="{pdf_font_name}"
                font-size="10"
                text-anchor="middle"
            >
                {sign}
            </text>

            <text
                x="{x}"
                y="{y + 10}"
                fill="#1e293b"
                font-family="{pdf_font_name}"
                font-size="8"
                text-anchor="middle"
            >
                {planets}
            </text>
            '''

        return f'''
        <div class="chart-block">

            <div class="chart-title">
                {safe(chart_name)}
                · North Indian
            </div>

            <svg
                viewBox="0 0 400 400"
                class="chart-svg"
                xmlns="http://www.w3.org/2000/svg"
            >

                <rect
                    x="10"
                    y="10"
                    width="380"
                    height="380"
                    fill="#ffffff"
                    stroke="#0d7880"
                    stroke-width="2"
                />

                <line x1="10" y1="10" x2="390" y2="390" stroke="#0d7880" stroke-width="1.5"/>
                <line x1="390" y1="10" x2="10" y2="390" stroke="#0d7880" stroke-width="1.5"/>

                <polygon
                    points="200,10 390,200 200,390 10,200"
                    fill="none"
                    stroke="#0d7880"
                    stroke-width="1.5"
                />

                {labels}

            </svg>

        </div>
        '''

    # ---------------------------------------------------------
    # South Indian chart as SVG (PDF-safe)
    # ---------------------------------------------------------

    def build_south_chart(
        chart_name,
        chart,
    ):
        houses = (
            (chart or {}).get(
                "houses",
                {}
            )
            or {}
        )

        sign_to_data = {}

        for h in houses.values():
            sign_to_data[
                sign_number_from_house(
                    h
                )
            ] = h

        # positions are 4x4 fixed-sign cells
        cells = {
            12: (0, 0),
            1: (1, 0),
            2: (2, 0),
            3: (3, 0),
            11: (0, 1),
            4: (3, 1),
            10: (0, 2),
            5: (3, 2),
            9: (0, 3),
            8: (1, 3),
            7: (2, 3),
            6: (3, 3),
        }

        cell_svg = ""

        for sign_no, (
            col,
            row
        ) in cells.items():

            x = col * 100
            y = row * 100

            h = sign_to_data.get(
                sign_no,
                {}
            )

            sign = safe(
                h.get("sign")
                or
                h.get("sign_en")
                or
                KP_SIGN_NAMES[
                    sign_no - 1
                ]
            )

            planets = safe_join(
                h.get(
                    "planets"
                )
                or []
            )

            cell_svg += f'''
            <rect
                x="{x}"
                y="{y}"
                width="100"
                height="100"
                fill="#ffffff"
                stroke="#cbd5e1"
                stroke-width="1"
            />

            <text
                x="{x + 8}"
                y="{y + 18}"
                fill="#0d7880"
                font-family="{pdf_font_name}"
                font-size="10"
            >
                {sign}
            </text>

            <text
                x="{x + 8}"
                y="{y + 82}"
                fill="#1e293b"
                font-family="{pdf_font_name}"
                font-size="8"
            >
                {planets}
            </text>
            '''

        return f'''
        <div class="chart-block">

            <div class="chart-title">
                {safe(chart_name)}
                · South Indian
            </div>

            <svg
                viewBox="0 0 400 400"
                class="chart-svg"
                xmlns="http://www.w3.org/2000/svg"
            >

                <rect
                    x="0"
                    y="0"
                    width="400"
                    height="400"
                    fill="#ffffff"
                    stroke="#0d7880"
                    stroke-width="3"
                />

                {cell_svg}

                <rect
                    x="100"
                    y="100"
                    width="200"
                    height="200"
                    fill="#f8fafc"
                    stroke="#cbd5e1"
                    stroke-width="1"
                />

                <text
                    x="200"
                    y="190"
                    fill="#0d7880"
                    font-family="{pdf_font_name}"
                    font-size="14"
                    text-anchor="middle"
                >
                    {safe(chart_name)}
                </text>

                <text
                    x="200"
                    y="212"
                    fill="#64748b"
                    font-family="{pdf_font_name}"
                    font-size="10"
                    text-anchor="middle"
                >
                    South Indian
                </text>

            </svg>

        </div>
        '''

    # ---------------------------------------------------------
    # Circular / round chart
    # ---------------------------------------------------------

    def build_round_chart(
        chart_name,
        chart,
    ):
        sign_map = chart_sign_map(
            chart
        )

        cx = 200.0
        cy = 200.0
        radius = 180.0

        radial_lines = ""
        labels = ""

        for index in range(
            12
        ):
            angle = math.radians(
                index * 30
                - 90
            )

            x = (
                cx
                + radius
                * math.cos(
                    angle
                )
            )

            y = (
                cy
                + radius
                * math.sin(
                    angle
                )
            )

            radial_lines += f'''
            <line
                x1="{cx}"
                y1="{cy}"
                x2="{x:.2f}"
                y2="{y:.2f}"
                stroke="#0d7880"
                stroke-width="1.3"
            />
            '''

            middle_angle = math.radians(
                index * 30
                - 75
            )

            tx = (
                cx
                + 128
                * math.cos(
                    middle_angle
                )
            )

            ty = (
                cy
                + 128
                * math.sin(
                    middle_angle
                )
            )

            sign_no = (
                index + 1
            )

            label = (
                f"{odia_digits[sign_no]} "
                f"{odia_occupants(sign_map[sign_no])}"
            ).strip()

            labels += f'''
            <text
                x="{tx:.2f}"
                y="{ty:.2f}"
                fill="#0d7880"
                font-family="{pdf_font_name}"
                font-size="10"
                text-anchor="middle"
            >
                {safe(label)}
            </text>
            '''

        return f'''
        <div class="chart-block">

            <div class="chart-title">
                {safe(chart_name)}
                · Circular
            </div>

            <svg
                viewBox="0 0 400 400"
                class="chart-svg"
                xmlns="http://www.w3.org/2000/svg"
            >

                <circle
                    cx="200"
                    cy="200"
                    r="180"
                    fill="#ffffff"
                    stroke="#0d7880"
                    stroke-width="2.5"
                />

                {radial_lines}

                <circle
                    cx="200"
                    cy="200"
                    r="72"
                    fill="#fffbea"
                    stroke="#0d7880"
                    stroke-width="1.5"
                />

                <text
                    x="200"
                    y="195"
                    fill="#0d7880"
                    font-family="{pdf_font_name}"
                    font-size="15"
                    text-anchor="middle"
                >
                    ରାଶି ଚକ୍ର
                </text>

                <text
                    x="200"
                    y="214"
                    fill="#64748b"
                    font-family="{pdf_font_name}"
                    font-size="9"
                    text-anchor="middle"
                >
                    {safe(chart_name)}
                </text>

                {labels}

            </svg>

        </div>
        '''

    def render_chart(
        chart_name,
        chart,
    ):
        chart_style = str(
            getattr(
                data,
                "chart_style",
                "ODIA",
            )
            or "ODIA"
        ).upper()

        if chart_style == "NORTH":
            return build_north_chart(
                chart_name,
                chart,
            )

        if chart_style == "SOUTH":
            return build_south_chart(
                chart_name,
                chart,
            )

        if chart_style in (
            "ROUND",
            "CIRCULAR",
        ):
            return build_round_chart(
                chart_name,
                chart,
            )

        return build_odia_chart(
            chart_name,
            chart,
        )

    # ---------------------------------------------------------
    # Core result sections
    # ---------------------------------------------------------

    lagna = (
        result.get(
            "lagna",
            {}
        )
        or {}
    )

    planets = (
        result.get(
            "planets",
            {}
        )
        or {}
    )

    house_lords = (
        result.get(
            "house_lords",
            {}
        )
        or {}
    )

    panchanga = (
        result.get(
            "panchanga",
            {}
        )
        or {}
    )

    vimshottari = (
        result.get(
            "vimshottari",
            {}
        )
        or {}
    )

    current_md = (
        vimshottari.get(
            "current_mahadasha"
        )
        or {}
    )

    current_ad = (
        vimshottari.get(
            "current_antardasha"
        )
        or {}
    )

    current_pd = (
        vimshottari.get(
            "current_pratyantardasha"
        )
        or {}
    )

    kp = (
        result.get(
            "kp"
        )
        or
        calculate_kp_details(
            result,
            data,
        )
    )

    planet_rows = ""

    for planet_name, p in planets.items():
        statuses = []

        if p.get(
            "is_retrograde"
        ):
            statuses.append(
                "Retrograde"
            )

        if p.get(
            "is_combust"
        ):
            statuses.append(
                "Combust"
            )

        if not statuses:
            statuses.append(
                "Direct"
            )

        planet_rows += f'''
        <tr>
            <td class="strong">{safe(planet_name)}</td>
            <td>{safe(p.get("sign"))}</td>
            <td>{safe(p.get("degree"))}</td>
            <td>{safe(p.get("nakshatra"))}</td>
            <td>{safe(p.get("pada"))}</td>
            <td>{safe(p.get("house"))}</td>
            <td>{safe(p.get("navamsa_sign"))}</td>
            <td>{safe(p.get("dignity"))}</td>
            <td>{safe_join(statuses)}</td>
        </tr>
        '''

    house_rows = ""

    for house_no, h in (
        result.get(
            "houses",
            {}
        )
        or {}
    ).items():

        lord_info = (
            house_lords.get(
                str(house_no)
            )
            or
            house_lords.get(
                house_no
            )
            or {}
        )

        house_rows += f'''
        <tr>
            <td>{safe(house_no)}</td>
            <td>{safe(h.get("sign"))}</td>
            <td>{safe(h.get("lord") or lord_info.get("lord"))}</td>
            <td>{safe(lord_info.get("lord_house"))}</td>
            <td>{safe_join(h.get("planets") or [])}</td>
        </tr>
        '''

    dasha_rows = ""

    for d in (
        result.get(
            "dasha",
            []
        )
        or []
    ):
        dasha_rows += f'''
        <tr>
            <td>{safe(d.get("lord"))}</td>
            <td>{safe(d.get("start_date"))}</td>
            <td>{safe(d.get("end_date"))}</td>
            <td>{safe(d.get("duration"))}</td>
            <td>{"CURRENT" if d.get("is_active") else ""}</td>
        </tr>
        '''

    yoga_rows = "".join(
        f'''
        <tr>
            <td>{safe(y.get("name"))}</td>
            <td>{safe(y.get("basis"))}</td>
        </tr>
        '''
        for y in (
            result.get(
                "yogas",
                []
            )
            or []
        )
    )

    if not yoga_rows:
        yoga_rows = '''
        <tr>
            <td colspan="2">
                No configured Yoga rule matched.
            </td>
        </tr>
        '''

    dosha_rows = ""

    for key, title in [
        (
            "manglik",
            "Manglik Dosha",
        ),
        (
            "kaal_sarp",
            "Kaal Sarp",
        ),
        (
            "pitru_indicator",
            "Pitru Dosha",
        ),
        (
            "sade_sati",
            "Sade Sati",
        ),
        (
            "dhaiya",
            "Saturn Dhaiya",
        ),
    ]:

        item = (
            (
                result.get(
                    "doshas",
                    {}
                )
                or {}
            ).get(
                key
            )
            or {}
        )

        details = []

        for field, label in [
            (
                "mars_house",
                "Mars House",
            ),
            (
                "phase",
                "Phase",
            ),
            (
                "saturn_sign",
                "Saturn Sign",
            ),
            (
                "saturn_from_moon_house",
                "Saturn from Moon",
            ),
        ]:

            if item.get(
                field
            ) is not None:

                details.append(
                    f"{label}: "
                    f"{safe(item.get(field))}"
                )

        if item.get(
            "basis"
        ):
            details.append(
                safe(
                    item.get(
                        "basis"
                    )
                )
            )

        if item.get(
            "rule"
        ):
            details.append(
                safe(
                    item.get(
                        "rule"
                    )
                )
            )

        dosha_rows += f'''
        <tr>
            <td>{safe(title)}</td>
            <td>
                {
                    "Present"
                    if item.get("present")
                    else "Not Present"
                }
            </td>
            <td>
                {
                    "<br/>".join(details)
                    if details
                    else "-"
                }
            </td>
        </tr>
        '''

    strength = (
        result.get(
            "strength",
            {}
        )
        or {}
    )

    strength_rows = ""

    for planet_name, item in (
        strength.get(
            "planets",
            {}
        )
        or {}
    ).items():

        strength_rows += f'''
        <tr>
            <td>{safe(planet_name)}</td>
            <td>{safe(item.get("score"))}/100</td>
            <td>{safe(item.get("label"))}</td>
            <td>{safe(item.get("dignity"))}</td>
            <td>{yes_no(item.get("retrograde"))}</td>
            <td>{yes_no(item.get("combust"))}</td>
        </tr>
        '''

    transit_rows = ""

    for planet_name, transit in (
        result.get(
            "transits",
            {}
        )
        or {}
    ).items():

        try:
            longitude_text = (
                f'{float(transit.get("longitude_raw")):.4f}°'
            )
        except Exception:
            longitude_text = safe(
                transit.get(
                    "longitude_raw"
                )
            )

        transit_rows += f'''
        <tr>
            <td>{safe(planet_name)}</td>
            <td>{safe(transit.get("sign") or transit.get("sign_en"))}</td>
            <td>{longitude_text}</td>
            <td>
                {
                    "Retrograde"
                    if transit.get("is_retrograde")
                    else "Direct"
                }
            </td>
        </tr>
        '''

    # ---------------------------------------------------------
    # KP tables
    # ---------------------------------------------------------

    kp_planet_rows = ""

    for planet_name, p in (
        kp.get(
            "planets",
            {}
        )
        or {}
    ).items():

        try:
            position = (
                f'{safe(p.get("sign"))} '
                f'{float(p.get("degree_in_sign", 0)):.4f}°'
            )
        except Exception:
            position = safe(
                p.get(
                    "sign"
                )
            )

        kp_planet_rows += f'''
        <tr>
            <td>{safe(planet_name)}</td>
            <td>{position}</td>
            <td>{safe(p.get("star_lord"))}</td>
            <td>{safe(p.get("sub_lord"))}</td>
            <td>{safe(p.get("sub_sub_lord"))}</td>
        </tr>
        '''

    if not kp_planet_rows:
        kp_planet_rows = '''
        <tr>
            <td colspan="5">
                KP planet longitude data unavailable.
            </td>
        </tr>
        '''

    kp_cusp_rows = ""

    for cusp_no, cusp in (
        kp.get(
            "cusps",
            {}
        )
        or {}
    ).items():

        try:
            position = (
                f'{safe(cusp.get("sign"))} '
                f'{float(cusp.get("degree_in_sign", 0)):.4f}°'
            )
        except Exception:
            position = safe(
                cusp.get(
                    "sign"
                )
            )

        kp_cusp_rows += f'''
        <tr>
            <td>{safe(cusp_no)}</td>
            <td>{position}</td>
            <td>{safe(cusp.get("sign_lord"))}</td>
            <td>{safe(cusp.get("star_lord"))}</td>
            <td>{safe(cusp.get("sub_lord"))}</td>
            <td>{safe(cusp.get("sub_sub_lord"))}</td>
        </tr>
        '''

    if not kp_cusp_rows:
        kp_cusp_rows = '''
        <tr>
            <td colspan="6">
                KP cusp data unavailable.
            </td>
        </tr>
        '''

    ruling_planets = (
        kp.get(
            "ruling_planets",
            {}
        )
        or {}
    )

    ruling_html = "".join(
        f'''
        <span class="chip">
            <b>
                {
                    safe(
                        key.replace(
                            "_",
                            " ",
                        ).title()
                    )
                }:
            </b>
            {safe(value)}
        </span>
        '''
        for key, value in (
            ruling_planets.items()
        )
    )

    # ---------------------------------------------------------
    # Varga charts
    # ---------------------------------------------------------

    charts = (
        result.get(
            "charts",
            {}
        )
        or {}
    )

    varga_order = [
        "D1",
        "D2",
        "D3",
        "D4",
        "D7",
        "D9",
        "D10",
        "D12",
        "D16",
        "D20",
        "D24",
        "D27",
        "D30",
        "D40",
        "D45",
        "D60",
    ]

    varga_names = {
        "D1": "Rashi",
        "D2": "Hora",
        "D3": "Drekkana",
        "D4": "Chaturthamsha",
        "D7": "Saptamsha",
        "D9": "Navamsa",
        "D10": "Dashamsha",
        "D12": "Dwadasamsha",
        "D16": "Shodasamsha",
        "D20": "Vimsamsha",
        "D24": "Chaturvimsamsha",
        "D27": "Bhamsa",
        "D30": "Trimsamsha",
        "D40": "Khavedamsha",
        "D45": "Akshavedamsha",
        "D60": "Shashtiamsha",
    }

    chart_blocks = []

    for chart_key in varga_order:
        chart = charts.get(
            chart_key
        )

        if (
            not chart
            and
            chart_key == "D1"
            and
            result.get("houses")
        ):
            chart = {
                "houses":
                    result.get(
                        "houses",
                        {}
                    ),
                "lagna_sign":
                    lagna.get(
                        "sign"
                    ),
            }

        if (
            not chart
            and
            chart_key == "D9"
            and
            result.get(
                "navamsa_houses"
            )
        ):
            chart = {
                "houses":
                    result.get(
                        "navamsa_houses",
                        {}
                    ),
                "lagna_sign":
                    lagna.get(
                        "navamsa_sign"
                    ),
            }

        if chart:
            chart_blocks.append(
                render_chart(
                    (
                        f"{chart_key} - "
                        f"{varga_names.get(chart_key, '')}"
                    ),
                    chart,
                )
            )

    varga_html = (
        '<div class="charts-grid">'
        +
        "".join(
            (
                '<div class="chart-col">'
                + block
                + '</div>'
            )
            for block in chart_blocks
        )
        +
        "</div>"
    )

    rashifal = (
        result.get(
            "rashifal",
            {}
        )
        or {}
    )

    rashifal_rows = ""

    for key, label in [
        (
            "overall",
            "Overall",
        ),
        (
            "career",
            "Career",
        ),
        (
            "finance",
            "Finance",
        ),
        (
            "love",
            "Love",
        ),
        (
            "health",
            "Health",
        ),
        (
            "lucky_number",
            "Lucky Number",
        ),
        (
            "lucky_color",
            "Lucky Color",
        ),
    ]:

        if key in rashifal:
            rashifal_rows += f'''
            <tr>
                <td class="strong">
                    {safe(label)}
                </td>
                <td>
                    {safe(rashifal.get(key))}
                </td>
            </tr>
            '''

    notes_html = "".join(
        f'''
        <div class="note">
            • {safe(note)}
        </div>
        '''
        for note in (
            result.get(
                "calculation_notes",
                []
            )
            or []
        )
    )

    if data.lang == "or":
        report_title = (
            "ବୈଦିକ ଜାତକ ଓ କୁଣ୍ଡଳୀ"
        )

        report_subtitle = (
            "Swiss Ephemeris ଆଧାରିତ "
            "ବୈଦିକ ଜ୍ୟୋତିଷ ଗଣନା"
        )

    elif data.lang == "hi":
        report_title = (
            "वैदिक जन्म कुंडली"
        )

        report_subtitle = (
            "Swiss Ephemeris आधारित "
            "वैदिक ज्योतिष गणना"
        )

    else:
        report_title = (
            "Vedic Jatak & Kundli Report"
        )

        report_subtitle = (
            "Swiss Ephemeris Based "
            "Vedic Astrology Calculation"
        )

    d1_chart = (
        charts.get(
            "D1"
        )
        or {
            "houses":
                result.get(
                    "houses",
                    {}
                ),
            "lagna_sign":
                lagna.get(
                    "sign"
                ),
        }
    )

    return f'''
    <!DOCTYPE html>
    <html>

    <head>

        <meta charset="UTF-8"/>

        <style>

            @font-face {{
                font-family:
                    "{pdf_font_name}";

                src:
                    url("{pdf_font_uri}");
            }}

            @page {{
                size:
                    A4;

                margin:
                    10mm;
            }}

            html,
            body,
            div,
            span,
            p,
            table,
            tr,
            td,
            th,
            strong,
            small {{
                font-family:
                    "{pdf_font_name}";
            }}

            body {{
                color:
                    #1e293b;

                font-size:
                    9px;

                line-height:
                    1.45;
            }}

            .header {{
                text-align:
                    center;

                border-bottom:
                    3px solid #0d7880;

                padding-bottom:
                    10px;

                margin-bottom:
                    12px;
            }}

            .title {{
                color:
                    #0d7880;

                font-size:
                    20px;
            }}

            .subtitle {{
                color:
                    #64748b;

                font-size:
                    9px;
            }}

            .section-title {{
                background:
                    #0d7880;

                color:
                    #ffffff;

                font-size:
                    12px;

                padding:
                    7px;

                margin:
                    13px 0 7px;
            }}

            table {{
                width:
                    100%;

                border-collapse:
                    collapse;

                margin-bottom:
                    8px;
            }}

            th {{
                background:
                    #eef7f7;

                color:
                    #0f172a;

                border:
                    1px solid #94a3b8;

                padding:
                    5px;

                font-size:
                    7.5px;

                text-align:
                    left;
            }}

            td {{
                border:
                    1px solid #cbd5e1;

                padding:
                    5px;

                font-size:
                    7.5px;

                vertical-align:
                    top;
            }}

            .birth-box {{
                background:
                    #fffbeb;

                border:
                    1px solid #fde68a;

                padding:
                    7px;
            }}

            .strong {{
                color:
                    #0f172a;
            }}

            .note {{
                background:
                    #eff6ff;

                border:
                    1px solid #bfdbfe;

                padding:
                    6px;

                margin-bottom:
                    4px;
            }}

            .chip {{
                display:
                    inline-block;

                border:
                    1px solid #bae6e6;

                background:
                    #f0fdfa;

                padding:
                    4px 6px;

                margin:
                    2px;

                border-radius:
                    5px;
            }}

            .page-break {{
                page-break-before:
                    always;
            }}

            .charts-grid {{
                font-size:
                    0;
            }}

            .chart-col {{
                display:
                    inline-block;

                width:
                    48%;

                margin:
                    1%;

                vertical-align:
                    top;

                font-size:
                    9px;

                page-break-inside:
                    avoid;
            }}

            .chart-block {{
                width:
                    100%;

                page-break-inside:
                    avoid;

                margin-bottom:
                    10px;
            }}

            .chart-title {{
                text-align:
                    center;

                color:
                    #0d7880;

                font-size:
                    10px;

                margin-bottom:
                    3px;
            }}

            .chart-svg {{
                width:
                    100%;

                height:
                    auto;

                display:
                    block;
            }}

        </style>

    </head>

    <body>

        <div class="header">

            <div class="title">
                {report_title}
            </div>

            <div class="subtitle">
                {report_subtitle}
            </div>

        </div>

        <div class="section-title">
            Birth Details / ଜନ୍ମ ବିବରଣୀ
        </div>

        <div class="birth-box">

            <table>

                <tr>
                    <td><b>Name</b></td>
                    <td>{safe(data.name)}</td>
                    <td><b>Date</b></td>
                    <td>{safe(data.date)}</td>
                </tr>

                <tr>
                    <td><b>Time</b></td>
                    <td>{safe(data.time)}</td>
                    <td><b>Timezone</b></td>
                    <td>UTC {safe(data.tz_offset)}</td>
                </tr>

                <tr>
                    <td><b>Latitude</b></td>
                    <td>{safe(data.latitude)}</td>
                    <td><b>Longitude</b></td>
                    <td>{safe(data.longitude)}</td>
                </tr>

                <tr>
                    <td><b>Ayanamsha</b></td>
                    <td>{safe(result.get("ayanamsha_mode") or data.ayanamsha)}</td>
                    <td><b>Node</b></td>
                    <td>{safe(result.get("node_type") or data.node_type)}</td>
                </tr>

            </table>

        </div>

        <div class="section-title">
            Rashi Chakra / ରାଶି ଚକ୍ର
        </div>

        {render_chart("D1 - Rashi", d1_chart)}

        <div class="section-title">
            Lagna / ଲଗ୍ନ
        </div>

        <table>
            <tr>
                <th>Rashi</th>
                <th>Degree</th>
                <th>Nakshatra</th>
                <th>Pada</th>
                <th>Navamsa</th>
            </tr>

            <tr>
                <td>{safe(lagna.get("sign"))}</td>
                <td>{safe(lagna.get("degree"))}</td>
                <td>{safe(lagna.get("nakshatra"))}</td>
                <td>{safe(lagna.get("pada"))}</td>
                <td>{safe(lagna.get("navamsa_sign"))}</td>
            </tr>
        </table>

        <div class="section-title">
            Planetary Positions / ଗ୍ରହ ସ୍ଥିତି
        </div>

        <table>
            <tr>
                <th>Planet</th>
                <th>Rashi</th>
                <th>Degree</th>
                <th>Nakshatra</th>
                <th>Pada</th>
                <th>House</th>
                <th>D9</th>
                <th>Dignity</th>
                <th>Status</th>
            </tr>

            {planet_rows}

        </table>

        <div class="section-title">
            12 Bhava / ଦ୍ୱାଦଶ ଭାବ
        </div>

        <table>
            <tr>
                <th>House</th>
                <th>Rashi</th>
                <th>Lord</th>
                <th>Lord House</th>
                <th>Planets</th>
            </tr>

            {house_rows}

        </table>

        <div class="section-title">
            Panchanga / ପଞ୍ଚାଙ୍ଗ
        </div>

        <table>
            <tr><td>Tithi</td><td>{safe(panchanga.get("tithi"))}</td></tr>
            <tr><td>Paksha</td><td>{safe(panchanga.get("paksha"))}</td></tr>
            <tr><td>Vara</td><td>{safe(panchanga.get("vara"))}</td></tr>
            <tr><td>Nakshatra</td><td>{safe(panchanga.get("nakshatra"))}</td></tr>
            <tr><td>Yoga</td><td>{safe(panchanga.get("yoga"))}</td></tr>
            <tr><td>Karana</td><td>{safe(panchanga.get("karana"))}</td></tr>
        </table>

        <div class="section-title">
            Current Vimshottari Dasha
        </div>

        <table>
            <tr>
                <th>Level</th>
                <th>Lord</th>
                <th>Start</th>
                <th>End</th>
            </tr>

            <tr>
                <td>Mahadasha</td>
                <td>{safe(current_md.get("lord"))}</td>
                <td>{safe(current_md.get("start_date"))}</td>
                <td>{safe(current_md.get("end_date"))}</td>
            </tr>

            <tr>
                <td>Antardasha</td>
                <td>{safe(current_ad.get("lord"))}</td>
                <td>{safe(current_ad.get("start_date"))}</td>
                <td>{safe(current_ad.get("end_date"))}</td>
            </tr>

            <tr>
                <td>Pratyantardasha</td>
                <td>{safe(current_pd.get("lord"))}</td>
                <td>{safe(current_pd.get("start_date"))}</td>
                <td>{safe(current_pd.get("end_date"))}</td>
            </tr>

        </table>

        <table>
            <tr>
                <th>Lord</th>
                <th>Start</th>
                <th>End</th>
                <th>Years</th>
                <th>Status</th>
            </tr>

            {dasha_rows}

        </table>

        <div class="section-title">
            Yogas / ଯୋଗ
        </div>

        <table>
            <tr>
                <th>Yoga</th>
                <th>Basis</th>
            </tr>

            {yoga_rows}

        </table>

        <div class="section-title">
            Dosha Analysis / ଦୋଷ ବିଶ୍ଳେଷଣ
        </div>

        <table>
            <tr>
                <th>Dosha</th>
                <th>Status</th>
                <th>Details</th>
            </tr>

            {dosha_rows}

        </table>

        <div class="section-title">
            Planet Strength / ଗ୍ରହ ବଳ
        </div>

        <div class="note">
            {safe(strength.get("note"))}
        </div>

        <table>
            <tr>
                <th>Planet</th>
                <th>Score</th>
                <th>Strength</th>
                <th>Dignity</th>
                <th>Retrograde</th>
                <th>Combust</th>
            </tr>

            {strength_rows}

        </table>

        <div class="section-title">
            Gochar / ଗୋଚର
        </div>

        <table>
            <tr>
                <th>Planet</th>
                <th>Rashi</th>
                <th>Longitude</th>
                <th>Motion</th>
            </tr>

            {transit_rows}

        </table>

        <div class="section-title">
            KP – Krishnamurti Paddhati
        </div>

        <div class="note">
            {safe(kp.get("note"))}
        </div>

        <div>
            {ruling_html}
        </div>

        <h4>
            KP Planets
        </h4>

        <table>
            <tr>
                <th>Planet</th>
                <th>Position</th>
                <th>Star Lord</th>
                <th>Sub Lord</th>
                <th>Sub-Sub Lord</th>
            </tr>

            {kp_planet_rows}

        </table>

        <h4>
            KP Cusps (Placidus)
        </h4>

        <table>
            <tr>
                <th>Cusp</th>
                <th>Position</th>
                <th>Sign Lord</th>
                <th>Star Lord</th>
                <th>Sub Lord</th>
                <th>Sub-Sub Lord</th>
            </tr>

            {kp_cusp_rows}

        </table>

        <div class="page-break">
        </div>

        <div class="section-title">
            Divisional / Varga Charts
        </div>

        {varga_html}

        <div class="section-title">
            Daily Rashifal / ଦୈନିକ ରାଶିଫଳ
        </div>

        <table>
            {rashifal_rows}
        </table>

        <div class="section-title">
            Calculation Notes
        </div>

        {notes_html}

    </body>

    </html>
    '''


# =====================================================================
# PDF EXPORT
# =====================================================================

@app.post("/api/export-pdf")
def export_kundli_pdf(
    data: BirthDataRequest
):
    try:
        if not ASTRO_ENGINE_LOADED:
            raise Exception(
                "Astrology calculation "
                "engine is not loaded."
            )

        font_name, font_path = (
            get_pdf_font(
                data.lang
            )
        )

        if not os.path.exists(
            font_path
        ):
            raise Exception(
                f"Required PDF font "
                f"is missing: {font_path}"
            )

        result = calculate_astrology(
            date_str=data.date,
            time_str=data.time,
            latitude=data.latitude,
            longitude=data.longitude,
            tz_offset=data.tz_offset,
            ayanamsha_mode=data.ayanamsha,
            lang=data.lang,
            node_type=data.node_type,
        )

        result["name"] = (
            data.name
        )

        moon_rashi_en = (
            result
            .get(
                "planets_en",
                {}
            )
            .get(
                "Moon",
                {}
            )
            .get(
                "sign_en",
                "Aries"
            )
        )

        result["rashifal"] = (
            get_daily_rashifal(
                moon_rashi_en,
                lang=data.lang,
            )
        )

        result["kp"] = (
            calculate_kp_details(
                result,
                data,
            )
        )

        html_content = (
            build_pdf_html(
                result,
                data
            )
        )

        pdf_bytes = HTML(
            string=html_content,
            base_url=BASE_DIR,
        ).write_pdf()

        if not pdf_bytes:
            raise Exception(
                "Generated PDF is empty."
            )

        pdf_base64 = (
            base64
            .b64encode(
                pdf_bytes
            )
            .decode(
                "utf-8"
            )
        )

        safe_name = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            data.name
        ).strip("_")

        filename = (
            f"Jatak_"
            f"{safe_name or 'Report'}"
            f".pdf"
        )

        print(
            "✅ PDF GENERATED:",
            filename,
            len(pdf_bytes),
            "bytes",
            "font:",
            font_name,
            "chart_style:",
            data.chart_style,
        )

        return sanitize_response({
            "status":
                "success",

            "filename":
                filename,

            "pdf_base64":
                pdf_base64,

            "font":
                font_name,

            "chart_style":
                data.chart_style,
        })

    except Exception as e:
        print(
            "❌ PDF EXPORT ERROR:",
            str(e)
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=400,
            detail=(
                f"PDF Export Error: "
                f"{str(e)}"
            ),
        )


# =====================================================================
# ODIA CALENDAR
# =====================================================================

@app.get("/api/odia-calendar")
def fetch_odia_calendar(
    date: str = "2026-08-11",
    lat: float = 20.2961,
    lon: float = 85.8245,
    tz: float = 5.5,
):
    try:
        data = get_kohinoor_odia_panchang(
            date_str=date,
            lat=lat,
            lon=lon,
            tz_offset=tz,
        )
        return sanitize_response({
            "status": "success",
            "data": data,
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/odia-calendar-month")
def fetch_odia_calendar_month(
    year: int = 2026,
    month: int = 8,
    lat: float = 20.2961,
    lon: float = 85.8245,
    tz: float = 5.5,
):
    try:
        data = get_kohinoor_month_calendar(
            year=year,
            month=month,
            lat=lat,
            lon=lon,
            tz_offset=tz,
        )

        return sanitize_response({
            "status": "success",
            "data": data,
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# PDF TEXT EXTRACTION
# =====================================================================

@app.post("/api/extract-pdf-text")
async def extract_pdf_page_text(
    pdf_url: Optional[str] = Form(None),
    page_number: int = Form(1),
    pdf: Optional[UploadFile] = File(None),
):
    try:
        pdf_bytes = None

        if pdf is not None:
            pdf_bytes = await pdf.read()

        elif pdf_url:
            if not pdf_url.lower().startswith("http"):
                raise HTTPException(status_code=400, detail="Invalid URL format.")

            res = requests.get(pdf_url, timeout=30)

            if res.status_code != 200:
                raise HTTPException(status_code=400, detail="Cannot download PDF from URL.")

            pdf_bytes = res.content

        else:
            raise HTTPException(status_code=400, detail="No PDF source provided.")

        doc = fitz.open(
            stream=io.BytesIO(pdf_bytes),
            filetype="pdf",
        )

        if page_number - 1 < 0 or page_number - 1 >= len(doc):
            raise HTTPException(status_code=400, detail="Page number out of range.")

        page = doc[page_number - 1]
        raw_text = page.get_text("text").strip()

        if needs_ocr_fallback(raw_text):
            print(f"⚠️ Direct text garbled/missing for page {page_number}. Running OCR...")

            pix = page.get_pixmap(
                matrix=fitz.Matrix(2.0, 2.0)
            )

            jpeg_bytes = pix.tobytes(
                "jpg",
                jpg_quality=75,
            )

            ocr_api_key = os.getenv("OCR_SPACE_API_KEY", "")

            if ocr_api_key:
                ocr_res = requests.post(
                    "https://api.ocr.space/parse/image",
                    files={
                        "page.jpg": (
                            "page.jpg",
                            jpeg_bytes,
                            "image/jpeg",
                        )
                    },
                    data={
                        "apikey": ocr_api_key,
                        "language": "ori",
                        "isOverlayRequired": "false",
                        "OCREngine": "2",
                        "scale": "true",
                    },
                    timeout=35,
                )

                json_data = ocr_res.json()

                if (
                    "ParsedResults" in json_data
                    and json_data["ParsedResults"]
                ):
                    raw_text = (
                        json_data["ParsedResults"][0]
                        .get("ParsedText", "")
                    )

        cleaned_text = clean_unicode_text(raw_text)

        if not cleaned_text:
            cleaned_text = "ଏହି ପୃଷ୍ଠାରେ କୌଣସି ପଢ଼ିବା ଯୋଗ୍ୟ ଲେଖା ମିଳିଲା ନାହିଁ ।"

        return sanitize_response({
            "status": "success",
            "text": cleaned_text,
        })

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(sanitize_response(str(e))),
        )


# =====================================================================
# TTS
# =====================================================================

def get_odia_tts_mp3_bytes(text: str) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    sentences = re.split(
        r"([।,!?\n]+)",
        text,
    )

    chunks = []
    current_chunk = ""

    for s in sentences:
        if len(current_chunk) + len(s) < 150:
            current_chunk += s
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = s

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    if not chunks:
        chunks = [text[:150]]

    combined_mp3_bytes = bytearray()

    for chunk in chunks[:8]:
        encoded_chunk = requests.utils.quote(chunk)

        tts_url = (
            "https://translate.google.com/translate_tts"
            f"?ie=UTF-8&q={encoded_chunk}&tl=or&client=tw-ob"
        )

        res = requests.get(
            tts_url,
            headers=headers,
            timeout=10,
        )

        if res.status_code == 200:
            combined_mp3_bytes.extend(res.content)

    return bytes(combined_mp3_bytes)


@app.post("/api/tts")
def generate_odia_speech(payload: dict):
    try:
        raw_text = payload.get("text", "")

        if not raw_text or not raw_text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        clean_text = clean_unicode_text(raw_text).strip()

        if not clean_text:
            clean_text = raw_text[:300]

        mp3_bytes = get_odia_tts_mp3_bytes(clean_text)

        if not mp3_bytes:
            raise HTTPException(status_code=500, detail="Could not generate Odia audio.")

        audio_base64 = base64.b64encode(
            mp3_bytes
        ).decode("utf-8")

        return sanitize_response({
            "status": "success",
            "audio_base64": audio_base64,
        })

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"TTS Error: {str(e)}",
        )


# =====================================================================
# WORD DETAILS
# =====================================================================

@app.get("/api/word-details")
def get_word_details(word: str):
    try:
        clean_word = word.strip().strip(".,!?:;\"'()[]{}«»<>")

        if not clean_word:
            return {
                "status": "error",
                "meaning": "ଶବ୍ଦ ଚୟନ କରନ୍ତୁ ।",
            }

        meaning_parts = []
        synonyms_list = []

        local_meaning = None

        if clean_word in ODIA_DICT:
            val = ODIA_DICT[clean_word]
            local_meaning = ", ".join(val) if isinstance(val, list) else str(val)

        else:
            lower_w = clean_word.lower()

            for k, v in ODIA_DICT.items():
                if k.lower() == lower_w:
                    local_meaning = ", ".join(v) if isinstance(v, list) else str(v)
                    break

            if not local_meaning:
                suffixes = [
                    "ମାନଙ୍କର", "ମାନଙ୍କୁ", "ମାନଙ୍କ",
                    "ଠାରୁ", "ମାନେ", "ଙ୍କର", "ଙ୍କୁ",
                    "କୁ", "ରେ", "ର", "ଟି", "ଟା", "ଏ", "ଙ୍କ",
                ]

                for suffix in sorted(suffixes, key=len, reverse=True):
                    if clean_word.endswith(suffix) and len(clean_word) > len(suffix):
                        stem = clean_word[:-len(suffix)]

                        if stem in ODIA_DICT:
                            val = ODIA_DICT[stem]
                            local_meaning = (
                                ", ".join(val)
                                if isinstance(val, list)
                                else str(val)
                            ) + f" (ମୂଳ: {stem})"
                            break

        if local_meaning:
            meaning_parts.append(
                f"📖 ଡିକ୍ସନାରୀ ଅର୍ଥ: {local_meaning}"
            )

        is_english = all(
            ord(c) < 128
            for c in clean_word
            if c.isalpha()
        )

        target_lang = "or" if is_english else "en"

        gtx_url = (
            "https://translate.googleapis.com/translate_a/single"
            "?client=gtx&sl=auto"
            f"&tl={target_lang}"
            "&dt=t&dt=bd"
            f"&q={requests.utils.quote(clean_word)}"
        )

        try:
            res_gtx = requests.get(
                gtx_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=6,
            )

            if res_gtx.status_code == 200:
                data_gtx = res_gtx.json()

                primary_trans = ""

                if data_gtx and len(data_gtx) > 0 and data_gtx[0]:
                    for item in data_gtx[0]:
                        if item and len(item) > 0 and item[0]:
                            primary_trans += item[0]

                if (
                    primary_trans
                    and primary_trans.strip().lower() != clean_word.lower()
                ):
                    label = (
                        "🌐 ଓଡ଼ିଆ ଅନୁବାଦ"
                        if is_english
                        else "🌐 English Translation"
                    )

                    meaning_parts.append(
                        f"{label}: {primary_trans.strip()}"
                    )

                if len(data_gtx) > 1 and data_gtx[1]:
                    for pos_group in data_gtx[1]:
                        if len(pos_group) >= 2:
                            pos = pos_group[0]
                            terms = pos_group[1]

                            if terms:
                                synonyms_list.append(
                                    f"• ({pos}): {', '.join(terms[:6])}"
                                )

        except Exception as e_gtx:
            print(f"⚠️ GTX Error: {e_gtx}")

        if is_english:
            try:
                dict_url = (
                    "https://api.dictionaryapi.dev/api/v2/entries/en/"
                    f"{requests.utils.quote(clean_word.lower())}"
                )

                res_dict = requests.get(
                    dict_url,
                    timeout=5,
                )

                if res_dict.status_code == 200:
                    data_dict = res_dict.json()

                    if isinstance(data_dict, list) and data_dict:
                        entry = data_dict[0]

                        for m in entry.get("meanings", []):
                            part_of_speech = m.get("partOfSpeech", "")
                            defs = m.get("definitions", [])
                            syns = m.get("synonyms", [])

                            if defs:
                                def_text = defs[0].get("definition", "")

                                if def_text:
                                    meaning_parts.append(
                                        f"💡 Def ({part_of_speech}): {def_text}"
                                    )

                            if syns:
                                synonyms_list.append(
                                    f"• Synonyms ({part_of_speech}): "
                                    + ", ".join(syns[:5])
                                )

            except Exception as e_dict:
                print(f"⚠️ FreeDictionary Error: {e_dict}")

        if not is_english and not local_meaning:
            try:
                wik_url = (
                    "https://or.wiktionary.org/w/api.php"
                    "?action=query&prop=extracts&exintro&explaintext"
                    f"&titles={requests.utils.quote(clean_word)}"
                    "&format=json"
                )

                res_wik = requests.get(
                    wik_url,
                    headers={"User-Agent": "OdiaPdfReaderApp/1.0"},
                    timeout=5,
                )

                if res_wik.status_code == 200:
                    pages = (
                        res_wik.json()
                        .get("query", {})
                        .get("pages", {})
                    )

                    for p_id, p_data in pages.items():
                        extract = p_data.get("extract", "")

                        if (
                            p_id != "-1"
                            and extract.strip()
                        ):
                            meaning_parts.append(
                                f"📚 Wiktionary: {extract.strip()}"
                            )

            except Exception as e_wik:
                print(f"⚠️ Wiktionary Error: {e_wik}")

        full_result = []

        if meaning_parts:
            full_result.extend(meaning_parts)

        if synonyms_list:
            full_result.append(
                "\n🔄 ସମାର୍ଥକ ଶବ୍ଦ / Synonyms & Alternate Meanings:"
            )
            full_result.extend(synonyms_list)

        if full_result:
            return {
                "status": "success",
                "word": clean_word,
                "meaning": "\n\n".join(full_result),
                "source": "Multi-Engine NLP",
            }

        return {
            "status": "success",
            "word": clean_word,
            "meaning": f"'{clean_word}' - {clean_word}",
            "source": "Literal Fallback",
        }

    except Exception:
        return {
            "status": "error",
            "word": word,
            "meaning": f"ଅର୍ଥ: {word}",
            "source": "Error Safety",
        }
