#include "bsp/foo.h"
#include "common/common.h"
#include "logging.h"
#include <stdio.h>

int main()
{
	printf("Hello World!\n");
	foo();

	if (1)
	{
		printf("hello");
	}

	if (logging_init() != SUCCESS)
	{
		printf("Oh no!\n");
	}
	logging_write(LOG_INFO, "Hello world log! %d", 69);
	logging_write(LOG_INFO, "Bye world log!");
	logging_cleanup();
}