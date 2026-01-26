"""Ice Measurement API backend for SnowAngel UAV."""

from __future__ import annotations

import asyncio
import contextlib
import csv
import logging
import math
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import httpx
import numpy as np
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from scipy.signal import find_peaks
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "snowangel"),
    "user": os.getenv("DB_USER", "snowangel"),
    "password": os.getenv("DB_PASS", "snowangel"),
}

# File upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# isitwater API configuration
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
ISITWATER_API_URL = "https://isitwater-com.p.rapidapi.com/"
ISITWATER_HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "isitwater-com.p.rapidapi.com",
}

# Cache for water check results to avoid redundant API calls
# Key: (latitude, longitude) tuple, Value: bool (True if water, False if land)
_WATER_CHECK_CACHE: dict[tuple[float, float], bool] = {}

# FMCW Radar constants (from ops_serial.py)
SAMPLING_RATE = 80000.0  # 80kHz
C = 3e8  # speed of light
BW = 990e6  # 990 MHz Bandwidth
T_CHIRP = 1.6e-3  # 1.6 ms chirp duration
S = BW / T_CHIRP  # chirp slope (Hz/s)
N_FULL = 1024
N = 512  # FFT is symmetric, so full length is double
BIN_SPACING = SAMPLING_RATE / N_FULL
FREQ_AXIS = np.arange(N) * BIN_SPACING
HZ_TO_M = C / (2 * S)
RANGE_AXIS = FREQ_AXIS * HZ_TO_M  # Range in meters for each bin


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
    """Create database tables if they don't exist."""
    with get_cursor(True) as cur:
        # Create flights table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS flights (
                flight_id SERIAL PRIMARY KEY,
                date TIMESTAMP NOT NULL,
                location TEXT,
                notes TEXT
            );
            """
        )

        # Create cleaned_measurements table first (raw_measurements references it)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cleaned_measurements (
                cleaned_id SERIAL PRIMARY KEY,
                flight_id INTEGER NOT NULL REFERENCES flights(flight_id) ON DELETE CASCADE,
                timestamp TIMESTAMP NOT NULL,
                coordinates POINT,
                temperature FLOAT,
                thickness FLOAT,
                quality_score FLOAT,
                processed_at TIMESTAMP
            );
            """
        )
        
        # Migration: Remove raw_id column from cleaned_measurements if it exists (old schema)
        cur.execute("""
            DO $$ 
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'cleaned_measurements' 
                    AND column_name = 'raw_id'
                ) THEN
                    ALTER TABLE cleaned_measurements DROP COLUMN raw_id CASCADE;
                END IF;
            END $$;
        """)

        # Create raw_measurements table
        # cleaned_id is nullable - NULL means this raw measurement wasn't included in any cleaned measurement
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_measurements (
                measurement_id SERIAL PRIMARY KEY,
                flight_id INTEGER NOT NULL REFERENCES flights(flight_id) ON DELETE CASCADE,
                timestamp TIMESTAMP NOT NULL,
                coordinates POINT,
                temperature FLOAT,
                fft_data FLOAT[],
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """
        )
        
        # Migration: Add cleaned_id column to raw_measurements if it doesn't exist
        cur.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'raw_measurements' 
                    AND column_name = 'cleaned_id'
                ) THEN
                    ALTER TABLE raw_measurements 
                    ADD COLUMN cleaned_id INTEGER REFERENCES cleaned_measurements(cleaned_id) ON DELETE SET NULL;
                END IF;
            END $$;
        """)

        # Create indexes for better query performance
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_raw_measurements_flight_id ON raw_measurements (flight_id);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_raw_measurements_cleaned_id ON raw_measurements (cleaned_id);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cleaned_measurements_flight_id ON cleaned_measurements (flight_id);"
        )


app = FastAPI(title="Ice Measurement API")

allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Log incoming request
        logger.info(f"→ {method} {path}")
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            status_code = response.status_code
            
            # Log response
            logger.info(f"← {method} {path} - {status_code} ({process_time:.3f}s)")
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"✗ {method} {path} - ERROR after {process_time:.3f}s: {type(e).__name__} - {e}")
            raise


app.add_middleware(LoggingMiddleware)


@app.on_event("startup")
def startup_event() -> None:
    """Initialize database tables on application startup."""
    ensure_tables()
    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(exist_ok=True)


@app.get("/")
def root():
    return {"message": "Ice Measurement API is running"}


@app.get("/api/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/api/summary")
def get_summary(flight_id: Optional[int] = Query(None, description="Filter by flight_id")):
    """
    Get summary statistics for all three tables.
    Useful for testing and debugging.
    """
    with get_cursor() as cur:
        # Count flights
        if flight_id:
            cur.execute("SELECT COUNT(*) as count FROM flights WHERE flight_id = %s;", (flight_id,))
        else:
            cur.execute("SELECT COUNT(*) as count FROM flights;")
        flights_count = cur.fetchone()["count"]
        
        # Count raw measurements
        if flight_id:
            cur.execute("SELECT COUNT(*) as count FROM raw_measurements WHERE flight_id = %s;", (flight_id,))
        else:
            cur.execute("SELECT COUNT(*) as count FROM raw_measurements;")
        raw_count = cur.fetchone()["count"]
        
        # Count cleaned measurements
        if flight_id:
            cur.execute("SELECT COUNT(*) as count FROM cleaned_measurements WHERE flight_id = %s;", (flight_id,))
        else:
            cur.execute("SELECT COUNT(*) as count FROM cleaned_measurements;")
        cleaned_count = cur.fetchone()["count"]
    
    return {
        "flights": flights_count,
        "raw_measurements": raw_count,
        "cleaned_measurements": cleaned_count,
        "filtered_by_flight_id": flight_id,
    }


