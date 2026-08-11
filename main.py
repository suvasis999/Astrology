import base64
import io
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from xhtml2pdf import pisa

from engine import calculate_astrology, get_daily_rashifal
from odia_calendar import get_kohinoor_odia_panchang, get_kohinoor_month_calendar

app = FastAPI(title="Vedic Astro Engine API")

# =====================================================================
# CORS MIDDLEWARE SETUP
# =====================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# REQUEST PYDANTIC MODEL
# =====================================================================
class BirthDataRequest(BaseModel):
    name: str = Field("Rahul Sharma", example="Rahul Sharma")
    date: str = Field(..., example="1995-10-16")
    time: str = Field(..., example="07:30:00")
    latitude: float = Field(..., example=28.6139)
    longitude: float = Field(..., example=77.2090)
    tz_offset: float = Field(..., example=5.5)
    ayanamsha: str = Field("LAHIRI", example="LAHIRI")
    lang: str = Field("en", example="or")  # Options: "en", "hi", or "or"


# =====================================================================
# HEALTH CHECK
# =====================================================================
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Vedic Astro Engine Server Running"}


# =====================================================================
# ASTROLOGY KUNDLI CALCULATION ENDPOINT
# =====================================================================
@app.post("/api/calculate")
def calculate_kundli(data: BirthDataRequest):
    try:
        result = calculate_astrology(
            date_str=data.date,
            time_str=data.time,
            latitude=data.latitude,
            longitude=data.longitude,
            tz_offset=data.tz_offset,
            ayanamsha_mode=data.ayanamsha,
            lang=data.lang,
        )

        result["name"] = data.name

        # Get localized Daily Rashifal
        moon_rashi_en = result["planets_en"]["Moon"]["sign"]
        result["rashifal"] = get_daily_rashifal(moon_rashi_en, lang=data.lang)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# HTML TEMPLATE BUILDER FOR PDF
