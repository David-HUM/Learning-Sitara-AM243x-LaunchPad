# Resumen: Zephyr en la TI LP-AM243

## Actualización confirmada, 2026-11-13

- El SBL aislado corrige el solapamiento de pilas con la app: BSS/pilas
  terminan en `0x70074700`; Zephyr carga SRAM desde `0x70080000`.
- Con autorización de David se grabaron y compararon SBL en `0x0` y app en
  `0x80000` por ACM1. Identidades exactas en el README de la app.
- Después de confirmar OSPI/QSPI y reiniciar se observó arranque desde
  `NOR SPI FLASH`, banner Zephyr `v4.4.0-13838-g5a56224939aa`, `[Z8] main`
  y `hola soy zephyr`. Pinctrl y la inicialización posterior fueron superados.
- Hubo dos secuencias de arranque y tres saludos en total, con dos saludos en
  la última secuencia. David confirmó que funciona correctamente y que la
  duplicación fue causada por él, no evidencia de resets espontáneos. No se
  acredita estabilidad prolongada ni persistencia tras corte de energía.
- **Las secciones siguientes sobre el límite en Z4 son antecedentes, no el
  estado actual.** No regrabar ni retirar las trazas automáticamente. Próximo
  paso: no investigar la duplicación ya aclarada; pruebas adicionales sólo
  si David las solicita.

## Proyecto

Este repositorio conserva el flujo para compilar y arrancar Zephyr en el
Cortex-R5F0_0 de la LaunchPad AM243x. La aplicación propia
[`apps/hola_zephyr/`](apps/hola_zephyr/README.md) imprime `hola soy zephyr` y
espera nominalmente tres segundos entre mensajes.

El arranque persistente usa la cadena ROM/RBL → SBL OSPI → aplicación. La
conversión local produce una imagen MCELF para el core 4 con entrada `0x0`,
firmada con la clave de desarrollo de TI. El comando `just flash-hola` graba y
verifica sólo la aplicación en `0x80000`; no instala ni reemplaza el SBL en
`0x0`. Para compilar y validar sin acceder a la placa:

```bash
just build-hola
just check-hola
```

La consola esperada es la UART de R5F0_0 a 115200, 8N1. El monitor serie debe
cerrarse durante la grabación. Después se selecciona QSPI y se reinicia la
placa.

## Estado anterior al SBL corregido (histórico)

- La app, el ELF, la imagen MCELF y la imagen firmada están compilados y pasan
  las comprobaciones locales de formato, core, entrada, segmentos, payload y
  hashes.
- La imagen firmada actual mide 67 726 bytes; cabe en el espacio de 512 KiB
  asignado desde `0x80000`.
- La captura más reciente llega a Z4 y no muestra Z4A. El mapa sitúa a
  continuación el init del dispositivo pinctrl TI K3 en PRE_KERNEL_1 prioridad
  40; Z4A está en prioridad 41.
- `pinctrl_ti_k3_init()` sólo llama a `DEVICE_MMIO_MAP`. El límite observado
  queda acotado a ese init/retorno o a la transmisión UART posterior, pero no
  demuestra bloqueo, excepción o reset. Se agregaron Z4PA-Z4PD dentro de esa
  función.
- La imagen con Z4PA-Z4PD ya se compiló y pasó `just check-hola`; falta grabarla
  para separar entrada al init, previo al mapeo, retorno del mapeo y fin del
  cuerpo.
- El recibo local dice `hardware_validation: not performed` porque el
  adaptador no controla ni registra pruebas físicas; no invalida la observación
  reportada por David.

## Issues: por qué podría no arrancar o no verse la salida

**La causa raíz todavía no está demostrada.** La captura llega a Z4 pero no a
Z4A. El mapa ordena inmediatamente después el init de pinctrl TI K3. Su función
de init sólo ejecuta `DEVICE_MMIO_MAP`; también es posible que no se observe la
marca posterior por UART. Z4PA-Z4PD instrumentan el cuerpo de esa función. Aún
no se concluye bloqueo, excepción o reset. `flashverify` no valida ejecución.

