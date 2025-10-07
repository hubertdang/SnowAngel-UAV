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

class OPS_FMCW : public FMCW_RADAR_SENSOR
{
    OPS_FMCW(uint8_t usb_port);

    int8_t sensor_init() override;
    int8_t sensor_read(fmcw_waveform_data_t & data)  override;
    int8_t sensor_start() override;
    int8_t sensor_stop()  override;
    ~OPS_FMCW() override {}
};

#endif // #ifndef OPS_FMCW_H