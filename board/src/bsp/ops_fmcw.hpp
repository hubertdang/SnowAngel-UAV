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

#include "bsp/sensor.h"
#include <cstdint>

class OPS_FMCW : public SENSOR
{
    OPS_FMCW(uint8_t usb_port);

    int sensor_init() override;
    int sensor_read() override;
    ~OPS_FMCW() override {}
};

#endif // #ifndef OPS_FMCW_H