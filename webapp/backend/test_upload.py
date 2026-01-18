#!/usr/bin/env python3
"""
Simple test script to upload a CSV file and check all three tables.
Usage: python test_upload.py <path_to_csv_file>
"""

import requests
import sys
import json
from pathlib import Path

API_BASE = "http://localhost:8000"

def test_upload(csv_path: str):
    """Upload CSV file and check results."""
    print(f"Testing CSV upload: {csv_path}")
    print("-" * 60)
    
    # 1. Upload CSV file
    print("\n1. Uploading CSV file...")
    with open(csv_path, 'rb') as f:
        files = {'file': (Path(csv_path).name, f, 'text/csv')}
        data = {
            'date': '2026-01-16 09:35:20',
            'location': 'Rideau Canal',
            'notes': 'Test upload'
        }
        
        try:
            response = requests.post(f"{API_BASE}/flights", files=files, data=data)
            response.raise_for_status()
            result = response.json()
            print(f"✅ Upload successful!")
            print(f"   Flight ID: {result['flight_id']}")
            print(f"   Status: {result['status']}")
            print(f"   Message: {result['message']}")
            flight_id = result['flight_id']
        except requests.exceptions.RequestException as e:
            print(f"❌ Upload failed: {e}")
            if hasattr(e.response, 'text'):
                print(f"   Error details: {e.response.text}")
            return
    
    # 2. Check flights table
    print("\n2. Checking flights table...")
    try:
        response = requests.get(f"{API_BASE}/flights")
        response.raise_for_status()
        flights = response.json()
        print(f"✅ Found {len(flights)} flight(s)")
        for flight in flights:
            if flight['flight_id'] == flight_id:
                print(f"   Flight {flight_id}: {flight['date']} - {flight['location']}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to get flights: {e}")
    
    # 3. Check raw_measurements table
    print(f"\n3. Checking raw_measurements table (flight_id={flight_id})...")
    try:
        response = requests.get(f"{API_BASE}/raw_measurements?flight_id={flight_id}")
        response.raise_for_status()
        raw_measurements = response.json()
        print(f"✅ Found {len(raw_measurements)} raw measurement(s)")
        if raw_measurements:
            print(f"   First measurement ID: {raw_measurements[0]['measurement_id']}")
            print(f"   Has FFT data: {len(raw_measurements[0].get('fft_data', []))} values")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to get raw measurements: {e}")
    
    # 4. Check cleaned_measurements table
    print(f"\n4. Checking cleaned_measurements table (flight_id={flight_id})...")
    try:
        response = requests.get(f"{API_BASE}/cleaned_measurements?flight_ids={flight_id}")
        response.raise_for_status()
        cleaned_measurements = response.json()
        print(f"✅ Found {len(cleaned_measurements)} cleaned measurement(s)")
        if cleaned_measurements:
            first = cleaned_measurements[0]
            print(f"   First measurement ID: {first['cleaned_id']}")
            print(f"   Thickness: {first.get('thickness', 'N/A')} cm")
            print(f"   Quality Score: {first.get('quality_score', 'N/A'):.3f}")
            print(f"   Linked to raw_id: {first.get('raw_id', 'N/A')}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to get cleaned measurements: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print(f"\nTo view all data, visit:")
    print(f"  Flights: {API_BASE}/flights")
    print(f"  Raw Measurements: {API_BASE}/raw_measurements?flight_id={flight_id}")
    print(f"  Cleaned Measurements: {API_BASE}/cleaned_measurements?flight_ids={flight_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_upload.py <path_to_csv_file>")
        print("Example: python test_upload.py snow_angel_uav_raw.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    if not Path(csv_path).exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)
    
    test_upload(csv_path)