# --- Helper Functions ---


async def _is_water(latitude: float, longitude: float) -> bool:
    """
    Check if coordinates are over water using isitwater API.
    Uses a cache to avoid redundant API calls for the same coordinates.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        True if coordinates are over water, False if over land
        Returns False if API call fails (fail-safe: don't insert on error)
    """
    if not RAPIDAPI_KEY:
        # If no API key, skip filtering (return True to allow all measurements)
        # In production, you might want to raise an error instead
        logger.debug(f"Skipping water check for ({latitude}, {longitude}): No API key configured")
        return True
    
    # Check cache first to avoid redundant API calls
    coord_key = (latitude, longitude)
    if coord_key in _WATER_CHECK_CACHE:
        cached_result = _WATER_CHECK_CACHE[coord_key]
        logger.info(f"Water check CACHE HIT for ({latitude}, {longitude}): {'water' if cached_result else 'land'}")
        return cached_result
    
    # Make API call if not in cache
    logger.info(f"Water check API CALL for ({latitude}, {longitude})")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                ISITWATER_API_URL,
                headers=ISITWATER_HEADERS,
                params={"latitude": str(latitude), "longitude": str(longitude)},
            )
            response.raise_for_status()
            data = response.json()
            is_water = data.get("water", False)
            # Cache the result
            _WATER_CHECK_CACHE[coord_key] = is_water
            result_type = "water" if is_water else "land"
            logger.info(f"Water check API SUCCESS for ({latitude}, {longitude}): {result_type} (cached)")
            return is_water
    except httpx.HTTPStatusError as e:
        # HTTP error (e.g., 429 rate limit)
        logger.error(f"Water check API HTTP ERROR for ({latitude}, {longitude}): {e.response.status_code} - {e}")
        _WATER_CHECK_CACHE[coord_key] = False
        return False
    except Exception as e:
        # On API error, be conservative: don't insert (return False)
        # Cache the error result to avoid retrying failed coordinates
        logger.error(f"Water check API ERROR for ({latitude}, {longitude}): {type(e).__name__} - {e}")
        _WATER_CHECK_CACHE[coord_key] = False
        return False


async def _filter_water_measurements(measurements: List[dict]) -> List[dict]:
    """
    Filter measurements to keep only those over water.
    Uses caching to avoid redundant API calls for duplicate coordinates.
    
    Args:
        measurements: List of parsed measurement dictionaries
        
    Returns:
        List of measurements that are over water
    """
    logger.info(f"Starting water filter for {len(measurements)} measurements")
    water_measurements = []
    last_coord_key = None
    api_call_count = 0
    cache_hit_count = 0
    
    for measurement in measurements:
        coords = measurement["coordinates"]
        latitude = coords[1]
        longitude = coords[0]
        coord_key = (latitude, longitude)
        
        # Check if we need to make an API call (not in cache)
        # Only delay before making API calls, not for cached results
        needs_api_call = coord_key not in _WATER_CHECK_CACHE
        
        if needs_api_call:
            api_call_count += 1
            if coord_key != last_coord_key:
                # Add delay before making API call to avoid rate limiting
                # (plan allows 1 request per second, using 3s to be safe)
                logger.debug(f"Rate limiting delay: 3s before API call for ({latitude}, {longitude})")
                await asyncio.sleep(3)
        else:
            cache_hit_count += 1
        
        if await _is_water(latitude, longitude):
            water_measurements.append(measurement)
        
        last_coord_key = coord_key
    
    logger.info(f"Water filter complete: {len(water_measurements)}/{len(measurements)} measurements over water "
                f"(API calls: {api_call_count}, cache hits: {cache_hit_count}, cache size: {len(_WATER_CHECK_CACHE)})")
    return water_measurements


