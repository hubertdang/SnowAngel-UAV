#include "board_fsm.hpp"
#include "bsp/foo.h"
#include "common/common.h"
#include "common/logging.h"
#include <stdio.h>

int main()
{
	printf("Hello World!\n");
	foo();

	enum board_state current_state = board_fsm_start();

	while (0)
	{
		/* Other periodic tasks should be added here */
		current_state = board_fsm_process(current_state);
	}

	if (logging_init() != SUCCESS)
	{
		printf("Oh no!\n");
	}
	logging_write(LOG_INFO, "Hello world log! %d", 69);
	logging_write(LOG_INFO, "Bye world log!");
	logging_cleanup();
}