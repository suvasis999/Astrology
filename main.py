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
import fitz  # PyMuPDF

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
        "version": "2.0.0",
        "astro_engine_loaded": ASTRO_ENGINE_LOADED,
        "swisseph_installed": swe_ok,
        "fitz_installed": fitz_ok,
        "dictionary_entries": len(ODIA_DICT),
        "message": "Vedic Astro Engine & Odia Reader Active",
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
            <h1 class="title">Vedic Horoscope & Kundli Report</h1>
            <div class="subtitle">Generated via Swiss Ephemeris based Vedic Astro Engine</div>
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

def build_pdf_html(result: dict, data: BirthDataRequest) -> str:

    # =========================================================
    # COMMON HELPERS
    # =========================================================

    def yes_no(value):
        return "Yes" if value else "No"

    def safe(value, default="-"):
        if value is None or value == "":
            return default
        return str(value)

    # =========================================================
    # PLANET TABLE
    # =========================================================

    planet_rows = ""

    for p_name, p in result.get("planets", {}).items():

        status = []

        if p.get("is_retrograde"):
            status.append("Retrograde")

        if p.get("is_combust"):
            status.append("Combust")

        if not status:
            status.append("Direct")

        planet_rows += f"""
        <tr>
            <td>{safe(p_name)}</td>

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
    # HOUSE TABLE
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

        lord_info = (
            house_lords.get(house_no)
            or
            house_lords.get(str(house_no))
            or
            {}
        )

        house_rows += f"""
        <tr>
            <td>
                {house_no}
            </td>

            <td>
                {safe(house.get('sign'))}
            </td>

            <td>
                {safe(
                    house.get('lord')
                    or
                    lord_info.get('lord')
                )}
            </td>

            <td>
                {safe(
                    lord_info.get(
                        'lord_house'
                    )
                )}
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

    panchanga_rows = f"""
        <tr>
            <td>Tithi</td>
            <td>{safe(panchanga.get('tithi'))}</td>
        </tr>

        <tr>
            <td>Paksha</td>
            <td>{safe(panchanga.get('paksha'))}</td>
        </tr>

        <tr>
            <td>Vara</td>
            <td>{safe(panchanga.get('vara'))}</td>
        </tr>

        <tr>
            <td>Nakshatra</td>
            <td>{safe(panchanga.get('nakshatra'))}</td>
        </tr>

        <tr>
            <td>Yoga</td>
            <td>{safe(panchanga.get('yoga'))}</td>
        </tr>

        <tr>
            <td>Karana</td>
            <td>{safe(panchanga.get('karana'))}</td>
        </tr>
    """


    # =========================================================
    # MAHADASHA TABLE
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
    # CURRENT DASHA
    # =========================================================

    vim = result.get(
        "vimshottari",
        {}
    )

    current_md = (
        vim.get(
            "current_mahadasha"
        )
        or
        {}
    )

    current_ad = (
        vim.get(
            "current_antardasha"
        )
        or
        {}
    )

    current_pd = (
        vim.get(
            "current_pratyantardasha"
        )
        or
        {}
    )

    current_dasha_html = f"""
    <table>
        <tr>
            <th>Level</th>
            <th>Lord</th>
            <th>Start</th>
            <th>End</th>
        </tr>

        <tr>
            <td>Mahadasha</td>
            <td>{safe(current_md.get('lord'))}</td>
            <td>{safe(current_md.get('start_date'))}</td>
            <td>{safe(current_md.get('end_date'))}</td>
        </tr>

        <tr>
            <td>Antardasha</td>
            <td>{safe(current_ad.get('lord'))}</td>
            <td>{safe(current_ad.get('start_date'))}</td>
            <td>{safe(current_ad.get('end_date'))}</td>
        </tr>

        <tr>
            <td>Pratyantardasha</td>
            <td>{safe(current_pd.get('lord'))}</td>
            <td>{safe(current_pd.get('start_date'))}</td>
            <td>{safe(current_pd.get('end_date'))}</td>
        </tr>
    </table>
    """


    # =========================================================
    # YOGAS
    # =========================================================

    yoga_rows = ""

    yogas = result.get(
        "yogas",
        []
    )

    if yogas:

        for yoga in yogas:

            yoga_rows += f"""
            <tr>
                <td>
                    {safe(yoga.get('name'))}
                </td>

                <td>
                    {safe(yoga.get('basis'))}
                </td>
            </tr>
            """

    else:

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

    dosha_labels = {
        "manglik":
            "Manglik Dosha",

        "kaal_sarp":
            "Kaal Sarp",

        "pitru_indicator":
            "Pitru Dosha Indicator",

        "sade_sati":
            "Sade Sati",

        "dhaiya":
            "Saturn Dhaiya",
    }

    for key, label in dosha_labels.items():

        item = (
            doshas.get(key)
            or
            {}
        )

        details = []

        if item.get(
            "mars_house"
        ):
            details.append(
                f"House: {item.get('mars_house')}"
            )

        if item.get(
            "phase"
        ):
            details.append(
                f"Phase: {item.get('phase')}"
            )

        if item.get(
            "saturn_sign"
        ):
            details.append(
                f"Saturn: {item.get('saturn_sign')}"
            )

        if item.get(
            "basis"
        ):
            details.append(
                str(
                    item.get("basis")
                )
            )

        if item.get(
            "rule"
        ):
            details.append(
                str(
                    item.get("rule")
                )
            )

        dosha_rows += f"""
        <tr>
            <td>
                {label}
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
                    "<br/>".join(details)
                    if details
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
            <td>
                {planet}
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
    # CURRENT TRANSITS
    # =========================================================

    transit_rows = ""

    for planet, transit in (
        result.get(
            "transits",
            {}
        )
    ).items():

        longitude = transit.get(
            "longitude_raw",
            0
        )

        try:
            longitude = (
                f"{float(longitude):.4f}°"
            )

        except Exception:
            longitude = safe(
                longitude
            )

        transit_rows += f"""
        <tr>
            <td>
                {planet}
            </td>

            <td>
                {safe(
                    transit.get('sign')
                    or
                    transit.get('sign_en')
                )}
            </td>

            <td>
                {longitude}
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
    # VARGA CHART DETAILS
    # =========================================================

    varga_html = ""

    charts = result.get(
        "charts",
        {}
    )

    preferred_order = [
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

    for chart_name in preferred_order:

        chart = charts.get(
            chart_name
        )

        if not chart:
            continue

        rows = ""

        for house_no, house in (
            chart.get(
                "houses",
                {}
            )
        ).items():

            planets = house.get(
                "planets",
                []
            )

            rows += f"""
            <tr>
                <td>
                    {house_no}
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
        <div class="subsection-title">
            {chart_name}
        </div>

        <div class="small-info">
            Lagna:
            <strong>
                {safe(chart.get('lagna_sign'))}
            </strong>
        </div>

        <table>
            <tr>
                <th>House</th>
                <th>Rashi</th>
                <th>Planets</th>
            </tr>

            {rows}

        </table>
        """


    # =========================================================
    # DAILY RASHIFAL
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
                <td>
                    <strong>
                        Overall
                    </strong>
                </td>

                <td>
                    {safe(rashifal.get('overall'))}
                </td>
            </tr>

            <tr>
                <td>
                    <strong>
                        Career
                    </strong>
                </td>

                <td>
                    {safe(rashifal.get('career'))}
                </td>
            </tr>

            <tr>
                <td>
                    <strong>
                        Finance
                    </strong>
                </td>

                <td>
                    {safe(rashifal.get('finance'))}
                </td>
            </tr>

            <tr>
                <td>
                    <strong>
                        Love
                    </strong>
                </td>

                <td>
                    {safe(rashifal.get('love'))}
                </td>
            </tr>

            <tr>
                <td>
                    <strong>
                        Health
                    </strong>
                </td>

                <td>
                    {safe(rashifal.get('health'))}
                </td>
            </tr>

            <tr>
                <td>
                    <strong>
                        Lucky Number
                    </strong>
                </td>

                <td>
                    {safe(rashifal.get('lucky_number'))}
                </td>
            </tr>

            <tr>
                <td>
                    <strong>
                        Lucky Color
                    </strong>
                </td>

                <td>
                    {safe(rashifal.get('lucky_color'))}
                </td>
            </tr>
        </table>
        """


    # =========================================================
    # NOTES
    # =========================================================

    notes_html = ""

    for note in result.get(
        "calculation_notes",
        []
    ):

        notes_html += (
            f"<div class='note'>• {note}</div>"
        )


    # =========================================================
    # COMPLETE PDF HTML
    # =========================================================

    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<style>

@page {{
    size: A4;
    margin: 14mm;
}}

body {{
    font-family:
        Helvetica,
        Arial,
        sans-serif;

    color: #1e293b;

    font-size: 10px;

    line-height: 1.45;
}}


/* ======================================
   HEADER
====================================== */

.header {{
    text-align: center;

    border-bottom:
        3px solid #b71c1c;

    padding-bottom:
        10px;

    margin-bottom:
        14px;
}}

.main-title {{
    font-size:
        21px;

    font-weight:
        bold;

    color:
        #b71c1c;

    margin:
        0;
}}

.subtitle {{
    color:
        #64748b;

    font-size:
        9px;

    margin-top:
        4px;
}}


/* ======================================
   SECTION HEADINGS
====================================== */

.section-title {{
    background-color:
        #b71c1c;

    color:
        #ffffff;

    font-size:
        13px;

    font-weight:
        bold;

    padding:
        7px;

    margin-top:
        16px;

    margin-bottom:
        8px;
}}

.subsection-title {{
    color:
        #b71c1c;

    border-bottom:
        1px solid #b71c1c;

    font-size:
        11px;

    font-weight:
        bold;

    padding-bottom:
        3px;

    margin-top:
        12px;

    margin-bottom:
        6px;
}}


/* ======================================
   TABLES
====================================== */

table {{
    width:
        100%;

    border-collapse:
        collapse;

    margin-bottom:
        10px;
}}

th {{
    border:
        1px solid #94a3b8;

    background-color:
        #f1f5f9;

    color:
        #0f172a;

    font-weight:
        bold;

    padding:
        5px;

    font-size:
        8px;

    text-align:
        left;
}}

td {{
    border:
        1px solid #cbd5e1;

    padding:
        5px;

    vertical-align:
        top;

    font-size:
        8px;
}}


/* ======================================
   INFO BOX
====================================== */

.birth-box {{
    background-color:
        #fffbeb;

    border:
        1px solid #fde68a;

    padding:
        10px;

    margin-bottom:
        12px;
}}

.small-info {{
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
    background-color:
        #eff6ff;

    border-bottom:
        1px solid #bfdbfe;

    padding:
        5px;

    color:
        #475569;

    font-size:
        8px;
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

    <div class="main-title">
        Vedic Jatak / Kundli Report
    </div>

    <div class="subtitle">
        Swiss Ephemeris Based Astrology Calculation
    </div>

</div>


<!-- =====================================================
     BIRTH DETAILS
===================================================== -->

<div class="section-title">
    Birth Details
</div>

<div class="birth-box">

<table>

<tr>

<td>
<strong>Name</strong>
</td>

<td>
{safe(data.name)}
</td>

<td>
<strong>Date</strong>
</td>

<td>
{safe(data.date)}
</td>

</tr>


<tr>

<td>
<strong>Time</strong>
</td>

<td>
{safe(data.time)}
</td>

<td>
<strong>Timezone</strong>
</td>

<td>
UTC {data.tz_offset:+}
</td>

</tr>


<tr>

<td>
<strong>Latitude</strong>
</td>

<td>
{safe(data.latitude)}
</td>

<td>
<strong>Longitude</strong>
</td>

<td>
{safe(data.longitude)}
</td>

</tr>


<tr>

<td>
<strong>Ayanamsha</strong>
</td>

<td>
{safe(result.get('ayanamsha_mode'))}
</td>

<td>
<strong>Ayanamsha Value</strong>
</td>

<td>
{safe(result.get('ayanamsha_value'))}
</td>

</tr>


<tr>

<td>
<strong>Node Type</strong>
</td>

<td>
{safe(result.get('node_type'))}
</td>

<td>
<strong>Lagna</strong>
</td>

<td>
{safe(result.get('lagna', {}).get('sign'))}
</td>

</tr>

</table>

</div>


<!-- =====================================================
     LAGNA
===================================================== -->

<div class="section-title">
    Lagna Details
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

<td>
{safe(result.get('lagna', {}).get('sign'))}
</td>

<td>
{safe(result.get('lagna', {}).get('degree'))}
</td>

<td>
{safe(result.get('lagna', {}).get('nakshatra'))}
</td>

<td>
{safe(result.get('lagna', {}).get('pada'))}
</td>

<td>
{safe(result.get('lagna', {}).get('navamsa_sign'))}
</td>

</tr>

</table>


<!-- =====================================================
     PLANETS
===================================================== -->

<div class="section-title">
    Planetary Positions
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


<!-- =====================================================
     HOUSES
===================================================== -->

<div class="section-title">
    12 Bhava / House Details
</div>

<table>

<tr>
<th>House</th>
<th>Rashi</th>
<th>Lord</th>
<th>Lord Placed</th>
<th>Planets</th>
</tr>

{house_rows}

</table>


<!-- =====================================================
     PANCHANGA
===================================================== -->

<div class="section-title">
    Panchanga
</div>

<table>

<tr>
<th>Item</th>
<th>Details</th>
</tr>

{panchanga_rows}

</table>


<!-- =====================================================
     DASHA
===================================================== -->

<div class="section-title">
    Current Vimshottari Period
</div>

{current_dasha_html}


<div class="subsection-title">
    Mahadasha Timeline
</div>

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


<!-- =====================================================
     YOGAS
===================================================== -->

<div class="section-title">
    Yogas
</div>

<table>

<tr>
<th>Yoga</th>
<th>Calculation Basis</th>
</tr>

{yoga_rows}

</table>


<!-- =====================================================
     DOSHAS
===================================================== -->

<div class="section-title">
    Dosha Analysis
</div>

<table>

<tr>
<th>Dosha</th>
<th>Status</th>
<th>Details</th>
</tr>

{dosha_rows}

</table>


<!-- =====================================================
     PLANET STRENGTH
===================================================== -->

<div class="section-title">
    Planet Strength
</div>

<div class="small-info">
{safe(strength.get('note'))}
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


<!-- =====================================================
     TRANSITS
===================================================== -->

<div class="section-title">
    Current Gochar / Transit
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


<!-- =====================================================
     VARGA
===================================================== -->

<div class="page-break"></div>

<div class="section-title">
    Divisional / Varga Charts
</div>

{varga_html}


<!-- =====================================================
     RASHIFAL
===================================================== -->

<div class="section-title">
    Daily Rashifal
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

@app.post("/api/export-pdf")
def export_kundli_pdf(data: BirthDataRequest):
    try:
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

        html_content = build_pdf_html(result, data)

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            io.StringIO(html_content),
            dest=pdf_buffer,
        )

        if pisa_status.err:
            raise Exception("HTML to PDF conversion failed")

        pdf_base64 = base64.b64encode(
            pdf_buffer.getvalue()
        ).decode("utf-8")

        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", data.name).strip("_")
        filename = f"Kundli_{safe_name or 'Report'}.pdf"

        return sanitize_response({
            "status": "success",
            "filename": filename,
            "pdf_base64": pdf_base64,
        })

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


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
