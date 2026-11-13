cmake_minimum_required(VERSION 3.28.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(hola_zephyr)

target_sources(app PRIVATE src/main.c src/boot_trace.c)

if(CONFIG_HOLA_EARLY_UART_TRACE)
  target_sources(app PRIVATE src/early_uart_trace.S)
  zephyr_linker_sources(ROM_START SORT_KEY "0x2hola_trace" early_uart_trace.ld)
  zephyr_link_libraries(
    -Wl,--wrap=z_arm_reset
    -Wl,--wrap=z_prep_c
    -Wl,--wrap=z_cstart)
endif()

# Scope the ARMv7-R DT-region compatibility fix to this app's MPU library.
if(CONFIG_ARM_MPU)
  target_compile_options(arch__arm__core__mpu PRIVATE
    -include ${CMAKE_CURRENT_SOURCE_DIR}/mpu_dt_compat.h)
endif()
