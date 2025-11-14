/**
 * Name: adafruit_ultimate_gps_pa1616d.cpp
 * Author: Hubert Dang
 *
 * This file implements the functions declared in adafruit_ultimate_gps_pa1616d.hpp
 *
 * Date: November 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include "adafruit_ultimate_gps_pa1616d.hpp"
#include "bsp/gps.hpp"
#include "common/logging.h"
#include <fcntl.h>
#include <sstream>
#include <string>
#include <termios.h>
#include <vector>

#define GNGGA_FIELD_LATITUDE 2
#define GNGGA_FIELD_NS_HEMISPHERE 3
#define GNGGA_FIELD_LONGITUDE 4
#define GNGGA_FIELD_EW_HEMISPHERE 5
#define GNGGA_FIELD_FIX_QUALITY 6

#define GNGGA_INVALID_FIX "0"

#define GPS_INIT_TIMEOUT 60

std::vector<std::string> split_nmea_sentence(const std::string &sentence);

static double nmea_coordinate_to_double(const std::string &coordinate,
                                        const std::string &hemisphere);

ADAFRUIT_ULTIMATE_GPS_PA1616D *ADAFRUIT_ULTIMATE_GPS_PA1616D::instance = nullptr;

ADAFRUIT_ULTIMATE_GPS_PA1616D::ADAFRUIT_ULTIMATE_GPS_PA1616D() : fd(-1) {}

ADAFRUIT_ULTIMATE_GPS_PA1616D::~ADAFRUIT_ULTIMATE_GPS_PA1616D()
{
	if (fd >= 0)
		close(fd);
}

GPS *instantiate_gps()
{
	return ADAFRUIT_ULTIMATE_GPS_PA1616D::get_gps_instance();
}

/**
 * Factory function to instance the GPS.
 *
 * @return Pointer to the instantiated ADAFRUIT_ULTIMATE_GPS_PA1616D singleton.
 */
GPS *ADAFRUIT_ULTIMATE_GPS_PA1616D::get_gps_instance()
{
	if (instance == nullptr)
		instance = new ADAFRUIT_ULTIMATE_GPS_PA1616D();
	return instance;
}

/**
 * Initialized the GPS.
 *
 * @return 0 on success, -X on failure with failure code
 */
int8_t ADAFRUIT_ULTIMATE_GPS_PA1616D::gps_init()
{
#ifdef RADAR_SIMULATION
	return 0;
#endif
	fd = open(GPS_SERIAL_DEVICE, O_RDWR);
	if (fd < 0)
		return -1;

	if (!configure_serial())
		return -2;

	int seconds_elasped = 0;
	std::string sentence;

	// GPS might take some time to search for satellites.
	while (seconds_elasped < GPS_INIT_TIMEOUT)
	{
		if (read_nmea_gngga_sentence(sentence))
		{
			std::vector<std::string> fields = split_nmea_sentence(sentence);
			if (fields.size() > GNGGA_FIELD_FIX_QUALITY &&
			    fields[GNGGA_FIELD_FIX_QUALITY] != GNGGA_INVALID_FIX)
			{
				return 0;
			}
		}

		sleep(1);
		seconds_elasped++;
	}

	// Breaking out of the loop means we timed out.
	return -3;
}

bool ADAFRUIT_ULTIMATE_GPS_PA1616D::configure_serial()
{
	struct termios tty;

	if (tcgetattr(fd, &tty) != 0)
	{
		logging_write(LOG_ERROR, "configure_serial: tcgetattr failed!");
		return false;
	}

	cfsetospeed(&tty, B9600);
	cfsetispeed(&tty, B9600);

	tty.c_cflag &= ~PARENB; // No parity
	tty.c_cflag &= ~CSTOPB; // 1 stop bit
	tty.c_cflag &= ~CSIZE;
	tty.c_cflag |= CS8;      // 8 data bits
	tty.c_cflag &= ~CRTSCTS; // No flow control
	tty.c_cflag |= CREAD | CLOCAL;

	tty.c_lflag &= ~ICANON;
	tty.c_lflag &= ~ECHO;
	tty.c_lflag &= ~ECHOE;
	tty.c_lflag &= ~ISIG;

	tty.c_iflag &= ~(IXON | IXOFF | IXANY);
	tty.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL);

	tty.c_oflag &= ~OPOST;
	tty.c_oflag &= ~ONLCR;

	tty.c_cc[VMIN] = 1;  // read at least 1 byte
	tty.c_cc[VTIME] = 1; // timeout in deciseconds

	if (tcsetattr(fd, TCSANOW, &tty) != 0)
	{
		logging_write(LOG_ERROR, "configure_serial: tcsetattr failed!");
		return false;
	}

	return true;
}

