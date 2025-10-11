#include "board_fsm.hpp"
#include "bsp/foo.h"
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
}