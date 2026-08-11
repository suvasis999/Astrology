import base64
import io
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

# Safe local engine imports (engine.py & odia_calendar.py)
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
# HELPER: SANITIZE JSON RESPONSE (PREVENTS UNICODE SERIALIZATION ERRORS)
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
# UNICODE & LEGACY FONT GARBLE DETECTOR
# =====================================================================
def needs_ocr_fallback(text: str) -> bool:
    """
    Detects if direct PyMuPDF text extraction produced ASCII gibberish,
    missing text, or legacy non-Unicode font output (e.g. Akruti/ShreeLipi).
    """
    if not text:
        return True
    
    clean = unicodedata.normalize('NFC', text).strip()
    if len(clean) < 15:
        return True

    # Count actual Odia Unicode characters (U+0B00 to U+0B7F)
    odia_char_count = sum(1 for ch in clean if 0x0B00 <= ord(ch) <= 0x0B7F)
    total_alpha = sum(1 for ch in clean if ch.isalpha())

    # If text has almost no real Odia Unicode but contains many ASCII letters, it's garbled!
    if odia_char_count < 5 and total_alpha > 10:
        return True

    # Check for excessive replacement or unprintable symbols
    weird_symbols = sum(1 for ch in clean if ch in '^~_`{}|\\<>#$@\uFFFD')
    if weird_symbols > 5:
        return True

    return False


def clean_unicode_text(text: str) -> str:
    """Removes unprintable control codes and normalizes Unicode."""
    if not text:
        return ""
    text = unicodedata.normalize('NFC', text)
    return "".join(ch for ch in text if ch in ('\n', '\r', '\t', ' ') or unicodedata.category(ch)[0] != 'C')


# =====================================================================
# ODIA NLP DICTIONARY DATASET LOAD
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
    title="Vedic Astro Engine & Kohinoor Odia Reader Server", 
    lifespan=lifespan
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    def clean_errors(errors):
        if isinstance(errors, list):
            return [clean_errors(e) for e in errors]
        elif isinstance(errors, dict):
            return {k: clean_errors(v) for k, v in errors.items()}
        elif isinstance(errors, bytes):
            return errors.decode('utf-8', errors='ignore')
        return errors

    safe_errors = clean_errors(exc.errors())
    return JSONResponse(status_code=422, content={"detail": safe_errors})


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
        "fitz_installed": fitz_ok,
        "dictionary_entries": len(ODIA_DICT),
        "message": "Vedic Astro Engine & Odia Reader Active"
    }


# =====================================================================
# ASTROLOGY KUNDLI CALCULATION ENDPOINT
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
# HTML TEMPLATE BUILDER & PDF EXPORT ENDPOINT
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

    return f"""
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
# HIGH-PRECISION PDF TEXT EXTRACTION (JPEG OCR UNDER 1MB LIMIT)
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
        raw_text = page.get_text("text").strip()

        # If direct text is missing, short, or garbled legacy font, run OCR.space Engine 2
        if needs_ocr_fallback(raw_text):
            print(f"⚠️ Direct text garbled/missing for page {page_number}. Running Compressed JPEG OCR...")
            
            # Render page image as JPEG at 2.0x scale (compressed to ~200 KB to fit under OCR.space 1 MB limit)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            jpeg_bytes = pix.tobytes("jpg", jpg_quality=75)

            ocr_res = requests.post(
                "https://api.ocr.space/parse/image",
                files={"page.jpg": ("page.jpg", jpeg_bytes, "image/jpeg")},
                data={
                    "apikey": "K82596486888957",
                    "language": "ori",
                    "isOverlayRequired": "false",
                    "OCREngine": "2",
                    "scale": "true"
                },
                timeout=35
            )
            json_data = ocr_res.json()
            if "ParsedResults" in json_data and json_data["ParsedResults"]:
                raw_text = json_data["ParsedResults"][0].get("ParsedText", "")

        cleaned_text = clean_unicode_text(raw_text)

        if not cleaned_text:
            cleaned_text = "ଏହି ପୃଷ୍ଠାରେ କୌଣସି ପଢ଼ିବା ଯୋଗ୍ୟ ଲେଖା ମିଳିଲା ନାହିଁ ।"

        return sanitize_response({"status": "success", "text": cleaned_text})

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(sanitize_response(str(e))))


# =====================================================================
# DIRECT GOOGLE WEB TRANSLATE TTS ENGINE (CHUNKED & UNBLOCKED)
# =====================================================================
def get_odia_tts_mp3_bytes(text: str) -> bytes:
    """
    Fetches Odia audio bytes directly from Google's web TTS stream.
    Splits text into chunks to avoid sentence length restrictions.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # Break text into ~150-character chunks by punctuation
    sentences = re.split(r'([।,!?\n]+)', text)
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

    for chunk in chunks[:8]:  # Limit to 8 chunks (~1200 chars max per request)
        encoded_chunk = requests.utils.quote(chunk)
        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_chunk}&tl=or&client=tw-ob"
        
        res = requests.get(tts_url, headers=headers, timeout=10)
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

        audio_base64 = base64.b64encode(mp3_bytes).decode("utf-8")
        return sanitize_response({"status": "success", "audio_base64": audio_base64})

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TTS Error: {str(e)}")