/**
 * Read data from GPS.
 * @param data pointer to store the gps data.
 *
 * @return 0 on success, -X on failure with failure code.
 */
int8_t ADAFRUIT_ULTIMATE_GPS_PA1616D::gps_read(gps_data_t *data)
{
#ifdef RADAR_SIMULATION
	return 0;
#endif
	if (fd < 0)
		return -1;

	if (!data)
		return -2;

	std::string line;

	// Keep reading until we get a valid GNGGA sentence
	while (!read_nmea_gngga_sentence(line))
	{
	}

	std::vector<std::string> fields = split_nmea_sentence(line);

	data->latitude =
	    nmea_coordinate_to_double(fields[GNGGA_FIELD_LATITUDE], fields[GNGGA_FIELD_NS_HEMISPHERE]);
	data->longitude =
	    nmea_coordinate_to_double(fields[GNGGA_FIELD_LONGITUDE], fields[GNGGA_FIELD_EW_HEMISPHERE]);

	return 0;
}

/*
 * Read a GNGGA NMEA sentence from the GPS module, e.g.,
 *
 * $GNGGA,012422.000,4515.9532,N,07543.7486,W,2,14,0.89,97.1,M,-34.2,M,,*77.
 *
 * An NMEA sentence is a string of data outputted from GPS modules. NMEA is a common standard
 * for GPS modules. GNGGA is a type of NMEA sentence that provides latitude and longitude.
 */
bool ADAFRUIT_ULTIMATE_GPS_PA1616D::read_nmea_gngga_sentence(std::string &sentence)
{
	static char serial_buf[SERIAL_BUF_SIZE];
	static int serial_buf_idx;
	char ch;

	/* Read by byte instead of a full line because the serial port delivers streaming bytes,
	 * not full lines. */
	while (read(fd, &ch, 1) == 1)
	{
		if (ch == '\n')
		{
			serial_buf[serial_buf_idx] = '\0';
			std::string line(serial_buf);
			serial_buf_idx = 0;

			if (line.rfind(GNGGA_SENTENCE_HEADER, 0) == 0)
			{
				sentence = line;
				return true;
			}
		}
		else if (serial_buf_idx < SERIAL_BUF_SIZE - 1)
		{
			serial_buf[serial_buf_idx++] = ch;
		}
		else
		{
			// Reset idx to prevent buffer overflow
			serial_buf_idx = 0;
		}
	}

	return false;
}

/*
 * Split an NMEA sentence into a vector of strings, each representing an individual field.
 */
std::vector<std::string> split_nmea_sentence(const std::string &sentence)
{
	std::vector<std::string> fields;
	std::stringstream ss(sentence);
	std::string field;

	while (std::getline(ss, field, ','))
	{
		fields.push_back(field);
	}

	return fields;
}

/*
 * Convert an NMEA sentence-formated ASCII coordinate to double.
 */
static double nmea_coordinate_to_double(const std::string &coordinate,
                                        const std::string &hemisphere)
{
	if (coordinate.empty())
		return 0;

	double raw = std::stod(coordinate);
	double deg = static_cast<int>(raw / 100);
	double min = raw - (deg * 100);
	double dec = deg + min / 60.0;

	// Convention is that N and E are positive, while S and W are negative
	if (hemisphere == "S" || hemisphere == "W")
		dec *= -1;

	return dec;
}
