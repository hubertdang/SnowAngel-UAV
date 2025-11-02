/**
 * Name: whatever_switch.cpp
 * Author: Hubert Dang
 *
 * This file implements the whatever switch functionality.
 *
 * Date: November 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include "whatever_switch.hpp"
#include "bsp/start_switch.hpp"
#include <cstdint>

WHATEVER_SWITCH *WHATEVER_SWITCH::instance = nullptr;

/**
 * Factory function to instantiate the start switch singleton.
 *
 * @return Pointer to the start switch singleton.
 */
START_SWITCH *WHATEVER_SWITCH::get_start_switch_instance()
{
	if (instance == nullptr)
		instance = new WHATEVER_SWITCH();
	return instance;
}

WHATEVER_SWITCH::WHATEVER_SWITCH() {}

/**
 * Initializes the start switch.
 *
 * @return 0 on success, -X on failure with failure code
 */
int8_t WHATEVER_SWITCH::start_switch_init()
{
	return 0;
}

/**
 * Reads the start switch's setting.
 *
 * @return 0 on success, -X on failure with failure code
 */
int8_t WHATEVER_SWITCH::start_switch_read(uint8_t *data)
{
	*data = SWITCH_START;
	return 0;
}

START_SWITCH *instantiate_start_switch()
{
	return WHATEVER_SWITCH::get_start_switch_instance();
}

WHATEVER_SWITCH::~WHATEVER_SWITCH() {}