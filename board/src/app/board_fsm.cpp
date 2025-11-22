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
#include "bsp/gps.hpp"
#include "bsp/start_switch.hpp"
#include "bsp/temperature_sensor.hpp"
#include "common/common.h"
#include "common/logging.h"
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>

static constexpr double EARTH_RADIUS_METERS = 6371000.0;
static constexpr double STOPPED_THRESHOLD_METERS = 0.5;

START_SWITCH *start_switch = nullptr;
TEMPERATURE_SENSOR *temp_sensor = nullptr;
FMCW_RADAR_SENSOR *fmcw_radar_sensor = nullptr;
GPS *gps = nullptr;

enum board_state board_fsm_init();
enum board_state board_fsm_idle();
enum board_state board_fsm_flying();
enum board_state board_fsm_stationary();
enum board_state board_fsm_fault();
enum board_state board_fsm_cleanup();

double haversine(double lat1, double lon1, double lat2, double lon2);

/**
 * Process a board state. Note that the next state is not always a different state.
 *
 * @param state The state to process
 *
 * @return The next state
 */
enum board_state board_fsm_process(enum board_state state)
{
	switch (state)
	{
	case BOARD_STATE_INIT:
		return board_fsm_init();
	case BOARD_STATE_IDLE:
		return board_fsm_idle();
	case BOARD_STATE_FLYING:
		return board_fsm_flying();
	case BOARD_STATE_STATIONARY:
		return board_fsm_stationary();
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

	gps = instantiate_gps();
	if ((rc = gps->gps_init()) != SUCCESS)
	{
		logging_write(LOG_ERROR, "GPS module init failed! (err %d)", rc);
		return BOARD_STATE_FAULT;
	}

	return BOARD_STATE_IDLE;
}

enum board_state board_fsm_idle()
{
	uint8_t rc;
	uint8_t switch_val;

	if ((rc = start_switch->start_switch_read(&switch_val)) != SUCCESS)
	{
		logging_write(LOG_ERROR, "Start switch read failed! (err %d)", rc);
		return BOARD_STATE_FAULT;
	}

	if (switch_val == SWITCH_START)
	{
		logging_write(LOG_INFO, "Switch flipped to \"START\"");
		return BOARD_STATE_FLYING;
	}

	return BOARD_STATE_IDLE;
}

enum board_state board_fsm_flying()
{
	/* GPS is noisy, so we require several consecutive stationary readings
	 * before we can confidently say the drone is stationary. */
	const uint8_t STATIONARY_READS_REQUIRED = 5;
	static uint8_t num_stationary_reads = 0;

	static gps_data_t previous_gps_data{};
	gps_data_t current_gps_data{};
	double distance_moved_meters;

	static bool has_previous_gps_data = false;

	uint8_t rc;

	if ((rc = gps->gps_read(&current_gps_data)) != SUCCESS)
	{
		logging_write(LOG_ERROR, "GPS read failed! (err %d)", rc);
		return BOARD_STATE_FAULT;
	}

	/* There is no valid previous data on first iteration, so skip to next */
	if (!has_previous_gps_data)
	{
		previous_gps_data = current_gps_data;
		has_previous_gps_data = true;
		return BOARD_STATE_FLYING;
	}

	distance_moved_meters = haversine(previous_gps_data.latitude, previous_gps_data.longitude,
	                                  current_gps_data.latitude, current_gps_data.longitude);
	previous_gps_data = current_gps_data;

	if (distance_moved_meters < STOPPED_THRESHOLD_METERS)
	{
		num_stationary_reads++;
	}
	else
	{
		/* Reset count in case we were stationary and started moving again */
		num_stationary_reads = 0;
	}

	if (num_stationary_reads == STATIONARY_READS_REQUIRED)
	{
		logging_write(LOG_INFO, "Drone stopped moving");
		num_stationary_reads = 0;
		return BOARD_STATE_STATIONARY;
	}

	return BOARD_STATE_FLYING;
}

enum board_state board_fsm_stationary()
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
	delete gps;

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
	case BOARD_STATE_FLYING:
		return "BOARD_STATE_FLYING";
	case BOARD_STATE_STATIONARY:
		return "BOARD_STATE_STATIONARY";
	case BOARD_STATE_FAULT:
		return "BOARD_STATE_FAULT";
	case BOARD_STATE_CLEANUP:
		return "BOARD_STATE_CLEANUP";
	case BOARD_STATE_DONE:
		return "BOARD_STATE_DONE";
	default:
		return "BOARD_STATE_INVALID";
	}
}

/**
 * Compute the distance between two points on Earth (latitude/longitude in degrees).
 *
 * @param lat1 Latitude of the first point, in degrees.
 * @param lon1 Longitude of the first point, in degrees.
 * @param lat2 Latitude of the second point, in degrees.
 * @param lon2 Longitude of the second point, in degrees.
 *
 * @return The distance in meters.
 */
double haversine(double lat1, double lon1, double lat2, double lon2)
{
	const double R = EARTH_RADIUS_METERS;

	// convert degrees to radians
	lat1 = lat1 * M_PI / 180.0;
	lon1 = lon1 * M_PI / 180.0;
	lat2 = lat2 * M_PI / 180.0;
	lon2 = lon2 * M_PI / 180.0;

	double dLat = lat2 - lat1;
	double dLon = lon2 - lon1;

	double a = std::sin(dLat / 2) * std::sin(dLat / 2) +
	           std::cos(lat1) * std::cos(lat2) * std::sin(dLon / 2) * std::sin(dLon / 2);

	double c = 2 * std::atan2(std::sqrt(a), std::sqrt(1 - a));

	return R * c;
}
