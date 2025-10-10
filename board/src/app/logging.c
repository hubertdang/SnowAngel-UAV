/**
 *
 * Name: logging.c
 * Author: Hubert Dang
 *
 * This file implements logging functionality for the SnowAngel-UAV app.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include "logging.h"
#include "time.h"
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LOG_FILE_NAME "./snow_angel_uav.log" /* located in board/build/ */
#define TIMESTAMP_SIZE 20                    /* exactly enough for YYYY-MM-DD HH:MM:SS */

static FILE *log_file;

const char *logging_level_to_string(enum log_level level);

int logging_init()
{
	const char *home_dir = getenv("HOME");

	if (home_dir == NULL)
		return -1;

	char log_file_path[512]; /* Big enough for file in home */
	snprintf(log_file_path, sizeof(log_file_path), "%s", LOG_FILE_NAME);

	remove(log_file_path);

	log_file = fopen(log_file_path, "w");

	if (log_file == NULL)
		return -2;

	return 0;
}

void logging_cleanup()
{
	if (log_file)
		fclose(log_file);
}

void logging_write(enum log_level level, const char *fmt, ...)
{
	if (log_file == NULL)
		return;

	const char *prefix = logging_level_to_string(level);

	if (prefix == NULL)
		return;

	time_t now = time(NULL);
	struct tm *curr_time = localtime(&now);

	char time_buf[TIMESTAMP_SIZE];
	strftime(time_buf, sizeof(time_buf), "%Y-%m-%d %H:%M:%S", curr_time);

	va_list args;
	va_start(args, fmt);

	fprintf(log_file, "[%s][%s]: ", time_buf, prefix);
	vfprintf(log_file, fmt, args);
	fprintf(log_file, "\n");

	va_end(args);
	fflush(log_file); /* make sure we don't lose logs if program crashes */
}

const char *logging_level_to_string(enum log_level level)
{
	if (level == LOG_INFO)
		return "INFO";
	else if (level == LOG_WARN)
		return "WARN";
	else if (level == LOG_ERROR)
		return "ERROR";
	else
		return NULL;
}
