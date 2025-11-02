/**
 * TODO: replace "whatever_switch" and "WHATEVER_SWITCH" with actual switch name.
 *
 * Name: whatever_switch.hpp
 * Author: Hubert Dang
 *
 * This file describes the private interface for the whatever switch.
 *
 * Date: November 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef WHATEVER_SWITCH_H
#define WHATEVER_SWITCH_H

#include "bsp/start_switch.hpp"

class WHATEVER_SWITCH : public START_SWITCH
{
public:
	static START_SWITCH *get_start_switch_instance();

	// WHATEVER_SWITCH should not be cloneable
	WHATEVER_SWITCH(START_SWITCH &other) = delete;

	// WHATEVER_SWITCH should not be assignable
	void operator=(const START_SWITCH &) = delete;

	int8_t start_switch_init() override;
	int8_t start_switch_read(uint8_t *data) override;

	~WHATEVER_SWITCH() override;

private:
	// constructor is private to enforce factory function usage
	WHATEVER_SWITCH();

private:
	static WHATEVER_SWITCH *instance;
};

#endif // #ifndef WHATEVER_SWITCH_H
