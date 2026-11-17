/*
 * Compatibility for this Zephyr checkout's ARMv7-R DT-to-MPU conversion.
 * arm_mpu_region has a separate size field on Cortex-R. The common
 * ARM_MPU_REGION_INIT macro otherwise leaves it zero and puts the size bits
 * into the attributes, as on Cortex-M. Apply only to the MPU library for this
 * app, without editing Zephyr sources. Remove after validating an upstream fix.
 */
#ifndef HOLA_ZEPHYR_MPU_DT_COMPAT_H_
#define HOLA_ZEPHYR_MPU_DT_COMPAT_H_

#include <zephyr/arch/arm/mpu/arm_mpu.h>

#if defined(CONFIG_ARMV7_R) && defined(CONFIG_CPU_AARCH32_CORTEX_R)
#undef ARM_MPU_REGION_INIT
#define ARM_MPU_REGION_INIT(p_name, p_base, p_size, p_attr) \
	{ \
		.name = (p_name), \
		.base = (p_base), \
		.size = size_to_mpu_rasr_size(p_size), \
		.attr = p_attr(0), \
	}
#endif

#endif
