import base64
import io
import re
import requests
import traceback
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from xhtml2pdf import pisa
import fitz  # PyMuPDF

# Safe gTTS Import
try:
    from gTTS import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    gTTS = None
    GTTS_AVAILABLE = False
    print("⚠️ gTTS package not found. Text-to-speech endpoint will return fallback error.")

# Import local engines (engine.py & odia_calendar.py)
try:
    from engine import calculate_astrology, get_daily_rashifal
    from odia_calendar import get_kohinoor_odia_panchang, get_kohinoor_month_calendar
    ASTRO_ENGINE_LOADED = True
except ImportError as e:
    ASTRO_ENGINE_LOADED = False
    print(f"⚠️ Engine import warning: {e}")


# =====================================================================
# HELPER: SANITIZE JSON RESPONSE (PREVENTS UNICODE DECODE ERRORS)
# =====================================================================
def sanitize_response(data):
    """Recursively converts raw bytes to base64 strings for UTF-8 JSON compliance."""
    if isinstance(data, dict):
        return {k: sanitize_response(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_response(i) for i in data]
    elif isinstance(data, bytes):
        return base64.b64encode(data).decode('utf-8')
    return data


# =====================================================================
# ODIA NLP DICTIONARY ENGINE
# =====================================================================
ODIA_DICT = {}

def load_odianlp_dictionary():
    """Downloads & caches OdiaNLP dictionary dataset from GitHub at startup."""
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
                print(f"✅ Loaded {len(ODIA_DICT)} entries into OdiaNLP dictionary.")
                return
        except Exception as e:
            print(f"⚠️ Failed source {url}: {e}")
            continue
            
    print("⚠️ OdiaNLP dictionary fallback mode active.")


# =====================================================================
# FASTAPI LIFESPAN MANAGEMENT
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        load_odianlp_dictionary()
    except Exception as e:
        print(f"⚠️ Dictionary startup warning: {e}")
    yield


app = FastAPI(
    title="Vedic Astro Engine & Kohinoor Odia Calendar API", 
    lifespan=lifespan
)

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
# CUSTOM EXCEPTION HANDLER
# =====================================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Safely handles request validation errors without crashing server."""
    def clean_errors(errors):
        if isinstance(errors, list):
            return [clean_errors(e) for e in errors]
        elif isinstance(errors, dict):
            return {k: clean_errors(v) for k, v in errors.items()}
        elif isinstance(errors, bytes):
            return errors.decode('utf-8', errors='ignore')
        return errors

    safe_errors = clean_errors(exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors},
    )


# =====================================================================
# PYDANTIC REQUEST MODELS
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


class PdfExtractRequest(BaseModel):
    pdf_url: str
    page_number: int = 1


# =====================================================================
# HEALTH CHECK ENDPOINT
# =====================================================================
@app.get("/")
def health_check():
    try:
        import fitz
        fitz_ok = True
    except:
        fitz_ok = False
        
    return {
        "status": "ok",
        "astro_engine_loaded": ASTRO_ENGINE_LOADED,
        "gtts_installed": GTTS_AVAILABLE,
        "fitz_installed": fitz_ok,
        "dictionary_entries": len(ODIA_DICT),
        "message": "Vedic Astro Engine & Kohinoor Calendar Server Running"
    }


# =====================================================================
# ASTROLOGY KUNDLI CALCULATION ENDPOINT
# =====================================================================
@app.post("/api/calculate")
def calculate_kundli(data: BirthDataRequest):
    """
    Calculates D1/D9 Kundli charts, Vimshottari Dasha, Panchanga, 
    and Rashi details using Swiss Ephemeris in engine.py.
    """
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
        )

        result["name"] = data.name
        moon_rashi_en = result.get("planets_en", {}).get("Moon", {}).get("sign", "Aries")
        result["rashifal"] = get_daily_rashifal(moon_rashi_en, lang=data.lang)

        return sanitize_response(result)
    except Exception as e:
        print("❌ Error inside /api/calculate:")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Calculation Error: {str(e)}")


# =====================================================================
# HTML TEMPLATE BUILDER FOR PDF EXPORT
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
# SERVER-SIDE PDF EXPORT ENDPOINT
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

        moon_rashi_en = result.get("planets_en", {}).get("Moon", {}).get("sign", "Aries")
        result["rashifal"] = get_daily_rashifal(moon_rashi_en, lang=data.lang)

        html_content = build_pdf_html(result, data)

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)

        if pisa_status.err:
            raise Exception("HTML to PDF conversion failed")

        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
        filename = f"Kundli_{data.name.replace(' ', '_')}.pdf"

        return sanitize_response({"status": "success", "filename": filename, "pdf_base64": pdf_base64})
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
        return sanitize_response({"status": "success", "data": data})
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
        return sanitize_response({"status": "success", "data": data})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# PDF TEXT EXTRACTION ENDPOINT
# =====================================================================
@app.post("/api/extract-pdf-text")
async def extract_pdf_page_text(
    pdf_url: Optional[str] = Form(None),
    page_number: int = Form(1),
    pdf: Optional[UploadFile] = File(None)
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

        doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
        
        if page_number - 1 < 0 or page_number - 1 >= len(doc):
            raise HTTPException(status_code=400, detail="Page number out of range.")

        page = doc[page_number - 1]
        text = page.get_text("text").strip()

        if len(text) < 15:
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            ocr_res = requests.post(
                "https://api.ocr.space/parse/image",
                files={"page.png": ("page.png", pix.tobytes("png"), "image/png")},
                data={"apikey": "K82596486888957", "language": "ori", "isOverlayRequired": "false"},
                timeout=30
            )
            json_data = ocr_res.json()
            if "ParsedResults" in json_data and json_data["ParsedResults"]:
                text = json_data["ParsedResults"][0].get("ParsedText", "")

        return sanitize_response({"status": "success", "text": text})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(sanitize_response(str(e))))


