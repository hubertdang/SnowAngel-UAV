/**
 * Name: adafruit_tm117.cpp
 * Author: Karran Dhillon
 *
 * This file implements the functions declared in adafruit_tm117.hpp
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include "adafruit_tm117.hpp"

//---------------------------------------------------------------------
// static variable initialization
ADAFRUIT_TM117 *ADAFRUIT_TM117::instance = nullptr;

/**
 * Factory function to instance the temperature sensor
 * @param i2c_addr The I2C slave address of the temperature sensor
 *
 * @return Pointer to the instantiated ADAFRUIT_TM117 object.
 */
TEMPERATURE_SENSOR *ADAFRUIT_TM117::get_temperature_sensor_instance(const uint8_t i2c_addr)
{
	if (instance == nullptr)
		instance = new ADAFRUIT_TM117(i2c_addr);
	return instance;
}

/**
 * Constructor for the ADAFRUIT_TM117 class
 * @param i2c_addr The I2C slave address of the temperature sensor
 */
ADAFRUIT_TM117::ADAFRUIT_TM117(uint8_t i2c_addr) : i2c_addr(i2c_addr) {}

/**
 * Initialized the temperature sensor
 *
 * @return 0 on success, -X on failure with failure code
 */
int8_t ADAFRUIT_TM117::temperature_sensor_init()
{
	return 0; // stub for now
}

/**
 * Reads the current temperature sensor reading over I2C
 * @param data Pointer to the structure to store the recieved temperature
 *
 * @return 0 on success, -X on failure with failure code.
 */
int8_t ADAFRUIT_TM117::temperature_sensor_read(temp_sensor_data_t *data)
{
#ifdef RADAR_SIMULATION
	data->temperature = -12.4; // fake, hard-coded temperature data
	return 0;
#endif
	return 0;
}
