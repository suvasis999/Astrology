# main.py
import base64
import io
import os
import re
import requests
import traceback
import unicodedata
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from xhtml2pdf import pisa

from weasyprint import HTML
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
    version="2.0.0",
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
        "version": "2.1.0",

        "astro_engine_loaded":
            ASTRO_ENGINE_LOADED,

        "swisseph_installed":
            swe_ok,

        "fitz_installed":
            fitz_ok,

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

        return sanitize_response(result)

    except Exception as e:
        print("❌ Error inside /api/calculate:")
        traceback.print_exc()
        raise HTTPException(
            status_code=400,
            detail=f"Calculation Error: {str(e)}"
        )


# =====================================================================
# PDF HTML
# =====================================================================

def build_pdf_html_(result: dict, data: BirthDataRequest) -> str:
    planet_rows = ""

    for p_name, p in result.get("planets", {}).items():
        planet_rows += f"""
        <tr>
            <td style="padding:6px;font-weight:bold;color:#b71c1c;">{p_name}</td>
            <td style="padding:6px;">{p.get('sign', '')}</td>
            <td style="padding:6px;font-family:monospace;color:#d97706;">{p.get('degree', '')}</td>
            <td style="padding:6px;">{p.get('nakshatra', '')} ({p.get('pada', '')})</td>
            <td style="padding:6px;">{p.get('house', '')}</td>
            <td style="padding:6px;">{p.get('navamsa_sign', '')}</td>
            <td style="padding:6px;">{'Yes' if p.get('is_retrograde') else 'No'}</td>
            <td style="padding:6px;">{'Yes' if p.get('is_combust') else 'No'}</td>
        </tr>
        """

    dasha_rows = ""
    for d in result.get("dasha", []):
        bg_style = "background-color:#fff7ed;font-weight:bold;" if d.get("is_active") else ""
        active_tag = " (CURRENT)" if d.get("is_active") else ""
        dasha_rows += f"""
        <tr style="{bg_style}">
            <td style="padding:6px;">{d.get('lord', '')} Mahadasha{active_tag}</td>
            <td style="padding:6px;">{d.get('start_date', '')}</td>
            <td style="padding:6px;">{d.get('end_date', '')}</td>
            <td style="padding:6px;">{d.get('duration', '')} yrs</td>
        </tr>
        """

    yoga_rows = ""
    for y in result.get("yogas", []):
        yoga_rows += f"""
        <tr>
            <td style="padding:6px;font-weight:bold;">{y.get('name', '')}</td>
            <td style="padding:6px;">{y.get('basis', '')}</td>
        </tr>
        """

    panchanga = result.get("panchanga", {})
    doshas = result.get("doshas", {})

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size:A4; margin:15mm; }}
            body {{ font-family:Helvetica,Arial,sans-serif; color:#1e293b; font-size:11px; }}
            .header {{ text-align:center; border-bottom:2px solid #b71c1c; padding-bottom:8px; margin-bottom:15px; }}
            .title {{ font-size:20px; font-weight:bold; color:#b71c1c; margin:0; }}
            .subtitle {{ font-size:10px; color:#64748b; margin-top:3px; }}
            .info-box {{ background:#fffbeb; border:1px solid #fde68a; padding:10px; margin-bottom:15px; }}
            .section-header {{ font-size:13px; font-weight:bold; color:#b71c1c; border-bottom:1px solid #fecaca; padding-bottom:3px; margin-top:15px; margin-bottom:8px; }}
            table {{ width:100%; border-collapse:collapse; margin-bottom:12px; }}
            th {{ background:#b71c1c; color:white; padding:6px; text-align:left; font-size:10px; }}
            td {{ border-bottom:1px solid #e2e8f0; font-size:10px; }}
            .card {{ background:#f8fafc; border:1px solid #e2e8f0; padding:10px; margin-top:8px; }}
        </style>
    </head>

    <body>

        <div class="header">
            <h1 class="title">Pustak -Vedic Horoscope & Kundli Report</h1>
           
        </div>

        <div class="info-box">
            <table>
                <tr>
                    <td><strong>Name:</strong> {data.name}</td>
                    <td><strong>Date:</strong> {data.date}</td>
                    <td><strong>Time:</strong> {data.time}</td>
                </tr>
                <tr>
                    <td><strong>Lagna:</strong> {result.get('lagna', {}).get('sign', '')}</td>
                    <td><strong>Ayanamsha:</strong> {data.ayanamsha}</td>
                    <td><strong>Timezone:</strong> UTC{data.tz_offset:+}</td>
                </tr>
            </table>
        </div>

        <div class="section-header">Planetary Positions</div>

        <table>
            <thead>
                <tr>
                    <th>Body</th>
                    <th>Rashi</th>
                    <th>Degree</th>
                    <th>Nakshatra</th>
                    <th>House</th>
                    <th>D9</th>
                    <th>Retro</th>
                    <th>Combust</th>
                </tr>
            </thead>
            <tbody>{planet_rows}</tbody>
        </table>

        <div class="section-header">Panchanga</div>

        <table>
            <tr>
                <td><strong>Tithi:</strong> {panchanga.get('tithi', '')}</td>
                <td><strong>Vara:</strong> {panchanga.get('vara', '')}</td>
            </tr>
            <tr>
                <td><strong>Nakshatra:</strong> {panchanga.get('nakshatra', '')}</td>
                <td><strong>Yoga:</strong> {panchanga.get('yoga', '')}</td>
            </tr>
            <tr>
                <td><strong>Karana:</strong> {panchanga.get('karana', '')}</td>
                <td><strong>Paksha:</strong> {panchanga.get('paksha', '')}</td>
            </tr>
        </table>

        <div class="section-header">Vimshottari Mahadasha</div>

        <table>
            <thead>
                <tr>
                    <th>Lord</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>Duration</th>
                </tr>
            </thead>
            <tbody>{dasha_rows}</tbody>
        </table>

        <div class="section-header">Detected Yogas</div>
        <table>
            <thead>
                <tr><th>Yoga</th><th>Basis</th></tr>
            </thead>
            <tbody>{yoga_rows or '<tr><td colspan="2">No configured yoga rule matched.</td></tr>'}</tbody>
        </table>

        <div class="section-header">Dosha / Transit Indicators</div>

        <div class="card">
            <strong>Manglik:</strong> {doshas.get('manglik', {}).get('present', False)}<br/>
            <strong>Kaal Sarp:</strong> {doshas.get('kaal_sarp', {}).get('present', False)}<br/>
            <strong>Pitru Indicator:</strong> {doshas.get('pitru_indicator', {}).get('present', False)}<br/>
            <strong>Sade Sati:</strong> {doshas.get('sade_sati', {}).get('present', False)}
            {(' - ' + str(doshas.get('sade_sati', {}).get('phase'))) if doshas.get('sade_sati', {}).get('phase') else ''}<br/>
            <strong>Dhaiya:</strong> {doshas.get('dhaiya', {}).get('present', False)}
        </div>

        {"<div class='section-header'>Daily Rashifal</div><div class='card'>" + result.get('rashifal', {}).get('overall', '') + "</div>" if result.get('rashifal') else ""}

        <div class="section-header">Calculation Notes</div>
        <div class="card">
            {"<br/>".join(result.get("calculation_notes", []))}
        </div>

    </body>
    </html>
    """

def build_pdf_html(
    result: dict,
    data: BirthDataRequest
) -> str:

    # =========================================================
    # FONT
    # =========================================================

    pdf_font_name, pdf_font_path = get_pdf_font(
        data.lang
    )

    if not os.path.exists(pdf_font_path):

        raise Exception(
            f"PDF font not found: {pdf_font_path}"
        )

    # xhtml2pdf works better with file URI
    pdf_font_uri = (
        "file:///" +
        pdf_font_path
        .replace("\\", "/")
        .lstrip("/")
    )

    # =========================================================
    # HELPERS
    # =========================================================

    def safe(value, default="-"):

        if value is None:
            return default

        if value == "":
            return default

        return str(value)


    def yes_no(value):

        if data.lang == "or":
            return "ହଁ" if value else "ନା"

        return "Yes" if value else "No"


    # =========================================================
    # LAGNA
    # =========================================================

    lagna = result.get(
        "lagna",
        {}
    )


    # =========================================================
    # PLANETS
    # =========================================================

    planet_rows = ""

    for p_name, p in result.get(
        "planets",
        {}
    ).items():

        status = []

        if p.get(
            "is_retrograde"
        ):
            status.append(
                "Retrograde"
            )

        if p.get(
            "is_combust"
        ):
            status.append(
                "Combust"
            )

        if not status:
            status.append(
                "Direct"
            )

        planet_rows += f"""
        <tr>

            <td class="strong">
                {safe(p_name)}
            </td>

            <td>
                {safe(p.get('sign'))}
            </td>

            <td>
                {safe(p.get('degree'))}
            </td>

            <td>
                {safe(p.get('nakshatra'))}
            </td>

            <td>
                {safe(p.get('pada'))}
            </td>

            <td>
                {safe(p.get('house'))}
            </td>

            <td>
                {safe(p.get('navamsa_sign'))}
            </td>

            <td>
                {safe(p.get('dignity'))}
            </td>

            <td>
                {", ".join(status)}
            </td>

        </tr>
        """


    # =========================================================
    # HOUSES
    # =========================================================

    house_rows = ""

    house_lords = result.get(
        "house_lords",
        {}
    )

    for house_no, house in result.get(
        "houses",
        {}
    ).items():

        planets = house.get(
            "planets",
            []
        )

        lord_data = (
            house_lords.get(
                house_no
            )
            or
            house_lords.get(
                str(house_no)
            )
            or
            {}
        )

        house_rows += f"""
        <tr>

            <td>
                {safe(house_no)}
            </td>

            <td>
                {safe(house.get('sign'))}
            </td>

            <td>
                {
                    safe(
                        house.get('lord')
                        or
                        lord_data.get('lord')
                    )
                }
            </td>

            <td>
                {
                    safe(
                        lord_data.get(
                            'lord_house'
                        )
                    )
                }
            </td>

            <td>
                {
                    ", ".join(planets)
                    if planets
                    else "-"
                }
            </td>

        </tr>
        """


    # =========================================================
    # PANCHANGA
    # =========================================================

    panchanga = result.get(
        "panchanga",
        {}
    )


    # =========================================================
    # DASHA
    # =========================================================

    dasha_rows = ""

    for d in result.get(
        "dasha",
        []
    ):

        active = (
            "CURRENT"
            if d.get("is_active")
            else ""
        )

        dasha_rows += f"""
        <tr>

            <td>
                {safe(d.get('lord'))}
            </td>

            <td>
                {safe(d.get('start_date'))}
            </td>

            <td>
                {safe(d.get('end_date'))}
            </td>

            <td>
                {safe(d.get('duration'))}
            </td>

            <td>
                {active}
            </td>

        </tr>
        """


    # =========================================================
    # CURRENT VIMSHOTTARI
    # =========================================================

    vimshottari = result.get(
        "vimshottari",
        {}
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


    # =========================================================
    # YOGAS
    # =========================================================

    yoga_rows = ""

    for yoga in result.get(
        "yogas",
        []
    ):

        yoga_rows += f"""
        <tr>

            <td class="strong">
                {safe(yoga.get('name'))}
            </td>

            <td>
                {safe(yoga.get('basis'))}
            </td>

        </tr>
        """

    if not yoga_rows:

        yoga_rows = """
        <tr>
            <td colspan="2">
                No configured Yoga rule matched.
            </td>
        </tr>
        """


    # =========================================================
    # DOSHAS
    # =========================================================

    doshas = result.get(
        "doshas",
        {}
    )

    dosha_rows = ""

    dosha_config = [
        (
            "manglik",
            "Manglik Dosha"
        ),
        (
            "kaal_sarp",
            "Kaal Sarp"
        ),
        (
            "pitru_indicator",
            "Pitru Dosha"
        ),
        (
            "sade_sati",
            "Sade Sati"
        ),
        (
            "dhaiya",
            "Saturn Dhaiya"
        ),
    ]

    for key, title in dosha_config:

        item = (
            doshas.get(key)
            or {}
        )

        detail = []

        if item.get(
            "mars_house"
        ):
            detail.append(
                f"Mars House: "
                f"{item.get('mars_house')}"
            )

        if item.get(
            "phase"
        ):
            detail.append(
                f"Phase: "
                f"{item.get('phase')}"
            )

        if item.get(
            "saturn_sign"
        ):
            detail.append(
                f"Saturn Sign: "
                f"{item.get('saturn_sign')}"
            )

        if item.get(
            "saturn_from_moon_house"
        ):
            detail.append(
                "Saturn from Moon: "
                f"{item.get('saturn_from_moon_house')}"
            )

        if item.get(
            "basis"
        ):
            detail.append(
                safe(
                    item.get(
                        "basis"
                    )
                )
            )

        if item.get(
            "rule"
        ):
            detail.append(
                safe(
                    item.get(
                        "rule"
                    )
                )
            )

        dosha_rows += f"""
        <tr>

            <td class="strong">
                {title}
            </td>

            <td>
                {
                    "Present"
                    if item.get("present")
                    else "Not Present"
                }
            </td>

            <td>
                {
                    "<br/>".join(detail)
                    if detail
                    else "-"
                }
            </td>

        </tr>
        """


    # =========================================================
    # PLANET STRENGTH
    # =========================================================

    strength = result.get(
        "strength",
        {}
    )

    strength_rows = ""

    for planet, item in (
        strength.get(
            "planets",
            {}
        )
    ).items():

        strength_rows += f"""
        <tr>

            <td class="strong">
                {safe(planet)}
            </td>

            <td>
                {safe(item.get('score'))}/100
            </td>

            <td>
                {safe(item.get('label'))}
            </td>

            <td>
                {safe(item.get('dignity'))}
            </td>

            <td>
                {yes_no(item.get('retrograde'))}
            </td>

            <td>
                {yes_no(item.get('combust'))}
            </td>

        </tr>
        """


    # =========================================================
    # TRANSITS
    # =========================================================

    transit_rows = ""

    for planet, transit in result.get(
        "transits",
        {}
    ).items():

        longitude = transit.get(
            "longitude_raw"
        )

        try:

            longitude_text = (
                f"{float(longitude):.4f}°"
            )

        except Exception:

            longitude_text = safe(
                longitude
            )

        transit_rows += f"""
        <tr>

            <td class="strong">
                {safe(planet)}
            </td>

            <td>
                {
                    safe(
                        transit.get('sign')
                        or
                        transit.get('sign_en')
                    )
                }
            </td>

            <td>
                {longitude_text}
            </td>

            <td>
                {
                    "Retrograde"
                    if transit.get(
                        "is_retrograde"
                    )
                    else "Direct"
                }
            </td>

        </tr>
        """


    # =========================================================
    # VARGA
    # =========================================================

    charts = result.get(
        "charts",
        {}
    )

    varga_html = ""

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

    for chart_name in varga_order:

        chart = charts.get(
            chart_name
        )

        if not chart:
            continue

        varga_rows = ""

        for house_no, house in (
            chart.get(
                "houses",
                {}
            )
        ).items():

            planets = (
                house.get(
                    "planets",
                    []
                )
                or []
            )

            varga_rows += f"""
            <tr>

                <td>
                    {safe(house_no)}
                </td>

                <td>
                    {safe(house.get('sign'))}
                </td>

                <td>
                    {
                        ", ".join(planets)
                        if planets
                        else "-"
                    }
                </td>

            </tr>
            """

        varga_html += f"""
        <div class="sub-title">
            {chart_name}
        </div>

        <div class="mini-info">
            Lagna:
            <strong>
                {
                    safe(
                        chart.get(
                            'lagna_sign'
                        )
                    )
                }
            </strong>
        </div>

        <table>

            <thead>

                <tr>
                    <th>House</th>
                    <th>Rashi</th>
                    <th>Planets</th>
                </tr>

            </thead>

            <tbody>
                {varga_rows}
            </tbody>

        </table>
        """


    # =========================================================
    # RASHIFAL
    # =========================================================

    rashifal = result.get(
        "rashifal",
        {}
    )

    rashifal_html = ""

    if rashifal:

        rashifal_html = f"""
        <table>

            <tr>
                <td class="strong">
                    Overall
                </td>

                <td>
                    {safe(rashifal.get('overall'))}
                </td>
            </tr>

            <tr>
                <td class="strong">
                    Career
                </td>

                <td>
                    {safe(rashifal.get('career'))}
                </td>
            </tr>

            <tr>
                <td class="strong">
                    Finance
                </td>

                <td>
                    {safe(rashifal.get('finance'))}
                </td>
            </tr>

            <tr>
                <td class="strong">
                    Love
                </td>

                <td>
                    {safe(rashifal.get('love'))}
                </td>
            </tr>

            <tr>
                <td class="strong">
                    Health
                </td>

                <td>
                    {safe(rashifal.get('health'))}
                </td>
            </tr>

            <tr>
                <td class="strong">
                    Lucky Number
                </td>

                <td>
                    {safe(rashifal.get('lucky_number'))}
                </td>
            </tr>

            <tr>
                <td class="strong">
                    Lucky Color
                </td>

                <td>
                    {safe(rashifal.get('lucky_color'))}
                </td>
            </tr>

        </table>
        """


    # =========================================================
    # CALCULATION NOTES
    # =========================================================

    notes_html = ""

    for note in result.get(
        "calculation_notes",
        []
    ):

        notes_html += f"""
        <div class="note">
            {safe(note)}
        </div>
        """


    # =========================================================
    # LANGUAGE TITLE
    # =========================================================

    if data.lang == "or":

        report_title = (
            "ବୈଦିକ ଜାତକ ଓ କୁଣ୍ଡଳୀ"
        )

        report_subtitle = (
            " "
            "ବୈଦିକ ଜ୍ୟୋତିଷ ଗଣନା"
        )

    elif data.lang == "hi":

        report_title = (
            "वैदिक जन्म कुंडली"
        )

        report_subtitle = (
            ""
            "वैदिक ज्योतिष गणना"
        )

    else:

        report_title = (
            "Vedic Jatak & Kundli Report"
        )

        report_subtitle = (
            " "
            "Vedic Astrology Calculation"
        )


    # =========================================================
    # HTML
    # =========================================================

    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8"/>

<style>

@font-face {{
    font-family: "{pdf_font_name}";
    src: url("{pdf_font_uri}");
}}


@page {{

    size: A4;

    margin-top: 14mm;
    margin-right: 12mm;
    margin-bottom: 14mm;
    margin-left: 12mm;
}}


html,
body {{

    font-family:
        "{pdf_font_name}";

    color:
        #1e293b;

    font-size:
        10px;

    line-height:
        1.5;
}}


div,
span,
p,
table,
thead,
tbody,
tr,
td,
th,
strong {{

    font-family:
        "{pdf_font_name}";
}}


/* =====================================================
   HEADER
===================================================== */

.header {{

    text-align:
        center;

    border-bottom:
        3px solid #b71c1c;

    padding-bottom:
        10px;

    margin-bottom:
        15px;
}}


.title {{

    font-family:
        "{pdf_font_name}";

    font-size:
        20px;

    color:
        #b71c1c;

    font-weight:
        normal;

    margin:
        0;
}}


.subtitle {{

    font-family:
        "{pdf_font_name}";

    font-size:
        9px;

    color:
        #64748b;

    margin-top:
        5px;
}}


/* =====================================================
   SECTION
===================================================== */

.section-title {{

    font-family:
        "{pdf_font_name}";

    background-color:
        #b71c1c;

    color:
        #ffffff;

    font-size:
        12px;

    font-weight:
        normal;

    padding:
        7px;

    margin-top:
        15px;

    margin-bottom:
        8px;
}}


.sub-title {{

    font-family:
        "{pdf_font_name}";

    color:
        #b71c1c;

    font-size:
        11px;

    font-weight:
        normal;

    border-bottom:
        1px solid #b71c1c;

    padding-bottom:
        4px;

    margin-top:
        12px;

    margin-bottom:
        6px;
}}


/* =====================================================
   TABLE
===================================================== */

table {{

    width:
        100%;

    border-collapse:
        collapse;

    margin-bottom:
        10px;

    font-family:
        "{pdf_font_name}";
}}


th {{

    font-family:
        "{pdf_font_name}";

    background-color:
        #f1f5f9;

    color:
        #0f172a;

    border:
        1px solid #94a3b8;

    padding:
        5px;

    font-size:
        8px;

    font-weight:
        normal;

    text-align:
        left;

    vertical-align:
        middle;
}}


td {{

    font-family:
        "{pdf_font_name}";

    color:
        #334155;

    border:
        1px solid #cbd5e1;

    padding:
        5px;

    font-size:
        8px;

    vertical-align:
        top;
}}


.strong {{

    font-family:
        "{pdf_font_name}";

    color:
        #0f172a;

    font-weight:
        normal;
}}


/* =====================================================
   BIRTH INFO
===================================================== */

.birth-box {{

    background-color:
        #fffbeb;

    border:
        1px solid #fde68a;

    padding:
        8px;

    margin-bottom:
        12px;
}}


.mini-info {{

    font-family:
        "{pdf_font_name}";

    background-color:
        #f8fafc;

    border:
        1px solid #e2e8f0;

    padding:
        6px;

    margin-bottom:
        6px;
}}


.note {{

    font-family:
        "{pdf_font_name}";

    background-color:
        #eff6ff;

    border:
        1px solid #bfdbfe;

    padding:
        6px;

    margin-bottom:
        4px;

    color:
        #475569;
}}


.page-break {{

    page-break-before:
        always;
}}

</style>

</head>


<body>


<!-- =====================================================
     HEADER
===================================================== -->

<div class="header">

    <div class="title">
        {report_title}
    </div>

    <div class="subtitle">
        {report_subtitle}
    </div>

</div>


<!-- =====================================================
     BIRTH DETAILS
===================================================== -->

<div class="section-title">
    Birth Details / ଜନ୍ମ ବିବରଣୀ
</div>


<div class="birth-box">

<table>

<tr>

    <td class="strong">
        Name
    </td>

    <td>
        {safe(data.name)}
    </td>

    <td class="strong">
        Date
    </td>

    <td>
        {safe(data.date)}
    </td>

</tr>


<tr>

    <td class="strong">
        Time
    </td>

    <td>
        {safe(data.time)}
    </td>

    <td class="strong">
        Timezone
    </td>

    <td>
        UTC {data.tz_offset:+}
    </td>

</tr>


<tr>

    <td class="strong">
        Latitude
    </td>

    <td>
        {safe(data.latitude)}
    </td>

    <td class="strong">
        Longitude
    </td>

    <td>
        {safe(data.longitude)}
    </td>

</tr>


<tr>

    <td class="strong">
        Ayanamsha
    </td>

    <td>
        {
            safe(
                result.get(
                    'ayanamsha_mode'
                )
                or data.ayanamsha
            )
        }
    </td>

    <td class="strong">
        Ayanamsha Value
    </td>

    <td>
        {
            safe(
                result.get(
                    'ayanamsha_value'
                )
            )
        }
    </td>

</tr>


<tr>

    <td class="strong">
        Node
    </td>

    <td>
        {
            safe(
                result.get(
                    'node_type'
                )
                or data.node_type
            )
        }
    </td>

    <td class="strong">
        Lagna
    </td>

    <td>
        {safe(lagna.get('sign'))}
    </td>

</tr>

</table>

</div>


<!-- =====================================================
     LAGNA
===================================================== -->

<div class="section-title">
    Lagna / ଲଗ୍ନ
</div>

<table>

<thead>

<tr>

    <th>Rashi</th>
    <th>Degree</th>
    <th>Nakshatra</th>
    <th>Pada</th>
    <th>Navamsa</th>

</tr>

</thead>


<tbody>

<tr>

    <td>
        {safe(lagna.get('sign'))}
    </td>

    <td>
        {safe(lagna.get('degree'))}
    </td>

    <td>
        {safe(lagna.get('nakshatra'))}
    </td>

    <td>
        {safe(lagna.get('pada'))}
    </td>

    <td>
        {safe(lagna.get('navamsa_sign'))}
    </td>

</tr>

</tbody>

</table>


<!-- =====================================================
     PLANETS
===================================================== -->

<div class="section-title">
    Planetary Positions / ଗ୍ରହ ସ୍ଥିତି
</div>

<table>

<thead>

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

</thead>

<tbody>

{planet_rows}

</tbody>

</table>


<!-- =====================================================
     HOUSES
===================================================== -->

<div class="section-title">
    12 Bhava / ଦ୍ୱାଦଶ ଭାବ
</div>

<table>

<thead>

<tr>

    <th>House</th>
    <th>Rashi</th>
    <th>Lord</th>
    <th>Lord House</th>
    <th>Planets</th>

</tr>

</thead>

<tbody>

{house_rows}

</tbody>

</table>


<!-- =====================================================
     PANCHANGA
===================================================== -->

<div class="section-title">
    Panchanga / ପଞ୍ଚାଙ୍ଗ
</div>

<table>

<tr>
    <td class="strong">Tithi</td>
    <td>{safe(panchanga.get('tithi'))}</td>
</tr>

<tr>
    <td class="strong">Paksha</td>
    <td>{safe(panchanga.get('paksha'))}</td>
</tr>

<tr>
    <td class="strong">Vara</td>
    <td>{safe(panchanga.get('vara'))}</td>
</tr>

<tr>
    <td class="strong">Nakshatra</td>
    <td>{safe(panchanga.get('nakshatra'))}</td>
</tr>

<tr>
    <td class="strong">Yoga</td>
    <td>{safe(panchanga.get('yoga'))}</td>
</tr>

<tr>
    <td class="strong">Karana</td>
    <td>{safe(panchanga.get('karana'))}</td>
</tr>

</table>


<!-- =====================================================
     CURRENT DASHA
===================================================== -->

<div class="section-title">
    Current Vimshottari Dasha / ବର୍ତ୍ତମାନ ଦଶା
</div>

<table>

<thead>

<tr>

    <th>Level</th>
    <th>Lord</th>
    <th>Start</th>
    <th>End</th>

</tr>

</thead>

<tbody>

<tr>

    <td>Mahadasha</td>

    <td>
        {safe(current_md.get('lord'))}
    </td>

    <td>
        {safe(current_md.get('start_date'))}
    </td>

    <td>
        {safe(current_md.get('end_date'))}
    </td>

</tr>


<tr>

    <td>Antardasha</td>

    <td>
        {safe(current_ad.get('lord'))}
    </td>

    <td>
        {safe(current_ad.get('start_date'))}
    </td>

    <td>
        {safe(current_ad.get('end_date'))}
    </td>

</tr>


<tr>

    <td>Pratyantardasha</td>

    <td>
        {safe(current_pd.get('lord'))}
    </td>

    <td>
        {safe(current_pd.get('start_date'))}
    </td>

    <td>
        {safe(current_pd.get('end_date'))}
    </td>

</tr>

</tbody>

</table>


<!-- =====================================================
     DASHA TIMELINE
===================================================== -->

<div class="sub-title">
    Mahadasha Timeline
</div>

<table>

<thead>

<tr>

    <th>Lord</th>
    <th>Start</th>
    <th>End</th>
    <th>Years</th>
    <th>Status</th>

</tr>

</thead>

<tbody>

{dasha_rows}

</tbody>

</table>


<!-- =====================================================
     YOGAS
===================================================== -->

<div class="section-title">
    Yogas / ଯୋଗ
</div>

<table>

<thead>

<tr>
    <th>Yoga</th>
    <th>Basis</th>
</tr>

</thead>

<tbody>

{yoga_rows}

</tbody>

</table>


<!-- =====================================================
     DOSHAS
===================================================== -->

<div class="section-title">
    Dosha Analysis / ଦୋଷ ବିଶ୍ଳେଷଣ
</div>

<table>

<thead>

<tr>

    <th>Dosha</th>
    <th>Status</th>
    <th>Details</th>

</tr>

</thead>

<tbody>

{dosha_rows}

</tbody>

</table>


<!-- =====================================================
     STRENGTH
===================================================== -->

<div class="section-title">
    Planet Strength / ଗ୍ରହ ବଳ
</div>

<div class="mini-info">

    {
        safe(
            strength.get(
                'note'
            )
        )
    }

</div>

<table>

<thead>

<tr>

    <th>Planet</th>
    <th>Score</th>
    <th>Strength</th>
    <th>Dignity</th>
    <th>Retrograde</th>
    <th>Combust</th>

</tr>

</thead>

<tbody>

{strength_rows}

</tbody>

</table>


<!-- =====================================================
     TRANSIT
===================================================== -->

<div class="section-title">
    Gochar / ଗୋଚର
</div>

<table>

<thead>

<tr>

    <th>Planet</th>
    <th>Rashi</th>
    <th>Longitude</th>
    <th>Motion</th>

</tr>

</thead>

<tbody>

{transit_rows}

</tbody>

</table>


<!-- =====================================================
     VARGA
===================================================== -->

<div class="page-break"></div>

<div class="section-title">
    Varga Charts / ବର୍ଗ ଚକ୍ର
</div>

{varga_html}


<!-- =====================================================
     RASHIFAL
===================================================== -->

<div class="section-title">
    Daily Rashifal / ଦୈନିକ ରାଶିଫଳ
</div>

{rashifal_html}


<!-- =====================================================
     NOTES
===================================================== -->

<div class="section-title">
    Calculation Notes
</div>

{notes_html}


</body>

</html>
"""
# =====================================================================
# PDF EXPORT
# =====================================================================

@app.post("/api/export-pdfdd")
def export_kundli_pdfdd(
    data: BirthDataRequest
):

    try:

        if not ASTRO_ENGINE_LOADED:

            raise Exception(
                "Astrology calculation "
                "engine is not loaded."
            )


        # -----------------------------------------------------
        # Check font before doing calculation
        # -----------------------------------------------------

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


        # -----------------------------------------------------
        # Astrology calculation
        # -----------------------------------------------------

        result = calculate_astrology(

            date_str=
                data.date,

            time_str=
                data.time,

            latitude=
                data.latitude,

            longitude=
                data.longitude,

            tz_offset=
                data.tz_offset,

            ayanamsha_mode=
                data.ayanamsha,

            lang=
                data.lang,

            node_type=
                data.node_type,
        )


        result["name"] = (
            data.name
        )


        # -----------------------------------------------------
        # Rashifal
        # -----------------------------------------------------

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

                lang=
                    data.lang,
            )
        )


        # -----------------------------------------------------
        # Generate HTML
        # -----------------------------------------------------

        html_content = (
            build_pdf_html(
                result,
                data
            )
        )


        # -----------------------------------------------------
        # HTML -> PDF
        # -----------------------------------------------------

        pdf_buffer = (
            io.BytesIO()
        )


        pisa_status = (
            pisa.CreatePDF(

                src=
                    io.StringIO(
                        html_content
                    ),

                dest=
                    pdf_buffer,

                encoding=
                    "UTF-8",
            )
        )


        if pisa_status.err:

            raise Exception(
                "PDF generation failed. "
                "xhtml2pdf returned an error."
            )


        pdf_bytes = (
            pdf_buffer
            .getvalue()
        )


        if not pdf_bytes:

            raise Exception(
                "Generated PDF is empty."
            )


        # -----------------------------------------------------
        # BASE64
        # -----------------------------------------------------

        pdf_base64 = (
            base64
            .b64encode(
                pdf_bytes
            )
            .decode(
                "utf-8"
            )
        )


        # -----------------------------------------------------
        # Filename
        # -----------------------------------------------------

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
            font_name
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


@app.post("/api/export-pdf")
def export_kundli_pdf(
    data: BirthDataRequest
):
    try:

        if not ASTRO_ENGINE_LOADED:
            raise Exception(
                "Astrology calculation engine is not loaded."
            )

        font_name, font_path = get_pdf_font(
            data.lang
        )

        if not os.path.exists(font_path):
            raise Exception(
                f"Required PDF font is missing: {font_path}"
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

        result["name"] = data.name

        moon_rashi_en = (
            result
            .get("planets_en", {})
            .get("Moon", {})
            .get("sign_en", "Aries")
        )

        result["rashifal"] = get_daily_rashifal(
            moon_rashi_en,
            lang=data.lang,
        )

        html_content = build_pdf_html(
            result,
            data
        )

        # -----------------------------------------
        # IMPORTANT:
        # Use WeasyPrint instead of xhtml2pdf
        # -----------------------------------------

        pdf_bytes = HTML(
            string=html_content,
            base_url=BASE_DIR
        ).write_pdf()

        if not pdf_bytes:
            raise Exception(
                "Generated PDF is empty."
            )

        pdf_base64 = base64.b64encode(
            pdf_bytes
        ).decode("utf-8")

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

        return {
            "status": "success",
            "filename": filename,
            "pdf_base64": pdf_base64,
            "font": font_name,
        }

    except Exception as e:

        traceback.print_exc()

        raise HTTPException(
            status_code=400,
            detail=f"PDF Export Error: {str(e)}"
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
