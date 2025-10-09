/**
 * 
 * Name: ops_fmcw.cpp
 * Author: Karran Dhillon
 * 
 * This file describes the implementations for the OPS-243C FMCW radar sensor.
 * 
 * Date: October 2025
 * 
 * Copyright 2025 SnowAngel-UAV
 */


#include "ops_fmcw.hpp"

/**
 * Constructor for the OPS_FMCW class.
 * @param usb_port The USB port number where the radar sensor is connected.
 */
OPS_FMCW::OPS_FMCW(uint8_t usb_port)
 : usb_port(usb_port)
{
    // establish serial connection to radar
}

/**
 * Initializes the radar sensor.
 *
 * @return Returns 0 on success, -X on failure with failure code.
 */
int8_t OPS_FMCW::fmcw_radar_sensor_init()
{
#ifdef RADAR_STUBS
    return 1;
#endif
    return 0;
}

/**
 * Sends a command to the radar sensor over the serial port
 * @param cmd The command string to send.
 *
 * @return Returns 0 on success, -1 on failure.
 */
int8_t OPS_FMCW::send_command(const std::string &cmd)
{
    return 0;
}