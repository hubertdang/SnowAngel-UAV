"""Temporary FastAPI backend powering the Ice Thickness Visualizer prototype."""

from __future__ import annotations

import contextlib
import os
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

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "snowangel"),
    "user": os.getenv("DB_USER", "snowangel"),
    "password": os.getenv("DB_PASS", "snowangel"),
}


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
                confidence_score NUMERIC(3, 2) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
                measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                location_label TEXT DEFAULT 'Rideau Canal',
                notes TEXT
            );
            """
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
        SELECT id, lat, lng, thickness_cm, confidence_score, measured_at, notes
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
async def upload_csv(file: UploadFile = File(...)):
    # File will be parsed in a later iteration; for now we simply acknowledge receipt.
    _ = await file.read()
    return {"status": "received", "filename": file.filename}


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