# =====================================================================
# ADVANCED ODIA NLP & TRANSLATION DICTIONARY ENDPOINT
# =====================================================================
@app.get("/api/word-details")
def get_word_details(word: str):
    try:
        clean_word = word.strip().strip(".,!?:;\"'()[]{}«»")
        if not clean_word:
            return {"status": "error", "meaning": "ଶବ୍ଦ ଚୟନ କରନ୍ତୁ ।"}

        # 1. Exact Match
        if clean_word in ODIA_DICT:
            val = ODIA_DICT[clean_word]
            meaning_str = ", ".join(val) if isinstance(val, list) else str(val)
            return {"status": "success", "word": clean_word, "meaning": meaning_str, "source": "OdiaNLP Exact"}

        # 2. Case-insensitive key match
        lower_word = clean_word.lower()
        for k, v in ODIA_DICT.items():
            if k.lower() == lower_word:
                meaning_str = ", ".join(v) if isinstance(v, list) else str(v)
                return {"status": "success", "word": k, "meaning": meaning_str, "source": "OdiaNLP Key"}

        # 3. Reverse English-to-Odia Search (e.g., "major")
        english_matches = []
        for odia_k, eng_v in ODIA_DICT.items():
            eng_str = ", ".join(eng_v) if isinstance(eng_v, list) else str(eng_v)
            if lower_word in eng_str.lower().split():
                english_matches.append(f"• {odia_k}: {eng_str}")
                if len(english_matches) >= 4:
                    break
        if english_matches:
            return {"status": "success", "word": clean_word, "meaning": "ଓଡ଼ିଆ ଅର୍ଥ (Matches):\n" + "\n".join(english_matches), "source": "OdiaNLP English Search"}

        # 4. Grammatical Suffix Stripping
        suffixes = ["ମାନଙ୍କର", "ମାନଙ୍କୁ", "ମାନଙ୍କ", "ଠାରୁ", "ମାନେ", "ଙ୍କର", "ଙ୍କୁ", "କୁ", "ରେ", "ର", "ଟି", "ଟା", "ଏ", "ଙ୍କ"]
        for suffix in sorted(suffixes, key=len, reverse=True):
            if clean_word.endswith(suffix) and len(clean_word) > len(suffix):
                stem = clean_word[:-len(suffix)]
                if stem in ODIA_DICT:
                    val = ODIA_DICT[stem]
                    meaning_str = ", ".join(val) if isinstance(val, list) else str(val)
                    return {"status": "success", "word": clean_word, "meaning": f"{meaning_str} (ମୂଳ ଶବ୍ଦ: {stem})", "source": "OdiaNLP Stemmed"}

        # 5. Dynamic Translation API Fallback (MyMemory)
        is_english = all(ord(c) < 128 for c in clean_word if c.isalpha())
        langpair = "en|or" if is_english else "or|en"
        
        try:
            api_url = f"https://api.my-memory.translated.net/get?q={requests.utils.quote(clean_word)}&langpair={langpair}"
            res = requests.get(api_url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                translated = data.get("responseData", {}).get("translatedText", "")
                if translated and "MYMEMORY WARNING" not in translated and translated.lower() != clean_word.lower():
                    label = "ଓଡ଼ିଆ ଅନୁବାଦ:" if is_english else "English Meaning:"
                    return {"status": "success", "word": clean_word, "meaning": f"{label}\n{translated}", "source": "Translation Engine"}
        except Exception as e:
            print(f"⚠️ Translation API error: {e}")

        # 6. Wiktionary Fallback
        try:
            url = f"https://or.wiktionary.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles={requests.utils.quote(clean_word)}&format=json"
            res_wik = requests.get(url, headers={"User-Agent": "OdiaPdfReaderApp/1.0"}, timeout=5)
            pages = res_wik.json().get("query", {}).get("pages", {})
            for p_id, p_data in pages.items():
                if p_id != "-1" and "extract" in p_data and p_data["extract"].strip():
                    return {"status": "success", "word": clean_word, "meaning": p_data["extract"].strip(), "source": "Wiktionary"}
        except Exception as e:
            print(f"⚠️ Wiktionary error: {e}")

        return {"status": "success", "word": clean_word, "meaning": f"'{clean_word}' ଶବ୍ଦର ବିବରଣୀ ଉପଲବ୍ଧ ନାହିଁ ।", "source": "None"}

    except Exception as e:
        return {"status": "error", "word": word, "meaning": f"ଅର୍ଥ ଆଣିବାରେ ତ୍ରୁଟି: {str(e)}", "source": "Error"}


# =====================================================================
# ODIA TEXT-TO-SPEECH (TTS) ENDPOINT
# =====================================================================
@app.post("/api/tts")
def generate_odia_speech(payload: dict):
    if not GTTS_AVAILABLE or gTTS is None:
        raise HTTPException(
            status_code=500,
            detail="gTTS package is not installed on the server."
        )

    try:
        raw_text = payload.get("text", "")
        lang = payload.get("lang", "or")

        if not raw_text or not raw_text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        clean_text = re.sub(r'[^\w\s\u0B00-\u0B7F.,!?-]', '', raw_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        if not clean_text:
            clean_text = raw_text[:300]

        if len(clean_text) > 500:
            clean_text = clean_text[:500] + "..."

        tts = gTTS(text=clean_text, lang=lang, slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)

        audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode("utf-8")
        return sanitize_response({"status": "success", "audio_base64": audio_base64})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Engine Error: {str(e)}")