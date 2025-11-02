#include "board_fsm.hpp"
#include "common/common.h"
#include "common/logging.h"
#include <stdio.h>
#include <stdlib.h>

int main()
{
	/* Logging init/cleanup is not handled by the board FSM because we want logging enabled
	   for the duration of the entire FSM's lifespan. It is a unique exception. */
	if (logging_init() != SUCCESS)
	{
		exit(EXIT_FAILURE);
	}

	enum board_state current_state = BOARD_STATE_INIT;

	do
	{
		current_state = board_fsm_process(current_state);
	} while (current_state != BOARD_STATE_DONE);

	logging_cleanup();
}