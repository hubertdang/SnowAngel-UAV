from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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

# --- Helper function placeholder ---
def process_uploaded_measurements(file: UploadFile, flight_id: int):
    """
    Placeholder function to handle file parsing and DB insertion.
    - Parse the uploaded file
    - Insert rows into raw_measurements and cleaned_measurements
    """
    # TODO: Implement parsing + insertion logic here
    pass


# --- Routes ---
@app.get("/")
def root():
    return {"message": "Ice Measurement API is running"}

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


    # Format results as dictionaries
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
