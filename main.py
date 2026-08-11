import base64
import io
import re
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from xhtml2pdf import pisa

# Safe gTTS import to prevent server boot failure
try:
    from gTTS import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    gTTS = None
    GTTS_AVAILABLE = False
    print("⚠️ gTTS package not found. Text-to-speech feature will return fallback error.")

from engine import calculate_astrology, get_daily_rashifal
from odia_calendar import get_kohinoor_odia_panchang, get_kohinoor_month_calendar

# =====================================================================
# ODIA NLP DICTIONARY ENGINE (Loaded from OdiaNLP/dictionary GitHub)
# =====================================================================
ODIA_DICT = {}

def load_odianlp_dictionary():
    """Downloads & caches OdiaNLP dictionary from GitHub at startup."""
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
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict):
                    ODIA_DICT.update(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            w = item.get("word") or item.get("odia")
                            m = item.get("meaning") or item.get("english")
                            if w and m:
                                ODIA_DICT[w.strip()] = m
                print(f"✅ Loaded {len(ODIA_DICT)} entries from OdiaNLP dictionary.")
                return
        except Exception as e:
            print(f"⚠️ Failed source {url}: {e}")
            continue
            
    print("⚠️ OdiaNLP dictionary offline fallback enabled.")


# =====================================================================
# FASTAPI LIFESPAN MANAGEMENT
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load dictionary safely
    try:
        load_odianlp_dictionary()
    except Exception as e:
        print(f"⚠️ Dictionary startup warning: {e}")
    yield


app = FastAPI(title="Vedic Astro Engine & Odia NLP API", lifespan=lifespan)

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
    lang: str = Field("en", example="or")


# =====================================================================
# HEALTH CHECK
# =====================================================================
@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Vedic Astro Engine Server Running",
        "gtts_enabled": GTTS_AVAILABLE,
        "dictionary_entries": len(ODIA_DICT),
    }


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
        moon_rashi_en = result["planets_en"]["Moon"]["sign"]
        result["rashifal"] = get_daily_rashifal(moon_rashi_en, lang=data.lang)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# HTML TEMPLATE BUILDER FOR PDF
