/**
 *
 * Name: board_fsm.c
 * Author: Hubert Dang
 *
 * Implementation of the finite state machine logic for the drone subsystem
 * board.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#include "board_fsm.h"

#define INITIAL_STATE BOARD_STATE_IDLE

enum board_state board_fsm_idle();
enum board_state board_fsm_init();
enum board_state board_fsm_wait();
enum board_state board_fsm_read();
enum board_state board_fsm_cleanup();
enum board_state board_fsm_fault();

enum board_state board_fsm_start()
{
	return board_fsm_process(INITIAL_STATE);
}

enum board_state board_fsm_process(enum board_state state)
{
	switch (state)
	{
	case BOARD_STATE_IDLE:
		return board_fsm_idle();
	case BOARD_STATE_INIT:
		return board_fsm_init();
	case BOARD_STATE_WAIT:
		return board_fsm_wait();
	case BOARD_STATE_READ:
		return board_fsm_read();
	case BOARD_STATE_CLEANUP:
		return board_fsm_cleanup();
	case BOARD_STATE_FAULT:
		return board_fsm_fault();
	default:
		return BOARD_STATE_INVALID;
	}
}

enum board_state board_fsm_idle()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}

enum board_state board_fsm_init()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}

enum board_state board_fsm_wait()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}

enum board_state board_fsm_read()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}

enum board_state board_fsm_cleanup()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}

enum board_state board_fsm_fault()
{
	/* TODO: execute "entry/exit actions" and "do activities" */
	/* TODO: execute "transition actions" going out of this state */
	return BOARD_STATE_FAULT;
}
