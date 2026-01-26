"""Temporary FastAPI backend powering the Ice Thickness Visualizer prototype."""

from __future__ import annotations

import contextlib
import csv
import io
import math
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Iterator, List, Optional

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware


RIDEAU_BOUNDS = {
    "north": float(os.getenv("RIDEAU_NORTH", 45.4325)),
    "south": float(os.getenv("RIDEAU_SOUTH", 45.3820)),
    "east": float(os.getenv("RIDEAU_EAST", -75.6700)),
    "west": float(os.getenv("RIDEAU_WEST", -75.7300)),
}

MAX_POINTS = int(os.getenv("MAX_CONDITION_POINTS", "800"))
MIN_THICKNESS_CM = float(os.getenv("MIN_THICKNESS_CM", "32"))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "snowangel"),
    "user": os.getenv("DB_USER", "snowangel"),
    "password": os.getenv("DB_PASS", "snowangel"),
}

FFT_N = 512
SAMPLING_RATE = 80000.0
SPEED_OF_LIGHT = 3e8
CHIRP_BW = 990e6
CHIRP_DURATION = 1.6e-3
CHIRP_SLOPE = CHIRP_BW / CHIRP_DURATION
BIN_SPACING = SAMPLING_RATE / 1024
HZ_TO_M = SPEED_OF_LIGHT / (2 * CHIRP_SLOPE)
RANGE_AXIS = [idx * BIN_SPACING * HZ_TO_M for idx in range(FFT_N)]


def _connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(**DB_CONFIG)


try:
    CONNECTION = _connect()
    CONNECTION.autocommit = True
except psycopg2.Error as exc:  # pragma: no cover - raised during boot
    raise RuntimeError(f"Failed to connect to database: {exc}")


def _connection() -> psycopg2.extensions.connection:
    global CONNECTION
    if CONNECTION.closed:  # psycopg2 closes with non-zero int
        CONNECTION = _connect()
        CONNECTION.autocommit = True
    return CONNECTION


