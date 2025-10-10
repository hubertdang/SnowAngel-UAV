/**
 *
 * Name: board_fsm.h
 * Author: Hubert Dang
 *
 * Private header for the finite state machine logic for the drone subsystem
 * board.
 *
 * Date: October 2025
 *
 * Copyright 2025 SnowAngel-UAV
 */

#ifndef BOARD_FSM_H
#define BOARD_FSM_H

enum board_state
{
	BOARD_STATE_INVALID,
	BOARD_STATE_IDLE,
	BOARD_STATE_INIT,
	BOARD_STATE_WAIT,
	BOARD_STATE_READ,
	BOARD_STATE_CLEANUP,
	BOARD_STATE_FAULT
};

enum board_state board_fsm_start();
enum board_state board_fsm_process(enum board_state state);

#endif /* BOARD_STATE_MACHINE_H */