def _distance_between_coords(coord1: tuple, coord2: tuple) -> float:
    """
    Calculate distance in meters between two coordinates using Haversine formula.
    
    Args:
        coord1: Tuple of (longitude, latitude)
        coord2: Tuple of (longitude, latitude)
        
    Returns:
        Distance in meters
    """
    # Earth radius in meters
    R = 6371000
    
    lon1, lat1 = math.radians(coord1[0]), math.radians(coord1[1])
    lon2, lat2 = math.radians(coord2[0]), math.radians(coord2[1])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def _combine_measurements(measurements: List[dict]) -> dict:
    """
    Combine multiple measurements by averaging coordinates and FFT data.
    
    Args:
        measurements: List of measurement dictionaries to combine
        
    Returns:
        Combined measurement dictionary
    """
    if not measurements:
        raise ValueError("Cannot combine empty list of measurements")
    
    if len(measurements) == 1:
        return measurements[0]
    
    # Average coordinates
    total_lon = sum(m["coordinates"][0] for m in measurements)
    total_lat = sum(m["coordinates"][1] for m in measurements)
    avg_lon = total_lon / len(measurements)
    avg_lat = total_lat / len(measurements)
    
    # Average temperature (could be weighted or simple average)
    avg_temp = sum(m["temperature"] for m in measurements) / len(measurements)
    
    # Average FFT data - handle different lengths
    fft_arrays = [m["fft_data"] for m in measurements]
    max_length = max(len(fft) for fft in fft_arrays)
    
    combined_fft = []
    for idx in range(max_length):
        values_at_idx = []
        for fft_array in fft_arrays:
            if idx < len(fft_array):
                values_at_idx.append(fft_array[idx])
        
        if values_at_idx:
            # Average values at this index (only from arrays that have this index)
            avg_value = sum(values_at_idx) / len(values_at_idx)
            combined_fft.append(avg_value)
        else:
            # This shouldn't happen, but handle edge case
            break
    
    # Use the earliest timestamp from the combined measurements
    earliest_timestamp = min(m["timestamp"] for m in measurements)
    
    # Use the first measurement's flight_id (all should be the same)
    flight_id = measurements[0]["flight_id"]
    
    # Strategy: Average FFT data, then reprocess (better signal processing)
    # This reduces noise and gives more accurate peak detection on the averaged signal
    thickness, quality_score = _process_fft_to_thickness(combined_fft)
    
    # Fallback: If averaged FFT fails validation, average the individual thickness values
    # This can happen if averaging smooths out peaks too much
    if thickness is None or quality_score is None:
        # Fallback to averaging individual thickness/quality_score values
        thicknesses = [m.get("thickness") for m in measurements if m.get("thickness") is not None]
        quality_scores = [m.get("quality_score") for m in measurements if m.get("quality_score") is not None]
        
        if thicknesses and quality_scores:
            thickness = sum(thicknesses) / len(thicknesses)
            quality_score = sum(quality_scores) / len(quality_scores)
            logger.debug(f"Fell back to averaging thickness values (averaged FFT failed validation)")
        else:
            # No valid thickness values to average
            return None
    
    combined_measurement = {
        "flight_id": flight_id,
        "timestamp": earliest_timestamp,
        "coordinates": (avg_lon, avg_lat),
        "temperature": avg_temp,
        "fft_data": combined_fft,
        "thickness": thickness,
        "quality_score": quality_score,
        "created_at": datetime.now(),
    }
    
    return combined_measurement


def _combine_same_coordinates(measurements: List[dict]) -> List[dict]:
    """
    Combine measurements that have identical coordinates (exact match).
    Only measurements with the exact same (longitude, latitude) are combined.
    
    Args:
        measurements: List of measurement dictionaries (should already be FFT-validated)
        
    Returns:
        List of combined measurements
    """
    if not measurements:
        return []
    
    logger.info(f"Combining measurements with identical coordinates: {len(measurements)} input")
    
    # Group measurements by their coordinates
    coord_groups = {}
    for measurement in measurements:
        coords = measurement["coordinates"]
        # Use tuple as key for exact coordinate matching
        coord_key = (coords[0], coords[1])
        
        if coord_key not in coord_groups:
            coord_groups[coord_key] = []
        coord_groups[coord_key].append(measurement)
    
    # Combine measurements within each coordinate group
    combined = []
    cluster_sizes = []
    failed_after_combining = 0
    
    for coord_key, group in coord_groups.items():
        if len(group) == 1:
            # Single measurement at this coordinate, no combining needed
            # It already has thickness and quality_score from FFT validation
            measurement = group[0]
            # Track which raw measurement IDs went into this cleaned measurement
            raw_id = measurement.get("_raw_measurement_id")
            if raw_id is not None:
                measurement["_source_raw_ids"] = [raw_id]
            else:
                logger.warning(f"Single measurement at {coord_key} has no _raw_measurement_id")
                measurement["_source_raw_ids"] = []
            combined.append(measurement)
            cluster_sizes.append(1)
        else:
            # Multiple measurements at same coordinate, combine them
            combined_measurement = _combine_measurements(group)
            # Verify that combined measurement is valid (has thickness/quality_score or None if failed)
            if combined_measurement is not None and "thickness" in combined_measurement and "quality_score" in combined_measurement:
                # Track which raw measurement IDs went into this combined cleaned measurement
                combined_measurement["_source_raw_ids"] = [
                    m.get("_raw_measurement_id") for m in group 
                    if m.get("_raw_measurement_id") is not None
                ]
                combined.append(combined_measurement)
                cluster_sizes.append(len(group))
            else:
                # Combined FFT failed validation and fallback also failed - skip this combined measurement
                failed_after_combining += 1
                logger.warning(f"Combined measurement failed after combining {len(group)} measurements at {coord_key} (both FFT reprocessing and thickness averaging failed)")
    
    if cluster_sizes:
        logger.info(f"Combined {len(measurements)} measurements into {len(combined)} groups. "
                   f"Group sizes: min={min(cluster_sizes)}, max={max(cluster_sizes)}, "
                   f"avg={sum(cluster_sizes)/len(cluster_sizes):.1f}")
        if failed_after_combining > 0:
            logger.warning(f"{failed_after_combining} combined measurements failed FFT validation after combining")
    
    return combined


