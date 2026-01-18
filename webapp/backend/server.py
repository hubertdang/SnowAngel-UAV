from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import psycopg2
import os
import io
import csv
import pandas as pd
from datetime import datetime

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


# --- Helper function placeholder ---
def process_uploaded_measurements(file: UploadFile, flight_id: int):
    """
    Parse uploaded CSV containing timestamp, lat, lon, fft_value (depth surrogate).
    Inserts raw rows into raw_measurements, performs cleaning (averaging, filtering),
    and inserts cleaned results into cleaned_measurements.
    """
    cur = conn.cursor()

    # --- 1. Read CSV ---
    content = file.file.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(content))

    expected_cols = {"timestamp", "latitude", "longitude", "fft_value"}
    if not expected_cols.issubset(df.columns):
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing columns. Expected {expected_cols}, got {set(df.columns)}"
        )

    # --- 2. Normalize data types ---
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "latitude", "longitude", "fft_value"])

    # --- 3. Insert RAW measurements ---
    raw_count = 0
    for _, row in df.iterrows():
        cur.execute(
            """
            INSERT INTO raw_measurements (flight_id, timestamp, coordinates, depth, created_at)
            VALUES (%s, %s, point(%s, %s), %s, NOW())
            RETURNING measurement_id;
            """,
            (
                flight_id,
                row["timestamp"].to_pydatetime(),
                float(row["longitude"]),
                float(row["latitude"]),
                float(row["fft_value"])
            )
        )
        raw_count += 1

    # --- 4. Cleaning Pass ---
    #  - Round coordinates slightly to merge nearby readings (~few cm)
    #  - Average depth across duplicates
    #  - Simple outlier rejection (within 2σ of group mean)
    df["lat_r"] = df["latitude"].round(5)
    df["lon_r"] = df["longitude"].round(5)
    grouped = df.groupby(["lat_r", "lon_r"], as_index=False)["fft_value"].agg(["mean", "std", "count"]).reset_index()

    cleaned_rows = []
    for _, g in grouped.iterrows():
        mean_depth = g["mean"]
        # Example: assume FFT magnitude inversely correlates to thickness
        # Placeholder conversion; replace with real calibration later
        thickness = max(0.0, mean_depth * 0.01)
        quality = 1.0 if g["count"] >= 5 else 0.5  # simple quality metric

        cleaned_rows.append({
            "lat": g["lat_r"],
            "lon": g["lon_r"],
            "thickness": thickness,
            "quality_score": quality
        })

    # --- 5. Insert CLEANED measurements ---
    cleaned_count = 0
    for row in cleaned_rows:
        # Find one representative raw_id (optional)
        cur.execute(
            """
            INSERT INTO cleaned_measurements
                (flight_id, raw_id, timestamp, coordinates, thickness, quality_score, processed_at)
            VALUES (%s,
                    (SELECT measurement_id FROM raw_measurements
                     WHERE flight_id=%s
                     ORDER BY created_at DESC LIMIT 1),
                    NOW(),
                    point(%s, %s),
                    %s,
                    %s,
                    NOW());
            """,
            (
                flight_id,
                flight_id,
                row["lon"],
                row["lat"],
                row["thickness"],
                row["quality_score"]
            )
        )
        cleaned_count += 1

    cur.close()

    return {
        "flight_id": flight_id,
        "raw_inserted": raw_count,
        "cleaned_inserted": cleaned_count,
        "status": "completed"
    }

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
async def add_flight(
    date: str = Form(...),
    location: str = Form(...),
    notes: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    """
    Creates a new flight and processes the uploaded measurement file.
    """
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO flights (date, location, notes) VALUES (%s, %s, %s) RETURNING flight_id;",
        (date, location, notes)
    )
    flight_id = cur.fetchone()[0]
    cur.close()

    # Placeholder for parsing & inserting measurement data
    process_uploaded_measurements(file, flight_id)

    return {"flight_id": flight_id, "status": "added", "file_received": file.filename}


@app.get("/cleaned/{flight_id}")
def get_cleaned_by_flight(flight_id: int):
    """
    Returns all cleaned measurements associated with a specific flight.
    """
    cur = conn.cursor()
    cur.execute(
        """SELECT cleaned_id, flight_id, raw_id, timestamp, coordinates, thickness, quality_score, processed_at
           FROM cleaned_measurements
           WHERE flight_id = %s
           ORDER BY cleaned_id;""",
        (flight_id,)
    )
    rows = cur.fetchall()
    cur.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No cleaned measurements found for flight_id={flight_id}")

# Raw measurements
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
        }
        for r in rows
    ]

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