# =====================================================================
# MULTI-ENGINE ODIA/ENGLISH WORD DETAILS & SYNONYMS ENDPOINT
# =====================================================================
@app.get("/api/word-details")
def get_word_details(word: str):
    try:
        clean_word = word.strip().strip(".,!?:;\"'()[]{}«»<>")
        if not clean_word:
            return {"status": "error", "meaning": "ଶବ୍ଦ ଚୟନ କରନ୍ତୁ ।"}

        meaning_parts = []
        synonyms_list = []

        # 1. Local OdiaNLP Dictionary Lookup with stem/suffix stripping
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
                suffixes = ["ମାନଙ୍କର", "ମାନଙ୍କୁ", "ମାନଙ୍କ", "ଠାରୁ", "ମାନେ", "ଙ୍କର", "ଙ୍କୁ", "କୁ", "ରେ", "ର", "ଟି", "ଟା", "ଏ", "ଙ୍କ"]
                for suffix in sorted(suffixes, key=len, reverse=True):
                    if clean_word.endswith(suffix) and len(clean_word) > len(suffix):
                        stem = clean_word[:-len(suffix)]
                        if stem in ODIA_DICT:
                            val = ODIA_DICT[stem]
                            local_meaning = (", ".join(val) if isinstance(val, list) else str(val)) + f" (ମୂଳ: {stem})"
                            break

        if local_meaning:
            meaning_parts.append(f"📖 ଡିକ୍ସନାରୀ ଅର୍ଥ: {local_meaning}")

        is_english = all(ord(c) < 128 for c in clean_word if c.isalpha())

        # 2. Google Translate GTX API (Full translation + parts of speech & synonyms)
        target_lang = "or" if is_english else "en"
        gtx_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&dt=bd&q={requests.utils.quote(clean_word)}"
        
        try:
            res_gtx = requests.get(gtx_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if res_gtx.status_code == 200:
                data_gtx = res_gtx.json()
                
                primary_trans = ""
                if data_gtx and len(data_gtx) > 0 and data_gtx[0]:
                    for item in data_gtx[0]:
                        if item and len(item) > 0 and item[0]:
                            primary_trans += item[0]
                
                if primary_trans and primary_trans.strip().lower() != clean_word.lower():
                    label = "🌐 ଓଡ଼ିଆ ଅନୁବାଦ" if is_english else "🌐 English Translation"
                    meaning_parts.append(f"{label}: {primary_trans.strip()}")

                if len(data_gtx) > 1 and data_gtx[1]:
                    for pos_group in data_gtx[1]:
                        if len(pos_group) >= 2:
                            pos = pos_group[0]
                            terms = pos_group[1]
                            if terms:
                                terms_str = ", ".join(terms[:6])
                                synonyms_list.append(f"• ({pos}): {terms_str}")

        except Exception as e_gtx:
            print(f"⚠️ GTX Error: {e_gtx}")

        # 3. FreeDictionary API for English Words
        if is_english:
            try:
                dict_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{requests.utils.quote(clean_word.lower())}"
                res_dict = requests.get(dict_url, timeout=5)
                if res_dict.status_code == 200:
                    data_dict = res_dict.json()
                    if isinstance(data_dict, list) and len(data_dict) > 0:
                        entry = data_dict[0]
                        meanings = entry.get("meanings", [])
                        for m in meanings:
                            part_of_speech = m.get("partOfSpeech", "")
                            defs = m.get("definitions", [])
                            syns = m.get("synonyms", [])
                            
                            if defs and len(defs) > 0:
                                def_text = defs[0].get("definition", "")
                                if def_text:
                                    meaning_parts.append(f"💡 Def ({part_of_speech}): {def_text}")
                            
                            if syns:
                                synonyms_list.append(f"• Synonyms ({part_of_speech}): {', '.join(syns[:5])}")
            except Exception as e_dict:
                print(f"⚠️ FreeDictionary Error: {e_dict}")

        # 4. Wiktionary Fallback for Odia Words
        if not is_english and not local_meaning:
            try:
                wik_url = f"https://or.wiktionary.org/w/api.php?action=query&prop=extracts&exintro&explaintext&titles={requests.utils.quote(clean_word)}&format=json"
                res_wik = requests.get(wik_url, headers={"User-Agent": "OdiaPdfReaderApp/1.0"}, timeout=5)
                if res_wik.status_code == 200:
                    pages = res_wik.json().get("query", {}).get("pages", {})
                    for p_id, p_data in pages.items():
                        if p_id != "-1" and "extract" in p_data and p_data["extract"].strip():
                            meaning_parts.append(f"📚 Wiktionary: {p_data['extract'].strip()}")
            except Exception as e_wik:
                print(f"⚠️ Wiktionary Error: {e_wik}")

        full_result = []
        if meaning_parts:
            full_result.extend(meaning_parts)

        if synonyms_list:
            full_result.append("\n🔄 ସମାର୍ଥକ ଶବ୍ଦ / Synonyms & Alternate Meanings:")
            full_result.extend(synonyms_list)

        if full_result:
            return {
                "status": "success",
                "word": clean_word,
                "meaning": "\n\n".join(full_result),
                "source": "Multi-Engine NLP"
            }

        return {
            "status": "success",
            "word": clean_word,
            "meaning": f"'{clean_word}' - {clean_word}",
            "source": "Literal Fallback"
        }

    except Exception as e:
        return {
            "status": "error",
            "word": word,
            "meaning": f"ଅର୍ଥ: {word}",
            "source": "Error Safety"
        }