def _combine_nearby_measurements(measurements: List[dict], distance_threshold_m: float = 5.0) -> List[dict]:
    """
    Combine measurements that are within the distance threshold of each other.
    Uses iterative expansion: starts with one measurement, combines nearby ones,
    then checks remaining measurements against the new combined coordinates.
    
    Example: If A->B (4m) and B->C (4m) but A->C (7m):
    - Start with A, find B within 5m, combine into AB
    - Check if C is within 5m of AB's new coordinates
    - If yes, add C; if no, leave C separate
    
    NOTE: This function is kept for reference but is no longer used in the pipeline.
    The pipeline now uses _combine_same_coordinates() instead.
    
    Args:
        measurements: List of measurement dictionaries
        distance_threshold_m: Distance threshold in meters (default: 5.0)
        
    Returns:
        List of combined measurements
    """
    if not measurements:
        return []
    
    logger.info(f"Combining nearby measurements: {len(measurements)} input, threshold: {distance_threshold_m}m")
    combined = []
    processed_indices = set()
    cluster_sizes = []
    
    for i, measurement in enumerate(measurements):
        if i in processed_indices:
            continue
        
        # Start with this measurement
        cluster = [measurement]
        cluster_indices = {i}
        
        # Iteratively expand the cluster
        # Keep checking until no new measurements are added
        changed = True
        while changed:
            changed = False
            current_combined = _combine_measurements(cluster)
            current_coords = current_combined["coordinates"]
            
            # Check all remaining measurements
            for j, other_measurement in enumerate(measurements):
                if j in cluster_indices or j in processed_indices:
                    continue
                
                # Check distance from combined coordinates to this measurement
                distance = _distance_between_coords(
                    current_coords,
                    other_measurement["coordinates"],
                )
                
                if distance <= distance_threshold_m:
                    # Add to cluster
                    cluster.append(other_measurement)
                    cluster_indices.add(j)
                    changed = True
        
        # Combine the final cluster
        combined_measurement = _combine_measurements(cluster)
        combined.append(combined_measurement)
        cluster_sizes.append(len(cluster))
        
        # Mark all measurements in cluster as processed
        processed_indices.update(cluster_indices)
    
    if cluster_sizes:
        logger.info(f"Combined {len(measurements)} measurements into {len(combined)} clusters. "
                   f"Cluster sizes: min={min(cluster_sizes)}, max={max(cluster_sizes)}, "
                   f"avg={sum(cluster_sizes)/len(cluster_sizes):.1f}")
    
    return combined


def _parse_csv_row(row: List[str], flight_id: int) -> dict:
    """
    Parse a single CSV row into a raw measurement dictionary.
    
    Expected format: Time,Longitude,Latitude,Temperature,FFT-Data...
    
    Args:
        row: List of strings from CSV row
        flight_id: The flight_id for this measurement
        
    Returns:
        Dictionary with parsed measurement data
    """
    if len(row) < 4:
        raise ValueError(f"CSV row must have at least 4 columns (Time, Longitude, Latitude, Temperature), got {len(row)}")
    
    # Parse timestamp (format: "2026-01-16 09:35:20")
    try:
        timestamp_str = row[0].strip()
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(f"Invalid timestamp format: {row[0]}") from e
    
    # Parse coordinates
    try:
        longitude = float(row[1].strip())
        latitude = float(row[2].strip())
    except ValueError as e:
        raise ValueError(f"Invalid coordinates: {row[1]}, {row[2]}") from e
    
    # Parse temperature
    try:
        temperature = float(row[3].strip())
    except ValueError as e:
        raise ValueError(f"Invalid temperature: {row[3]}") from e
    
    # Parse FFT data (everything from index 4 onwards)
    fft_data = []
    for i in range(4, len(row)):
        if row[i].strip():  # Skip empty values
            try:
                fft_data.append(float(row[i].strip()))
            except ValueError:
                # Skip invalid FFT values but log warning
                continue
    
    return {
        "flight_id": flight_id,
        "timestamp": timestamp,
        "coordinates": (longitude, latitude),  # PostgreSQL POINT format
        "temperature": temperature,
        "fft_data": fft_data,
        "created_at": datetime.now(),
    }


def _insert_raw_measurements_with_ids(raw_measurements: List[dict]) -> List[int]:
    """
    Insert parsed raw measurements into the raw_measurements table and return their IDs.
    Inserts ALL measurements (before validation) to preserve complete data.
    
    Args:
        raw_measurements: List of dictionaries containing measurement data
        
    Returns:
        List of measurement_id values in the same order as input measurements
    """
    if not raw_measurements:
        return []
    
    # Prepare data with properly formatted coordinates for PostgreSQL POINT type
    prepared_data = []
    for measurement in raw_measurements:
        coords = measurement["coordinates"]
        prepared_data.append({
            "flight_id": measurement["flight_id"],
            "timestamp": measurement["timestamp"],
            "longitude": coords[0],
            "latitude": coords[1],
            "temperature": measurement["temperature"],
            "fft_data": measurement["fft_data"],
            "created_at": measurement.get("created_at", datetime.now()),
        })
    
    measurement_ids = []
    with get_cursor(True) as cur:
        for data in prepared_data:
            cur.execute(
                """
                INSERT INTO raw_measurements (flight_id, timestamp, coordinates, temperature, fft_data, created_at)
                VALUES (%(flight_id)s, %(timestamp)s, POINT(%(longitude)s, %(latitude)s), %(temperature)s, %(fft_data)s, %(created_at)s)
                RETURNING measurement_id;
                """,
                data,
            )
            result = cur.fetchone()
            measurement_ids.append(result["measurement_id"])
    
    return measurement_ids


