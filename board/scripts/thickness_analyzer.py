#!/usr/bin/env python3
"""
Name: thickness_analyzer.py
Author: Karran Dhillon

Snow Thickness Measurement from FMCW Radar FFT Data

Parses CSV format: Date-Time,Longitude,Latitude,Temperature,FFT-Data
and estimates snow thickness using FMCW radar signal processing.

Date: January 2026

Copyright 2025 SnowAngel-UAV
"""

import sys
import csv
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from datetime import datetime
import folium
from folium.plugins import HeatMap


class ThicknessAnalyzer:
    """Analyze snow thickness from FMCW radar FFT data."""
    
    def __init__(self):
        # OPS241-B radar parameters
        self.sampling_rate = 80000.0    # 80 kHz (320kHz base; to keep 1.6ms chirp sampling rate quartered)
        self.c = 3e8                    # speed of light (m/s)
        self.BW = 990e6                 # 990 MHz Bandwidth of FMCW chirp
        self.T_chirp = 1.6e-3           # 1.6 ms chirp duration
        self.S = self.BW / self.T_chirp # chirp slope (Hz/s)
        
        # FFT parameters
        N_full = 1024
        N = 512  # FFT is symmetric, so full length is double
        
        self.N = N
        self.N_full = N_full
        self.bin_spacing = self.sampling_rate / N_full   # Hz/bin (312Hz/bin (312 Hz per point))
        self.freq_axis = np.arange(N) * self.bin_spacing # 0 Hz to (N-1)*bin_spacing
        
        # Convert frequency to range
        hz_to_m = self.c / (2 * self.S)  # m/Hz
        self.range_axis = self.freq_axis * hz_to_m
        
        print("[INFO] ThicknessAnalyzer initialized")
        print(f"[INFO] Radar range resolution: {self.c/(2*self.BW)*100:.2f} cm")
        print(f"[INFO] Frequency bin spacing: {self.bin_spacing:.1f} Hz")
        print(f"[INFO] Range bin spacing: {self.range_axis[1]-self.range_axis[0]:.4f} m")
    
    def parse_csv_line(self, line: str) -> dict:
        """
        Parse a CSV line with format:
        Date-Time,Latitude,Longitude,Temperature,FFT-Data
        
        Returns a dictionary with parsed fields.
        """
        parts = line.strip().split(',')
        
        expected_fields = 4 + self.N  # 4 metadata + 512 FFT bins
        if len(parts) != expected_fields:
            raise ValueError(f"Invalid CSV format: expected {expected_fields} fields, got {len(parts)}")
        
        timestamp = parts[0]
        latitude = float(parts[1])
        longitude = float(parts[2])
        temperature = float(parts[3])
        
        # Rest are FFT data points
        fft_data = np.array([float(x) for x in parts[4:]], dtype=float)

        if len(fft_data) != self.N:
            raise ValueError(f"Expected {self.N} FFT bins, got {len(fft_data)}")
        
        if len(fft_data) != self.N:
            raise ValueError(f"Expected {self.N} FFT bins, got {len(fft_data)}")

        return {
            'timestamp': timestamp,
            'longitude': longitude,
            'latitude': latitude,
            'temperature': temperature,
            'fft_data': fft_data,
            'raw_line': line
        }
    
    def analyze_fft(self, fft_data: np.ndarray, min_range=0.05, max_range=2.0) -> dict:
        """
        Analyze FFT data to find peaks and estimate thickness.
        
        Args:
            fft_data: FFT magnitude data array
            min_range: Minimum range to search (meters)
            max_range: Maximum range to search (meters)
        
        Returns:
            Dictionary with analysis results including estimated thickness
        """
        # Find valid range indices
        valid_mask = (self.range_axis >= min_range) & (self.range_axis <= max_range)
        valid_indices = np.where(valid_mask)[0]
        
        if len(valid_indices) == 0:
            return {'error': 'No valid range data in specified window'}
        
        valid_fft = fft_data[valid_indices]
        
        # Find peaks in the FFT data
        peak_prominence = 0.003 * np.max(valid_fft)
        peaks, peak_properties = find_peaks(
            valid_fft,
            distance=2,  # at least 2 bins apart (~3.7 cm)
            prominence=peak_prominence,
            height=0.01*np.max(fft_data)  # minimum height filter
        )
        
        # Convert back to original indices
        peaks = valid_indices[peaks]
        peaks = np.sort(peaks)
        
        result = {
            'num_peaks': len(peaks),
            'peak_indices': peaks.tolist(),
            'peak_ranges': self.range_axis[peaks].tolist(),
            'peak_magnitudes': fft_data[peaks].tolist(),
            'max_magnitude': np.max(fft_data),
            'noise_floor': np.min(fft_data),
            'snr_db': 20 * np.log10(np.max(fft_data) / (np.std(fft_data) + 1e-10))
        }
        
        # Estimate thickness from first two peaks (air/snow interface and snow/ground interface)
        if len(peaks) >= 2:
            r1 = self.range_axis[peaks[0]]
            r2 = self.range_axis[peaks[1]]
            thickness = abs(r2 - r1)
            
            result['thickness_m'] = thickness
            result['thickness_cm'] = thickness * 100
            result['first_peak_range_m'] = r1
            result['second_peak_range_m'] = r2
            result['first_peak_idx'] = int(peaks[0])
            result['second_peak_idx'] = int(peaks[1])
        elif len(peaks) == 1:
            result['warning'] = 'Only one peak found; cannot estimate thickness'
            result['thickness_m'] = None
            result['thickness_cm'] = None
        else:
            result['error'] = 'No peaks found in FFT data'
            result['thickness_m'] = None
            result['thickness_cm'] = None
        
        return result
    
    def process_line(self, csv_line: str) -> dict:
        """
        Process a single CSV line and return thickness measurement and metadata.
        """
        data = self.parse_csv_line(csv_line)
        analysis = self.analyze_fft(data['fft_data'])
        
        return {
            'timestamp': data['timestamp'],
            'longitude': data['longitude'],
            'latitude': data['latitude'],
            'temperature': data['temperature'],
            'thickness_cm': analysis.get('thickness_cm'),
            'thickness_m': analysis.get('thickness_m'),
            'num_peaks': analysis.get('num_peaks'),
            'snr_db': analysis.get('snr_db'),
            'analysis': analysis
        }
    
    def process_file(self, filename: str) -> list:
        """
        Process a CSV file with multiple measurements.
        
        Returns list of measurement results.
        """
        results = []
        with open(filename, 'r') as f:
            for i, line in enumerate(f):
                try:
                    result = self.process_line(line)
                    results.append(result)
                    print(f"[Line {i+1:5d}] {result['timestamp']} | "
                          f"Temp: {result['temperature']:.1f}°C | "
                          f"Thickness: {result['thickness_cm']:05.2f} cm | "
                          f"Peak1: {result['analysis'].get('first_peak_range_m', 0)*100:.2f} cm | "
                          f"Peak2: {result['analysis'].get('second_peak_range_m', 0)*100:.2f} cm | "
                          f"SNR: {result['snr_db']:.1f} dB")
                except Exception as e:
                    print(f"[ERROR] Line {i+1}: {e}")
        
        return results
    
    def plot_fft(self, fft_data: np.ndarray, peaks=None, title="FFT Magnitude Spectrum"):
        """Plot FFT data with peaks highlighted."""
        plt.figure(figsize=(12, 6))
        plt.plot(self.range_axis * 100, fft_data, 'b-', linewidth=1.5, label='FFT Magnitude')
        
        if peaks is not None and len(peaks) > 0:
            peak_ranges = self.range_axis[peaks] * 100
            peak_mags = fft_data[peaks]
            plt.plot(peak_ranges, peak_mags, 'ro', markersize=8, label=f'Peaks (n={len(peaks)})')
            
            # Annotate peaks
            for i, (r, m) in enumerate(zip(peak_ranges, peak_mags)):
                plt.annotate(f'P{i+1}\n{r:.1f}cm', xy=(r, m), xytext=(r, m+5),
                           ha='center', fontsize=9)
        
        plt.xlabel('Range (cm)')
        plt.ylabel('Magnitude (a.u.)')
        plt.title(title)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        return plt
    
    def plot_results(self, results: list):
        """Plot thickness measurements over time."""
        if not results:
            print("[WARNING] No results to plot")
            return
        
        timestamps = [r['timestamp'] for r in results]
        thicknesses = [r['thickness_cm'] if r['thickness_cm'] else 0 for r in results]
        temperatures = [r['temperature'] for r in results]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Thickness over time
        ax1.plot(range(len(thicknesses)), thicknesses, 'b-o', linewidth=2)
        ax1.set_xlabel('Measurement #')
        ax1.set_ylabel('Thickness (cm)')
        ax1.set_title('Snow Thickness Over Time')
        ax1.grid(True, alpha=0.3)
        
        # Temperature correlation
        ax2.scatter(temperatures, thicknesses, alpha=0.6, s=100)
        ax2.set_xlabel('Temperature (°C)')
        ax2.set_ylabel('Thickness (cm)')
        ax2.set_title('Thickness vs Temperature')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def plot_map_with_thickness(self, results: list, output_file='snow_thickness_map.html'):
        """
        Plot GPS locations on an interactive map with thickness measurements.
        
        Args:
            results: List of measurement results with GPS coordinates
            output_file: Output HTML file for the map
        """
        if not results:
            print("[WARNING] No results to plot on map")
            return
        
        # Filter out results without valid coordinates
        valid_results = [r for r in results if r['latitude'] and r['longitude'] and r['thickness_cm']]
        
        if not valid_results:
            print("[WARNING] No valid GPS/thickness data to map")
            return
        
        # Calculate map center
        lats = [r['latitude'] for r in valid_results]
        lons = [r['longitude'] for r in valid_results]
        center_lat = np.mean(lats)
        center_lon = np.mean(lons)
        
        # Create folium map using built-in providers
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=15,
            tiles='OpenStreetMap.Mapnik'
        )
        
        # Add alternative tile layers using folium's built-in providers
        folium.TileLayer(
            'OpenStreetMap.Mapnik',
            name='OpenStreetMap',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            'CartoDB positron',
            name='CartoDB Light',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            'CartoDB voyager',
            name='CartoDB Detailed',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Normalize thickness for color scaling
        thicknesses = [r['thickness_cm'] for r in valid_results]
        min_thick = min(thicknesses)
        max_thick = max(thicknesses)
        thickness_range = max_thick - min_thick if max_thick > min_thick else 1
        
        # Add markers for each measurement
        for r in valid_results:
            # Normalize thickness to 0-1 for color mapping
            norm_thick = (r['thickness_cm'] - min_thick) / thickness_range if thickness_range > 0 else 0.5
            
            # Color: blue (thin) to red (thick)
            if norm_thick < 0.5:
                color = 'blue'
            elif norm_thick < 0.7:
                color = 'green'
            elif norm_thick < 0.85:
                color = 'orange'
            else:
                color = 'red'
            
            popup_text = f"""
            <b>Thickness:</b> {r['thickness_cm']:05.2f} cm<br>
            <b>Temperature:</b> {r['temperature']:.1f}°C<br>
            <b>Timestamp:</b> {r['timestamp']}<br>
            <b>Peaks:</b> {r['num_peaks']}<br>
            <b>SNR:</b> {r['snr_db']:.1f} dB<br>
            <b>Location:</b> ({r['latitude']:.6f}, {r['longitude']:.6f})
            """
            
            folium.CircleMarker(
                location=[r['latitude'], r['longitude']],
                radius=5 + norm_thick * 10,  # Size scales with thickness
                popup=folium.Popup(popup_text, max_width=250),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2
            ).add_to(m)
        
        # Add heatmap layer
        heat_data = [[r['latitude'], r['longitude'], r['thickness_cm']] for r in valid_results]
        HeatMap(heat_data, min_opacity=0.5, radius=20, blur=25).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 250px; height: 200px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <b>Snow Thickness Map</b><br><br>
        <span style="color: blue;">●</span> Thin (0-25%)<br>
        <span style="color: green;">●</span> Light (25-50%)<br>
        <span style="color: orange;">●</span> Moderate (50-75%)<br>
        <span style="color: red;">●</span> Thick (75-100%)<br><br>
        Min: {:.2f} cm<br>
        Max: {:.2f} cm<br>
        Avg: {:.2f} cm
        </div>
        '''.format(min_thick, max_thick, np.mean(thicknesses))
        
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add layer control to toggle between satellite and street views
        folium.LayerControl().add_to(m)
        
        m.save(output_file)
        print(f"[INFO] Map saved to: {output_file}")
        return m


# --- Example usage ---
if __name__ == "__main__":
    analyzer = ThicknessAnalyzer()

    # Process multiple lines from file (if file provided as argument)
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        print(f"\n[INFO] Processing file: {filename}")
        results = analyzer.process_file(filename)

        print(f"\n[SUMMARY] Processed {len(results)} measurements")
        if results:
            thicknesses = [r['thickness_cm'] for r in results if r['thickness_cm'] is not None]
            if thicknesses:
                print(f"Average thickness: {np.mean(thicknesses):.2f} cm")
                print(f"Min thickness: {np.min(thicknesses):.2f} cm")
                print(f"Max thickness: {np.max(thicknesses):.2f} cm")

        # Plot results
        print("\n[INFO] Generating result plots...")
        analyzer.plot_results(results)
        
        # Generate map
        print("\n[INFO] Generating GPS thickness map...")
        analyzer.plot_map_with_thickness(results)
        
        plt.show()
    else:
        # Example: single line processing
        example_line = "2026-01-16 09:41:34,45.403093,-75.680470,-16.14,1246,2191,3106,3952,4695,5299,5735,5981,6020,5848,5468,4892,4141,3246,2241,1167,361,8,5,3,1,0,0,0,0,0,0,1067,1012,916,788,646,533,420,312,318,354,382,399,403,392,367,327,275,220,185,148,109,69,30,27,29,31,32,678,674,666,651,632,611,595,590,600,623,657,695,735,773,807,838,863,880,886,878,855,818,769,712,649,588,535,498,480,478,487,503,520,536,547,551,547,535,515,489,458,422,384,343,302,265,240,216,191,182,182,184,184,180,172,161,149,136,126,118,115,116,121,128,144,161,177,190,202,210,215,217,216,212,205,195,182,167,149,279,258,238,220,207,202,205,216,231,247,264,281,296,310,322,331,337,340,341,340,338,334,331,328,326,325,326,328,329,330,328,325,319,310,299,284,267,248,227,206,186,166,149,134,122,112,108,109,115,125,135,144,153,160,166,172,176,180,183,185,187,189,191,192,192,192,191,190,188,185,182,179,176,173,170,167,165,162,159,155,152,151,151,153,158,163,167,171,173,173,172,169,165,160,154,147,139,132,124,118,113,110,108,107,106,109,115,120,125,129,132,133,133,132,129,126,121,116,110,103,96,93,98,103,108,112,115,118,121,123,125,127,128,129,129,129,128,125,122,118,114,110,106,103,100,98,97,97,97,97,97,96,95,91,87,81,75,68,62,62,71,81,92,103,114,123,131,137,142,145,146,145,143,140,136,131,126,122,117,113,110,108,105,103,101,98,95,91,87,82,77,72,70,68,68,67,66,65,64,62,61,60,63,66,69,71,71,71,71,70,68,66,65,63,61,59,57,56,55,54,54,54,54,54,55,55,55,55,55,56,57,59,60,62,63,64,65,66,66,67,67,68,69,70,71,72,74,75,76,77,78,81,82,83,84,85,84,84,83,82,81,79,77,75,74,72,70,69,67,66,65,63,62,61,59,59,58,58,58,60,62,64,65,66,67,67,67,66,65,63,61,58,56,54,53,52,52,52,53,55,56,58,59,60,60,61,60,60,59,59,58,58,57,56,54,52,49,46,44,41,40,39,40,41,43,44,46,47,47,47,47,46,44,41,38,35,31,27,24,21,20,20,20,21,23,26,28,30,32,33,33,33,33,32,31,31,30,31,32,35,37,39,41,43,44,44,44,43,42,40,38,37,35,34,32,30,29,28,28"

        print("\n[TEST] Processing example line...")
        result = analyzer.process_line(example_line)
        print(f"\nTimestamp: {result['timestamp']}")
        print(f"Location: ({result['longitude']:.6f}, {result['latitude']:.6f})")
        print(f"Temperature: {result['temperature']:.2f}°C")
        print(f"Estimated Thickness: {result['thickness_cm']:.2f} cm ({result['thickness_m']:.4f} m)")
        print(f"Number of Peaks: {result['num_peaks']}")
        print(f"Signal-to-Noise Ratio: {result['snr_db']:.1f} dB")

        # Plot the FFT
        print("\n[INFO] Generating FFT plot...")
        analyzer.plot_fft(
            result['analysis']['fft_data'] if 'fft_data' in result['analysis'] else np.array(example_line.split(',')[4:], dtype=float),
            peaks=np.array(result['analysis'].get('peak_indices', [])),
            title=f"FFT Spectrum - {result['timestamp']}"
        )
        plt.show()