# =====================================================================
def build_pdf_html(result: dict, data: BirthDataRequest) -> str:
    """Generates clean HTML styled for A4 PDF rendering via xhtml2pdf."""

    # Planetary Table Rows
    planet_rows = ""
    for p_name, p in result.get("planets", {}).items():
        planet_rows += f"""
        <tr>
            <td style="padding: 6px; font-weight: bold; color: #b71c1c;">{p_name}</td>
            <td style="padding: 6px;">{p.get('sign', '')}</td>
            <td style="padding: 6px; font-family: monospace; color: #d97706;">{p.get('degree', '')}</td>
            <td style="padding: 6px;">{p.get('nakshatra', '')} ({p.get('pada', '')})</td>
            <td style="padding: 6px;">{p.get('house', '')}</td>
            <td style="padding: 6px;">{p.get('navamsa_sign', '')}</td>
        </tr>
        """

    # Vimshottari Dasha Rows
    dasha_rows = ""
    for d in result.get("dasha", []):
        bg_style = (
            "background-color: #fff7ed; font-weight: bold;"
            if d.get("is_active")
            else ""
        )
        active_tag = " (CURRENT)" if d.get("is_active") else ""
        dasha_rows += f"""
        <tr style="{bg_style}">
            <td style="padding: 6px;">{d.get('lord', '')} Mahadasha{active_tag}</td>
            <td style="padding: 6px;">{d.get('start_date', '')}</td>
            <td style="padding: 6px;">{d.get('end_date', '')}</td>
            <td style="padding: 6px;">{d.get('duration', '')} yrs</td>
        </tr>
        """

    # Panchanga Details
    panchanga = result.get("panchanga", {})

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 15mm;
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                color: #1e293b;
                font-size: 11px;
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #b71c1c;
                padding-bottom: 8px;
                margin-bottom: 15px;
            }}
            .title {{
                font-size: 20px;
                font-weight: bold;
                color: #b71c1c;
                margin: 0;
            }}
            .subtitle {{
                font-size: 10px;
                color: #64748b;
                margin-top: 3px;
            }}
            .info-box {{
                background-color: #fffbeb;
                border: 1px solid #fde68a;
                padding: 10px;
                margin-bottom: 15px;
            }}
            .info-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .info-table td {{
                padding: 4px;
                border: none;
            }}
            .section-header {{
                font-size: 13px;
                font-weight: bold;
                color: #b71c1c;
                border-bottom: 1px solid #fecaca;
                padding-bottom: 3px;
                margin-top: 15px;
                margin-bottom: 8px;
            }}
            table.data-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 12px;
            }}
            table.data-table th {{
                background-color: #b71c1c;
                color: #ffffff;
                padding: 6px;
                text-align: left;
                font-size: 10px;
            }}
            table.data-table td {{
                border-bottom: 1px solid #e2e8f0;
                font-size: 10px;
            }}
            .rashifal-card {{
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                padding: 10px;
                margin-top: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1 class="title">Vedic Horoscope & Kundli Report</h1>
            <div class="subtitle">Generated via Vedic Astro Engine</div>
        </div>

        <div class="info-box">
            <table class="info-table">
                <tr>
                    <td><strong>Name:</strong> {data.name}</td>
                    <td><strong>Date of Birth:</strong> {data.date}</td>
                    <td><strong>Time:</strong> {data.time}</td>
                </tr>
                <tr>
                    <td><strong>Lagna (Rising):</strong> {result.get('lagna', {}).get('sign', '')}</td>
                    <td><strong>Ayanamsha:</strong> {data.ayanamsha}</td>
                    <td><strong>Timezone:</strong> UTC+{data.tz_offset}</td>
                </tr>
            </table>
        </div>

        <div class="section-header">🪐 Planetary Positions</div>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Body</th>
                    <th>Rashi</th>
                    <th>Degree</th>
                    <th>Nakshatra</th>
                    <th>D1 House</th>
                    <th>D9 Sign</th>
                </tr>
            </thead>
            <tbody>
                {planet_rows}
            </tbody>
        </table>

        <div class="section-header">🌕 Panchanga Details</div>
        <table class="data-table">
            <tr>
                <td><strong>Tithi:</strong> {panchanga.get('tithi', '')}</td>
                <td><strong>Vara (Day):</strong> {panchanga.get('vara', '')}</td>
            </tr>
            <tr>
                <td><strong>Nakshatra:</strong> {panchanga.get('nakshatra', '')}</td>
                <td><strong>Yoga:</strong> {panchanga.get('yoga', '')}</td>
            </tr>
        </table>

        <div class="section-header">⏳ Vimshottari Dasha Timeline</div>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Mahadasha Lord</th>
                    <th>Start Date</th>
                    <th>End Date</th>
                    <th>Duration</th>
                </tr>
            </thead>
            <tbody>
                {dasha_rows}
            </tbody>
        </table>

        {"<div class='section-header'>🔮 Daily Rashifal</div><div class='rashifal-card'>" + result.get('rashifal', {}).get('overall', '') + "</div>" if result.get('rashifal') else ""}
    </body>
    </html>
    """
    return html


# =====================================================================
# SERVER-SIDE PDF EXPORT ENDPOINT (BASE64 JSON RESPONSE)
# =====================================================================
@app.post("/api/export-pdf")
def export_kundli_pdf(data: BirthDataRequest):
    try:
        # 1. Compute Kundli Data
        result = calculate_astrology(
            date_str=data.date,
            time_str=data.time,
            latitude=data.latitude,
            longitude=data.longitude,
            tz_offset=data.tz_offset,
            ayanamsha_mode=data.ayanamsha,
            lang=data.lang,
        )
        result["name"] = data.name

        moon_rashi_en = result["planets_en"]["Moon"]["sign"]
        result["rashifal"] = get_daily_rashifal(moon_rashi_en, lang=data.lang)

        # 2. Build HTML
        html_content = build_pdf_html(result, data)

        # 3. Convert HTML to PDF Stream via xhtml2pdf
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)

        if pisa_status.err:
            raise Exception("HTML to PDF conversion failed")

        # 4. Encode PDF bytes to Base64
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
        filename = f"Kundli_{data.name.replace(' ', '_')}.pdf"

        # 5. Return JSON payload for mobile client
        return {"status": "success", "filename": filename, "pdf_base64": pdf_base64}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# KOHINOOR ODIA CALENDAR ENDPOINTS
# =====================================================================
@app.get("/api/odia-calendar")
def fetch_odia_calendar(
    date: str = "2026-08-11",
    lat: float = 20.2961,
    lon: float = 85.8245,
    tz: float = 5.5,
):
    try:
        data = get_kohinoor_odia_panchang(date_str=date, lat=lat, lon=lon, tz_offset=tz)
        return {"status": "success", "data": data}
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
        data = get_kohinoor_month_calendar(year=year, month=month, lat=lat, lon=lon, tz_offset=tz)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))