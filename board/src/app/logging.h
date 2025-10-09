/**
 *
 * Name: logging.h
 * Author: Hubert Dang
 *
 * This file implements logging functionality for the SnowAngel-UAV app.
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

int logging_init();
void logging_write(enum log_level level, const char *msg);
void logging_cleanup();

#endif