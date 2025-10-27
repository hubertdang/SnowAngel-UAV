/**
 * Name: adafruit_tm117.hpp
 * Author: Karran Dhillon
 *
 * This file describes the prviate interface for the ADAFRUIT-TM117
 * Temperature sensor.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef ADAFRUIT_TM117_H
#define ADAFRUIT_TM117_H

#include "bsp/temperature_sensor.hpp"
#include <fcntl.h>
#include <iostream>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define TMP117_I2C_ADDR 0x48
#define TMP117_SDA_PIN 3 // GPIO2
#define TMP117_SCL_PIN 5 // GPIO3
#define TMP117_I2C_ID "/dev/i2c-1"

class ADAFRUIT_TM117 : public TEMPERATURE_SENSOR
{
public:
	static TEMPERATURE_SENSOR *get_temperature_sensor_instance(const uint8_t i2c_addr);

	// ADADRUIT_TM117 should not be cloneable
	ADAFRUIT_TM117(ADAFRUIT_TM117 &other) = delete;

	// ADAFRUIT_TM117 should not be assignable
	void operator=(const ADAFRUIT_TM117 &) = delete;

	int8_t temperature_sensor_init() override;
	int8_t temperature_sensor_read(temp_sensor_data_t *data) override;

	~ADAFRUIT_TM117() override;

private:
	// constructor is private to enforce factory function usage
	ADAFRUIT_TM117(uint8_t i2c_addr);

private:
	static ADAFRUIT_TM117 *instance;
	uint8_t i2c_addr;
	int fd; // file descriptor
};
#endif // #ifndef ADAFRUIT_TM117_H
