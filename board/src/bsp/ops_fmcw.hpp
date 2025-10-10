/**
 *
 * Name: ops_fmcw.hpp
 * Author: Karran Dhillon
 *
 * This file describes the private interface for the OPS-243C FMCW radar sensor.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef OPS_FMCW_H
#define OPS_FMCW_H

#include "bsp/fmcw_radar_sensor.hpp"
#include <cstdint>
#include <string>

class OPS_FMCW : public FMCW_RADAR_SENSOR
{
public:
	OPS_FMCW(uint8_t usb_port);

	int8_t fmcw_radar_sensor_init() override;
	int8_t fmcw_radar_sensor_read_rx_signal(fmcw_waveform_data_t *data) override;
	int8_t fmcw_radar_sensor_start_tx_signal() override;
	int8_t fmcw_radar_sensor_stop_tx_signal() override;
	~OPS_FMCW() override {}

private:
	int8_t send_command(const char *cmd);
	int8_t read_response(std::string *response);

private:
	uint8_t usb_port;
};

#endif // #ifndef OPS_FMCW_H