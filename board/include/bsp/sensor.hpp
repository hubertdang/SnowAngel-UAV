/**
 * 
 * Name: sensor.hpp
 * Author: Karran Dhillon
 * 
 * This file describes the public interface to the sensor bsp layer.
 * 
 * Date: October 2025
 * 
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef SENSOR_H
#define SENSOR_H

class SENSOR
{
public:
    // the following functions describe the public interface.
    // CAUTION! CAUTION! DO NOT describe the state or implementation of the sensor. 
    // CAUTION! CAUTION! Please be wary if deciding to change the interface. You
    //                   risk exposing extra information to the application code.

    // Pure virtual functions enforce child class implementations
    virtual int sensor_init() = 0;
    virtual int sensor_read() = 0;

    virtual ~SENSOR() {}
    // do not declare anything as private or protected
};

#endif // #ifndef SENSOR_H