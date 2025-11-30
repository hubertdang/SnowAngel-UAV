#!/usr/bin/env python3
"""
Name: ops_serial.py
Author: Karran Dhillon

OPS241-B FMCW Radar Python Wrapper

High-level interface for communicating with the OPS241-B radar module over serial port.
Used for debugging, data acquisition, and visualization of radar data.

Date: November 2025

Copyright 2025 SnowAngel-UAV
"""

import serial # pip install pyserial
import time
import json
import os
from typing import Optional
import numpy as np # pip install numpy
import matplotlib.pyplot as plt # pip install matplotlib
from scipy.signal import find_peaks # pip install scipy

OUTPUT_FILE = "radar_data.json"

class OPS241B:
    def __init__(self, port="/dev/ttyACM0", baudrate=57600, timeout=1.0):
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        time.sleep(0.5)
        print(f"[INFO] Connected to OPS241-B on {port} @ {baudrate} baud")

        self.sampling_rate = 80000.0    # 80kHz
        self.c = 3e8                    # speed of light
        self.BW = 990e6                 # 990 MHz Bandwidth of FMCW chirp
        self.T_chirp = 1.6e-3           # 1.6 ms chirp duration
        self.S = self.BW / self.T_chirp # chirp slope (Hz/s)
        N_full = 1024
        N = 512 # FFT is symmetric, so full length is double

        self.bin_spacing = self.sampling_rate / N_full # 320kHz / 1024 bins = 312.5 Hz/bin
        self.freq_axis = np.arange(N) * self.bin_spacing # gives multiples of bin spacing (0 .. fs/2)
        hz_to_m = self.c / (2 * self.S) # meters per Hz relative to chirp slope
        self.range_axis = self.freq_axis * hz_to_m # Hz/m for each bin

    # --- Basic I/O helpers ---
    def send_command(self, cmd: str) -> None:
        """Send a command to the radar."""
        if not cmd.endswith("\n"):
            cmd += "\n"
        self.ser.write(cmd.encode("utf-8"))
        time.sleep(0.05)

    def read_line(self, n = 1) -> Optional[str]:
        """Read one line from the radar."""
        lines = []
        while (n > 0):
            lines.append(self.ser.readline().decode(errors="ignore").strip())
            n = n - 1
        return lines

    def _drain(self, duration: float = 0.1) -> None:
        """Flush out any stale lines."""
        end = time.time() + duration
        while time.time() < end:
            self.ser.readline()
        self.ser.reset_input_buffer()

    # --- Smart query (works under continuous stream) ---
    def query(self, cmd: str, n = 1) -> Optional[str]:
        """
        Send a command and return the first non-streaming line that matches.
        Streaming {"range": "..."} lines are skipped automatically.
        """
        self._drain()
        self.send_command(cmd)
        return self.read_line(n)

    # --- Convenience methods ---
    def get_info(self) -> Optional[str]:
        """Fetch module information with '??'."""
        return self.query("??", 12)

    def set_units_meters(self):
        self.send_command("uM")

    def set_fmcw_mode(self):
        radar.send_command("oF") # enable FFT output
    def set_adc_mode(self):
        radar.send_command("oR") # enable ADC output

    def set_precision(self, decimals=2):
        self.send_command(f"F{decimals}")

    def set_json_output(self, enable=True):
        self.send_command("OJ" if enable else "Oj")

    def set_resolution(self):
        self.send_command("S(") # 128 buffer
        time.sleep(1)
        self.send_command("x8") # 1024 FFT

    def disable_fft_or_adc(self):
        self.send_command("of") # disable FFF
        self.send_command("or") # disable ADC

    def stream_data(self, seconds=5):
        """Print streaming lines for N seconds."""
        print(f"[INFO] Streaming for {seconds} s...")
        end = time.time() + seconds
        while time.time() < end:
            line = self.read_line()
            if line:
                print(line)

    def get_fft_data(self, skip_drain=False) -> str:
        """Fetch a single FFT data line."""
        if not skip_drain:
            radar._drain()
        end = time.time() + 0.5 # wait up to 0.5s
        while time.time() < end:
            line = self.read_line()[0]
            if line.startswith('{"FFT":'):
                return line
        return None

    def get_adc_data(self) -> str:
        """Fetch a single ADC data line."""
        radar._drain()
        end = time.time() + 0.5 # wait up to 0.5s
        while time.time() < end:
            line = self.read_line()[0]
            if line.startswith('{"I":'): # I comes first
                I_data = json.loads(line)
            elif line.startswith('{"Q":') and 'I_data' in locals():
                Q_data = json.loads(line)
            if 'I_data' in locals() and 'Q_data' in locals():
                return {"I": I_data["I"], "Q": Q_data["Q"]}
        return None

    def plot_fft(self, filename: str):
        """Plot FFT data from a JSON file."""
        # Grab raw radar FFT data from JSON file
        if not os.path.exists(filename):
            raise FileNotFoundError(f"The file '{filename}' was not found.")
        with open(filename, 'r') as file:
            data = json.load(file)

        fft_data = data.get('FFT')
        if not fft_data:
            raise ValueError("No FFT data found in the JSON file.")

        fft_data = np.array(fft_data, dtype=float) # FFT data is already upper half only

        plt.figure(figsize=(10, 6))
        plt.plot(self.range_axis, fft_data)
        plt.title("OPS241-B FFT Magnitude Spectrum")
        plt.xlabel("Range (m)")
        plt.ylabel("Magnitude")
        plt.grid(True)
        plt.show()

        print(f"Plotted FFT bins, bin spacing {self.bin_spacing:.1f} Hz")

    def calculate_fft_raw_thickness(self, filename):
        """
        Calculate thickness from a .log file.
        Expected format: 12.4,14.5,21.4,... (512, for each line
        """
        # Grab raw radar FFT data from JSON file
        if not os.path.exists(filename):
            raise FileNotFoundError(f"The file '{filename}' was not found.")
        with open(filename, 'r') as file:
            lines = file.readlines()
            averages = []
            for line in lines:
                fft_data = line.strip().split(',')
                averaged_fft = np.array(fft_data, dtype=float) # FFT data is already upper
        
                # Consider ranges between 0.1 m and 1 m only for peak detection
                valid = (self.range_axis > 0.1) & (self.range_axis < 1)
                valid_indices = np.where(valid)[0]

                peaks, _ = find_peaks(
                                    averaged_fft[valid_indices],
                                    distance=2,                     # at least 2 bins apart (≈3.7 cm)
                                    prominence=0.003*np.max(averaged_fft),
                                    )
                peaks = valid_indices[peaks]  # Convert back to original indices
                peaks = np.sort(peaks)[:2]  # Get the two smallest peak indices (closest ranges)

                # Get the top two peaks
                if len(peaks) == 2:
                    r1 = self.range_axis[peaks[0]]
                    r2 = self.range_axis[peaks[1]]
                    ice_thickness_m = (r2 - r1)
                    averages.append(ice_thickness_m*100)
                    print(f"[RESULT] Estimated thickness {ice_thickness_m*100:.2f} cm between top two peaks")
                else:
                    print("[WARNING] Less than two peaks found in the specified range.")
                    if len(peaks) > 0:
                        print(f"[INFO] Corresponding ranges (m): {self.range_axis[peaks]}")
            if averages:
                mean_thickness = np.mean(averages)
                std_thickness = np.std(averages)
                print(f"[FINAL RESULT] Mean estimated thickness over {len(averages)} samples: {mean_thickness:.2f} cm ± {std_thickness:.2f} cm")

    def find_peak_frequency(self, fft_mag, freqs, ranges) -> float:
        # ---- find strongest reflection ----
        peak_bin = np.argmax(fft_mag)
        peak_freq = freqs[peak_bin]
        peak_range = ranges[peak_bin]

        print(f"[RESULT] Peak bin = {peak_bin}")
        print(f"[RESULT] Beat freq = {peak_freq:.1f} Hz")
        print(f"[RESULT] Estimated range = {peak_range*100:.1f} cm")

    def average_fft(self, num_averages: int = 1):
        """Fetch and average multiple FFT data sets."""
        accumulated_fft = None
        for i in range(num_averages):
            line = self.get_fft_data(skip_drain=True) # no need to drain input buffer, slows down averaging
            if line is None:
                print(f"[WARNING] No FFT data received for average {i+1}")
                continue
            data = json.loads(line)
            fft_data = np.array(data.get('FFT', []), dtype=float)
            if accumulated_fft is None:
                accumulated_fft = fft_data
            else:
                accumulated_fft += fft_data # element-wise addition

        if accumulated_fft is not None:
            averaged_fft = accumulated_fft / num_averages
            print(f"[INFO] Completed averaging over {num_averages} FFT datasets")

            # Consider ranges between 0.1 m and 1 m only for peak detection
            valid = (self.range_axis > 0.1) & (self.range_axis < 1)
            valid_indices = np.where(valid)[0]

            peaks, _ = find_peaks(
                                  averaged_fft[valid_indices],
                                  distance=2,                     # at least 2 bins apart (≈3.7 cm)
                                  prominence=0.003*np.max(averaged_fft),
                                 )
            peaks = valid_indices[peaks]  # Convert back to original indices
            peaks = np.sort(peaks)[:2]  # Get the two smallest peak indices (closest ranges)

            # Get the top two peaks
            if len(peaks) == 2:
                r1 = self.range_axis[peaks[0]]
                r2 = self.range_axis[peaks[1]]
                ice_thickness_m = (r2 - r1)
                print(f"[RESULT] First peak at range {r1*100:.2f} cm")
                print(f"[RESULT] Second peak at range {r2*100:.2f} cm")
                print(f"[RESULT] Estimated thickness {ice_thickness_m*100:.2f} cm between top two peaks")
            else:
                print("[WARNING] Less than two peaks found in the specified range.")
                if len(peaks) > 0:
                    print(f"[INFO] Corresponding ranges (m): {self.range_axis[peaks]}")
            return averaged_fft
        else:
            print("[ERROR] No FFT data was averaged.")
            return None

    def continiously_find_peak_frequency(self):
        """Continuously fetch FFT data and find peak frequency."""
        data = json.loads(self.get_fft_data())
        fft_data = np.array(data.get('FFT', []), dtype=float)
        N = len(fft_data) # FFT is symmetric, so full length is double
        N_full = N * 2

        # OPS241-B parameters
        bin_spacing = self.sampling_rate / N_full
        freq_axis = np.arange(N) * bin_spacing # gives multiples of bin spacing (9 .. fs/2)
        c = 3e8
        BW = 990e6
        T_chirp = 1.6e-3
        S = BW / T_chirp
        hz_to_m = c / (2 * S)
        range_axis = freq_axis * hz_to_m # Hz/m for each bin
        self.find_peak_frequency(fft_data, freq_axis, range_axis)

    def plot_fft_from_adc(self, filename: str, fft_len: int = 1024):
        """Plot FFT from raw ADC I/Q data stored in JSON file."""
        # ---- Load Data ----
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File '{filename}' not found.")

        with open(filename, 'r') as f:
            data = json.load(f)

        if "I" not in data or "Q" not in data:
            raise ValueError("JSON file must contain 'I' and 'Q' arrays.")

        I = np.array(data["I"], dtype=float)
        Q = np.array(data["Q"], dtype=float)

        if len(I) != len(Q):
            raise ValueError("I and Q arrays must have the same length.")

        N = len(I)
        print(f"Loaded {N} complex samples from {filename}")

        # ---- Form complex signal ----
        iq = (I - np.mean(I)) + 1j * (Q - np.mean(Q))

        # ---- Apply window and FFT (zero-padded) ----
        window = np.hanning(N) # Apply a hanning window to imrove FFT quality
        fft_data = np.fft.fft(iq * window, n=fft_len) # pad with zeros to fft_len
        magnitude = np.abs(fft_data[:fft_len // 2]) # Take only positive frequencies (upper half)

        # ---- Compute frequency and range axes ----
        freqs = np.linspace(0, self.sampling_rate / 2, fft_len // 2, endpoint=False) # Frequency axis

        hz_to_m = self.c / (2 * self.S) # meters per Hz
        ranges = hz_to_m * freqs        # convert frequency bins to meters

        print(f"Range resolution ≈ {self.c/(2*self.BW):.3f} m (true), "
              f"bin spacing ≈ {ranges[1]-ranges[0]:.3f} m (after zero-padding)")

        # ---- Plot ----
        plt.figure(figsize=(10, 6))
        plt.plot(freqs, magnitude)
        #plt.plot(ranges, magnitude)
        plt.title("OPS241-B I/Q Zero-Padded FFT Magnitude")
        # plt.xlabel("Range (m)")
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Magnitude (a.u.)")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def close(self):
        self.ser.close()
        print("[INFO] Closing serial port to sensor")

    def print_lines(self, lines):
        for line in lines:
            print(line)

# --- Example usage ---
if __name__ == "__main__":
    radar = OPS241B("/dev/ttyACM0")

    radar.calculate_fft_raw_thickness("../build/radar_fft.log")

    # # Query module info safely
    # print("[INFO] Disabling continious straming for info query...")
    # radar.send_command("r>15") # set range to 10 m to reduce streaming load (i.e. stop reporting as often)
    # radar.disable_fft_or_adc()
    # time.sleep(0.5)

    # # Configure for meters, 2 decimals, JSON output
    # print("[INFO] Configuring radar for FFT data output...")
    # radar.set_units_meters()
    # radar.set_precision(2)
    # radar.set_json_output(True)
    # radar.set_resolution()
    # time.sleep(2)

    # print("[INFO] Turning on FMCW mode...")
    # radar.set_fmcw_mode()

    # # Average multiple FFT datasets
    # print("[INFO] Collecting FFT data...")
    # while True:
    #     average_fft = radar.average_fft(num_averages=1)
    #     radar._drain()
    #     if average_fft is not None:
    #         # Save averaged FFT to JSON
    #         with open(OUTPUT_FILE, "w") as f:
    #             json.dump({"FFT": average_fft.tolist()}, f, indent=2)
    #         print(f"[INFO] Saved averaged FFT data to {OUTPUT_FILE}")

    #         # Plot the averaged FFT data
    #         radar.plot_fft(OUTPUT_FILE)

