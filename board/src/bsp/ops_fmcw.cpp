/**
 *
 * Name: ops_fmcw.cpp
 * Author: Karran Dhillon
 *
 * This file describes the implementations for the OPS-243C FMCW radar sensor.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include "ops_fmcw.hpp"
#include <cstdio>

#ifdef RADAR_SIMULATION
#include <fstream>

#define RADAR_SIM_PATH "../sim/radar_ice_fft_data.sim"
#endif

//---------------------------------------------------------------------
// static variable initialization
OPS_FMCW *OPS_FMCW::instance = nullptr;

/**
 * Factory function to instantiate the FMCW radar sensor.
 * @param usb_port The USB port number where the radar sensor is connected.
 *
 * @return Pointer to the instantiated FMCW_RADAR_SENSOR object.
 */
FMCW_RADAR_SENSOR *OPS_FMCW::get_fmcw_radar_instance(const uint8_t usb_port)
{
	if (instance == nullptr)
		instance = new OPS_FMCW(usb_port);
	return instance;
}

/**
 * Constructor for the OPS_FMCW class.
 * @param usb_port The USB port number where the radar sensor is connected.
 */
OPS_FMCW::OPS_FMCW(uint8_t usb_port) : usb_port(usb_port)
{
#ifdef RAND_SIMULATION
	return;
#endif
	// stub for now.
}

/**
 * Initializes the radar sensor.
 *
 * @return Returns 0 on success, -X on failure with failure code.
 */
int8_t OPS_FMCW::fmcw_radar_sensor_init()
{
#ifdef RADAR_SIMULATION
	return 0;
#endif
	// stub for now.
	return 0;
}

/**
 * Starts the transmission of the FMCW signal.
 *
 * @return Returns 0 on success, -X on failure with failure code.
 */
int8_t OPS_FMCW::fmcw_radar_sensor_start_tx_signal()
{
#ifdef RADAR_SIMULATION
	return 0;
#endif
	// stub for now
	return 0;
}

/**
 * Reads the received FMCW signal data from the radar sensor.
 * @param data Pointer to the structure to store the received waveform data.
 *
 * @return Returns 0 on success, -X on failure with failure code.
 */
int8_t OPS_FMCW::fmcw_radar_sensor_read_rx_signal(fmcw_waveform_data_t *data)
{
#ifdef RADAR_SIMULATION
	// use fake FFT data
	// has peaks at 458.3 Hz and 550 Hz (10cm ice thickness)
	// drone: 50cm above surface, 1.6ms chirp slope, 2048 samples, 220MHz bandwidth

	std::ifstream sim_file(RADAR_SIM_PATH);
	if (!sim_file.is_open())
	{
		printf("Failed to open file: %s\n", RADAR_SIM_PATH);
		return -1;
	}

	std::string line;
	if (!std::getline(sim_file, line))
	{
		printf("Failed to read line from file: %s\n", RADAR_SIM_PATH);
		sim_file.close();
		return -1;
	}
	data->fft_size = FMCW_RADAR_FFT_SIZE;
	std::snprintf(reinterpret_cast<char *>(data->raw_data), FMCW_RADAR_MAX_DATA_SIZE, "%s",
	              line.c_str());
	sim_file.close();
	return 0;
#endif
	// stub for now
	return 0;
}

/**
 * Stops the transmission of the FMCW signal.
 *
 * @return Returns 0 on success, -X on failure with failure code.
 */
int8_t OPS_FMCW::fmcw_radar_sensor_stop_tx_signal()
{
#ifdef RADAR_SIMULATION
	return 0;
#endif
	// stub for now
	return 0;
}

//------------------------------ Helper Functions -------------------------------
/**
 * Sends a command to the radar sensor over the serial port
 * @param cmd The command string to send.
 *
 * @return Returns 0 on success, -1 on failure.
 */
int8_t OPS_FMCW::send_command(const char *cmd)
{
	// stub for now.
	return 0;
}

/**
 * Reads a response from the radar sensor over the serial port. Note
 * std::string used due to dynamic length of response.
 * @param response The string to store the response.
 *
 * @return Returns 0 on success, -1 on failure.
 */
int8_t OPS_FMCW::read_response(std::string *response)
{
	// stub for now.
	return 0;
}
