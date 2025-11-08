/**
 * Name: test_ops_fmcw.cpp
 * Author: Karran Dhillon
 *
 * Unit test file for the ops_fmcw.cpp functions
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include <cassert>
#include <cstdio>
#include <cstdint>
#include "bsp/fmcw_radar_sensor.hpp"

int main(void)
{
    // Test instance creation
    FMCW_RADAR_SENSOR *radar = instantiate_fmcw_radar_sensor();
    assert(radar != nullptr);

    // Test initialization
    int8_t init_result = radar->fmcw_radar_sensor_init();
    assert(init_result == 0);

    // Test reading radar data
    fmcw_waveform_data_t radar_data;
    int8_t read_result = radar->fmcw_radar_sensor_read_rx_signal(&radar_data);
    assert(read_result == 0);

    printf("All tests passed successfully.\n");
    return 0;
}