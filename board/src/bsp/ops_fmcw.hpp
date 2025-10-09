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

// command shortcuts
//--------------------------------
// General commands
#define FMCW_CMD_INFO         "??" // gets module information (product name, serial number, firmware version)
#define FMCW_CMD_FMCW_MODE    "GD" // only operate in FMCW mode (opposed to CW)

// ADC/FFT configuration
// 256 samples, 2048 FFT size, 80kHz sampling rate
// 1.6ms chirp, (24.015GHz - 24.235GHz)
// 8.52cm range resolution (mimum distance between two objects to be detected separately)
#if FMCW_RADAR_FFT_SIZE == 2048
    #define FMCW_CMD_SET_FFT_CFG  "x8" // sets ADC to 256 samples, 80kHz sampling rate
#elif FMCW_RADAR_FFT_SIZE == 1024
    #define FMCW_CMD_SET_FFT_CFG  "x4"
#else
    #error "Unsupported FFT size"
#endif

#define FMCW_CMD_TURN_ON_FFT  "oF" // enables raw FFT output on serial port
#define FMCW_CMD_JSON_MODE    "OJ" // enables JSON output mode on serial port

// I/O commands
#define FMCW_CMD_LED_ON       "OL" // enable LED on radar sensor
#define FMCW_CMD_LED_OFF      "Ol"
//--------------------------------

class OPS_FMCW : public FMCW_RADAR_SENSOR
{
public:
    OPS_FMCW(uint8_t usb_port);

    int8_t fmcw_radar_sensor_init()  override;
    int8_t fmcw_radar_sensor_read_rx_signal(fmcw_waveform_data_t *data) override;
    int8_t fmcw_radar_sensor_start_tx_signal() override;
    int8_t fmcw_radar_sensor_stop_tx_signal()  override;
    ~OPS_FMCW() override {}

private:
    int8_t send_command(const std::string &cmd);
    int8_t read_response(std::string &response, const uint16_t timeout_ms = 1000);

private:
    uint8_t usb_port;
};

#endif // #ifndef OPS_FMCW_H