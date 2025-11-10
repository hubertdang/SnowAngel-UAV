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
#include <cstring>
#include <errno.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

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
FMCW_RADAR_SENSOR *OPS_FMCW::get_fmcw_radar_instance(const char *usb_port)
{
	if (instance == nullptr)
		instance = new OPS_FMCW(usb_port);
	return instance;
}

/**
 * Constructor for the OPS_FMCW class.
 * @param usb_port The USB port number where the radar sensor is connected.
 */
OPS_FMCW::OPS_FMCW(const char *usb_port) : usb_port(usb_port) {}

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
	fd = open(FMCW_RADAR_USB_PORT, O_RDWR | O_NOCTTY | O_SYNC);
	if (fd < 0)
	{
		printf("Failed to open USB port to OPS 241-B: `%s`\n", FMCW_RADAR_USB_PORT);
		return -1;
	}

	struct termios tty = {0};
	if (tcgetattr(fd, &tty) != 0)
	{
		printf("Failed to get current tty attributes with error: %s\n", strerror(errno));
		return -2;
	}

	cfsetospeed(&tty, FMCW_RADAR_BAUD_RATE);
	cfsetispeed(&tty, FMCW_RADAR_BAUD_RATE);

	// Configure serial port protocol
	tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8; // 8-bit chars
	tty.c_iflag &= ~IGNBRK;                     // Don't ignore break characters
	tty.c_lflag = 0;                            // no signaling chars, no echo
	tty.c_oflag = 0;                            // no remapping
	tty.c_cc[VMIN] = 1;                         // read at least 1 char
	tty.c_cc[VTIME] = 1;                        // or 0.1s read timeout

	tty.c_iflag &= ~(IXON | IXOFF | IXANY);     // turn off s/w flow control
	tty.c_cflag |= (CLOCAL | CREAD);            // ignore modem controls
	tty.c_cflag &= ~(PARENB | PARODD);          // no parity
	tty.c_cflag &= ~CSTOPB;                     // 1 stop bit
	tty.c_cflag &= ~CRTSCTS;                    // no hw flow control

	if (tcsetattr(fd, TCSANOW, &tty) != 0)
	{
		printf("Failed to set tty attributes with error: %s\n", strerror(errno));
		return -3;
	}

	// Temporarily disable continious stream (to query sensor)
	send_command(FMCW_CMD_DISABLE_STREAM);
	send_command(FMCW_CMD_TURN_ON_FFT);
	send_command(FMCW_CMD_TURN_ON_ADC);
	send_command(FMCW_CMD_TURN_OFF_FFT);
	send_command(FMCW_CMD_TURN_OFF_ADC);
	usleep(1000000); // 100ms delay to let the configuration settle

	// Query device information
	std::string response;
	query(FMCW_CMD_INFO, &response, 8);
	printf("FMCW radar information: %s\n", response.c_str());

	// Setup radar for FFT data
	send_command(FMCW_CMD_JSON_MODE);
	send_command(FMCW_CMD_PRECISION);
	send_command(FMCW_CMD_SET_UNITS_M);
	send_command(FMCW_CMD_SET_FFT_SIZE);
	send_command(FMCW_CMD_SET_ZEROS);

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
	send_command(FMCW_CMD_TURN_ON_FFT); // starts continiously streaming FFT data
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
		return -2;
	}
	std::snprintf(reinterpret_cast<char *>(data->raw_data), FMCW_RADAR_MAX_DATA_SIZE, "%s",
	              line.c_str());
	sim_file.close();
	return 0;
#endif
	tcflush(fd, TCIFLUSH); // clear the input buffer of stale data

	// Read the FFT data
	for (int8_t i = 0; i < 10; i++)
	{
		std::string fft_data;
		read_response(&fft_data);

		std::string pattern = "{\"FFT\":[";
		size_t start = fft_data.find(pattern);
		if (start != std::string::npos)
			fft_data.erase(0, start + pattern.size());
		else
			continue; // line not valid

		size_t end = fft_data.find("]}");
		if (end != std::string::npos)
			fft_data.erase(end);
		else
			continue; // line not valid
		memcpy(data->raw_data, fft_data.c_str(), FMCW_RADAR_MAX_DATA_SIZE);
		return 0;
	}
	return -1;
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
	send_command(FMCW_CMD_TURN_OFF_FFT);
	return 0;
}

//------------------------------ Helper Functions -------------------------------
/**
 * Sends a command to the radar sensor over the serial port
 * @param cmd The command string to send.
 *
 * @return Returns 0 on success, -1 on failure.
 */
int8_t OPS_FMCW::send_command(std::string cmd)
{
	std::string command = cmd + "\r\n";
	ssize_t written = write(fd, command.c_str(), command.size());
	if (written != (ssize_t)command.size())
		return -1;
	return 0;
}

/**
 * Reads a line from the radar sensor over the serial port. Note
 * std::string used due to dynamic length of response.
 * @param response The string to store the response.
 *
 * @return Returns 0 on success, -1 on failure.
 */
int8_t OPS_FMCW::read_response(std::string *response)
{
	char ch;
	while (true)
	{
		int n = read(fd, &ch, 1); // reading 1 character at a time
		if (n > 0)
		{
			if (ch == '\n' || ch == '\r') // end of line
				break;
			else
				*response += ch;
		}
		else if (n < 0)
		{
			printf("Failed to read response with error: %s\n", strerror(errno));
			break;
		}
		else       // EoF or nore more characters
			break; // timeout
	}
	return 0;
}

/**
 * Sends a command to the radar sensor and reads the response.
 * @param cmd The command string to send.
 * @param response The string to store the response.
 * @param num_lines The number of lines to read from the response. Default is 1
 *
 * @return Returns 0 on success, -1 on failure with failure code.
 */
int8_t OPS_FMCW::query(std::string cmd, std::string *response, uint8_t num_lines)
{
	tcflush(fd, TCIFLUSH); // flush the input buffer of stail data
	send_command(cmd);
	usleep(1000000); // Pi runs faster than radar, give 100ms buffer time
	for (int8_t i = 0; i < num_lines; i++)
		read_response(response);
	return 0;
}

FMCW_RADAR_SENSOR *instantiate_fmcw_radar_sensor()
{
	return OPS_FMCW::get_fmcw_radar_instance(FMCW_RADAR_USB_PORT);
}
