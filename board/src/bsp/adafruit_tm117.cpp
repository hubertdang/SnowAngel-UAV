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
#ifdef RADAR_SIMULATION
	return 0;
#endif
	fd = open(TMP117_I2C_ID, O_RDWR);
	if (fd < 0)
	{
		printf("Failed to open I2C bus\n");
		return -1;
	}

	if (ioctl(fd, I2C_SLAVE, i2c_addr) < 0)
	{
		printf("Failed to set I2C slave address\n");
		close(fd);
		return -2;
	}
	return 0;
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
	uint8_t buf[2] = {};
	if (write(fd, buf, 1) != 1)
	{
		printf("Failed to write register address\n");
		close(fd);
		return -1;
	}

	if (read(fd, buf, 2) != 2)
	{
		printf("Failed to read temperature data\n");
		close(fd);
		return -2;
	}

	// TMP117 returns 16-bit signed value: bits 15:0 with 0.0078°C resolution
	int16_t raw = (buf[0] << 8) | buf[1];
	double temperature = raw * 0.0078125f; // 1/128 = 0.0078125

	printf("Temperature: %.4fC\n", temperature);
	data->temperature = temperature;
	close(fd);
	return 0;
}

TEMPERATURE_SENSOR *instantiate_temperature_sensor()
{
	return ADAFRUIT_TM117::get_temperature_sensor_instance(TMP117_I2C_ADDR);
}

ADAFRUIT_TM117::~ADAFRUIT_TM117()
{
	if (fd)
		close(fd);
}
