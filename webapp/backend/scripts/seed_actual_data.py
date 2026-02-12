#!/usr/bin/env python3
"""Populate the ice_conditions table with the provided measurement set."""

from __future__ import annotations

import os
from datetime import datetime
from typing import List

import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "snowangel"),
    "user": os.getenv("DB_USER", "snowangel"),
    "password": os.getenv("DB_PASS", "snowangel"),
}

RAW_POINTS = [
    ("2026-01-16 09:35:20", 45.402968, -75.680595, -10.4, 36.0),
    ("2026-01-16 09:35:22", 45.402968, -75.680595, -10.4, 34.1),
    ("2026-01-16 09:35:23", 45.402968, -75.680595, -10.3, 30.3),
    ("2026-01-16 09:35:25", 45.402968, -75.680595, -10.3, 28.4),
    ("2026-01-16 09:35:25", 45.402968, -75.680595, -10.3, 20.8),
    ("2026-01-16 09:35:28", 45.402968, -75.680595, -10.3, 20.8),
    ("2026-01-16 09:35:28", 45.402968, -75.680595, -10.2, 20.8),
    ("2026-01-16 09:35:31", 45.402968, -75.680595, -10.2, 20.8),
    ("2026-01-16 09:35:34", 45.402968, -75.680595, -10.2, 20.8),
    ("2026-01-16 09:35:37", 45.402968, -75.680595, -10.4, 24.6),
    ("2026-01-16 09:37:11", 45.402998, -75.680700, -16.0, 22.7),
    ("2026-01-16 09:37:11", 45.402998, -75.680700, -16.0, 26.5),
    ("2026-01-16 09:37:14", 45.402998, -75.680700, -15.9, 26.5),
    ("2026-01-16 09:37:14", 45.402998, -75.680700, -15.9, 28.4),
]


def ensure_table(conn) -> None:
    with conn.cursor() as cur:
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
            )
            """
        )
        cur.execute("ALTER TABLE ice_conditions ADD COLUMN IF NOT EXISTS temperature_c NUMERIC(5, 2)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ice_conditions_lat_lng ON ice_conditions (lat, lng)")
    conn.commit()


def build_rows() -> List[dict]:
    rows = []
    for timestamp, lat, lng, temp, thickness in RAW_POINTS:
        rows.append(
            {
                "lat": lat,
                "lng": lng,
                "thickness_cm": thickness,
                "temperature_c": temp,
                "confidence_score": 1.0,
                "measured_at": datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S"),
            }
        )
    return rows


def main() -> None:
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ice_conditions")
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO ice_conditions (
                    lat, lng, thickness_cm, temperature_c, confidence_score, measured_at
                )
                VALUES (
                    %(lat)s, %(lng)s, %(thickness_cm)s, %(temperature_c)s, %(confidence_score)s, %(measured_at)s
                )
                """,
                build_rows(),
            )
        conn.commit()
        print(f"Inserted {len(RAW_POINTS)} measurements.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
