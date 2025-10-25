from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import psycopg2
import os

# --- Database connection ---
try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        database=os.getenv("DB_NAME", "db"),
        user=os.getenv("DB_USER", "temp"),
        password=os.getenv("DB_PASS", "pass")
    )
    conn.autocommit = True
except Exception as e:
    raise RuntimeError(f"Failed to connect to database: {e}")

app = FastAPI(title="Ice Measurement API")

# --- Pydantic models ---
class Flight(BaseModel):
    date: str
    location: str
    notes: Optional[str] = None

class RawMeasurement(BaseModel):
    flight_id: int
    timestamp: str
    x: float
    y: float
    depth: float

class CleanedMeasurement(BaseModel):
    flight_id: int
    raw_id: int
    timestamp: str
    x: float
    y: float
    thickness: float
    quality_score: float

# --- Routes ---
@app.get("/")
def root():
    return {"message": "Ice Measurement API is running"}

# Flights
@app.get("/flights")
def get_flights():
    cur = conn.cursor()
    cur.execute("SELECT * FROM flights ORDER BY flight_id;")
    rows = cur.fetchall()
    cur.close()
    return [{"flight_id": r[0], "date": str(r[1]), "location": r[2], "notes": r[3]} for r in rows]

@app.post("/flights")
def add_flight(flight: Flight):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO flights (date, location, notes) VALUES (%s, %s, %s) RETURNING flight_id;",
        (flight.date, flight.location, flight.notes)
    )
    flight_id = cur.fetchone()[0]
    cur.close()
    return {"flight_id": flight_id, "status": "added"}

# Raw measurements
@app.get("/raw")
def get_raw():
    cur = conn.cursor()
    cur.execute("SELECT * FROM raw_measurements ORDER BY measurement_id;")
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "measurement_id": r[0],
            "flight_id": r[1],
            "timestamp": str(r[2]),
            "x": r[3][0],
            "y": r[3][1],
            "depth": r[4],
            "created_at": str(r[5])
        } for r in rows
    ]

@app.post("/raw")
def add_raw(data: RawMeasurement):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO raw_measurements (flight_id, timestamp, coordinates, depth)
           VALUES (%s, %s, point(%s, %s), %s)
           RETURNING measurement_id;""",
        (data.flight_id, data.timestamp, data.x, data.y, data.depth)
    )
    measurement_id = cur.fetchone()[0]
    cur.close()
    return {"measurement_id": measurement_id, "status": "added"}

# Cleaned measurements
@app.get("/cleaned")
def get_cleaned():
    cur = conn.cursor()
    cur.execute("SELECT * FROM cleaned_measurements ORDER BY cleaned_id;")
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "cleaned_id": r[0],
            "flight_id": r[1],
            "raw_id": r[2],
            "timestamp": str(r[3]),
            "x": r[4][0],
            "y": r[4][1],
            "thickness": r[5],
            "quality_score": r[6],
            "processed_at": str(r[7])
        } for r in rows
    ]

@app.post("/cleaned")
def add_cleaned(data: CleanedMeasurement):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO cleaned_measurements (flight_id, raw_id, timestamp, coordinates, thickness, quality_score)
           VALUES (%s, %s, %s, point(%s, %s), %s, %s)
           RETURNING cleaned_id;""",
        (data.flight_id, data.raw_id, data.timestamp, data.x, data.y, data.thickness, data.quality_score)
    )
    cleaned_id = cur.fetchone()[0]
    cur.close()
    return {"cleaned_id": cleaned_id, "status": "added"}
