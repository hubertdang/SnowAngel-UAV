/**
 *
 * Name: board_fsm.cpp
 * Author: Hubert Dang
 *
 * Implementation of the finite state machine logic for the drone subsystem
 * board.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include "board_fsm.hpp"
#include "bsp/fmcw_radar_sensor.hpp"
#include "bsp/start_switch.hpp"
#include "bsp/temperature_sensor.hpp"
#include "common/common.h"
#include "common/logging.h"
#include <cstdio>
#include <cstdlib>

START_SWITCH *start_switch = nullptr;
TEMPERATURE_SENSOR *temp_sensor = nullptr;
FMCW_RADAR_SENSOR *fmcw_radar_sensor = nullptr;

enum board_state board_fsm_init();
enum board_state board_fsm_idle();
enum board_state board_fsm_wait();
enum board_state board_fsm_read();
enum board_state board_fsm_fault();
enum board_state board_fsm_cleanup();

const char *board_fsm_state_to_str(enum board_state state);

enum board_state board_fsm_process(enum board_state state)
{
	logging_write(LOG_INFO, "Processing %s", board_fsm_state_to_str(state));

	switch (state)
	{
	case BOARD_STATE_INIT:
		return board_fsm_init();
	case BOARD_STATE_IDLE:
		return board_fsm_idle();
	case BOARD_STATE_WAIT:
		return board_fsm_wait();
	case BOARD_STATE_READ:
		return board_fsm_read();
	case BOARD_STATE_FAULT:
		return board_fsm_fault();
	case BOARD_STATE_CLEANUP:
		return board_fsm_cleanup();
	default:
		return board_fsm_fault();
	}
}

enum board_state board_fsm_init()
{
	int rc;

	start_switch = instantiate_start_switch();
	if ((rc = start_switch->start_switch_init()) != SUCCESS)
	{
		logging_write(LOG_ERROR, "Start switch init failed! (err %d)", rc);
		return BOARD_STATE_FAULT;
	}

	temp_sensor = instantiate_temperature_sensor();
	if ((rc = temp_sensor->temperature_sensor_init()) != SUCCESS)
	{
		logging_write(LOG_ERROR, "Temperature sensor init failed! (err %d)", rc);
		return BOARD_STATE_FAULT;
	}

	fmcw_radar_sensor = instantiate_fmcw_radar_sensor();
	if ((rc = fmcw_radar_sensor->fmcw_radar_sensor_init()) != SUCCESS)
	{
		logging_write(LOG_ERROR, "FMCW radar sensor init failed! (err %d)", rc);
		return BOARD_STATE_FAULT;
	}

	return BOARD_STATE_IDLE;
}

enum board_state board_fsm_idle()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}

enum board_state board_fsm_wait()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}

enum board_state board_fsm_read()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}

enum board_state board_fsm_fault()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_CLEANUP;
}

enum board_state board_fsm_cleanup()
{
	delete start_switch;
	delete temp_sensor;
	delete fmcw_radar_sensor;

	return BOARD_STATE_DONE;
}

const char *board_fsm_state_to_str(enum board_state state)
{
	switch (state)
	{
	case BOARD_STATE_INIT:
		return "BOARD_STATE_INIT";
	case BOARD_STATE_IDLE:
		return "BOARD_STATE_IDLE";
	case BOARD_STATE_WAIT:
		return "BOARD_STATE_WAIT";
	case BOARD_STATE_READ:
		return "BOARD_STATE_READ";
	case BOARD_STATE_FAULT:
		return "BOARD_STATE_FAULT";
	case BOARD_STATE_CLEANUP:
		return "BOARD_STATE_CLEANUP";
	default:
		return "BOARD_STATE_INVALID";
	}
}