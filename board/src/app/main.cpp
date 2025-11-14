#include "board_fsm.hpp"
#include "common/common.h"
#include "common/logging.h"
#include <stdlib.h>
#include <unistd.h>

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
		usleep(15000); /* Reduce CPU usage */
	} while (current_state != BOARD_STATE_DONE);

	logging_cleanup();
}
