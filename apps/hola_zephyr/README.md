# Hola Zephyr: saludo periódico en LP-AM243

Aplicación propia y permanente, separada de `zephyr/samples/hello_world`.
Imprime exactamente `hola soy zephyr` al entrar en `main()` y después duerme
con `k_sleep(K_SECONDS(3))` entre mensajes. El intervalo es nominal, no una
garantía de temporización de precisión. No usa espera ocupada ni shell.

**Target:** `lp_am243/am2434/r5f0_0`. Usa la consola UART de la placa. La prueba
actual habilita MPU, banner y diagnóstico; usa un overlay y una cabecera de
compatibilidad propios de esta app. El diagnóstico también instrumenta
condicionalmente `zephyr/kernel/init.c`; con la flag desactivada, el flujo del
kernel no cambia. No se editan fuentes del SDK TI.
Los mensajes del SBL son independientes y no prueban que Zephyr haya arrancado.
**El arranque sigue pendiente:** la captura física más reciente llega a Z4 y no
muestra Z4A; no se ha confirmado el saludo periódico en hardware. Para el flujo
actual ver [compilar, empaquetar y comprobar](#compilar-empaquetar-y-comprobar).
El diagnóstico que sigue conserva observaciones anteriores, no pruebas físicas
nuevas.

## Prueba con MPU y diagnóstico

### Corrección de RAM del SBL, 2026-11-13

La comparación con `VeriSOM/software/am243/Docs/README.md` identificó que el SBL
compilado del SDK local colocaba pilas hasta `0x70084700`, mientras que la app
empieza a cargar en `0x70080000`. La MPU de esta app ya estaba habilitada;
no se ha desactivado ni retirado la instrumentación de arranque.

`bootloader/ram-layout.json` fija código/datos del SBL en
`[0x70000100, 0x70060000)` y BSS/pilas en `[0x70060000, 0x70080000)`.
`scripts/hola_sbl.py` copia el `main.c`, `makefile` y `example.syscfg` TI al
directorio generado `build/sbl/` y ajusta sólo las asignaciones SRAM de esa
copia. El SDK original y su SBL precompilado no se sobrescriben. La copia
conserva las licencias TI. No se copian el GPIO ni los ajustes de placa OSM.

Desde esta app, el flujo local es:

```bash
just build-sbl
just build
just package
just check-boot
just check
```

`package` y `check` rechazan un SBL ausente, modificado, demasiado grande o
solapado. La comprobación usa **todas las secciones ELF SHF_ALLOC del SBL,
incluidas BSS y pilas NOBITS**, y los `PT_LOAD/p_memsz` de Zephyr; no compara
sólo el tamaño de los archivos. También exige MPU habilitada en `.config`.
Los hashes cubren las fuentes/bibliotecas TI controladas, layout y artefactos.
Un cambio requiere repetir `build-sbl` y `package` según el error indicado.

Salidas del SBL bajo `build/sbl/ti-arm-clang/`:
`sbl_ospi.release.out`, `sbl_ospi.release.map`, `sbl_ospi.release.bin` y
`sbl_ospi.release.hs_fs.tiimage`. El recibo local queda en
`build/sbl/verification.json`. Todo permanece bajo el build ignorado por Git.

Validación local del 2026-11-13: **95 pruebas** correctas; SBL y aplicación
compilados, empaquetados y comprobados. El nuevo ELF SBL sitúa BSS y pilas en
`[0x70060000, 0x70074700)`; la app carga SRAM desde `0x70080000`. El guard
rechazó también el ELF real del SBL anterior por su `.stack` solapada. La
verificación existente de Hello World sigue siendo válida, sin reconstruirlo.
Se comprobaron intactos los cambios previos y el SBL precompilado del SDK.

**Ningún comando de preparación instala el nuevo SBL en la placa.** El `flash`
habitual sigue escribiendo sólo la app en `0x80000`, conservando el SBL de `0x0`.
Por tanto, preparar o grabar sólo la aplicación no corrige un SBL antiguo que
siga instalado. Reemplazarlo requiere una operación y autorización separadas;
`check-boot` sólo acredita el par de archivos local, no lo que está en flash.

### Instalación autorizada y observación, 2026-11-13

David autorizó la instalación en `/dev/ttyACM1`. Tras confirmar UART ROM,
Uniflash confirmó las cuatro operaciones: escritura y `flashverify` del SBL
corregido en `0x0`, y escritura y `flashverify` de la app en `0x80000`.
La sesión terminó correctamente. No se solicitaron chip erase ni cambios PHY.

| Imagen instalada | SHA256 |
| --- | --- |
| SBL corregido | `d5e7d4a395198a6a87a27702f47c4ea6fea6acb1506ffb7e47ee1e9e3e261896` |
| hola_zephyr | `93dc7454b41e2b6a791f6b304160b83ea704e5b2fb0f9a89d783585d2c7746fc` |

La primera captura UART posterior sólo recibió control XMODEM (`0x15`, `0x18`, `C`),
sin banner ni saludo. No se confirmó en la conversación el cambio físico a
QSPI y el reinicio durante esa captura; por ello no se distingue UART BOOT
seleccionado de un eventual retorno a UART tras un fallo de arranque. La
escucha se detuvo para liberar el puerto. En esa captura todavía no se había
observado ejecución de Zephyr.

### Arranque desde flash confirmado, 2026-11-13

Tras confirmar David la selección OSPI/QSPI y pedir el reinicio, la captura
de ACM1 mostró `Boot Media: NOR SPI FLASH`, núcleo `r5f0-0`, entrega a la app,
Z4PA-Z4PD y Z4A-Z4C, seguidos de Z5, Z6, Z7, el banner
`Booting Zephyr OS build v4.4.0-13838-g5a56224939aa`, `[Z8] main` y
`hola soy zephyr`. **Arranque desde NOR y llegada al main de Zephyr observados.**

Se capturaron dos secuencias completas de arranque y tres saludos en total;
dos saludos pertenecen a la última secuencia. David confirmó el 2026-11-13 que
funciona correctamente y que la duplicación fue causada por su intervención.
No se atribuye esa duplicación a reinicios espontáneos. La prueba confirma
arranque y ejecución funcional, no estabilidad prolongada ni una prueba
específica de persistencia tras corte de alimentación.
El límite anterior en pinctrl ya fue superado en esta prueba: no debe seguir
presentándose como un bloqueo actual confirmado. La captura terminó y liberó
el puerto, sin otra escritura de flash. No queda pendiente investigar el doble
arranque observado. Pruebas prolongadas o un ciclo de alimentación sólo si
David las solicita.

### Configuración diagnóstica conservada

Solicitada por David el 2026-11-12 tras observar silencio después de
`switching to application`. Flags en `prj.conf`: `ARM_MPU`, `BOOT_BANNER`,
`EARLY_CONSOLE`, `ASSERT`, `FAULT_DUMP=2`, `LOG_MODE_IMMEDIATE` y backend UART.
`LOG_PRINTK=n` mantiene el saludo fuera del backend de logging. Los mensajes
se muestran por UART: no se guardan archivos ni historiales de intentos.

Dos ajustes acompañan la habilitación de MPU en esta copia:

- `app.overlay` reserva el primer KiB para vectores y marcador, dejando la
  ventana de enlazado ATCM desde `0x400`, sin el atributo MPU desalineado de la
  ventana original. Añade una descripción MPU de ATCM completo:
  base `0x0`, tamaño `0x8000`, incluyendo los vectores. BTCM conserva su mapa.
- `mpu_dt_compat.h` corrige sólo para ARMv7-R la macro `ARM_MPU_REGION_INIT`:
  rellena el campo separado `.size` y no mezcla esos bits con `.attr`. La macro
  original de este checkout no rellena ese campo, aunque el driver R5 lo usa.
  CMake incluye esta cabecera únicamente al compilar la biblioteca MPU de la
  app. Revisar y retirar esta adaptación cuando se valide una corrección upstream.

Estos son problemas concretos al preparar la configuración **con MPU**, no una
demostración de que causaran el silencio del build anterior, que no la habilitaba.
La consola temprana y el banner tampoco garantizan salida antes de inicializar
UART; si el core no llega a esa etapa, será necesaria una prueba más temprana.

## Flag de trazas anteriores al kernel

`CONFIG_HOLA_EARLY_UART_TRACE=y`, definida en el `Kconfig` propio de la app y
activada en `prj.conf`, añade marcadores de arranque por UART0. Para quitarlos,
cambiarla a `n` y recompilar.

| Marcador | Punto alcanzado |
| --- | --- |
| `[Z0] reset en ATCM` | Entrada desde el vector de reset, todavía en ATCM |
| `[Z1] antes de z_prep_c` | Ensamblador de reset terminado, antes de preparar el entorno C |
| `[Z1A] z_prep_c entry` | Primera instrucción C instrumentada dentro de `z_prep_c` |
| `[Z1B] soc_prep_hook returned` | Hook inicial de SoC terminó |
| `[Z1C] tpidruro initialized` | Se escribió el puntero per-CPU |
| `[Z1D]/[Z1E]` | Antes/después de inicializar FPU, si está configurada |
| `[Z1F]/[Z1G]` | Antes/después de limpiar BSS |
| `[Z1H]/[Z1I]` | Antes/después de copiar DATA |
| `[Z1J]/[Z1K]` | Antes de inicializar stacks/después de ese paso |
| `[Z1L]` / `[Z1M]` | Antes / después de la inicialización de interrupciones completa |
| `[Z1N]/[Z1O]` | Antes/después del paso de caché |
| `[Z1P]/[Z1Q]` | Antes/después de inicializar MPU |
| `[Z1R]/[Z1S]` | Antes/después de configurar regiones MPU estáticas |
| `[Z1T] before z_cstart` | Preparación previa completada; próximo paso es `z_cstart` |
| `[Z1M-A]` a `[Z1M-D]` | Entrada VIM, lectura de `VIM_INFO` y resultado de la comprobación de cantidad de IRQ |
| `[Z1M-E]` a `[Z1M-M]` | Se completó la escritura de máscara de los grupos VIM 0 a 8 |
| `[Z1M-N]` | Llegó al final del cuerpo instrumentado de `z_vim_irq_init`, antes de su epílogo/retorno |
| `[Z1M-O]` | `z_vim_irq_init` retornó a `z_soc_irq_init` |
| `[Z1M-P]` | `z_soc_irq_init` retornó a `z_arm_interrupt_init` |
| `[ZR1]` | Entrada al handler ensamblador de reset, después del wrapper Z0 |
| `[ZR2]/[ZR3]` | Antes/después de cargar direcciones de `z_prep_c` y stacks |
| `[ZR4]`-`[ZR9]` | Stack FIQ, IRQ, ABT, UND, SVC y SYS configurado, respectivamente |
| `[ZR10]/[ZR11]` | Antes/después de los hooks de reset/watchdog/ECC habilitados |
| `[ZR12]/[ZR13]` | Antes/después de la relocación de la tabla de vectores |
| `[Z2] antes de z_cstart` | Preparación C/MPU terminada; próximo paso es entrar al kernel |
| `[Z2A] z_cstart entry` | Primera instrucción instrumentada dentro de `z_cstart` |
| `[Z2B] gcov init complete` | Se ejecutó `gcov_static_init()` |
| `[Z2C] before EARLY init` | Próximo paso es despachar callbacks `SYS_INIT(EARLY)` |
| `[Z2D] after EARLY init` | Los callbacks EARLY terminaron |
| `[Z3] init EARLY` | `z_cstart` inició y entró a la fase EARLY |
| `[Z4] init PRE_KERNEL_1` | Fase EARLY y hooks previos completados; comenzó PRE_KERNEL_1 |
| `[Z4A] pinctrl TI K3 init returned` | Retornó la inicialización de pinctrl; marcador de diagnóstico agregado después del log físico actual |
| `[Z4B] UART NS16550 init returned` | Retornó la inicialización del controlador UART |
| `[Z4C] UART console init returned` | Retornó la inicialización de la consola UART |
| `[Z4PA]`/`[Z4PB]` | Entrada de `pinctrl_ti_k3_init` / antes de `DEVICE_MMIO_MAP` |
| `[Z4PC]`/`[Z4PD]` | Retorno de `DEVICE_MMIO_MAP` / fin del cuerpo de init de pinctrl |
| `[Z5] init PRE_KERNEL_2` | Callbacks PRE_KERNEL_1 completados |
| `[Z6] init POST_KERNEL` | Callbacks PRE_KERNEL_2 completados |
| `[Z7] init APPLICATION` | Callbacks POST_KERNEL completados |
| `[Z8] main` | Scheduler y fase APPLICATION completados; entró en `main()` |

`src/early_uart_trace.S` escribe en UART0 `0x02800000`, comprobando LSR.THRE.
Z0-Z2 y Z1A-Z1T no usan `printk` ni logger y escriben directamente a UART.
Z1A-Z1T se ejecutan dentro de `z_prep_c`, después de que el reset establezca
el stack. Z3-Z8 se llaman desde callbacks de inicialización Zephyr y desde
`main()`, pero siguen escribiendo directamente a UART sin depender de consola
ni logger.
Cada espera UART tiene un límite; si vence, el marcador se omite y el arranque
continúa. **Se reutiliza la configuración UART que deja el SBL**: no modifica
reloj, pines ni baudrate. La ausencia de un marcador puede deberse a esa
dependencia UART; por sí sola no prueba que el core no alcanzara el punto.

`early_uart_trace.ld` añade el primer marcador **después de los vectores en el
mismo segmento cargable que empieza en cero**, no en un segmento TCM separado.
Así se conserva la copia diferida de los primeros 80 bytes que hace este SBL.
Se mantiene la entrada ELF/MCELF `0x0`. Las opciones de enlace `--wrap` redirigen
los tres puntos tempranos y cada wrapper continúa hacia la función original,
respetando ARM/Thumb. Z1A-Z1T trazan `prep_c.c`; Z1M-A...Z1M-N trazan `intc_vim.c`; Z1M-O/P
marcan los retornos de las funciones IRQ SoC y ARM; ZR1-ZR13 trazan el reset
ensamblador; Z4PA-Z4PD trazan el mapeo MMIO del driver de pinctrl;
Z2A-Z2D son trazas directas en el init del kernel; Z3-Z7 son callbacks
`SYS_INIT` en cada nivel y Z8 se emite al entrar en `main()`. El adaptador
comprueba hashes de Kconfig, ensamblador, callbacks C, snippet,
`zephyr/kernel/init.c`, `zephyr/arch/arm/core/cortex_a_r/prep_c.c`,
`zephyr/arch/arm/core/cortex_a_r/reset.S`,
`zephyr/drivers/interrupt_controller/intc_vim.c`,
`zephyr/drivers/pinctrl/pinctrl_ti_k3.c`,
`zephyr/soc/ti/k3/common/cortex_r/soc.c` y
`zephyr/arch/arm/core/cortex_a_r/irq_init.c`.

La captura más reciente llega a Z4 y no muestra Z4A. En el mapa, el siguiente
init es el dispositivo pinctrl TI K3 (PRE_KERNEL_1 prioridad 40); Z4A está
inmediatamente después (prioridad 41). El init del driver sólo ejecuta
`DEVICE_MMIO_MAP`, así que el límite observado se acota a ese init/retorno o a
la salida UART posterior; no se ha demostrado una causa raíz. Se añadieron
Z4PA-Z4PD dentro de `pinctrl_ti_k3_init`: Z4PA marca entrada, Z4PB el paso
previo al mapeo, Z4PC que el mapeo retornó y Z4PD el fin del cuerpo. Si aparecen
PA/PB sin PC, investigar el mapeo MMIO; si PC/PD aparecen pero no Z4A,
inspeccionar el retorno del driver y la transmisión del marcador. Si ninguno
aparece, confirmar que se flasheó la imagen nueva y que la UART sigue siendo
visible. No concluir reset o bloqueo sólo por un marcador ausente.
El SBL suma los `p_filesz` de sus segmentos `PT_LOAD` para `Boot Image Size` y
lo imprime dividido por 1024 como entero. El ELF de la captura documentada suma
65 828 bytes, de ahí los 64 KB observados. No es el tamaño del SBL, del
MCELF/archivo firmado ni de la partición OSPI; no se presupone ese tamaño para
los builds nuevos.

## Compilar, empaquetar y comprobar

Desde la raíz del proyecto, entrar en la app y usar su `justfile`:

```bash
cd apps/hola_zephyr
just build-sbl
just build
just package
just check-boot
just check
```

**`build` sólo compila mediante `west build`.** No convierte a MCELF, no firma,
no prepara el CFG y no abre puertos. **`package`** convierte el ELF a MCELF,
firma HS-FS con la clave de desarrollo TI, verifica y prepara el writer/CFG.
**`check`** comprueba lo preparado sin hardware. Después de editar fuentes,
repetir los tres pasos: una imagen anterior no representa las fuentes nuevas.

Desde la raíz siguen disponibles `just build-hola` (**SBL aislado + build + package**) y
`just check-hola`. `just apps` enumera las apps y `just workspace` muestra el
workspace. Hello World tiene fuentes en `apps/hello_world`, build y recetas
propios; los alias `*-zephyr` de la raíz siguen seleccionándolo, no esta app.

El [workspace documentado en la raíz](../../Readme.md#12-workspace-zephyr-y-aplicaciones-locales)
usa `apps/west.yml`, con Zephyr fijado a
`5a56224939aac71065aacd5dd69942a8e67565c6`, módulos `cmsis`, `cmsis_6` y
`hal_ti` y dependencias TI fijadas a SHAs locales. `.west/config` selecciona
`manifest.path=apps`, `manifest.file=west.yml` y `zephyr.base=zephyr`.
Se conservan Python y SDK de `.zephyr.local.json`; sus módulos apuntan a copias
locales independientes en `modules/hal/`, con sus directorios Git. El manifiesto
usa entradas explícitas sin `import`, conservando los `manifest-rev` existentes;
registra las extensiones con `west-commands: scripts/west-commands.yml`.
**No ejecutar `west update`,
instalar ni descargar nada para este flujo.** No hace falta activar el entorno
ni exportar variables. Los gitlinks del índice sin `.gitmodules` siguen pendientes
de revisión al preparar un futuro commit autorizado: no se dan por corregidos.

CMake usa esta app y el kernel local `zephyr/`. Generador MCELF y firmador:
SDK 12.01 configurado en el JSON, igual que Hello World. Flash writer compilado
y herramienta Uniflash: clon local `mcu_plus_sdk/`, siguiendo la guía. El adaptador
compartido conserva hashes, guards y trazas sin modificar las herramientas TI.

| Archivo relativo a `apps/hola_zephyr/` | Función |
| --- | --- |
| `build/zephyr/zephyr.elf` | Firmware compilado |
| `build/boot-image/hola_zephyr.mcelf` | Imagen TI para core 4, entrada 0, sin XIP |
| `build/boot-image/hola_zephyr.mcelf.hs_fs` | Imagen con firma de desarrollo para grabar |
| `build/sbl_uart_uniflash.release.hs_fs.tiimage` | Copia del flash writer compilado en el clon |
| `build/flash.cfg` | CFG generado: sólo `flash` y `flashverify` en `0x80000` |
| `build/boot-image/verification.json` | Estado local, selección de app y hashes |

El flash writer se **copia al directorio de trabajo**, no se enlaza. El CFG
usa su nombre de archivo y la ruta local real de la imagen, sin variables por
expandir. El adaptador ejecuta Uniflash desde `apps/hola_zephyr/build/`.
Fuentes y recetas son permanentes; los resultados de este build fijo se ignoran
en Git. **El antiguo `build/hola_zephyr/` de la raíz se conserva intacto:** no se
mueve, borra ni reutiliza su caché. Las instrucciones anteriores que lo citan
son históricas, no una alternativa al build actual.

## Grabar y abrir consola, sólo con autorización de hardware

Requiere el SBL OSPI compatible ya instalado. Con UART BOOT seleccionado,
la placa reiniciada, el puerto real identificado y el monitor serie cerrado,
desde `apps/hola_zephyr/`:

```bash
just flash /dev/ttyACM0
```

El puerto es explícito y se pasa al adaptador mediante `--port`; sustituirlo por
el dispositivo real. Desde la raíz se conserva `just flash-hola /dev/ttyACM0`.
La apertura del puerto puede afectar DTR/RTS. Este comando **sí escribe flash**:
graba y verifica la app en `0x80000`; **no vuelve a escribir el SBL en `0x0`,
los datos PHY ni una imagen XIP; no borra toda la flash**. El flash writer se
carga en RAM como herramienta; el firmware queda persistente en QSPI.

Después de un resultado correcto, apagar, seleccionar QSPI y encender. Desde
la app, abrir la consola a **115200, 8N1** indicando también el puerto:

```bash
just serial /dev/ttyACM0
```

`serial` abre UART, no compila ni graba, y pasa `--port` explícitamente. Cerrar
la consola antes de grabar otra vez. Resultado **esperado si alcanza `main()`**,
no observado ni validado por esta actualización documental:

```text
hola soy zephyr
hola soy zephyr
hola soy zephyr
```

Si falla la grabación, se puede **repetir el mismo comando con puerto explícito**,
sin mover archivos, recompilar ni desbloquear recibos, si siguen siendo válidos
los artefactos preparados. No se generan logs, recibos ni archivos históricos
de intentos; la salida sólo aparece en terminal. Los archivos antiguos se
ignoran sin borrarlos. No hay reintentos en bucle ni cambio automático de puerto;
se conserva la exclusión de operaciones simultáneas y la validación de imagen
y puerto. Un build/empaquetado fallido sí impide usar una imagen incompleta.

## Validación y límites

**Registro previo a la reorganización, no ejecución nueva:** compilación ARM,
conversión MCELF, firma y `check-hola` se habían comprobado localmente; también
Hello World. La suite incluye
la ejecución del `main.c` real con consola y sueño simulados en el host:
comprueba texto y solicitudes de 3000 ms, **no UART ni tiempos en la placa**.
Subsiste el aviso DTS de dirección unitaria: `/memory@0` frente a `reg = 0x400`
en el overlay actual. No impide la compilación.

La reorganización se validó localmente el 2026-11-13: 80 pruebas sin hardware
y `build` mediante west, `package` y `check` correctos para ambas apps en sus
directorios nuevos. Las fuentes de diagnóstico y los cambios previos de Zephyr
y TI se conservaron. No hubo grabación ni consola, y no se acredita arranque
físico del nuevo flujo. Se conservan los hallazgos únicos de imágenes anteriores.

**Historial anterior al SBL corregido, no estado actual:** David informó silencio
tras el SBL con imágenes anteriores. Una captura previa llegaba a Z4 y no
mostraba Z4A. El mapa sitúa a continuación el init
de pinctrl TI K3 (PRE_KERNEL_1 prioridad 40), cuyo
`pinctrl_ti_k3_init()` ejecuta `DEVICE_MMIO_MAP`; Z4A está en prioridad 41.
Z4PA-Z4PD instrumentan la entrada al init, el paso anterior al mapeo, su retorno
y el final del cuerpo. La imagen con esos marcadores ya se compiló y pasó
`just check-hola`; `just test` también pasó con 81 pruebas. Falta grabar y
observarla en hardware. No está demostrada la causa raíz: el mapeo, el retorno
del init o la visibilidad de UART siguen siendo posibilidades. El SBL informa
`Boot Image Size` como suma de los `p_filesz` de segmentos `PT_LOAD`, dividida
por 1024 en entero; los 64 KB corresponden a 65 828 bytes cargables del ELF de
referencia, no al SBL ni a la partición. La firma usa la clave de desarrollo
TI y no acredita seguridad o aprobación de producción.

Base de arranque y preparación: [from guide.md](../../from%20guide.md),
especialmente secciones 8, 9 y 13, y la
[guía oficial de la placa](https://docs.zephyrproject.org/latest/boards/ti/lp_am243/doc/index.html).
