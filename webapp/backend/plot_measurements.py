#!/usr/bin/env python3
"""
Plot measurement data: measurement number vs thickness and temperature.

Usage:
    python plot_measurements.py [flight_id]
    
    If flight_id is provided, plots only that flight.
    If no flight_id, plots all flights.
"""

import os
import sys
import requests
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional, List, Dict


API_BASE = os.getenv("API_BASE", "http://localhost:8000")


def get_measurements(flight_id: Optional[int] = None) -> List[Dict]:
    """
    Fetch cleaned measurements from API.
    
    Args:
        flight_id: Optional flight_id to filter by. If None, gets all flights.
        
    Returns:
        List of measurement dictionaries
    """
    try:
        if flight_id:
            # Get measurements for specific flight
            response = requests.get(f"{API_BASE}/cleaned_measurements", 
                                  params={"flight_ids": str(flight_id)})
        else:
            # Get all measurements
            response = requests.get(f"{API_BASE}/cleaned_measurements")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to API at {API_BASE}")
        print("Make sure the backend server is running:")
        print("  docker-compose up backend")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"❌ API error: {e}")
        if e.response.status_code == 404:
            print(f"Flight {flight_id} not found.")
        sys.exit(1)


def get_flight_info(flight_id: int) -> Optional[Dict]:
    """Get flight information from API."""
    try:
        response = requests.get(f"{API_BASE}/flights/{flight_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError:
        return None


def plot_measurements(measurements: List[Dict], flight_id: Optional[int] = None):
    """
    Plot measurement number vs thickness and temperature.
    
    Args:
        measurements: List of measurement dictionaries
        flight_id: Optional flight_id for title
    """
    if not measurements:
        print("No measurements to plot.")
        return
    
    # Extract data
    measurement_numbers = list(range(1, len(measurements) + 1))
    thicknesses = [m["thickness"] for m in measurements if m["thickness"] is not None]
    temperatures = [m["temperature"] for m in measurements if m["temperature"] is not None]
    raw_counts = [m.get("raw_count", 0) for m in measurements]
    
    # Get measurement numbers for valid data
    thickness_indices = [i + 1 for i, m in enumerate(measurements) if m["thickness"] is not None]
    temp_indices = [i + 1 for i, m in enumerate(measurements) if m["temperature"] is not None]
    
    # Create figure with two y-axes
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    # Plot thickness on left y-axis
    color1 = 'tab:blue'
    ax1.set_xlabel('Measurement Number', fontsize=12)
    ax1.set_ylabel('Thickness (cm)', color=color1, fontsize=12)
    line1 = ax1.plot(thickness_indices, thicknesses, 'o-', color=color1, 
                     label='Thickness', markersize=4, linewidth=1.5)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True, alpha=0.3)
    
    # Plot temperature on right y-axis
    ax2 = ax1.twinx()
    color2 = 'tab:red'
    ax2.set_ylabel('Temperature (°C)', color=color2, fontsize=12)
    line2 = ax2.plot(temp_indices, temperatures, 's-', color=color2, 
                     label='Temperature', markersize=4, linewidth=1.5, alpha=0.7)
    ax2.tick_params(axis='y', labelcolor=color2)
    
    # Title
    if flight_id:
        flight_info = get_flight_info(flight_id)
        if flight_info:
            title = f"Flight {flight_id} - {flight_info['date']}"
            if flight_info['location']:
                title += f" ({flight_info['location']})"
        else:
            title = f"Flight {flight_id}"
    else:
        # Group by flight_id for multi-flight plot
        flight_ids = sorted(set(m["flight_id"] for m in measurements))
        title = f"All Flights: {', '.join(map(str, flight_ids))}"
    
    plt.title(title, fontsize=14, fontweight='bold')
    
    # Add legend
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    
    # Add statistics text
    if thicknesses:
        avg_thickness = np.mean(thicknesses)
        std_thickness = np.std(thicknesses)
        stats_text = f'Thickness: μ={avg_thickness:.2f}cm, σ={std_thickness:.2f}cm'
    else:
        stats_text = 'Thickness: No data'
    
    if temperatures:
        avg_temp = np.mean(temperatures)
        std_temp = np.std(temperatures)
        stats_text += f'\nTemperature: μ={avg_temp:.2f}°C, σ={std_temp:.2f}°C'
    
    # Add raw measurement count info
    if raw_counts:
        total_raw = sum(raw_counts)
        avg_raw = np.mean(raw_counts)
        max_raw = max(raw_counts)
        stats_text += f'\nRaw measurements: total={total_raw}, avg={avg_raw:.1f}/point, max={max_raw}'
    
    plt.figtext(0.02, 0.02, stats_text, fontsize=9, 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Add raw count annotations on the plot
    if raw_counts and any(rc > 1 for rc in raw_counts):
        # Annotate points that have multiple raw measurements
        for i, m in enumerate(measurements):
            if m.get("thickness") is not None:
                raw_count = m.get("raw_count", 0)
                if raw_count > 1:
                    measurement_num = i + 1
                    thickness_val = m["thickness"]
                    ax1.annotate(f'{raw_count}x', 
                               xy=(measurement_num, thickness_val), 
                               xytext=(5, 5), textcoords='offset points',
                               fontsize=7, alpha=0.6, color='blue')
    
    plt.tight_layout()
    plt.show()


def main():
    """Main function."""
    flight_id = None
    
    if len(sys.argv) > 1:
        try:
            flight_id = int(sys.argv[1])
        except ValueError:
            print(f"Error: Invalid flight_id '{sys.argv[1]}'. Must be an integer.")
            sys.exit(1)
    
    print(f"Fetching measurements from API{' for flight ' + str(flight_id) if flight_id else ' (all flights)'}...")
    measurements = get_measurements(flight_id)
    
    if not measurements:
        print("No measurements found.")
        sys.exit(0)
    
    print(f"Found {len(measurements)} measurements.")
    
    # Group by flight_id if plotting all flights
    if flight_id is None:
        flight_ids = sorted(set(m["flight_id"] for m in measurements))
        if len(flight_ids) > 1:
            print(f"Found {len(flight_ids)} flights: {', '.join(map(str, flight_ids))}")
            print("Plotting all flights together. Use flight_id argument to plot individual flights.")
    
    plot_measurements(measurements, flight_id)


if __name__ == "__main__":
    main()
