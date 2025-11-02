/**
 *
 * Name: start_switch.hpp
 * Author: Hubert Dang
 *
 * This file describes the public interface to the start/stop switch.
 *
 * Date: November 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef START_SWITCH_H
#define START_SWITCH_H

#include <cstdint>

/* TODO: update these to reflect what the switch actually reads */
#define SWITCH_START 1
#define SWITCH_STOP 0

class START_SWITCH
{
public:
	// the following functions describe the public interface.
	// CAUTION! CAUTION! DO NOT describe the state or implementation of the sensor.
	// CAUTION! CAUTION! Please be wary if deciding to change the interface. You
	//                   risk exposing extra information to the application code.

	// Pure virtual functions enforce child class implementations
	virtual int8_t start_switch_init() = 0;
	virtual int8_t start_switch_read(uint8_t *data) = 0;

	virtual ~START_SWITCH() {}
	// do not declare anything as private or protected
};

START_SWITCH *instantiate_start_switch();

//----------------------------------------------------------------

#endif // #ifndef START_SWITCH_H
