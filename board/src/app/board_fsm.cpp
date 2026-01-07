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
#include "bsp/temperature_sensor.hpp"
#include "common/common.h"
#include "common/logging.h"
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <unistd.h>

constexpr const char *RAW_DATA_CSV = "./snow_angel_uav_raw.csv";

constexpr int GPS_POLL_RATE_USEC = 1000000;

constexpr double STOPPED_THRESHOLD_METERS = 2.0;
constexpr double FLYING_THRESHOLD_METERS = 3.0;

constexpr int STABLIZATION_TIME_USEC = 2000000;

TEMPERATURE_SENSOR *temp_sensor = nullptr;
FMCW_RADAR_SENSOR *fmcw_radar_sensor = nullptr;
GPS *gps = nullptr;

std::ofstream raw_data_csv;

enum board_state board_fsm_init();
enum board_state board_fsm_flying();
enum board_state board_fsm_stationary();
enum board_state board_fsm_fault();
enum board_state board_fsm_cleanup();

int8_t wait_until_stationary();
int8_t wait_until_flying();

void persist_to_csv(double lat, double lon, double tmp, uint8_t *waveform, size_t waveform_len);
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

	raw_data_csv.open(RAW_DATA_CSV, std::ios::app);
	if (!raw_data_csv.is_open())
	{
		logging_write(LOG_ERROR, "Failed to open %s", RAW_DATA_CSV);
		return BOARD_STATE_FAULT;
	}

	return BOARD_STATE_FLYING;
}

/**
 * Wait until the drone becomes stationary. GPS is noisy, so we require several consecutive
 * stationary readings before we can confidently say the drone is stationary.
 *
 * @return 0 on success, negative number otherwise.
 */
int8_t wait_until_stationary()
{
	constexpr uint8_t STATIONARY_READS_REQUIRED = 2;

	uint8_t rc = 0;
	uint8_t num_stationary_reads = 0;
	double cumulative_distance_moved_meters = 0.0;
	gps_data_t previous_gps_data{};
	gps_data_t current_gps_data{};

	/* Get initial coordinates */
	if ((rc = gps->gps_read(&previous_gps_data)) != SUCCESS)
	{
		logging_write(LOG_ERROR, "GPS read failed! (err %d)", rc);
		return rc;
	}

	/* Poll GPS to check if we've stopped flying */
	while (true)
	{
		usleep(GPS_POLL_RATE_USEC);

		if ((rc = gps->gps_read(&current_gps_data)) != SUCCESS)
		{
			logging_write(LOG_ERROR, "GPS read failed! (err %d)", rc);
			return rc;
		}

		cumulative_distance_moved_meters +=
		    haversine(previous_gps_data.latitude, previous_gps_data.longitude,
		              current_gps_data.latitude, current_gps_data.longitude);
		previous_gps_data = current_gps_data;

		logging_write(LOG_INFO, "cumulative_distance_moved_meters = %f",
		              cumulative_distance_moved_meters);

		if (cumulative_distance_moved_meters < FLYING_THRESHOLD_METERS)
		{
			num_stationary_reads++;
		}
		else
		{
			num_stationary_reads = 0;             // Reset because we started moving again
			cumulative_distance_moved_meters = 0; // Reset because we started moving again
			logging_write(LOG_INFO, "Reset count");
		}

		if (num_stationary_reads == STATIONARY_READS_REQUIRED)
			break; // Drone is stationary
	}

	return SUCCESS;
}

/**
 * Wait until the drone starts flying. GPS is noisy, so we require several consecutive
 * flying readings before we can confidently say the drone is flying.
 *
 * @return 0 on success, negative number otherwise.
 */
