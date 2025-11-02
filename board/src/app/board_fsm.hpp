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
	BOARD_STATE_WAIT,
	BOARD_STATE_READ,
	BOARD_STATE_FAULT,
	BOARD_STATE_CLEANUP,
	BOARD_STATE_DONE
};

#ifdef __cplusplus
extern "C"
{
#endif

/**
 * board_fsm_process - process a board state
 *
 * @param state The state to process
 *
 * Note that the next state is not always a different state.
 *
 * @return The next state
 */
enum board_state board_fsm_process(enum board_state state);

#ifdef __cplusplus
}
#endif

#endif /* BOARD_STATE_MACHINE_H */