/**
 *
 * Name: sensor.hpp
 * Author: Karran Dhillon
 *
 * This file describes the public interface to the sensor bsp layer.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef FMCW_RADAR_SENSOR_H
#define FMCW_RADAR_SENSOR_H

#include <cstdint>

//----------------------------------------------------------------
#define FMCW_RADAR_FFT_SIZE 2048

typedef struct fmcw_waveform_data
{
// Size Calculation:
// '{"FFT":['                                                 //   8
// FMCW_RADAR_FFT_SIZE samples, each 2 decimal digits + comma // + 6*FMCW_RADAR_FFT_SIZE
// ']}\0'                                                     // + 3
#define FMCW_RADAR_MAX_DATA_SIZE (8 + (6 * FMCW_RADAR_FFT_SIZE) + 3)

	uint8_t raw_data[FMCW_RADAR_MAX_DATA_SIZE];
	uint16_t fft_size;
} fmcw_waveform_data_t;

//----------------------------------------------------------------

class FMCW_RADAR_SENSOR
{
public:
	// the following functions describe the public interface.
	// CAUTION! CAUTION! DO NOT describe the state or implementation of the sensor.
	// CAUTION! CAUTION! Please be wary if deciding to change the interface. You
	//                   risk exposing extra information to the application code.

	// Pure virtual functions enforce child class implementations
	virtual int8_t fmcw_radar_sensor_init() = 0;
	virtual int8_t fmcw_radar_sensor_start_tx_signal() = 0;
	virtual int8_t fmcw_radar_sensor_read_rx_signal(fmcw_waveform_data_t *data) = 0;
	virtual int8_t fmcw_radar_sensor_stop_tx_signal() = 0;

	virtual ~FMCW_RADAR_SENSOR() {}
	// do not declare anything as private or protected
};

//----------------------------------------------------------------

FMCW_RADAR_SENSOR *instantiate_fmcw_radar_sensor(uint8_t usb_port);

#endif // #ifndef FMCW_RADAR_SENSOR_H