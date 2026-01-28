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
from scipy.signal import peak_widths
from scipy.interpolate import lagrange
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
        self.n = 1.78                   # refractive index of ice
        
        # FFT parameters
        N_full = 1024
        N = 512  # FFT is symmetric, so full length is double
        
        self.N = N
        self.N_full = N_full
        self.bin_spacing = self.sampling_rate / N_full  # Hz per bin
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
    
    def refine_peak_parabolic_log(self, fft_data: np.ndarray, k: int) -> float:
        if k <= 0 or k >= len(fft_data) - 1:
            return float(k)

        y1 = np.log(fft_data[k - 1] + 1e-12)
        y2 = np.log(fft_data[k] + 1e-12)
        y3 = np.log(fft_data[k + 1] + 1e-12)

        denom = (y1 - 2*y2 + y3)
        if denom == 0:
            return float(k)

        delta = 0.5 * (y1 - y3) / denom
        return float(k + delta)

    
    def analyze_fft(self, fft_data: np.ndarray, min_range=0.35, max_range=2.0) -> dict:
        """
        Analyze FFT data to find peaks and estimate thickness.
        
        Args:
            fft_data: FFT magnitude data array
            min_range: Minimum range to search (meters); default is 31cm
            max_range: Maximum range to search (meters); default is 200cm
        
        Returns:
            Dictionary with analysis results including estimated thickness
        """
        # Initialize result dictionary
        result = {
            'num_peaks': 0,
            'peak_indices': [],
            'peak_ranges': [],
            'peak_magnitudes': [],
            'max_magnitude': np.max(fft_data),
            'noise_floor': np.min(fft_data),
            'snr_db': 20 * np.log10(np.max(fft_data) / (np.std(fft_data) + 1e-10))
        }
        # Find peaks in the FFT data
        peak_prominence = 0.05 * np.max(fft_data)
        peaks, peak_properties = find_peaks(
            fft_data,
            distance=(30 / 1.89),  # at least 15cm between peaks
            prominence=peak_prominence,
            height=0.02*np.max(fft_data),# minimum height filter
            width=3, # width of peak is ~3 bins (~6 cm)
            wlen=80  # look for peaks within a window of 25 bins (+/-30 bins on each side)
        )
        
        # Post filter processing:
        # # 1) Require peaks to have shoulders (width) at half-height
        # results = peak_widths(fft_data, peaks, rel_height=0.5)  # half-height shoulders
        # left_ips = results[2]
        # right_ips = results[3]

        # # require shoulders at least k bins away from the peak (not a cliff)
        # k = 4
        # mask = (peaks - left_ips >= k) & (right_ips - peaks >= k)
        # peaks = peaks[mask]

        # 2) Filter peaks to valid range window
        valid_mask = (self.range_axis[peaks] >= min_range) & (self.range_axis[peaks] <= max_range)
        peaks = peaks[valid_mask]
        peaks = np.sort(peaks)

        # 3) Make sure first peak is the strongest (air/snow interface)
        if len(peaks) >= 2:
            if fft_data[peaks[1]] > fft_data[peaks[0]]:
                result["error"] = "Second peak stronger than first peak; invalid measurement"
                result['thickness_m'] = 0
                result['thickness_cm'] = 0
                return result

        # 4) Make sure first peak is within 130cm
        if len(peaks) >= 1:
            if self.range_axis[peaks[0]] > 1.3:
                result["error"] = f"First peak beyond 130cm; invalid measurement. Peak is at {self.range_axis[peaks[0]]*100:.1f} cm"
                result['thickness_m'] = 0
                result['thickness_cm'] = 0
                return result
        
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
            # Refine peak locations using Lagrange interpolation
            refined_peak1 = self.refine_peak_parabolic_log(fft_data, peaks[0])
            refined_peak2 = self.refine_peak_parabolic_log(fft_data, peaks[1])
            
            r1 = self.range_axis[int(refined_peak1)]
            r2 = self.range_axis[int(refined_peak2)]
            
            # Use refined locations to adjust range values
            frac1 = refined_peak1 - int(np.floor(refined_peak1))
            frac2 = refined_peak2 - int(np.floor(refined_peak2))
            bin_width = self.range_axis[1] - self.range_axis[0]
            
            r1 = r1 + frac1 * bin_width # adjust for fractional bin
            r2 = r2 + frac2 * bin_width # adjust for fractional bin
            
            thickness = abs(r2 - r1) / self.n

            # TODO Karran: remove, this is just for debugging
            if (thickness * 100) < 30 or (thickness * 100) > 50:
                result['error'] = f'Unrealistic thickness calculated: {thickness*100:.1f} cm'
                result['thickness_m'] = 0
                result['thickness_cm'] = 0
                return result

            
            result['thickness_m'] = thickness
            result['thickness_cm'] = thickness * 100
            result['first_peak_range_m'] = r1
            result['second_peak_range_m'] = r2
            result['first_peak_idx'] = int(peaks[0])
            result['second_peak_idx'] = int(peaks[1])
        elif len(peaks) == 1:
            result['error'] = f'Only one peak found at {self.range_axis[peaks[0]]*100:.1f} cm; cannot estimate thickness'
            result['thickness_m'] = 0
            result['thickness_cm'] = 0
        else:
            result['error'] = 'No peaks found in FFT data'
            result['thickness_m'] = 0
            result['thickness_cm'] = 0
        
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
            'first_peak_range_m': analysis.get('first_peak_range_m'),
            'second_peak_range_m': analysis.get('second_peak_range_m'),
            'snr_db': analysis.get('snr_db'),
            'analysis': analysis,
            'fft_data': data['fft_data']
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
                    if(result['analysis'].get('error', None)):
                        print(f"[Line {i+1:5d}] {result['timestamp']} | ERROR: {result['analysis']['error']}")
                    else:
                        print(f"[Line {i+1:5d}] {result['timestamp']} | "
                            f"Temp: {result['temperature']:.1f}°C | "
                            f"Thickness: {result['thickness_cm']:05.2f} cm | "
                            f"Peak1: {result['analysis'].get('first_peak_range_m', 0)*100:05.2f} cm | "
                            f"Peak2: {result['analysis'].get('second_peak_range_m', 0)*100:05.2f} cm | "
                            f"SNR: {result['snr_db']:.1f} dB")
                except Exception as e:
                    print(f"[ERROR] Line {i+1}: {e}")
        
        return results
    
    def plot_fft(self, fft_data: np.ndarray, peaks=None, title="FFT Magnitude Spectrum", thickness_cm=None):
        """Plot FFT data with peaks highlighted."""
        plt.figure(figsize=(12, 6))
        #plt.plot(self.range_axis * 100, fft_data, 'b-', linewidth=1.5, label='FFT Magnitude')
        plt.plot(
            self.range_axis * 100,
            fft_data,
            marker='o',
            linestyle='None',
            markersize=3
        )
        if peaks is not None and len(peaks) > 0:
            peak_ranges = self.range_axis[peaks] * 100
            peak_mags = fft_data[peaks]
            plt.plot(peak_ranges, peak_mags, 'ro', markersize=8, label=f'Peaks (n={len(peaks)})')
            
            # Annotate peaks
            for i, (r, m) in enumerate(zip(peak_ranges, peak_mags)):
                plt.annotate(f'P{i+1}\n{r:.1f}cm', xy=(r, m), xytext=(r, m+5),
                           ha='center', fontsize=9)
        
        plt.xlabel('Optical Range (cm)')
        plt.ylabel('Magnitude (a.u.)')
        if thickness_cm is not None:
            plt.title(f"{title}\nEstimated Thickness: {thickness_cm:.2f} cm")
        else:
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
        
        # Filter out results with zero or None thickness
        valid_results = [r for r in results if r['thickness_cm'] and r['thickness_cm'] > 0]
        
        if not valid_results:
            print("[WARNING] No valid thickness measurements to plot")
            return
        
        timestamps = [r['timestamp'] for r in valid_results]
        thicknesses = [r['thickness_cm'] for r in valid_results]
        temperatures = [r['temperature'] for r in valid_results]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # Thickness over time
        ax1.scatter(range(len(thicknesses)), thicknesses, color='blue', s=50, alpha=0.7)
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
    
    def plot_fft_at_same_location(self, results: list, tolerance_m=5.0):
        """
        Group measurements by GPS location and plot overlaid FFT data at same locations.
        
        Args:
            results: List of measurement results with GPS coordinates
            tolerance_m: Distance tolerance in meters to consider locations as the same
        """
        if not results:
            print("[WARNING] No results to plot")
            return
        
        # Filter results with valid GPS and FFT data
        valid_results = [r for r in results if r['latitude'] and r['longitude'] and r.get('fft_data') is not None]
        
        if not valid_results:
            print("[WARNING] No valid GPS/FFT data to plot")
            return
        
        # Group results by location (within tolerance)
        location_groups = {}
        for r in valid_results:
            lat, lon = r['latitude'], r['longitude']
            
            # Find if this location matches an existing group
            found_group = None
            for group_key in location_groups:
                group_lat, group_lon = group_key
                # Calculate approximate distance in meters (rough approximation)
                # 1 degree latitude ≈ 111 km, 1 degree longitude ≈ 111 km * cos(lat)
                lat_dist = abs(lat - group_lat) * 111000
                lon_dist = abs(lon - group_lon) * 111000 * np.cos(np.radians(lat))
                distance = np.sqrt(lat_dist**2 + lon_dist**2)
                
                if distance < tolerance_m:
                    found_group = group_key
                    break
            
            if found_group is None:
                found_group = (lat, lon)
                location_groups[found_group] = []
            
            location_groups[found_group].append(r)
        
        print(f"\n[INFO] Found {len(location_groups)} unique locations")
        
        # Plot FFT data for each location group
        for location_idx, (location_key, group_results) in enumerate(location_groups.items()):
            if len(group_results) < 2:
                continue  # Skip groups with only one measurement
            
            lat, lon = location_key
            print(f"\n[INFO] Plotting {len(group_results)} FFT measurements at ({lat:.6f}, {lon:.6f})")
            
            # Create figure for this location
            fig, ax = plt.subplots(figsize=(14, 8))
            
            # Get colormap for different timestamps
            colors = plt.cm.viridis(np.linspace(0, 1, len(group_results)))
            
            # Store line objects and scatter collections for toggling
            line_objects = []
            scatter_objects = []
            
            # Plot FFT from each measurement
            for idx, r in enumerate(group_results):
                fft_data = r.get('fft_data')
                if fft_data is None:
                    continue
                
                thickness = r['thickness_cm'] if r['thickness_cm'] else 0
                has_error = 'error' in r.get('analysis', {})
                
                # Skip measurements with thickness 0 or errors
                if thickness <= 0 or has_error:
                    continue
                
                timestamp = r['timestamp']
                temp = r['temperature']
                
                # Plot with transparency
                line, = ax.plot(self.range_axis * 100, fft_data,
                       color=colors[idx], linewidth=1.5, alpha=0.7,
                       label=f"{timestamp} | {thickness:.1f}cm | {temp:.1f}°C",
                       picker=5)  # picker enables click detection
                line_objects.append(line)
                
                # Highlight peaks for this measurement
                peak_indices = r['analysis'].get('peak_indices', [])
                if peak_indices:
                    peak_ranges = self.range_axis[peak_indices] * 100
                    peak_mags = fft_data[peak_indices]
                    scatter = ax.scatter(peak_ranges, peak_mags, color=colors[idx], 
                             s=100, marker='o', edgecolors='black', linewidth=1.5, zorder=5,
                             picker=5)  # picker enables click detection
                    scatter_objects.append((scatter, len(line_objects) - 1))
            
            # Calculate and plot average FFT at this location
            valid_ffts = [r.get('fft_data') for r in group_results if r.get('fft_data') is not None and r.get('thickness_cm', 0) > 0]
            if valid_ffts:
                # Average FFTs from measurements with valid thickness estimates
                avg_fft = np.mean(np.array(valid_ffts), axis=0)
                
                # Analyze the average FFT
                avg_analysis = self.analyze_fft(avg_fft)
                avg_peaks = np.array(avg_analysis.get('peak_indices', []))
                
                thickness = avg_analysis.get('thickness_cm', 0)
                has_error = 'error' in avg_analysis
                
                # Only include in plot if thickness is valid (> 0) and no error
                if thickness > 0 and not has_error:
                    avg_line = ax.scatter(self.range_axis * 100, avg_fft,
                           color='black', s=50, alpha=0.9, marker='s',
                           label=f'AVERAGE (n={len(valid_ffts)}) | Thickness: {thickness:.2f} cm',
                           picker=5, zorder=10)  # picker enables click detection
                    line_objects.append(avg_line)
                else:
                    # Still plot the average FFT but without label
                    avg_line = ax.scatter(self.range_axis * 100, avg_fft,
                           color='black', s=50, alpha=0.9, marker='s',
                           picker=5, zorder=10)  # picker enables click detection
                    line_objects.append(avg_line)
                
                # Highlight peaks from average analysis
                if len(avg_peaks) > 0:
                    avg_peak_ranges = self.range_axis[avg_peaks] * 100
                    avg_peak_mags = avg_fft[avg_peaks]
                    ax.scatter(avg_peak_ranges, avg_peak_mags, color='black', 
                             s=150, marker='x', linewidth=3, zorder=6)
            
            ax.set_xlabel('Optical Range (cm)', fontsize=12)
            ax.set_ylabel('Magnitude (a.u.)', fontsize=12)
            ax.set_title(f'Overlaid FFT Data at Location ({lat:.6f}, {lon:.6f})',
                        fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            legend = ax.legend(loc='upper right', fontsize=9, framealpha=0.95)
            ax.set_ylim(bottom=0)
            
            # Make legend labels clickable
            for legline, line in zip(legend.get_lines(), line_objects):
                legline.set_picker(5)  # 5 points tolerance
            
            # Create toggle function for this figure
            def on_pick(event):
                """Toggle line visibility when legend is clicked."""
                if isinstance(event.artist, plt.Line2D):
                    # Check if it's a legend line
                    legline = event.artist
                    if legline in legend.get_lines():
                        # Find corresponding data line
                        idx = legend.get_lines().index(legline)
                        if idx < len(line_objects):
                            line = line_objects[idx]
                            vis = not line.get_visible()
                            line.set_visible(vis)
                            
                            # Also toggle corresponding scatter points
                            for scatter, line_idx in scatter_objects:
                                if line_idx == idx:
                                    scatter.set_visible(vis)
                            
                            # Toggle legend label appearance
                            if vis:
                                legline.set_alpha(1.0)
                            else:
                                legline.set_alpha(0.2)
                            
                            fig.canvas.draw_idle()
            
            # Connect the pick event
            fig.canvas.mpl_connect('pick_event', on_pick)
            
            plt.tight_layout()
            
            # Save figure
            safe_lat = str(lat).replace('.', '_').replace('-', 'n')
            safe_lon = str(lon).replace('.', '_').replace('-', 'n')
            filename = f'fft_overlay_location_{safe_lat}_{safe_lon}.png'
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"[INFO] Saved plot to: {filename}")
            
            plt.show()
        
        print(f"\n[INFO] FFT overlay plotting complete")
    
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
            thicknesses = [r['thickness_cm'] for r in results if r['thickness_cm'] is not None and r['thickness_cm'] > 0]
            if thicknesses:
                print(f"Average thickness: {np.mean(thicknesses):.2f} cm")
                print(f"Min thickness: {np.min(thicknesses):.2f} cm")
                print(f"Max thickness: {np.max(thicknesses):.2f} cm")

        # Plot results
        print("\n[INFO] Generating result plots...")
        analyzer.plot_results(results)
        
        # Plot overlaid FFT at same locations
        print("\n[INFO] Generating FFT overlay plots at same GPS locations...")
        analyzer.plot_fft_at_same_location(results, tolerance_m=5.0)
        
        # Generate map
        # print("\n[INFO] Generating GPS thickness map...")
        # analyzer.plot_map_with_thickness(results)
        
        plt.show()
    else:
        # Example: single line processing
        # example_line = "2026-01-16 09:46:31,45.402975,-75.680645,-12.29,0,0,19,253,430,606,761,826,852,775,732,782,788,750,669,545,409,359,314,259,311,457,543,564,560,523,446,4146,3908,3673,3446,3217,3005,2820,2661,2603,2560,2564,2697,2854,3014,3162,3294,3395,3460,3485,3470,3414,3314,3171,2989,2770,2520,2245,3282,2984,2694,2426,2195,2005,1844,1699,1562,1428,1301,1187,1103,1062,1050,1041,1024,1006,982,979,983,997,1023,1070,1133,1205,1278,1350,1417,1477,1526,1565,1590,1602,1602,1589,1564,1528,1481,1427,1365,1299,1228,1156,1082,1007,934,861,790,721,663,606,554,501,448,394,340,287,264,248,232,222,222,246,265,279,290,299,309,321,334,350,368,389,412,435,457,477,493,655,665,669,667,658,643,622,595,563,527,488,447,409,378,350,328,312,305,306,310,316,321,325,326,326,323,318,311,302,292,282,272,264,260,260,267,278,293,310,327,343,356,365,370,371,366,357,343,325,305,283,262,243,229,220,213,208,204,199,194,189,186,182,177,171,164,155,145,137,129,122,118,114,112,111,112,113,114,116,118,120,121,122,123,123,122,121,119,116,113,111,108,107,106,107,108,110,112,115,118,121,124,125,125,125,123,120,116,113,110,108,105,103,100,99,99,100,104,109,115,120,125,130,134,139,144,151,158,167,178,188,198,208,216,222,227,230,232,231,229,225,219,212,204,196,188,181,173,166,159,165,172,181,190,200,209,219,229,239,247,255,261,265,267,268,266,261,255,247,236,225,213,200,188,177,166,156,147,139,132,126,120,114,109,104,98,93,89,84,81,79,76,73,70,66,63,61,61,63,66,69,71,72,73,71,69,65,60,55,52,49,49,54,60,66,70,74,76,76,75,74,71,69,67,66,65,67,69,73,78,82,86,90,93,96,100,104,106,107,107,106,105,104,102,101,100,99,98,98,99,99,100,101,102,103,104,104,104,104,103,102,100,98,95,91,87,83,78,74,70,66,63,60,58,57,57,56,56,57,58,59,60,62,64,66,68,71,74,77,79,81,82,82,82,80,78,76,73,71,69,68,66,65,63,61,59,57,54,51,48,44,41,37,33,30,30,32,35,36,38,39,40,42,43,44,46,49,52,56,59,63,67,70,73,76,77,78,77,76,74,70,66,62,58,53,50,48,46,46,47,48,49,49,50,50,50,49,49,49,49,49,50,50,50,50,49,48,46,44,41,38,35,32,29,26,24,25,27,29"
        example_line = "2026-01-16 09:35:37,45.402968,-75.680595,-10.37,1,1,2,3,6,9,11,14,16,17,18,19,20,23,26,27,28,28,27,25,23,20,17,14,12,9,7,2315,2060,1959,2013,2193,2453,2752,3056,3339,3584,3782,3927,4016,4049,4027,3953,3831,3664,3458,3218,2950,2659,2352,2036,1716,1400,1091,2143,1863,1602,1360,1141,943,765,606,466,344,237,146,90,62,48,43,46,88,133,178,222,263,300,332,359,380,395,403,405,400,390,374,352,325,295,262,227,193,161,134,115,107,103,101,104,110,118,125,131,136,141,145,146,145,144,142,137,130,120,109,96,88,96,103,107,110,112,122,128,132,138,145,148,148,143,136,125,111,96,230,214,200,188,180,177,178,184,194,206,220,234,246,255,261,262,259,251,239,223,203,182,159,138,123,113,110,111,114,118,122,125,129,134,135,134,129,122,111,98,84,68,52,38,32,31,37,48,61,73,83,91,97,100,102,100,97,92,86,80,75,72,71,73,76,80,85,92,98,103,107,108,107,105,101,96,92,87,83,79,78,77,77,77,77,77,77,76,75,72,70,66,62,57,52,47,42,38,33,29,24,20,21,24,27,31,34,37,40,41,43,44,44,45,45,45,46,47,48,49,51,53,57,62,67,71,76,81,84,87,89,90,89,88,86,84,82,79,78,76,75,74,73,70,66,61,55,48,40,36,38,47,60,75,91,108,124,141,156,172,186,199,211,222,231,240,247,254,259,264,267,269,271,271,271,269,267,263,257,251,243,233,223,212,200,188,175,162,150,138,127,117,108,98,89,80,73,66,60,55,63,72,80,88,94,98,101,103,104,103,101,98,94,90,85,80,75,70,65,61,58,55,52,50,48,47,46,45,45,45,45,46,46,46,46,45,45,44,42,41,39,38,36,35,34,33,32,32,31,30,29,28,26,25,23,21,20,19,19,19,19,20,20,21,22,23,25,26,28,29,31,32,33,35,36,36,36,36,36,35,34,32,31,30,29,28,27,25,24,24,25,26,28,30,33,35,38,40,42,44,45,45,46,45,45,44,42,40,37,34,31,28,25,22,19,18,17,16,15,16,16,17,18,19,21,22,24,25,27,28,29,30,32,33,34,35,35,35,36,36,37,38,39,39,40,41,41,41,41,41,40,39,38,37,35,34,34,34,34,35,36,37,38,39,40,40,40,40,39,38,37,35,34,33,31,30,29,28,27"
        print("\n[TEST] Processing example line...")
        result = analyzer.process_line(example_line)
        print(f"\nTimestamp: {result['timestamp']}")
        print(f"Location: ({result['longitude']:.6f}, {result['latitude']:.6f})")
        print(f"Temperature: {result['temperature']:.2f}°C")
        print(f"Estimated Thickness: {result['thickness_cm']:.2f} cm ({result['thickness_m']:.4f} m)")
        print(f"Number of Peaks: {result['num_peaks']}")
        print(f"Signal-to-Noise Ratio: {result['snr_db']:.1f} dB")
        print(f"First Peak Range : {result['analysis'].get('first_peak_range_m', 0)*100:.2f} cm")
        print(f"Second Peak Range: {result['analysis'].get('second_peak_range_m', 0)*100:.2f} cm")
        if ('error' in result['analysis']):
            print(f"ERROR: {result['analysis']['error']}")

        # Plot the FFT
        print("\n[INFO] Generating FFT plot...")
        analyzer.plot_fft(
            result['analysis']['fft_data'] if 'fft_data' in result['analysis'] else np.array(example_line.split(',')[4:], dtype=float),
            peaks=np.array(result['analysis'].get('peak_indices', [])),
            title=f"FFT Spectrum for OPS241-B Received Echoes",
            thickness_cm=result['thickness_cm']
        )
        plt.show()
