/**
 * Name: adafruit_ultimate_gps_pa1616d.hpp
 * Author: Hubert Dang
 *
 * This file describes the prviate interface for the Adafruit Ultimate GPS PA1616D breakout
 * gps module.
 *
 * Date: November 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef ADAFRUIT_ULTIMATE_GPS_PA1616D_H
#define ADAFRUIT_ULTIMATE_GPS_PA1616D_H

#include "bsp/gps.hpp"
#include <string>
#include <unistd.h>

class ADAFRUIT_ULTIMATE_GPS_PA1616D : public GPS
{
public:
	static GPS *get_gps_instance();

	// ADADRUIT_ULTIMATE_GPS_PA1616D should not be cloneable
	ADAFRUIT_ULTIMATE_GPS_PA1616D(ADAFRUIT_ULTIMATE_GPS_PA1616D &other) = delete;

	// ADADRUIT_ULTIMATE_GPS_PA1616D should not be assignable
	void operator=(const ADAFRUIT_ULTIMATE_GPS_PA1616D &) = delete;

	int8_t gps_init() override;
	int8_t gps_read(gps_data_t *data) override;

	~ADAFRUIT_ULTIMATE_GPS_PA1616D() override;

private:
	// constructor is private to enforce factory function usage
	ADAFRUIT_ULTIMATE_GPS_PA1616D();

	bool configure_serial();
	bool read_nmea_gngga_sentence(std::string &sentence);

private:
	static ADAFRUIT_ULTIMATE_GPS_PA1616D *instance;

	static constexpr const char *GPS_SERIAL_DEVICE = "/dev/serial0";
	static constexpr const char *GNGGA_SENTENCE_HEADER = "$GNGGA";
	static constexpr size_t SERIAL_BUF_SIZE = 256; // minimum safe NMEA sentence is 82 bytes

	int fd;
};

#endif // #ifndef ADAFRUIT_ULTIMATE_GPS_PA1616D_H
