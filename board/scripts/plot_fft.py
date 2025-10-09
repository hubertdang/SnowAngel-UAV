################################################
# Script to plot FFT spectrum from radar data stored in JSON file
#
# Author: Karran Dhillon
# Date: October 2025
#
# Assumes JSON file has a key "FFT" with an array of samples
# Example JSON format: {"FFT": [sample1, sample2, ..., sampleN]}
#
# Copyright 2025 SnowAngel-UAV
################################################
import numpy as np
import matplotlib.pyplot as plt
import json
import os

# Parameters
Fs = 20000 # Sampling rate (of the ADC sampling the echoes recieved)

# Grab raw radar FFT data from JSON file
if not os.path.exists('radar_data.json'):
    raise FileNotFoundError("The file 'radar_data.json' was not found.")
with open('radar_data.json', 'r') as file:
    data = json.load(file)

fft_data = data['FFT']
N = len(fft_data)  # Number of samples (FFT size)

# Frequency axis (bin numbers converted to actual frequencies)
frequencies = np.fft.fftfreq(N, d=1/Fs)

# Only take the positive frequencies (real part)
positive_freqs = frequencies[:N//2]
magnitude = np.abs(fft_data[:N//2])

# Plot the FFT spectrum (magnitude)
print("Plotting FFT Spectrum:")
print("Fs (Sampling Rate):", Fs)
print("N (FFT Size):", N)

plt.figure(figsize=(10, 6))
plt.plot(positive_freqs, magnitude)
plt.title("FFT Spectrum of Radar Data")
plt.xlabel("Frequency (Hz)")
plt.ylabel("Magnitude")
plt.grid(True)
plt.show()