@contextlib.contextmanager
def get_cursor(commit: bool = False) -> Iterator[psycopg2.extensions.cursor]:
    conn = _connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def ensure_tables() -> None:
    with get_cursor(True) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ice_conditions (
                id SERIAL PRIMARY KEY,
                lat DOUBLE PRECISION NOT NULL,
                lng DOUBLE PRECISION NOT NULL,
                thickness_cm NUMERIC(4, 1) NOT NULL,
                temperature_c NUMERIC(5, 2),
                confidence_score NUMERIC(3, 2) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
                measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                location_label TEXT DEFAULT 'Rideau Canal',
                notes TEXT
            );
            """
        )
        cur.execute(
            "ALTER TABLE ice_conditions ADD COLUMN IF NOT EXISTS temperature_c NUMERIC(5, 2);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_ice_conditions_lat_lng ON ice_conditions (lat, lng);"
        )


@dataclass
class Condition:
    id: int
    lat: float
    lng: float
    thickness_cm: float
    temperature_c: Optional[float]
    confidence_score: float
    measured_at: datetime
    notes: Optional[str]

    @classmethod
    def from_row(cls, row: psycopg2.extras.RealDictRow) -> "Condition":
        def _to_float(value):
            if isinstance(value, Decimal):
                return float(value)
            return value

        return cls(
            id=row["id"],
            lat=_to_float(row["lat"]),
            lng=_to_float(row["lng"]),
            thickness_cm=_to_float(row["thickness_cm"]),
            temperature_c=_to_float(row.get("temperature_c")),
            confidence_score=_to_float(row["confidence_score"]),
            measured_at=row["measured_at"],
            notes=row.get("notes"),
        )


app = FastAPI(title="Ice Thickness Visualizer API")

allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    ensure_tables()


@app.get("/")
def root():
    return {"message": "Ice Thickness Visualizer backend ready"}


@app.get("/api/health")
def healthcheck():
    return {"status": "ok"}


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # pragma: no cover - FastAPI handles validation
        raise HTTPException(status_code=400, detail="date must be in YYYY-MM-DD format") from exc


def _parse_float(value: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        raise ValueError(f"Unable to parse float from '{value}'")
    return float(match.group(0))


def _parse_timestamp(value: str) -> datetime:
    cleaned = value.strip().replace("T", " ")
    if " " in cleaned:
        date_part, time_part = cleaned.split(" ", 1)
    else:
        raise ValueError("Timestamp must include a date and time")
    time_part = time_part.strip()
    segments = time_part.split(":")
    while len(segments) < 3:
        segments.append("00")
    padded = [segment.zfill(2) for segment in segments[:3]]
    normalized = f"{date_part} {padded[0]}:{padded[1]}:{padded[2]}"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported timestamp format '{value}'")


def _analyze_fft(fft_data: List[float], min_range: float = 0.05, max_range: float = 2.0) -> Optional[float]:
    valid_indices = [idx for idx, r in enumerate(RANGE_AXIS) if min_range <= r <= max_range]
    if not valid_indices:
        return None

    valid_fft = [fft_data[idx] for idx in valid_indices]
    if not valid_fft:
        return None

    peak_prominence = 0.003 * max(valid_fft)
    min_height = 0.01 * max(fft_data)

    peaks: List[int] = []
    last_peak = -999
    for idx in valid_indices[1:-1]:
        if fft_data[idx] <= fft_data[idx - 1] or fft_data[idx] <= fft_data[idx + 1]:
            continue
        if fft_data[idx] < min_height:
            continue

        left_min = min(fft_data[valid_indices[0] : idx + 1])
        right_min = min(fft_data[idx : valid_indices[-1] + 1])
        prominence = fft_data[idx] - max(left_min, right_min)
        if prominence < peak_prominence:
            continue
        if idx - last_peak < 2:
            continue

        peaks.append(idx)
        last_peak = idx

    if len(peaks) < 2:
        return None

    peaks.sort()
    r1 = RANGE_AXIS[peaks[0]]
    r2 = RANGE_AXIS[peaks[1]]
    return abs(r2 - r1) * 100


def _parse_row(fields: List[str]) -> Optional[dict]:
    if len(fields) < 5:
        return None
    timestamp_raw, lat_raw, lng_raw, temp_raw = fields[:4]
    if "timestamp" in timestamp_raw.lower():
        return None
    measured_at = _parse_timestamp(timestamp_raw)

    if len(fields) == 5:
        thickness = _parse_float(fields[4])
    else:
        fft_samples: List[float] = []
        for value in fields[4:]:
            try:
                fft_samples.append(_parse_float(value))
            except ValueError:
                fft_samples.append(math.nan)
        fft_samples = [val for val in fft_samples if not math.isnan(val)]
        if len(fft_samples) < 2:
            return None

        if len(fft_samples) >= FFT_N:
            thickness = _analyze_fft(fft_samples[:FFT_N])
            if thickness is None:
                return None
        else:
            fft_samples.sort(reverse=True)
            thickness = (fft_samples[0] - fft_samples[1]) / 10.0

    if thickness < MIN_THICKNESS_CM:
        return None

    return {
        "lat": _parse_float(lat_raw),
        "lng": _parse_float(lng_raw),
        "temperature_c": _parse_float(temp_raw),
        "thickness_cm": thickness,
        "confidence_score": 1.0,
        "measured_at": measured_at,
    }


def _parse_upload_content(content: str) -> List[dict]:
    rows: List[dict] = []
    timestamp_re = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
    starts = [match.start() for match in timestamp_re.finditer(content)]
    if starts:
        starts.append(len(content))
        for idx in range(len(starts) - 1):
            chunk = content[starts[idx] : starts[idx + 1]].strip()
            if not chunk:
                continue
            chunk = chunk.lstrip(",\n\r ")
            raw = [segment.strip() for segment in chunk.split(",") if segment.strip()]
            parsed = _parse_row(raw)
            if parsed:
                rows.append(parsed)
        return rows

    reader = csv.reader(io.StringIO(content), skipinitialspace=True)
    for raw in reader:
        if not raw:
            continue
        if len(raw) == 1:
            line = raw[0].strip()
            if not line:
                continue
            if "|" in line and "," not in line:
                raw = [segment.strip() for segment in line.split("|")]
            else:
                raw = [segment.strip() for segment in re.split(r"[,\t]+", line)]
        parsed = _parse_row([segment.strip() for segment in raw if segment.strip()])
        if parsed:
            rows.append(parsed)
    return rows


@app.get("/api/conditions")
def get_conditions(
    north: float = Query(RIDEAU_BOUNDS["north"], description="Northern latitude boundary"),
    south: float = Query(RIDEAU_BOUNDS["south"], description="Southern latitude boundary"),
    east: float = Query(RIDEAU_BOUNDS["east"], description="Eastern longitude boundary"),
    west: float = Query(RIDEAU_BOUNDS["west"], description="Western longitude boundary"),
    limit: int = Query(400, ge=1, le=2000, description="Maximum number of points to return"),
    day: Optional[str] = Query(
        None,
        description="Optional ISO date (YYYY-MM-DD) to filter measurements by measurement date.",
    ),
):
    if south > north:
        raise HTTPException(status_code=400, detail="south boundary must be <= north boundary")
    if west > east:
        raise HTTPException(status_code=400, detail="west boundary must be <= east boundary")

    bounded_limit = min(limit, MAX_POINTS)
    day_filter = _parse_date(day) if day else None

    sql = [
        """
        SELECT id, lat, lng, thickness_cm, temperature_c, confidence_score, measured_at, notes
        FROM ice_conditions
        WHERE lat BETWEEN %s AND %s
          AND lng BETWEEN %s AND %s
        """
    ]
    params: List = [south, north, west, east]

    if day_filter:
        sql.append("AND DATE(measured_at) = %s")
        params.append(day_filter)

    sql.append("ORDER BY measured_at DESC LIMIT %s")
    params.append(bounded_limit)

    with get_cursor() as cur:
        cur.execute("\n".join(sql), params)
        rows = cur.fetchall()

    return [asdict(Condition.from_row(row)) for row in rows]


@app.post("/api/uploads")
async def upload_csv(
    file: UploadFile = File(...),
    replace: bool = Query(False, description="Replace existing measurements before inserting new rows."),
):
    payload = await file.read()
    content = payload.decode("utf-8-sig")
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    rows = _parse_upload_content(content)
    if not rows:
        raise HTTPException(status_code=400, detail="No valid rows found in upload")

    converted_name = f"{os.path.splitext(file.filename)[0]}_converted.csv"
    converted_dir = os.path.join(os.path.dirname(__file__), "converted_uploads")
    os.makedirs(converted_dir, exist_ok=True)
    converted_path = os.path.join(converted_dir, converted_name)
    with open(converted_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "x", "y", "temp", "thickness"])
        for row in rows:
            writer.writerow(
                [
                    row["measured_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    f"{row['lat']:.6f}",
                    f"{row['lng']:.6f}",
                    f"{row['temperature_c']:.2f}",
                    f"{row['thickness_cm']:.2f}",
                ]
            )

    with get_cursor(True) as cur:
        if replace:
            cur.execute("DELETE FROM ice_conditions;")
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO ice_conditions (
                lat, lng, thickness_cm, temperature_c, confidence_score, measured_at
            )
            VALUES (
                %(lat)s, %(lng)s, %(thickness_cm)s, %(temperature_c)s, %(confidence_score)s, %(measured_at)s
            );
            """,
            rows,
        )

    return {
        "status": "ok",
        "filename": file.filename,
        "inserted": len(rows),
        "replaced": replace,
        "converted_csv": converted_path,
    }


@app.post("/api/conditions/reset")
def reset_conditions():
    with get_cursor(True) as cur:
        cur.execute("DELETE FROM ice_conditions;")
    return {"status": "ok", "message": "All measurements removed"}


@app.get("/api/condition-dates")
def get_condition_dates(
    limit: int = Query(
        120,
        ge=1,
        le=200,
        description="Number of distinct dates to return (latest first)",
    )
):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT DATE(measured_at) AS day
            FROM ice_conditions
            ORDER BY day DESC
            LIMIT %s;
            """,
            (limit,),
        )
        rows = cur.fetchall()

    return [row["day"].isoformat() for row in rows]
