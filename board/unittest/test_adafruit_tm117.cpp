/**
 * Name: test_adafruit_tm177.cpp
 * Author: Karran Dhillon
 *
 * Unit test file for the adafruit_tm117.cpp functions
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include <cassert>
#include <cstdio>
#include <cstdint>
#include "bsp/temperature_sensor.hpp"

int main()
{
    // Test instance creation
    TEMPERATURE_SENSOR *sensor = instantiate_temperature_sensor();
    assert(sensor != nullptr);

    // Test initialization
    int8_t init_result = sensor->temperature_sensor_init();
    assert(init_result == 0);

    // Test reading temperature
    temp_sensor_data_t temperature_data;
    int8_t read_result = sensor->temperature_sensor_read(&temperature_data);
    printf("Temperature: %.2f C\n", temperature_data.temperature);
    assert(read_result == 0);
    assert(temperature_data.temperature > -40.0f && temperature_data.temperature < 125.0f); // Assuming valid range for TMP117

    printf("All tests passed successfully.\n");
    return 0;
}
