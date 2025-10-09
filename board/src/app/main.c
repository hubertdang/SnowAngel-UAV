#include "bsp/foo.h"
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

	logging_init();
	logging_write(LOG_INFO, "Hello world log!");
	logging_cleanup();
}