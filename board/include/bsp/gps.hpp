/**
 *
 * Name: gps.hpp
 * Author: Hubert Dang
 *
 * This file describes the public interface to the gps module.
 *
 * Date: November 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef GPS_H 
#define GPS_H 

#include <cstdint>

typedef struct gps_data
{
	double latitude;
	double longitude;
} gps_data_t;

class GPS
{
public:
	// the following functions describe the public interface.
	// CAUTION! CAUTION! DO NOT describe the state or implementation of the sensor.
	// CAUTION! CAUTION! Please be wary if deciding to change the interface. You
	//                   risk exposing extra information to the application code.

	// Pure virtual functions enforce child class implementations
	virtual int8_t gps_init() = 0;
	virtual int8_t gps_read(gps_data_t *data) = 0;

	virtual ~GPS() {}
	// do not declare anything as private or protected
};

GPS *instantiate_gps();

//----------------------------------------------------------------

#endif // #ifndef GPS_MODULE_H 