| Issue | Evidencia y efecto | Estado |
| --- | --- | --- |
| Pinctrl TI K3 en PRE_KERNEL_1 | Se ve Z4 pero no Z4A. El mapa coloca pinctrl en prioridad 40 y Z4A en 41; el init ejecuta `DEVICE_MMIO_MAP`. | Z4PA-Z4PD ya compilados y verificados dentro de la función. Aún no se confirma si falla el mapeo o si la UART deja de mostrar trazas. |
| UART y fases PRE_KERNEL_1 posteriores | Una captura anterior llegó a Z4 sin Z5; no demuestra la ejecución de UART NS16550 ni console init. | Z4B/Z4C quedan como marcadores posteriores si pinctrl retorna y la traza sigue visible. |
| Fases anteriores | Capturas previas alcanzaron Z1M-N y ZR13; la captura actual llega a Z4. | No son el límite actual; confirmar la revisión flasheada si las secuencias cambian. |
| Etapas posteriores | Z5-Z7 marcan PRE_KERNEL_2, POST_KERNEL y APPLICATION; Z8 se emite al entrar a `main()`. | No se alcanza evidencia de estas etapas en el log compartido; usar el último marcador de la siguiente ejecución. |
| Llegada a `main()` frente a consola | Si aparece Z8 pero no `hola soy zephyr`, ya está demostrado que `main()` corre y la investigación se concentra en `printk`, UART de consola y transmisión. | En la prueba actual no aparece Z8, pero la UART permite observar las trazas tempranas. Aún no se ha probado la consola Zephyr. |
| MPU ARMv7-R | En esta copia de Zephyr, `ARM_MPU_REGION_INIT` no rellena el campo `.size` separado que utiliza Cortex-R; la app añade una compatibilidad y alinea el mapa ATCM. Como Z2 ocurre después de `z_arm_mpu_init()` en `z_prep_c`, que Z2 aparezca descarta que esa llamada se quede bloqueada en la imagen probada. | El defecto concreto del macro queda corregido en esta app y no es la explicación principal del fallo observado con Z2. No excluye problemas MPU posteriores ni demuestra qué ocurría con una imagen anterior. |
| SBL y partición OSPI | El CFG de `flash-hola` sólo actualiza la aplicación en `0x80000`; conserva el SBL existente en `0x0`. La salida de Z0/Z1/Z2 muestra que el SBL sí entrega ejecución a código de la imagen actual. | Una incompatibilidad completa SBL/imagen es menos probable para esta prueba, aunque conviene registrar la versión exacta del SBL. No regrabarlo a ciegas. |
| Tamaño de imagen | MCU+ SDK suma los `p_filesz` de los segmentos `PT_LOAD` y `Bootloader_profilePrintInfo()` imprime ese total dividido por 1024 como entero. El ELF actual suma 65 828 bytes, que se muestra como 64 KB. | Es la carga de aplicación que procesa el SBL, no el tamaño del SBL, el tamaño total del MCELF/firmado ni el tamaño de la partición. Cabe en la ranura de 512 KiB; no explica que falte Z3. |
| Aviso DTS `/memory@0` | El aviso de dirección/unidad en el overlay no impidió compilar. No hay evidencia de que cause el fallo de ejecución. | No es una causa respaldada por la evidencia actual; dejarlo como pendiente independiente. |

### Cómo aislar el fallo

Grabar la imagen ya compilada con Z4PA-Z4PD. Registrar la secuencia y confirmar
el artefacto exacto. PA/PB sin PC apunta a revisar `DEVICE_MMIO_MAP`; PC/PD sin
Z4A acota al retorno del driver o a la transmisión UART. Si ninguna marca aparece, confirmar
la imagen flasheada y la UART. JTAG puede capturar PC/CPSR, excepción y reset.
Z4B/Z4C aíslan UART NS16550 y console si el arranque avanza. No regrabar SBL.

- `Z0` confirma que se alcanzó el vector de reset en ATCM y se intentó continuar
  con el reset de Zephyr.
- `Z1` confirma que se llegó al límite anterior a `z_prep_c`.
- `Z2` confirma que la secuencia de preparación anterior a la llamada a
  `z_cstart` completó memoria/CPU, stacks, interrupciones y MPU, y llegó al
  wrapper de entrada a `z_cstart`.
- La captura más reciente llega a Z4, no Z4A. Z4PA-Z4PD separan el init de
  pinctrl y su mapeo MMIO. La ausencia de marcas no demuestra por sí sola
  bloqueo, excepción o reset; verificar también artefacto y UART.
- Z3 marca EARLY; Z4 indica PRE_KERNEL_1; Z5 PRE_KERNEL_2; Z6 POST_KERNEL;
  Z7 APPLICATION; Z8 confirma entrada a `main()`. Si aparecen en otra prueba,
  avanzar el análisis desde el último marcador presente.
- Si aparece Z8 pero falta el saludo, comprobar por separado `printk`, UART de
  consola R5F0_0, TX y baudrate. Si Z8 no aparece, usar JTAG para capturar PC,
  CPSR y estado de excepción/fault antes de resetear.
- Registrar secuencia completa, banner Zephyr y saludo. Los marcadores directos
  prueban avance de CPU, pero reutilizan la UART que deja el SBL.
- El `Boot Image Size: 64 KB` del log es la suma de bytes cargables `PT_LOAD`
  reportada en KiB enteros (65 828 bytes en el ELF actual), no el tamaño del
  SBL, del archivo MCELF/firmado ni una indicación de que la partición tenga
  sólo 64 KiB.

Antes de esa prueba, confirmar el modo de arranque QSPI, la UART correcta, que
se está usando la imagen recién construida y que la placa conserva un SBL OSPI
compatible. No se debe grabar un SBL distinto en `0x0` sin validar primero el
artefacto y la configuración.

## Referencias

- [Guía de Zephyr y MCU+ SDK](from%20guide.md)
- [README de la aplicación hola_zephyr](apps/hola_zephyr/README.md)
- [README principal](Readme.md)
