/* ROM_START snippet sorted after the architecture's vector table. */
. = ALIGN(4);
__hola_trace_atcm_start = .;
KEEP(*(.hola_trace.atcm))
. = ALIGN(4);
__hola_trace_atcm_end = .;
