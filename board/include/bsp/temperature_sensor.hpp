/**
 *
 * Name: temperature_sensor.hpp
 * Author: Karran Dhillon
 *
 * This file describes the public interface to the temperature sensor
 * bsp layer
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef TEMP_SENSOR_H
#define TEMP_SENSOR_H

#include <cstdint>
//----------------------------------------------------------------
typedef struct temp_sensor_data
{
	double temperature; // in celius to 2 decimal precision
} temp_sensor_data_t;

//----------------------------------------------------------------

class TEMPERATURE_SENSOR
{
public:
	// the following functions describe the public interface.
	// CAUTION! CAUTION! DO NOT describe the state or implementation of the sensor.
	// CAUTION! CAUTION! Please be wary if deciding to change the interface. You
	//                   risk exposing extra information to the application code.

	// Pure virtual functions enforce child class implementations
	virtual int8_t temperature_sensor_init() = 0;
	virtual int8_t temperature_sensor_read(temp_sensor_data_t *data) = 0;

	virtual ~TEMPERATURE_SENSOR() {}
	// do not declare anything as private or protected
};

TEMPERATURE_SENSOR *instantiate_temperature_sensor(uint8_t i2c_addr);

//----------------------------------------------------------------

#endif // #ifndef TEMP_SENSOR_H