int8_t wait_until_flying()
{
	uint8_t rc = 0;
	double distance_moved_meters = 0.0;
	gps_data_t initial_gps_data{};
	gps_data_t current_gps_data{};

	/* Get initial coordinates */
	if ((rc = gps->gps_read(&initial_gps_data)) != SUCCESS)
	{
		logging_write(LOG_ERROR, "GPS read failed! (err %d)", rc);
		return rc;
	}

	/* Poll GPS to check if we're far away enough from our initial location */
	while (true)
	{
		usleep(GPS_POLL_RATE_USEC);

		if ((rc = gps->gps_read(&current_gps_data)) != SUCCESS)
		{
			logging_write(LOG_ERROR, "GPS read failed! (err %d)", rc);
			return rc;
		}

		distance_moved_meters = haversine(initial_gps_data.latitude, initial_gps_data.longitude,
		                                  current_gps_data.latitude, current_gps_data.longitude);

		logging_write(LOG_INFO, "distance_moved_meters = %f", distance_moved_meters);

		if (distance_moved_meters >= FLYING_THRESHOLD_METERS)
		{
			break; // Drone is flying
		}
	}

	return SUCCESS;
}

enum board_state board_fsm_flying()
{
	if (wait_until_stationary() != SUCCESS)
		return BOARD_STATE_FAULT;
	return BOARD_STATE_STATIONARY;
}

void persist_to_csv(double lat, double lon, double tmp, uint8_t *waveform, size_t waveform_len)
{
	constexpr double GPS_DATA_PRECISION = 6; // Number of decimal places
	constexpr double TMP_DATA_PRECISION = 2; // Number of decimal places

	auto now = std::time(nullptr);
	auto tm = *std::localtime(&now);

	std::ostringstream csv_line;
	csv_line << std::put_time(&tm, "%Y-%m-%d %H:%M:%S") << "," << std::fixed
	         << std::setprecision(GPS_DATA_PRECISION) << lat << "," << lon << ","
	         << std::setprecision(TMP_DATA_PRECISION) << tmp << ","
	         << std::string(waveform, waveform + waveform_len);
	raw_data_csv << csv_line.str() << "\n";
	raw_data_csv.flush();
}

enum board_state board_fsm_stationary()
{
	constexpr int NUM_RADAR_READS_PER_STOP = 10;

	usleep(STABLIZATION_TIME_USEC); // Extra time to let the drone settle before transmitting radar

	fmcw_radar_sensor->fmcw_radar_sensor_start_tx_signal();

	gps_data_t gps_data;
	temp_sensor_data_t tmp_data;
	fmcw_waveform_data_t waveform_data;

	int8_t rc;

	/* Profile ice thickness */
	for (int read_count = 0; read_count < NUM_RADAR_READS_PER_STOP; read_count++)
	{
		if ((rc = gps->gps_read(&gps_data)) != SUCCESS)
		{
			logging_write(LOG_ERROR, "GPS read failed! (err %d)", rc);
			return BOARD_STATE_FAULT;
		}

		if ((rc = temp_sensor->temperature_sensor_read(&tmp_data)) != SUCCESS)
		{
			logging_write(LOG_ERROR, "Temperature sensor read failed! (err %d)", rc);
			return BOARD_STATE_FAULT;
		}

		if ((rc = fmcw_radar_sensor->fmcw_radar_sensor_read_rx_signal(&waveform_data)) != SUCCESS)
		{
			logging_write(LOG_ERROR, "FMCW radar sensor read failed! (err %d)", rc);
			return BOARD_STATE_FAULT;
		}

		persist_to_csv(gps_data.latitude, gps_data.longitude, tmp_data.temperature,
		               waveform_data.raw_data, sizeof(waveform_data.raw_data));
	}

	fmcw_radar_sensor->fmcw_radar_sensor_stop_tx_signal();

	if (wait_until_flying() != SUCCESS)
		return BOARD_STATE_FAULT;
	return BOARD_STATE_FLYING;
}

enum board_state board_fsm_fault()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_CLEANUP;
}

enum board_state board_fsm_cleanup()
{
	delete temp_sensor;
	delete fmcw_radar_sensor;
	delete gps;

	if (raw_data_csv.is_open())
		raw_data_csv.close();

	return BOARD_STATE_DONE;
}

const char *board_fsm_state_to_str(enum board_state state)
{
	switch (state)
	{
	case BOARD_STATE_INIT:
		return "BOARD_STATE_INIT";
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
	constexpr double EARTH_RADIUS_METERS = 6371000.0;
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
