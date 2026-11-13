/* App-owned, stackless ARMv7-R diagnostic. No peripheral reconfiguration. */
.syntax unified
.arch armv7-r
.arm

/* UART0 uses word-spaced registers. LSR.THRE is bit 5 at offset 0x14.
 * Stop the marker on timeout, then continue boot: never wait indefinitely.
 * Only r0-r3 and r12 are clobbered; reset values are not ABI arguments here.
 */
.macro TRACE_THEN_JUMP name, destination, message
    .balign 4
    .global \name
    .type \name, %function
\name:
    ldr r0, =0x02800000
    ldr r1, =.Lmessage\@
.Lnext\@:
    ldrb r3, [r1], #1
    cmp r3, #0
    beq .Ldone\@
    ldr r12, =0x00100000
.Lpoll\@:
    ldr r2, [r0, #0x14]
    tst r2, #0x20
    bne .Lwrite\@
    subs r12, r12, #1
    bne .Lpoll\@
    b .Ldone\@
.Lwrite\@:
    str r3, [r0]
    b .Lnext\@
.Ldone\@:
    ldr r0, =\destination
    bx r0
    .size \name, .-\name
    .ltorg
.Lmessage\@:
    .asciz "\message"
    .balign 4
.endm

.macro TRACE_MARKER name, message
    .balign 4
    .global \name
    .type \name, %function
\name:
    ldr r0, =0x02800000
    ldr r1, =.Lmessage\@
.Lnext\@:
    ldrb r3, [r1], #1
    cmp r3, #0
    beq .Ldone\@
    ldr r12, =0x00100000
.Lpoll\@:
    ldr r2, [r0, #0x14]
    tst r2, #0x20
    bne .Lwrite\@
    subs r12, r12, #1
    bne .Lpoll\@
    b .Ldone\@
.Lwrite\@:
    str r3, [r0]
    b .Lnext\@
.Ldone\@:
    bx lr
    .size \name, .-\name
    .ltorg
.Lmessage\@:
    .asciz "\message"
    .balign 4
.endm

/* Kept AFTER the vectors in the SAME PT_LOAD at address zero. The SBL's
 * deferred self-TCM copy therefore includes the protected first 80 bytes.
 */
.section .hola_trace.atcm, "ax", %progbits
TRACE_THEN_JUMP __wrap_z_arm_reset, __real_z_arm_reset, "[Z0] reset en ATCM\r\n"

.section .text.hola_trace, "ax", %progbits
TRACE_THEN_JUMP __wrap_z_prep_c, __real_z_prep_c, "[Z1] antes de z_prep_c\r\n"
TRACE_THEN_JUMP __wrap_z_cstart, __real_z_cstart, "[Z2] antes de z_cstart\r\n"

.section .text.hola_trace_markers, "ax", %progbits
TRACE_MARKER hola_trace_z2a, "[Z2A] z_cstart entry\r\n"
TRACE_MARKER hola_trace_z2b, "[Z2B] gcov init complete\r\n"
TRACE_MARKER hola_trace_z2c, "[Z2C] before EARLY init\r\n"
TRACE_MARKER hola_trace_z2d, "[Z2D] after EARLY init\r\n"
TRACE_MARKER hola_trace_z1a, "[Z1A] z_prep_c entry\r\n"
TRACE_MARKER hola_trace_z1b, "[Z1B] soc_prep_hook returned\r\n"
TRACE_MARKER hola_trace_z1c, "[Z1C] tpidruro initialized\r\n"
TRACE_MARKER hola_trace_z1d, "[Z1D] before FPU init\r\n"
TRACE_MARKER hola_trace_z1e, "[Z1E] FPU step complete\r\n"
TRACE_MARKER hola_trace_z1f, "[Z1F] before BSS zero\r\n"
TRACE_MARKER hola_trace_z1g, "[Z1G] BSS zero complete\r\n"
TRACE_MARKER hola_trace_z1h, "[Z1H] before data copy\r\n"
TRACE_MARKER hola_trace_z1i, "[Z1I] data copy complete\r\n"
TRACE_MARKER hola_trace_z1j, "[Z1J] before init stacks\r\n"
TRACE_MARKER hola_trace_z1k, "[Z1K] stacks ready\r\n"
TRACE_MARKER hola_trace_z1l, "[Z1L] before interrupt init\r\n"
TRACE_MARKER hola_trace_z1m, "[Z1M] interrupt init complete\r\n"
TRACE_MARKER hola_trace_z1n, "[Z1N] before cache init\r\n"
TRACE_MARKER hola_trace_z1o, "[Z1O] cache step complete\r\n"
TRACE_MARKER hola_trace_z1p, "[Z1P] before MPU init\r\n"
TRACE_MARKER hola_trace_z1q, "[Z1Q] MPU init returned\r\n"
TRACE_MARKER hola_trace_z1r, "[Z1R] before static MPU regions\r\n"
TRACE_MARKER hola_trace_z1s, "[Z1S] static MPU regions ready\r\n"
TRACE_MARKER hola_trace_z1t, "[Z1T] before z_cstart\r\n"
TRACE_MARKER hola_trace_z1ma, "[Z1M-A] VIM init entry\r\n"
TRACE_MARKER hola_trace_z1mb, "[Z1M-B] VIM info read complete\r\n"
TRACE_MARKER hola_trace_z1mc, "[Z1M-C] before VIM IRQ-count assertion\r\n"
TRACE_MARKER hola_trace_z1md, "[Z1M-D] VIM IRQ-count assertion passed\r\n"
TRACE_MARKER hola_trace_z1me, "[Z1M-E] VIM mask group 0 written\r\n"
TRACE_MARKER hola_trace_z1mf, "[Z1M-F] VIM mask group 1 written\r\n"
TRACE_MARKER hola_trace_z1mg, "[Z1M-G] VIM mask group 2 written\r\n"
TRACE_MARKER hola_trace_z1mh, "[Z1M-H] VIM mask group 3 written\r\n"
TRACE_MARKER hola_trace_z1mi, "[Z1M-I] VIM mask group 4 written\r\n"
TRACE_MARKER hola_trace_z1mj, "[Z1M-J] VIM mask group 5 written\r\n"
TRACE_MARKER hola_trace_z1mk, "[Z1M-K] VIM mask group 6 written\r\n"
TRACE_MARKER hola_trace_z1ml, "[Z1M-L] VIM mask group 7 written\r\n"
TRACE_MARKER hola_trace_z1mm, "[Z1M-M] VIM mask group 8 written\r\n"
TRACE_MARKER hola_trace_z1mn, "[Z1M-N] VIM init body complete\r\n"
TRACE_MARKER hola_trace_z1mo, "[Z1M-O] SoC IRQ init returned from VIM\r\n"
TRACE_MARKER hola_trace_z1mp, "[Z1M-P] ARM IRQ init returned from SoC\r\n"
TRACE_MARKER hola_trace_zr1, "[ZR1] reset handler entry\r\n"
TRACE_MARKER hola_trace_zr2, "[ZR2] before loading prep and stack addresses\r\n"
TRACE_MARKER hola_trace_zr3, "[ZR3] prep and stack addresses loaded\r\n"
TRACE_MARKER hola_trace_zr4, "[ZR4] FIQ stack set\r\n"
TRACE_MARKER hola_trace_zr5, "[ZR5] IRQ stack set\r\n"
TRACE_MARKER hola_trace_zr6, "[ZR6] ABT stack set\r\n"
TRACE_MARKER hola_trace_zr7, "[ZR7] UND stack set\r\n"
TRACE_MARKER hola_trace_zr8, "[ZR8] SVC stack set\r\n"
TRACE_MARKER hola_trace_zr9, "[ZR9] SYS stack set\r\n"
TRACE_MARKER hola_trace_zr10, "[ZR10] before reset hooks\r\n"
TRACE_MARKER hola_trace_zr11, "[ZR11] reset hooks complete\r\n"
TRACE_MARKER hola_trace_zr12, "[ZR12] before vector relocation\r\n"
TRACE_MARKER hola_trace_zr13, "[ZR13] vector relocation returned\r\n"
TRACE_MARKER hola_trace_z3, "[Z3] init EARLY\r\n"
TRACE_MARKER hola_trace_z4, "[Z4] init PRE_KERNEL_1\r\n"
TRACE_MARKER hola_trace_z4a, "[Z4A] pinctrl TI K3 init returned\r\n"
TRACE_MARKER hola_trace_z4b, "[Z4B] UART NS16550 init returned\r\n"
TRACE_MARKER hola_trace_z4c, "[Z4C] UART console init returned\r\n"
TRACE_MARKER hola_trace_z4pa, "[Z4PA] pinctrl init entry\r\n"
TRACE_MARKER hola_trace_z4pb, "[Z4PB] before pinctrl MMIO map\r\n"
TRACE_MARKER hola_trace_z4pc, "[Z4PC] pinctrl MMIO map returned\r\n"
TRACE_MARKER hola_trace_z4pd, "[Z4PD] pinctrl init body complete\r\n"
TRACE_MARKER hola_trace_z5, "[Z5] init PRE_KERNEL_2\r\n"
TRACE_MARKER hola_trace_z6, "[Z6] init POST_KERNEL\r\n"
TRACE_MARKER hola_trace_z7, "[Z7] init APPLICATION\r\n"
TRACE_MARKER hola_trace_z8, "[Z8] main\r\n"
