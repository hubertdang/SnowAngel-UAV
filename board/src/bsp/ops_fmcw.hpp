/**
 *
 * Name: ops_fmcw.hpp
 * Author: Karran Dhillon
 *
 * This file describes the private interface for the OPS-243C FMCW radar sensor.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef OPS_FMCW_H
#define OPS_FMCW_H

#include "bsp/fmcw_radar_sensor.hpp"
#include <cstdint>
#include <string>

#define FMCW_RADAR_BUFFER_SIZE 512 // fft buffer size per chirp
#define FMCW_RADAR_CT_MS 1.6       // chirp time
#define FMCW_RADAR_FS_KHZ 320      // sample rate
#define FMCW_RADAR_BW_MHZ 990      // chirp bandwidth (ramp length)
#define FMCW_RADAR_SLOPE (FMCW_RADAR_BW_MHZ * 1000000) / (FMCW_RADAR_CT_MS / 1000) // Hz/sec

//--------------------------------
// Serial interface
#define FMCW_RADAR_USB_PORT "/dev/ttyACM0" // fixed, never changes
#define FMCW_RADAR_BAUD_RATE 1152000

//--------------------------------
// General commands
#define FMCW_CMD_INFO                                                                              \
	"??" // gets module information (product name, serial number, firmware version)
#define FMCW_CMD_DISABLE_STREAM "r>20"
#define FMCW_CMD_SET_UNITS_M "uM"
#define FMCW_CMD_PRECISION "F2" // 2 decimal pts

// ADC/FFT configuration
// 256 samples, 2048 FFT size, 80kHz sampling rate
// 1.6ms chirp, (24.015GHz - 24.235GHz)
// 8.52cm range resolution (mimum distance between two objects to be detected separately)
#if FMCW_RADAR_FFT_SIZE == 512
#define FMCW_CMD_SET_FFT_CFG "x2" // 512 samples, scaled by 2 with zero-padding
#else
#error "Unsupported FFT size"
#endif

#define FMCW_CMD_SET_FFT_SIZE "S<" // 512 data buffer
#define FMCW_CMD_SET_ZEROS "x2"    // double FFT with zero-padding
#define FMCW_CMD_TURN_ON_FFT "oF"  // enables raw FFT output on serial port
#define FMCW_CMD_TURN_OFF_FFT "of"
#define FMCW_CMD_TURN_OFF_ADC "or"
#define FMCW_CMD_TURN_ON_ADC "oR"
#define FMCW_CMD_JSON_MODE "OJ" // enables JSON output mode on serial port

// I/O commands
#define FMCW_CMD_LED_ON "OL" // enable LED on radar sensor
#define FMCW_CMD_LED_OFF "Ol"
//--------------------------------

class OPS_FMCW : public FMCW_RADAR_SENSOR
{
public:
	static FMCW_RADAR_SENSOR *get_fmcw_radar_instance(const char *usb_port);

	// OPS_FMCW should not be cloneable.
	OPS_FMCW(OPS_FMCW &other) = delete;

	// OPS_FMCW should not be assignable.
	void operator=(const OPS_FMCW &) = delete;

	int8_t fmcw_radar_sensor_init() override;
	int8_t fmcw_radar_sensor_read_rx_signal(fmcw_waveform_data_t *data) override;
	int8_t fmcw_radar_sensor_start_tx_signal() override;
	int8_t fmcw_radar_sensor_stop_tx_signal() override;
	~OPS_FMCW() override {}

private:
	// Constructor is private to enforce factory function usage.
	// Follows the singleton design pattern.
	OPS_FMCW(const char *usb_port);

	// helper functions
	int8_t send_command(std::string cmd);
	int8_t read_response(std::string *response);
	int8_t query(std::string cmd, std::string *response, uint8_t num_lines = 1);

private:
	static OPS_FMCW *instance;
	std::string usb_port;
	int8_t fd;
};

#endif // #ifndef OPS_FMCW_H
