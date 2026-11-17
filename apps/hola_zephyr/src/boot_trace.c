#include <zephyr/init.h>

#ifdef CONFIG_HOLA_EARLY_UART_TRACE
void hola_trace_z3(void);
void hola_trace_z4(void);
void hola_trace_z4a(void);
void hola_trace_z4b(void);
void hola_trace_z4c(void);
void hola_trace_z5(void);
void hola_trace_z6(void);
void hola_trace_z7(void);

static int trace_early_init(void)
{
	hola_trace_z3();
	return 0;
}
SYS_INIT(trace_early_init, EARLY, 0);

static int trace_pre_kernel_1(void)
{
	hola_trace_z4();
	return 0;
}
SYS_INIT(trace_pre_kernel_1, PRE_KERNEL_1, 0);

static int trace_pinctrl_init_returned(void)
{
	hola_trace_z4a();
	return 0;
}
SYS_INIT(trace_pinctrl_init_returned, PRE_KERNEL_1, 41);

static int trace_uart_init_returned(void)
{
	hola_trace_z4b();
	return 0;
}
SYS_INIT(trace_uart_init_returned, PRE_KERNEL_1, 51);

static int trace_uart_console_init_returned(void)
{
	hola_trace_z4c();
	return 0;
}
SYS_INIT(trace_uart_console_init_returned, PRE_KERNEL_1, 61);

static int trace_pre_kernel_2(void)
{
	hola_trace_z5();
	return 0;
}
SYS_INIT(trace_pre_kernel_2, PRE_KERNEL_2, 0);

static int trace_post_kernel(void)
{
	hola_trace_z6();
	return 0;
}
SYS_INIT(trace_post_kernel, POST_KERNEL, 0);

static int trace_application(void)
{
	hola_trace_z7();
	return 0;
}
SYS_INIT(trace_application, APPLICATION, 0);
#endif
