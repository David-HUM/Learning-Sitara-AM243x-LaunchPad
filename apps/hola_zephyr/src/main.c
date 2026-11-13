#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#ifdef CONFIG_HOLA_EARLY_UART_TRACE
void hola_trace_z8(void);
#endif

int main(void)
{
#ifdef CONFIG_HOLA_EARLY_UART_TRACE
	hola_trace_z8();
#endif
	for (;;) {
		printk("hola soy zephyr\n");
		k_sleep(K_SECONDS(3));
	}

	return 0;
}
