#!/usr/bin/env python3
"""Populate the ice_conditions table with dummy Rideau Canal heat data."""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from typing import Iterable, List

import psycopg2
import psycopg2.extras

RIDEAU_PATH = [
    (45.3848, -75.7047),  # Carleton University locks
    (45.3884, -75.7028),
    (45.3928, -75.7059),  # Dow's Lake south edge
    (45.3968, -75.7063),
    (45.4006, -75.7027),  # Dow's Lake east narrows
    (45.4039, -75.6977),  # Lansdowne
    (45.4076, -75.6937),
    (45.4112, -75.6902),  # Bank St bridge
    (45.4148, -75.6866),
    (45.4184, -75.6847),  # Somerset / Pretoria
    (45.4226, -75.6843),
    (45.4261, -75.6868),
    (45.4296, -75.6909),  # Rideau / Wellington
]

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "snowangel"),
    "user": os.getenv("DB_USER", "snowangel"),
    "password": os.getenv("DB_PASS", "snowangel"),
}


@dataclass
class IceSample:
    lat: float
    lng: float
    thickness_cm: float
    confidence_score: float
    measured_at: datetime
    notes: str


def interpolate(coord_a, coord_b, ratio: float) -> float:
    return coord_a + (coord_b - coord_a) * ratio


def day_profile(day_index: int) -> dict:
    if day_index == 0:
        return {"confidence_bias": 0.82, "thickness_center": 26, "thin_probability": 0.05}
    if day_index == 1:
        return {"confidence_bias": 0.65, "thickness_center": 21, "thin_probability": 0.12}
    return {"confidence_bias": 0.45, "thickness_center": 14, "thin_probability": 0.28}


def random_time_within(day: date) -> datetime:
    minutes = random.randint(0, 23 * 60 + 59)
    hour = minutes // 60
    minute = minutes % 60
    return datetime.combine(day, time(hour=hour, minute=minute))


def generate_samples(days: int, count_per_day: int) -> Iterable[IceSample]:
    start_day = datetime.utcnow().date()
    for idx in range(days):
        target_day = start_day - timedelta(days=idx)
        profile = day_profile(idx)

        for _ in range(count_per_day):
            segment = random.randint(0, len(RIDEAU_PATH) - 2)
            ratio = random.random()
            base_lat = interpolate(RIDEAU_PATH[segment][0], RIDEAU_PATH[segment + 1][0], ratio)
            base_lng = interpolate(RIDEAU_PATH[segment][1], RIDEAU_PATH[segment + 1][1], ratio)

            lat = base_lat + random.uniform(-0.0006, 0.0006)
            lng = base_lng + random.uniform(-0.0008, 0.0008)

            confidence = max(0.05, min(0.98, random.gauss(profile["confidence_bias"], 0.14)))

            if random.random() < profile["thin_probability"]:
                thickness = random.uniform(4.0, 10.0)
                confidence = min(confidence, 0.35)
                note = "Thin ice"
            else:
                thickness = max(2.0, min(40.0, random.gauss(profile["thickness_center"], 3.5)))
                note = "Great conditions" if confidence > 0.7 else "Use caution"

            measured_at = random_time_within(target_day)

            yield IceSample(
                lat=round(lat, 6),
                lng=round(lng, 6),
                thickness_cm=round(thickness, 1),
                confidence_score=round(confidence, 2),
                measured_at=measured_at,
                notes=note,
            )


def ensure_table(conn) -> None:
    with conn.cursor() as cur:
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
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ice_conditions_lat_lng ON ice_conditions (lat, lng)")
    conn.commit()


def insert_samples(conn, samples: List[IceSample], append: bool) -> None:
    with conn.cursor() as cur:
        if not append:
            cur.execute("DELETE FROM ice_conditions")
        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO ice_conditions (lat, lng, thickness_cm, confidence_score, measured_at, notes)
            VALUES (%(lat)s, %(lng)s, %(thickness_cm)s, %(confidence_score)s, %(measured_at)s, %(notes)s)
            """,
            [sample.__dict__ for sample in samples],
        )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=250, help="Samples to generate per day")
    parser.add_argument("--days", type=int, default=3, help="How many distinct days of data to seed")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing rows instead of replacing them",
    )
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        ensure_table(conn)
        samples = list(generate_samples(args.days, args.count))
        insert_samples(conn, samples, append=args.append)
        print(f"Inserted {len(samples)} synthetic samples into ice_conditions table")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
