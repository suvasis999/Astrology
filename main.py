# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from engine import calculate_astrology, get_daily_rashifal
from engine_advanced import (
    check_vargottama, check_combustion, check_paap_kartari,
    check_panchak, calculate_hora_timings, search_aspect_contacts, PLANET_IDS
)
import swisseph as swe

app = FastAPI(title="Financial Astrology Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BirthDataRequest(BaseModel):
    name: str = "Client"
    date: str = "2026-08-02"
    time: str = "11:22:00"
    latitude: float = 18.9220
    longitude: float = 72.8347
    tz_offset: float = 5.5
    ayanamsha: str = "LAHIRI"

class AspectSearchRequest(BaseModel):
    planet1: str = "Sun"
    planet2: str = "Mercury"
    aspect_degree: float = 0.0  # 0=Conjunction, 120=Trine, 90=Square
    range_days: int = 300
    direction: str = "Forward"  # "Forward" or "Backward"

@app.post("/api/calculate")
def calculate_all(data: BirthDataRequest):
    try:
        # Base Engine Output
        res = calculate_astrology(
            date_str=data.date, time_str=data.time,
            latitude=data.latitude, longitude=data.longitude,
            tz_offset=data.tz_offset, ayanamsha_mode=data.ayanamsha
        )
        res["name"] = data.name

        # Calculate Advanced Indicators (Vargottama, Combust, Panchak, Kartari)
        sun_lon = res["planets"]["Sun"]["longitude_raw"]
        
        # Check Vargottama & Combustion for each planet
        for p_name, p_data in res["planets"].items():
            # Vargottama
            p_data["is_vargottama"] = check_vargottama(
                p_data["sign_index"], p_data["navamsa_sign_index"]
            )
            # Combustion
            comb_info = check_combustion(p_name, p_data["longitude_raw"], sun_lon, p_data["is_retrograde"])
            p_data["is_combust"] = comb_info["is_combust"]
            p_data["combust_orb"] = comb_info["orb_degrees"]

        # Check Panchak Status
        moon_lon = res["planets"]["Moon"]["longitude_raw"]
        res["panchak"] = check_panchak(moon_lon)

        # Check Paap Kartari for all 12 Houses
        house_planets_map = {h: res["houses"][h]["planets"] for h in res["houses"]}
        res["paap_kartari_houses"] = [
            h for h in range(1, 13) if check_paap_kartari(h, house_planets_map)
        ]

        # Hora Timings
        res["horas"] = calculate_hora_timings(res["julian_day"], data.latitude, data.longitude, data.tz_offset)

        # Daily Rashifal
        res["rashifal"] = get_daily_rashifal(res["planets"]["Moon"]["sign"])

        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/aspect-search")
def aspect_search(data: AspectSearchRequest):
    try:
        p1 = PLANET_IDS.get(data.planet1, swe.SUN)
        p2 = PLANET_IDS.get(data.planet2, swe.MERCURY)
        
        start_jd = swe.julday(2026, 8, 2, 12.0)
        if data.direction.lower() == "backward":
            start_jd -= data.range_days

        contacts = search_aspect_contacts(
            start_jd=start_jd, days_range=data.range_days,
            p1_id=p1, p2_id=p2, target_aspect_deg=data.aspect_degree
        )
        return {"contacts": contacts, "count": len(contacts)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
