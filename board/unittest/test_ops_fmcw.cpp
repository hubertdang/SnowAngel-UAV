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
#include <unistd.h>
#include <sstream>
#include "bsp/fmcw_radar_sensor.hpp"

int main(void)
{
    // Test instance creation
    FMCW_RADAR_SENSOR *radar = instantiate_fmcw_radar_sensor();
    assert(radar != nullptr);

    // Test initialization
    int8_t init_result = radar->fmcw_radar_sensor_init();
    assert(init_result == 0);

    int8_t start_tx_result = radar->fmcw_radar_sensor_start_tx_signal();
    assert(start_tx_result == 0);

    usleep(1000000); // 1s sleep to give time to sensor to start
    // Test reading radar data
    fmcw_waveform_data_t radar_data = {};
    int8_t read_result = radar->fmcw_radar_sensor_read_rx_signal(&radar_data);
    assert(read_result == 0);
    assert(radar_data.raw_data[0] != 0); // check that some data is populated
    printf("Raw FFT data obtained: \"%s\"\n", radar_data.raw_data);

    int commas = 0;
    for (int i = 0; radar_data.raw_data[i] != '\0'; ++i) {
        if (radar_data.raw_data[i] == ',')
            ++commas;
    }
    int count = commas + 1;
    assert(count == 512); // Ensure we have 512 samples

    int8_t stop_result = radar->fmcw_radar_sensor_stop_tx_signal();
    assert(stop_result == 0);

    printf("All tests passed successfully.\n");
    return 0;
}