def _process_fft_to_thickness(fft_data: List[float]) -> Tuple[Optional[float], Optional[float]]:
    """
    Process FFT data to calculate ice thickness.
    
    Based on ops_serial.py calculation:
    - Finds peaks in valid range (0.1m to 1m)
    - Validates at least 2 peaks exist
    - Validates first peak magnitude > second peak magnitude
    - Calculates thickness as (r2 - r1) where r1, r2 are peak ranges
    
    Args:
        fft_data: List of FFT magnitude values
        
    Returns:
        Tuple of (thickness_in_cm, quality_score) or (None, None) if invalid
        quality_score: ratio of first peak to second peak magnitude
    """
    if not fft_data or len(fft_data) == 0:
        return None, None
    
    fft_array = np.array(fft_data, dtype=float)
    
    # Consider ranges between 0.1 m and 1 m only for peak detection
    valid = (RANGE_AXIS > 0.1) & (RANGE_AXIS < 1)
    valid_indices = np.where(valid)[0]
    
    if len(valid_indices) == 0:
        return None, None
    
    # Find peaks with same parameters as ops_serial.py
    peaks, properties = find_peaks(
        fft_array[valid_indices],
        distance=2,  # at least 2 bins apart (≈3.7 cm)
        prominence=0.003 * np.max(fft_array),
    )
    
    peaks = valid_indices[peaks]  # Convert back to original indices
    peaks = np.sort(peaks)[:2]  # Get the two smallest peak indices (closest ranges)
    
    # Validate: need at least 2 peaks
    if len(peaks) < 2:
        return None, None
    
    # Get peak ranges and magnitudes
    r1 = RANGE_AXIS[peaks[0]]
    r2 = RANGE_AXIS[peaks[1]]
    magnitude1 = fft_array[peaks[0]]
    magnitude2 = fft_array[peaks[1]]
    
    # Validate: first peak must be bigger than second peak
    if magnitude1 <= magnitude2:
        return None, None
    
    # Calculate ice thickness (difference between two peak ranges)
    ice_thickness_m = r2 - r1
    ice_thickness_cm = ice_thickness_m * 100
    
    # Calculate quality score (ratio of first to second peak)
    quality_score = float(magnitude1 / magnitude2) if magnitude2 > 0 else 1.0
    
    # Clamp quality score to reasonable range (0-1)
    quality_score = min(quality_score / 10.0, 1.0)  # Normalize (assuming max ratio ~10)
    
    return ice_thickness_cm, quality_score


def _process_and_validate_measurements(measurements: List[dict]) -> List[dict]:
    """
    Process FFT data for each measurement and validate peaks.
    Discards measurements that don't meet validation criteria.
    
    Args:
        measurements: List of measurement dictionaries with FFT data
        
    Returns:
        List of validated measurements with thickness and quality_score added
    """
    validated_measurements = []
    rejected_count = 0
    rejection_reasons = {"no_peaks": 0, "first_not_larger": 0, "invalid_range": 0}
    
    for measurement in measurements:
        fft_data = measurement.get("fft_data", [])
        thickness, quality_score = _process_fft_to_thickness(fft_data)
        
        if thickness is not None and quality_score is not None:
            # Add processed data to measurement
            measurement["thickness"] = thickness
            measurement["quality_score"] = quality_score
            validated_measurements.append(measurement)
        else:
            rejected_count += 1
            # Note: _process_fft_to_thickness doesn't return rejection reason,
            # so we can't track specific reasons without modifying it
    
    logger.info(f"FFT validation: {len(validated_measurements)} passed, {rejected_count} rejected "
               f"(need 2+ peaks in 0.1-1m range, first peak > second peak)")
    
    return validated_measurements


def _insert_cleaned_measurements(cleaned_measurements: List[dict]) -> List[int]:
    """
    Insert cleaned measurements into the cleaned_measurements table.
    
    Args:
        cleaned_measurements: List of dictionaries with processed measurement data
        Must include: flight_id, timestamp, coordinates, temperature, thickness, quality_score
        May include: raw_measurement_ids (list of raw measurement IDs that were combined)
        
    Returns:
        List of cleaned_id values in the same order as input measurements
    """
    if not cleaned_measurements:
        return []
    
    # Prepare data for insertion
    prepared_data = []
    for measurement in cleaned_measurements:
        coords = measurement["coordinates"]
        prepared_data.append({
            "flight_id": measurement["flight_id"],
            "timestamp": measurement["timestamp"],
            "longitude": coords[0],
            "latitude": coords[1],
            "temperature": measurement["temperature"],
            "thickness": measurement["thickness"],
            "quality_score": measurement["quality_score"],
            "processed_at": datetime.now(),
        })
    
    cleaned_ids = []
    with get_cursor(True) as cur:
        for data in prepared_data:
            cur.execute(
                """
                INSERT INTO cleaned_measurements (flight_id, timestamp, coordinates, temperature, thickness, quality_score, processed_at)
                VALUES (%(flight_id)s, %(timestamp)s, POINT(%(longitude)s, %(latitude)s), %(temperature)s, %(thickness)s, %(quality_score)s, %(processed_at)s)
                RETURNING cleaned_id;
                """,
                data,
            )
            result = cur.fetchone()
            cleaned_ids.append(result["cleaned_id"])
    
    return cleaned_ids