# =====================================================================
def build_pdf_html(result: dict, data: BirthDataRequest) -> str:
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

    dasha_rows = ""
    for d in result.get("dasha", []):
        bg_style = "background-color: #fff7ed; font-weight: bold;" if d.get("is_active") else ""
        active_tag = " (CURRENT)" if d.get("is_active") else ""
        dasha_rows += f"""
        <tr style="{bg_style}">
            <td style="padding: 6px;">{d.get('lord', '')} Mahadasha{active_tag}</td>
            <td style="padding: 6px;">{d.get('start_date', '')}</td>
            <td style="padding: 6px;">{d.get('end_date', '')}</td>
            <td style="padding: 6px;">{d.get('duration', '')} yrs</td>
        </tr>
        """

    panchanga = result.get("panchanga", {})

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4; margin: 15mm; }}
            body {{ font-family: Helvetica, Arial, sans-serif; color: #1e293b; font-size: 11px; }}
            .header {{ text-align: center; border-bottom: 2px solid #b71c1c; padding-bottom: 8px; margin-bottom: 15px; }}
            .title {{ font-size: 20px; font-weight: bold; color: #b71c1c; margin: 0; }}
            .subtitle {{ font-size: 10px; color: #64748b; margin-top: 3px; }}
            .info-box {{ background-color: #fffbeb; border: 1px solid #fde68a; padding: 10px; margin-bottom: 15px; }}
            .info-table {{ width: 100%; border-collapse: collapse; }}
            .info-table td {{ padding: 4px; border: none; }}
            .section-header {{ font-size: 13px; font-weight: bold; color: #b71c1c; border-bottom: 1px solid #fecaca; padding-bottom: 3px; margin-top: 15px; margin-bottom: 8px; }}
            table.data-table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
            table.data-table th {{ background-color: #b71c1c; color: #ffffff; padding: 6px; text-align: left; font-size: 10px; }}
            table.data-table td {{ border-bottom: 1px solid #e2e8f0; font-size: 10px; }}
            .rashifal-card {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; margin-top: 8px; }}
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

        html_content = build_pdf_html(result, data)

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)

        if pisa_status.err:
            raise Exception("HTML to PDF conversion failed")

        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
        filename = f"Kundli_{data.name.replace(' ', '_')}.pdf"

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


# =====================================================================
# ODIA NLP DICTIONARY LOOKUP ENDPOINT
# =====================================================================
@app.get("/api/word-details")
def get_word_details(word: str):
    """Looks up Odia word meanings in OdiaNLP dictionary with Wiktionary fallback."""
    try:
        clean_word = word.strip()
        if not clean_word:
            return {"status": "error", "meaning": "ଶବ୍ଦ ଚୟନ କରନ୍ତୁ ।"}

        # 1. Exact Match in OdiaNLP Dictionary
        if clean_word in ODIA_DICT:
            meaning = ODIA_DICT[clean_word]
            if isinstance(meaning, list):
                meaning = ", ".join(meaning)
            return {
                "status": "success",
                "word": clean_word,
                "meaning": meaning,
                "source": "OdiaNLP"
            }

        # 2. Fuzzy/Substring Search in OdiaNLP Dictionary
        for odia_key, val in ODIA_DICT.items():
            if clean_word in odia_key or odia_key in clean_word:
                meaning = val if isinstance(val, str) else ", ".join(val)
                return {
                    "status": "success",
                    "word": clean_word,
                    "meaning": f"{meaning} ({odia_key})",
                    "source": "OdiaNLP Fuzzy"
                }

        # 3. Fallback: Query Wiktionary
        url = f"https://or.wiktionary.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles={clean_word}&format=json"
        res = requests.get(url, headers={"User-Agent": "OdiaPdfReaderApp/1.0"}, timeout=5)
        pages = res.json().get("query", {}).get("pages", {})
        
        for p_id, p_data in pages.items():
            if p_id != "-1" and "extract" in p_data and p_data["extract"].strip():
                return {
                    "status": "success",
                    "word": clean_word,
                    "meaning": p_data["extract"].strip(),
                    "source": "Wiktionary"
                }

        return {
            "status": "success",
            "word": clean_word,
            "meaning": f"'{clean_word}' ଶବ୍ଦର ବିଶେଷ ବିବରଣୀ ଉପଲବ୍ଧ ନାହିଁ ।",
            "source": "None"
        }

    except Exception as e:
        return {
            "status": "error",
            "word": word,
            "meaning": f"ଅର୍ଥ ଆଣିବାରେ ତ୍ରୁଟି: {str(e)}",
            "source": "Error"
        }


# =====================================================================
# ODIA TEXT-TO-SPEECH (TTS) ENDPOINT (Sanitized & Truncated)
# =====================================================================
@app.post("/api/tts")
def generate_odia_speech(payload: dict):
    """Converts Odia text to Base64 MP3 Audio safely."""
    if not GTTS_AVAILABLE or gTTS is None:
        raise HTTPException(
            status_code=500,
            detail="gTTS package is not installed on the server. Ensure gTTS is listed in requirements.txt on Render."
        )

    try:
        raw_text = payload.get("text", "")
        lang = payload.get("lang", "or")

        if not raw_text or not raw_text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        # Clean extra spaces, newlines, and control characters
        clean_text = re.sub(r'\s+', ' ', raw_text).strip()

        # Limit to 800 characters max per chunk to prevent gTTS timeout/crash
        if len(clean_text) > 800:
            clean_text = clean_text[:800] + "..."

        tts = gTTS(text=clean_text, lang=lang, slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)

        audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode("utf-8")
        return {"status": "success", "audio_base64": audio_base64}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))