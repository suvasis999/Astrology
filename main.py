# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from engine import calculate_astrology

app = FastAPI(title="Vedic Astro Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BirthDataRequest(BaseModel):
    name: str = Field("User", example="Rahul Sharma") # <--- Added Name Field
    date: str = Field(..., example="1995-10-16")
    time: str = Field(..., example="07:30:00")
    latitude: float = Field(..., example=28.6139)
    longitude: float = Field(..., example=77.2090)
    tz_offset: float = Field(..., example=5.5)
    ayanamsha: str = Field("LAHIRI", example="LAHIRI")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Vedic Astro Engine Server Running"}

@app.post("/api/calculate")
def calculate_kundli(data: BirthDataRequest):
    try:
        result = calculate_astrology(
            date_str=data.date,
            time_str=data.time,
            latitude=data.latitude,
            longitude=data.longitude,
            tz_offset=data.tz_offset,
            ayanamsha_mode=data.ayanamsha
        )
        # Attach the person's name to the final payload
        result["name"] = data.name
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))