def _update_raw_measurements_with_cleaned_id(raw_measurement_ids: List[int], cleaned_id: int) -> None:
    """
    Update raw measurements to link them to a cleaned measurement.
    
    Args:
        raw_measurement_ids: List of raw measurement IDs that were combined into this cleaned measurement
        cleaned_id: The cleaned_id to link them to
    """
    if not raw_measurement_ids:
        return
    
    with get_cursor(True) as cur:
        # Update all raw measurements to point to this cleaned_id
        placeholders = ",".join(["%s"] * len(raw_measurement_ids))
        cur.execute(
            f"""
            UPDATE raw_measurements 
            SET cleaned_id = %s
            WHERE measurement_id IN ({placeholders});
            """,
            [cleaned_id] + raw_measurement_ids,
        )


async def process_and_clean_csv(file: UploadFile, file_path: Path, flight_id: int) -> None:
    """
    Process uploaded CSV file: save, parse, insert raw data, clean/process, insert cleaned data.
    
    This function handles all file operations:
    1. Saves the uploaded file to disk temporarily
    2. Reads and parses the CSV file
    3. Inserts rows into raw_measurements table
    4. Cleans and processes the raw data
    5. Inserts cleaned data into cleaned_measurements table
    6. Deletes the CSV file after processing
    
    Args:
        file: UploadFile object from FastAPI
        file_path: Path where the file should be saved (generated by caller)
        flight_id: The flight_id associated with this CSV data
        
    Raises:
        Exception: If processing fails, the caller should handle flight deletion
        Note: File will be deleted on both success and failure (via try/finally)
    """
    try:
        # Write file content to disk
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Read and parse CSV file (no headers - all rows are data)
        parsed_measurements = []
        with open(file_path, "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            
            # Process all rows as data (CSV has no headers)
            for row in reader:
                if row:  # Skip empty rows
                    try:
                        parsed_measurements.append(_parse_csv_row(row, flight_id))
                    except ValueError as e:
                        # Skip invalid rows, but continue processing
                        print(f"Warning: Skipping invalid row: {e}")
                        continue
        
        if not parsed_measurements:
            raise ValueError("CSV file is empty or contains no valid data rows")
        
        logger.info(f"Step 1: Parsed {len(parsed_measurements)} measurements from CSV")
        
        # Filter to keep only measurements over water (clean before inserting)
        # NOTE TODO TEMPORARILY DISABLED: Water check commented out due to API rate limit
        # water_measurements = await _filter_water_measurements(parsed_measurements)
        # if not water_measurements:
        #     raise ValueError("No measurements found over water. All measurements were filtered out.")
        water_measurements = parsed_measurements  # Bypass water check for testing
        logger.info(f"Step 2: After water filter (bypassed): {len(water_measurements)} measurements")
        
        # Insert ALL parsed measurements into raw_measurements FIRST (before validation/combining)
        # This preserves complete data even if some measurements fail validation
        # We do this early so we can track raw_measurement_id through the validation process
        logger.info(f"Step 2.5: Inserting all {len(water_measurements)} measurements into raw_measurements table...")
        raw_measurement_ids = _insert_raw_measurements_with_ids(water_measurements)
        
        # Create a mapping from measurement index to raw_measurement_id
        # This will be used later to link raw measurements to cleaned measurements
        for i, measurement in enumerate(water_measurements):
            measurement["_raw_measurement_id"] = raw_measurement_ids[i]
        
        # Process FFT data FIRST: calculate thickness and validate peaks
        # This filters out bad measurements before they can contaminate good ones through averaging
        # Discards measurements that don't have at least 2 peaks or where first peak <= second peak
        # Note: validated_measurements are references to water_measurements, so they'll have _raw_measurement_id
        validated_measurements = _process_and_validate_measurements(water_measurements)
        logger.info(f"Step 3: After FFT validation (need 2+ peaks, first > second): {len(validated_measurements)} measurements")
        
        if not validated_measurements:
            raise ValueError("No measurements passed FFT validation (need at least 2 peaks with first > second).")
        
        # Combine measurements with identical coordinates only (not nearby, exact match)
        # validated_measurements should have _raw_measurement_id since they reference water_measurements
        combined_measurements = _combine_same_coordinates(validated_measurements)
        logger.info(f"Step 4: After combining identical coordinates: {len(combined_measurements)} measurements")
        
        if not combined_measurements:
            raise ValueError("No measurements remaining after combining identical coordinates.")
        
        # Insert cleaned measurements and get their IDs
        cleaned_ids = _insert_cleaned_measurements(combined_measurements)
        
        # Update raw_measurements to link them to cleaned_measurements via cleaned_id
        # For each combined measurement, find all raw measurements that went into it
        linked_count = 0
        for i, cleaned_measurement in enumerate(combined_measurements):
            cleaned_id = cleaned_ids[i]
            
            # Get the raw measurement IDs that were combined into this cleaned measurement
            # The combined measurement should have a list of source measurements
            raw_ids_for_this_cleaned = cleaned_measurement.get("_source_raw_ids", [])
            
            if raw_ids_for_this_cleaned:
                # Filter out None values (in case some measurements didn't have _raw_measurement_id)
                raw_ids_for_this_cleaned = [rid for rid in raw_ids_for_this_cleaned if rid is not None]
                
                if raw_ids_for_this_cleaned:
                    _update_raw_measurements_with_cleaned_id(raw_ids_for_this_cleaned, cleaned_id)
                    linked_count += len(raw_ids_for_this_cleaned)
                    logger.info(f"Linked cleaned_id {cleaned_id} to {len(raw_ids_for_this_cleaned)} raw measurements: {raw_ids_for_this_cleaned}")
                else:
                    logger.warning(f"Cleaned measurement {cleaned_id} has _source_raw_ids but all are None - check if _raw_measurement_id was set")
            else:
                logger.warning(f"Cleaned measurement {cleaned_id} has no _source_raw_ids - cannot link to raw measurements. Measurement keys: {list(cleaned_measurement.keys())}")
        
        logger.info(f"Step 5: Inserted {len(combined_measurements)} cleaned measurements, linked {linked_count} raw measurements")
        
    finally:
        # Always delete the file after processing (success or failure)
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass  # Ignore cleanup errors


# --- Flight Endpoints ---


@app.post("/flights")
async def create_flight(
    date: str = Form(...),
    location: str = Form(...),
    notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """
    Create a new flight and process the uploaded measurement CSV file.
    
    - Creates a flight record in the flights table
    - Saves the uploaded CSV file temporarily
    - Processes the CSV to extract raw and cleaned measurements
    - Deletes the file after processing
    
    If processing fails, the flight record is deleted and an error is returned.
    """
    flight_id = None
    
    try:
        # Create flight record
        with get_cursor(True) as cur:
            cur.execute(
                "INSERT INTO flights (date, location, notes) VALUES (%s, %s, %s) RETURNING flight_id;",
                (date, location, notes),
            )
            result = cur.fetchone()
            flight_id = result["flight_id"]
        
        # Generate file path for CSV
        file_suffix = Path(file.filename).suffix if file.filename else ".csv"
        file_path = UPLOAD_DIR / f"flight_{flight_id}_{uuid.uuid4().hex[:8]}{file_suffix}"
        
        # Process the CSV file (helper handles file operations including deletion)
        await process_and_clean_csv(file, file_path, flight_id)
        
        return {
            "flight_id": flight_id,
            "status": "created",
            "file_received": file.filename,
            "message": "Flight created and measurements processed successfully",
        }
        
    except Exception as e:
        # Delete flight record if processing failed
        if flight_id:
            try:
                with get_cursor(True) as cur:
                    cur.execute("DELETE FROM flights WHERE flight_id = %s;", (flight_id,))
            except Exception:
                pass  # Ignore cleanup errors
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process flight: {str(e)}",
        )


@app.get("/flights")
def get_flights():
    """Return all flights from the flights table."""
    with get_cursor() as cur:
        cur.execute("SELECT flight_id, date, location, notes FROM flights ORDER BY flight_id;")
        rows = cur.fetchall()
    
    return [
        {
            "flight_id": row["flight_id"],
            "date": str(row["date"]),
            "location": row["location"],
            "notes": row["notes"],
        }
        for row in rows
    ]


@app.get("/flights/{flight_id}")
def get_flight(flight_id: int):
    """Get a specific flight by flight_id."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT flight_id, date, location, notes FROM flights WHERE flight_id = %s;",
            (flight_id,),
        )
        row = cur.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Flight {flight_id} not found")
    
    return {
        "flight_id": row["flight_id"],
        "date": str(row["date"]),
        "location": row["location"],
        "notes": row["notes"],
    }


@app.delete("/flights/{flight_id}")
def delete_flight(flight_id: int):
    """
    Delete a flight and all associated measurements.
    
    Note: Foreign key constraints will cascade delete raw_measurements
    and cleaned_measurements associated with this flight.
    """
    with get_cursor(True) as cur:
        cur.execute("DELETE FROM flights WHERE flight_id = %s RETURNING flight_id;", (flight_id,))
        result = cur.fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Flight {flight_id} not found")
    
    return {"status": "deleted", "flight_id": flight_id}


@app.delete("/flights")
def delete_all_flights():
    """
    Delete all flights and all associated measurements.
    
    Note: Foreign key constraints will cascade delete raw_measurements
    and cleaned_measurements associated with all flights.
    
    This is a destructive operation that cannot be undone.
    """
    with get_cursor(True) as cur:
        # Get count before deletion
        cur.execute("SELECT COUNT(*) as count FROM flights;")
        count_before = cur.fetchone()["count"]
        
        # Delete all flights (cascade will handle measurements)
        cur.execute("DELETE FROM flights;")
    
    return {
        "status": "deleted",
        "flights_deleted": count_before,
        "message": f"Deleted {count_before} flight(s) and all associated measurements",
    }


@app.post("/flights/{flight_id}/reprocess")
async def reprocess_flight(flight_id: int):
    """
    Manually trigger reprocessing of measurements for a flight.
    
    This endpoint allows you to re-run the processing pipeline for a flight
    if the initial processing failed or needs to be updated.
    
    Note: This requires the original CSV file to still exist, or you would need
    to reconstruct it from raw_measurements. For now, this is a placeholder.
    """
    # TODO: Implement reprocessing logic
    # This might require:
    # - Re-reading raw_measurements for the flight
    # - Re-running the cleaning/processing logic
    # - Updating cleaned_measurements
    
    raise HTTPException(
        status_code=501,
        detail="Reprocessing not yet implemented. This is a placeholder endpoint.",
    )


# --- Measurement Endpoints ---


@app.get("/raw_measurements")
def get_raw_measurements(flight_id: Optional[int] = Query(None, description="Filter by flight_id")):
    """
    Get raw measurements, optionally filtered by flight_id.
    
    If flight_id is provided, returns only measurements for that flight.
    Otherwise, returns all raw measurements.
    """
    with get_cursor() as cur:
        if flight_id:
            cur.execute(
                """
                SELECT measurement_id, flight_id, cleaned_id, timestamp, 
                       coordinates::text AS coordinates_text,
                       temperature, fft_data, created_at
                FROM raw_measurements
                WHERE flight_id = %s
                ORDER BY measurement_id;
                """,
                (flight_id,),
            )
        else:
            cur.execute(
                """
                SELECT measurement_id, flight_id, cleaned_id, timestamp, 
                       coordinates::text AS coordinates_text,
                       temperature, fft_data, created_at
                FROM raw_measurements
                ORDER BY measurement_id;
                """
            )
        rows = cur.fetchall()
    
    def parse_point(point_text: str) -> dict:
        """Parse PostgreSQL POINT text representation (x,y) to dict."""
        if not point_text:
            return None
        # POINT format is "(x,y)" - remove parentheses and split
        coords = point_text.strip("()").split(",")
        if len(coords) == 2:
            return {"x": float(coords[0]), "y": float(coords[1])}
        return None
    
    return [
        {
            "measurement_id": row["measurement_id"],
            "flight_id": row["flight_id"],
            "cleaned_id": row["cleaned_id"],
            "timestamp": str(row["timestamp"]),
            "coordinates": parse_point(row["coordinates_text"]),
            "temperature": row["temperature"],
            "fft_data": row["fft_data"],
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


@app.get("/cleaned_measurements")
def get_cleaned_measurements(
    flight_ids: Optional[str] = Query(
        None, description="Comma-separated list of flight_ids to filter by (e.g., '1,2,3')"
    ),
):
    """
    Get cleaned measurements, optionally filtered by flight_ids.
    
    If flight_ids is provided (comma-separated), returns only measurements
    for those flights. Otherwise, returns all cleaned measurements.
    """
    with get_cursor() as cur:
        if flight_ids:
            # Parse comma-separated flight_ids
            try:
                flight_id_list = [int(fid.strip()) for fid in flight_ids.split(",")]
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid flight_ids format. Use comma-separated integers."
                )
            
            # Use IN clause for multiple flight_ids
            placeholders = ",".join(["%s"] * len(flight_id_list))
            cur.execute(
                f"""
                SELECT c.cleaned_id, c.flight_id, c.timestamp, 
                       c.coordinates::text AS coordinates_text,
                       c.temperature, c.thickness, c.quality_score, c.processed_at,
                       COALESCE(COUNT(r.measurement_id), 0) AS raw_count
                FROM cleaned_measurements c
                LEFT JOIN raw_measurements r ON r.cleaned_id = c.cleaned_id
                WHERE c.flight_id IN ({placeholders})
                GROUP BY c.cleaned_id
                ORDER BY c.cleaned_id;
                """,
                flight_id_list,
            )
        else:
            cur.execute(
                """
                SELECT c.cleaned_id, c.flight_id, c.timestamp, 
                       c.coordinates::text AS coordinates_text,
                       c.temperature, c.thickness, c.quality_score, c.processed_at,
                       COALESCE(COUNT(r.measurement_id), 0) AS raw_count
                FROM cleaned_measurements c
                LEFT JOIN raw_measurements r ON r.cleaned_id = c.cleaned_id
                GROUP BY c.cleaned_id
                ORDER BY c.cleaned_id;
                """
            )
        rows = cur.fetchall()
    
    def parse_point(point_text: str) -> dict:
        """Parse PostgreSQL POINT text representation (x,y) to dict."""
        if not point_text:
            return None
        # POINT format is "(x,y)" - remove parentheses and split
        coords = point_text.strip("()").split(",")
        if len(coords) == 2:
            return {"x": float(coords[0]), "y": float(coords[1])}
        return None
    
    return [
        {
            "cleaned_id": row["cleaned_id"],
            "flight_id": row["flight_id"],
            "timestamp": str(row["timestamp"]),
            "coordinates": parse_point(row["coordinates_text"]),
            "temperature": row["temperature"],
            "thickness": row["thickness"],
            "quality_score": row["quality_score"],
            "processed_at": str(row["processed_at"]),
            "raw_count": row["raw_count"],
        }
        for row in rows
    ]
