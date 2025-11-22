/**
 *
 * Name: board_fsm.hpp
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
	BOARD_STATE_INIT, /* Initial state */
	BOARD_STATE_IDLE,
	BOARD_STATE_FLYING,
	BOARD_STATE_STATIONARY,
	BOARD_STATE_FAULT,
	BOARD_STATE_CLEANUP,
	BOARD_STATE_DONE
};

#ifdef __cplusplus
extern "C"
{
#endif

enum board_state board_fsm_process(enum board_state state);

const char *board_fsm_state_to_str(enum board_state state);

#ifdef __cplusplus
}
#endif

#endif /* BOARD_STATE_MACHINE_H */
