/**
 *
 * Name: logging.h
 * Author: Hubert Dang
 *
 * This file implements logging functionality for the SnowAngel-UAV board software.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef LOGGING_H
#define LOGGING_H

#define LOG_INFO_ENABLE 1
#define LOG_WARN_ENABLE 1
#define LOG_ERROR_ENABLE 1

enum log_level
{
	LOG_INFO,
	LOG_WARN,
	LOG_ERROR,
};

/**
 * logging_init - initialize logging functionality
 *
 * This function should only be called once and then never again.
 *
 * @return 0 on success, negative number on failure
 */
int logging_init();

/**
 * logging_cleanup - release logging resources
 *
 * This function should always be called when logging stops and before the program terminates.
 */
void logging_cleanup();

/**
 * logging_write - write a log
 *
 * @param log_level The level/type of log
 * @param msg The log message
 * @param ... Arguments corresponding to the format specifier in msg
 *
 * Logging must be initialized before calling this function.
 */
void logging_write(enum log_level level, const char *msg, ...);

#endif
