# From guide: Zephyr en TI LP-AM243, adaptado a MCU+ SDK 12.01

**Base:** [TI AM243x LaunchPad, documentación oficial de Zephyr](https://docs.zephyrproject.org/latest/boards/ti/lp_am243/doc/index.html).
**Consulta y contraste local:** 2026-11-12. `latest` es una referencia móvil.
**Alcance:** Ubuntu, Cortex-R5F0_0, Hello World y app propia `hola_zephyr`, imágenes de desarrollo y arranque desde QSPI mediante SBL OSPI.

Esta guía sigue las secciones oficiales de bootflow, preparación del MCU+ SDK,
construcción de SBL, conversión de imágenes, grabación y depuración. Adapta los
pasos a este proyecto y conserva las correcciones encontradas al compilar.
No sustituye la documentación de seguridad de TI ni acredita un diseño para producción.

**Confirmación posterior de David, 2026-11-12:** informó que completó el
recorrido de esta guía hasta el final. La app independiente de la sección 13
reutiliza esa preparación; no requiere repetir la construcción/instalación
del SBL. Las notas históricas de diagnóstico conservan sus límites de evidencia
y no son pasos obligatorios para la nueva app.

**Anotación de David:** `download_components.sh` no funciona en su recorrido.
La causa exacta no se ha diagnosticado; no se presenta como un fallo universal
del script ni como algo que necesariamente se arregle con `chmod`.

## 1. Qué conservar y qué adaptar de la guía oficial

| Tema de la guía oficial | Aplicación en este proyecto |
| --- | --- |
| ROM/RBL → SBL → firmware | Se conserva. El SBL inicializa el entorno de arranque antes de Zephyr. |
| Target R5F de la LaunchPad | `lp_am243/am2434/r5f0_0`; no usar el target M4 para este Hello World. |
| QSPI en la placa, nombres `ospi` en TI | Se conserva. El nombre del ejemplo no cambia el modo físico de la flash. |
| Workspace MCU+ SDK gestionado con West | Ya existe aquí; no volver a ejecutar `west init` en la misma raíz. |
| `download_components.sh` | No es un prerrequisito demostrado como funcional aquí. Revisar las herramientas instaladas manualmente. |
| SDK `am243x/dev.yml` y ramas de desarrollo | El manifiesto local omite dependencias y mezcla revisiones. Fijar las versiones contrastadas de la sección 4. |
| Parche de `entryPoint = 0` en `Bootloader_runCpu` | Está aplicado localmente; tiene límites y necesita un SBL recompilado y grabado para afectar a la placa. |
| `make libs` para todo el SDK | Sigue siendo una ruta completa, pero la sección 6 permite construir sólo las bibliotecas necesarias para los SBL elegidos. |
| Conversión ELF → RPRC → appimage | No copiarla a este SDK: las notas TI de 12.01 deprecian RPRC y señalan MCELF. |
| Variables dentro del `.cfg` | Deben convertirse en rutas reales. Uniflash no expande `$SDK`, `$IMAGE` o `$FLASH_FILE` dentro de un archivo. |
| `sbl_null` y depurador durante el desarrollo | Alternativa útil para investigar el arranque sin flashear cada nuevo ELF; no activada ni verificada aquí. |

Fuentes: guía oficial, secciones **Booting a firmware**, **MCU+ SDK / Setup**,
**Building MCU+ SDK SBLs**, **Creating a SBL bootable RPRC image from a Zephyr ELF**
y **Debugging**; [notas TI 12.01, migración](mcu_plus_sdk/docs_src/docs/api_guide/device/am64x_am243x/release_notes_12_01_00.md).

## 2. Árboles y versiones: no mezclar sus funciones

Ejecutar los comandos desde la raíz del proyecto, salvo indicación contraria:

```bash
cd ~/projects/Learning-Sitara-AM243x-LaunchPad
```

| Ruta | Función |
| --- | --- |
| `zephyr/` | Copia completa de Zephyr que se compila, incluido `samples/hello_world`. |
| `build/zephyr_hello/` | Build fijo nuevo. No reutiliza el caché copiado de `zephyr/build/am243_hello`. |
| `apps/hola_zephyr/` | App propia que imprime `hola soy zephyr` y duerme tres segundos entre mensajes. |
| `build/hola_zephyr/` | Build fijo, imágenes, copia del flash writer y CFG exclusivos de la app propia. |
| `mcu_plus_sdk/` | SDK TI desde Git, con el parche local del bootloader y las dependencias incorporadas. |
| `mcupsdk-manifests.git/`, `.west/config` | Manifiesto del workspace **MCU+ SDK**, no del workspace Zephyr anterior. |
| `~/ti/mcu_plus_sdk_am243x_12_01_00_33/` | SDK instalado: fuente de contraste y de componentes que faltaban en el clon. |
| `.zephyr.local.json` | Rutas absolutas de este equipo: Python, ambos SDK y módulos CMSIS/TI. Está ignorado por Git. |
| `tools/sbls-am243x-lp/zephyr_hellw_sbl_ospi.cfg` | CFG local generado para actualizar **sólo la aplicación**. No instala un SBL nuevo. |

Las rutas de esta documentación son portables. Los archivos locales generados
contienen las rutas absolutas que necesita cada herramienta, sin publicar el
directorio personal de una computadora.

### Versiones contrastadas

| Componente | Revisión o versión |
| --- | --- |
| Zephyr de esta copia | `v4.4.0-13838-g5a56224939aa`, versión declarada `4.4.99` |
| Zephyr SDK | `1.0.1` |
| MCU+ SDK core | `REL.MCUSDK.K3.12.01.00.33` |
| TI Arm Clang | `4.0.4.LTS` |
| SysConfig para este SDK | `1.27.0`; también hay `1.28.2`, pero no se elige automáticamente por ser más nuevo |
| Ethernet PHY | `v2026.03.9` de `ethernet-rtos-drivers` |
| ENET core | `REL.MCUSDK.K3.12.01.00.31` de `mcupsdk-enet-lld` |
| ICSS EMAC LLD | `REL.ICSDK.2026.01.00.05` |

El SDK core corresponde a la etiqueta 12.01.00.33. ENET tiene una numeración
de componente distinta: su etiqueta `.31` coincide con las fuentes del ENET
distribuido con el SDK `.33`; no hay que inventar una etiqueta ENET `.33`.

## 3. Preparación sin depender del script de descarga

La guía oficial recomienda separar los entornos Python de MCU+ SDK y Zephyr.
Es una buena separación para una instalación nueva. El flujo local actual
usa los intérpretes explícitos documentados en la sección 8: no cambia ni
reinstala entornos automáticamente.

Para comprobar las herramientas de TI ya instaladas:

```bash
test -x "$HOME/ti/ti-cgt-armllvm_4.0.4.LTS/bin/tiarmclang"
test -x "$HOME/ti/sysconfig_1.27.0/nodejs/node"
test -f "$HOME/ti/sysconfig_1.27.0/dist/cli.js"
node --version
openssl version
```

Si un `test` devuelve un estado distinto de cero, revisar esa ruta o instalar
el componente aprobado antes de compilar. Estos comandos no instalan nada.
Las dependencias Python del SDK están declaradas en
[`mcu_plus_sdk/requirements.txt`](mcu_plus_sdk/requirements.txt); se necesitan
en el intérprete que realmente ejecute la herramienta, no sólo en otro venv.

Notas para el script:

- La guía contempla `--skip_doxygen=true --skip_ccs=true`; no demuestra que
  esos argumentos resuelvan el fallo observado por David.
- `chmod +x` sólo aborda un fallo de permisos de ejecución. No resuelve
  URLs rotas, descargas fallidas o una versión incompatible.
- No reinstalar CCS por estos errores de fuentes. TI Arm Clang y SysConfig
  pueden indicarse directamente al invocar `make`, sin `export`.

La guía propone `west init` y `west update` para un workspace nuevo. Aquí
**ya existe `.west/config` con `am243x/dev.yml`**. No repetir la inicialización
ni ejecutar una actualización global sin revisar sus efectos: el manifiesto
apunta a `next`/`mcupsdk_next` y puede deshacer la alineación de versiones.

## 4. Corregir las dependencias y sus revisiones

Esta sección reproduce las reparaciones, no ordena repetirlas si ya están hechas.
No clonar encima de directorios existentes. No usar `reset --hard`, `clean -fd`
o un checkout forzado para resolver conflictos con trabajo local.

### 4.1. ICSS EMAC LLD ausente

Error observado:

```text
Cannot find module '../source/networking/icss_emac_lld/icss_emac/.project/project.js'
```

El repositorio se enumera en el README del MCU+ SDK, pero no en el manifiesto
AM243x utilizado. Si el directorio aún no existe, desde `mcu_plus_sdk/`:

```bash
git clone --branch REL.ICSDK.2026.01.00.05 --single-branch \
  https://github.com/TexasInstruments/icss-emac-lld.git \
  source/networking/icss_emac_lld
```

Esta etiqueta contiene el proyecto requerido. La generación de buildfiles
pasó después de incorporar las dependencias, según la salida compartida por David.
Eso no acredita que todas las bibliotecas ICSS hayan terminado de compilar.

### 4.2. PHY Ethernet: `phy_common_priv.obj` y después `generic_phy.obj`

Los objetos faltaban porque sus fuentes pertenecen al repositorio externo
`ethernet-rtos-drivers`, ubicado en `source/board/ethphy/enet`.

**Corrección de la primera recomendación:** el manifiesto `all/dev.yml` cita
`v2025.01`, pero esa etiqueta no contiene `generic_phy.c` ni `generic_phy.h`.
La revisión contrastada es **`v2026.03.9`**: sus 23 archivos C/H coinciden con
los del componente PHY del instalador 12.01.00.33, normalizando CRLF.

Para una incorporación nueva, desde `mcu_plus_sdk/`:

```bash
git clone --branch v2026.03.9 --single-branch \
  https://github.com/TexasInstruments/ethernet-rtos-drivers.git \
  source/board/ethphy/enet
```

Si ya existe el clon antiguo, comprobar primero `git status --short` dentro
de ese repositorio y preservar cambios si los hay. Con el árbol limpio:

```bash
git -C source/board/ethphy/enet fetch origin tag v2026.03.9 &&
git -C source/board/ethphy/enet switch --detach v2026.03.9
```

No eliminar `generic_phy.c` del makefile ni crear objetos vacíos.

### 4.3. Algoritmo OSPI tuning ausente

Error observado:

```text
'ospi_tuning/ospi_tuning_algo/algo_v1/ospi_phy_tuning.h' file not found
```

Faltaba todo el componente dentro de `source/drivers/ospi/v0/lld/`.
El SDK instalado sí contiene la cabecera y la implementación de `algo_v1`.
Desde `mcu_plus_sdk/`, sólo cuando ese directorio todavía no existe:

```bash
cp -a "$HOME/ti/mcu_plus_sdk_am243x_12_01_00_33/source/drivers/ospi/v0/lld/ospi_tuning" \
  source/drivers/ospi/v0/lld/
```

El makefile ya enumera `ospi_phy_tuning.c` y su directorio. No modificar el
`#include`, quitar `ENABLE_PHY_TUNING_SOC_BUILD` o copiar sólo la cabecera.
La presencia del algoritmo se verificó después de la reparación.

Este PHY de **OSPI** no es el PHY **Ethernet** de la sección anterior. Tampoco
es lo mismo que la operación Uniflash `flash-phy-tuning-data`, que escribe
datos en la flash y requiere revisar la configuración y el mapa de memoria.

### 4.4. ENET core incompatible con las cabeceras CSL

Error observado:

```text
call to undeclared function 'CSL_CPSW_accPortStats'
```

El ENET de la rama de desarrollo esperaba una API ausente en las cabeceras
CSL del SDK core 12.01. La etiqueta compatible es
**`REL.MCUSDK.K3.12.01.00.31`**: los 135 archivos C/H de `src` e `include`
coinciden con el ENET del instalador 12.01.00.33, normalizando CRLF.

No sustituir `accPortStats` por `getPortStats` manualmente. El ENET compatible
también cambia los argumentos y la acumulación de estadísticas.

En este caso había 42 makefiles modificados en el repositorio ENET. Antes de
cambiar su revisión, conservarlos; desde `mcu_plus_sdk/`:

```bash
git -C source/networking/enet/core stash push -m "Guardar makefiles antes de alinear ENET con SDK 12.01" &&
git -C source/networking/enet/core switch --detach REL.MCUSDK.K3.12.01.00.31
```

La etiqueta ya estaba disponible localmente. El stash conserva los cambios;
no aplicar `stash pop` automáticamente sobre otra revisión. Regenerar primero
los makefiles correctos y revisar después cualquier cambio que se quiera recuperar.

### 4.5. Comprobar la alineación sin cambiarla

Desde la raíz del proyecto:

```bash
git -C mcu_plus_sdk describe --tags --exact-match HEAD
git -C mcu_plus_sdk/source/board/ethphy/enet describe --tags --exact-match HEAD
git -C mcu_plus_sdk/source/networking/enet/core describe --tags --exact-match HEAD
git -C mcu_plus_sdk/source/networking/icss_emac_lld describe --tags --exact-match HEAD
```

Conservar la tabla de versiones como referencia. Los cambios locales de
`bootloader.c` y `.metadata/product.json` no se descartan para alinear dependencias.

## 5. Parche del bootloader que pide la guía

En **MCU+ SDK / Setup**, la guía pide forzar `entryPoint = 0` dentro de
`Bootloader_runCpu`, debido a cómo Zephyr construye la imagen descrita allí.

En este clon ya está hecho: se comentaron la condición sobre `rprcOffset`
y sus llaves, dejando la asignación a cero incondicional antes de
`Bootloader_socCpuResetRelease`. Para revisarlo, sin volver a editarlo:

```bash
git -C mcu_plus_sdk diff -- source/drivers/bootloader/bootloader.c
```

Límites importantes:

- El parche afecta al bootloader del clon, no al Zephyr ELF.
- Fuerza la entrada para los usuarios de esa función; no generalizarlo a
  aplicaciones cuyo punto de entrada no sea cero ni a otros productos.
- `Bootloader_runSelfCpu` es una ruta distinta. No se ha demostrado que este
  parche explique o resuelva el silencio observado en la entrega al firmware.
- Hay que recompilar `drivers`, reenlazar el SBL y grabar **ese SBL** para
  que cambie el código que ejecuta la placa.
- El `sbl_prebuilt` del SDK instalado no cambia por editar el clon.
- `just flash-zephyr` sólo actualiza la aplicación: **no instala este parche
  en el SBL de la flash**.

La entrada `0x0` del Hello World local fue comprobada. La eficacia física del
parche para este problema sigue sin verificarse.

## 6. Optimización: construir sólo las bibliotecas de estos SBL

La guía utiliza:

```bash
make gen-buildfiles DEVICE=am243x PROFILE=release
make libs DEVICE=am243x PROFILE=release
```

`make libs` recorre también Ethernet, TSN, FreeRTOS, USB y otros componentes.
Para el objetivo actual se pueden seleccionar menos bibliotecas:

| SBL | Bibliotecas SDK enumeradas en su makefile R5F NoRTOS |
| --- | --- |
| `sbl_ospi` | `nortos`, `drivers`, `board` |
| `sbl_uart_uniflash` | Las anteriores y `middleware` |

Además se enlazan las bibliotecas de runtime del compilador. Las dependencias
anteriores y los nombres de targets se verificaron en los makefiles locales.
**Esta ruta reducida se validó estáticamente; no se ejecutó aquí su build/link.**

Desde `mcu_plus_sdk/`, después de una generación correcta de makefiles:

```bash
make -f makefile.am243x DEVICE=am243x PROFILE=release \
  nortos_r5f.ti-arm-clang \
  board_r5f.ti-arm-clang.nortos \
  drivers_r5f.ti-arm-clang.nortos \
  middleware_r5f.ti-arm-clang.nortos
```

Esto evita construir ENET/TSN y variantes de CPU/OS que no están en esos dos
SBL. No elimina sus fuentes ni convierte el SDK entero en un build validado.
Siguen siendo necesarias las fuentes PHY de board y el algoritmo OSPI de drivers.
La generación global de makefiles aún puede exigir proyectos ICSS: optimizar
los targets de compilación no equivale a reparar ese generador.

Si se desea compilar **todas** las bibliotecas, mantener la ruta completa y
usar `&&` para no continuar tras un fallo:

```bash
make gen-buildfiles DEVICE=am243x &&
make libs DEVICE=am243x PROFILE=release
```

`development mode` es el modo del generador; no contradice `PROFILE=release`
de las bibliotecas. No es necesario limpiar todo cada vez que se añade una
fuente ausente. Cambiar de toolchain, flags o configuración exige revisar la
consistencia de los artefactos; no sustituir esa revisión por borrar todo a ciegas.

## 7. Construir los SBL necesarios, no todos los ejemplos

La sección oficial **Building MCU+ SDK SBLs** permite elegir según el uso:

| Ejemplo | Uso |
| --- | --- |
| `sbl_ospi` | Persistencia: SBL en flash que carga la aplicación desde `0x80000`. |
| `sbl_uart_uniflash` | Flash writer temporal cargado por UART; recibe operaciones de escritura/verificación. |
| `sbl_uart` | Carga temporal de firmware por UART; no confundir con escribir flash. |
| `sbl_null` | Preparar el SoC para cargar un ELF con el depurador. |

Para el flujo persistente, desde `mcu_plus_sdk/`:

```bash
make -C examples/drivers/boot/sbl_ospi/am243x-lp/r5fss0-0_nortos/ti-arm-clang \
  DEVICE=am243x PROFILE=release \
  CGT_TI_ARM_CLANG_PATH="$HOME/ti/ti-cgt-armllvm_4.0.4.LTS" \
  SYSCFG_PATH="$HOME/ti/sysconfig_1.27.0" PYTHON=/usr/bin/python3 &&
make -C examples/drivers/boot/sbl_uart_uniflash/am243x-lp/r5fss0-0_nortos/ti-arm-clang \
  DEVICE=am243x PROFILE=release \
  CGT_TI_ARM_CLANG_PATH="$HOME/ti/ti-cgt-armllvm_4.0.4.LTS" \
  SYSCFG_PATH="$HOME/ti/sysconfig_1.27.0" PYTHON=/usr/bin/python3
```

Son argumentos de `make`, no variables que haya que exportar en la terminal.
No se han ejecutado en esta tarea documental. Además de las bibliotecas,
requieren que las dependencias Python y SysConfig estén operativas.

Los makefiles seleccionan aquí las imágenes de desarrollo `.hs_fs.tiimage`
salvo configuración HS específica. Verificar los archivos realmente generados
en el directorio del ejemplo y en `tools/boot/sbl_prebuilt/am243x-lp/`.
No confundir un `.out` para depuración, un SBL `.tiimage` cargable por ROM
y la aplicación `.mcelf.hs_fs` cargable por el SBL.

No se acredita con estos comandos una configuración de secure boot HS-SE,
el uso de claves de producción o compatibilidad con cualquier dispositivo TI.

## 8. Compilar Zephyr y crear MCELF sin `export` ni `EOF`

Desde la raíz del proyecto:

```bash
just build-zephyr && just check-zephyr
```

El flujo local es:

```text
zephyr/samples/hello_world
  → build/zephyr_hello/zephyr/zephyr.elf
  → build/zephyr_hello/boot-image/hello_world.mcelf
  → build/zephyr_hello/boot-image/hello_world.mcelf.hs_fs
```

Puntos comprobados del adaptador [`scripts/zephyr_local.py`](scripts/zephyr_local.py):

- Target `lp_am243/am2434/r5f0_0`, core TI `4`, entrada `0x0`, sin XIP.
- El kernel, la aplicación y la placa se toman del árbol `zephyr/` local.
- Los módulos `cmsis`, `cmsis_6` y `ti` se reutilizan del workspace anterior,
  mediante rutas explícitas, no mediante el manifiesto MCU+ SDK de esta raíz.
- El caché copiado apuntaba al workspace anterior. Por eso se usa el build
  fijo nuevo y se verifica `ZEPHYR_BASE` en `CMakeCache.txt`.
- El adaptador y Uniflash usan `/usr/bin/python3`; CMake, el generador MCELF
  y el firmador de aplicación usan el Python especificado en `.zephyr.local.json`.
- Las herramientas TI de este flujo de **Hello World** se toman del **SDK instalado**,
  según el JSON. No se cambian al clon por compilar sus bibliotecas.
- Generación con `genimage_am64x.py`, argumento `--core-img=4:<ELF>`;
  se omite `--xip`, no se escribe `--xip=None`.
- Firma con `appimage_x509_cert_gen.py`, `--authtype 1` y
  `app_degenerateKey.pem`. Es una clave de desarrollo, no la clave ROM ni
  una aprobación de producción.
- Se validan segmentos cargables, primer segmento MCELF `PT_NOTE`, notas de
  core/entrada, payload después del certificado, tamaño y hashes.

La guía oficial aún muestra `elf2rprc`, `xipGen` y `multicoreImageGen`, con
SysConfig `1.21.2`. **No mezclar esa receta con el flujo 12.01/MCELF.**
Las notas de migración TI del SDK 12.01 indican que RPRC está deprecado.

Firmar directamente `zephyr.elf` no crea un MCELF: sólo antepone el certificado.
David observó un fallo al usar ese ELF firmado. La conversión al formato
esperado por el SBL y la firma son pasos distintos.

**Compatibilidad del lector MCELF:** el generador AM64 de TI 12.01 elimina
la tabla de secciones (`e_shoff = e_shnum = 0`) pero conserva `e_shstrndx`.
Eso hizo fallar pyelftools con la nueva app. El adaptador pone ese índice a
cero sólo en una copia en memoria para leer las cabeceras de programa;
**no modifica el MCELF generado, el firmado ni las herramientas TI**.
Los segmentos y el payload firmado siguen comparándose con sus bytes originales.

## 9. Grabación: separar instalación del SBL y actualización de aplicación

La guía explica el recorrido ROM → flash writer → escritura de flash. Las
operaciones de grabación de esta sección **sí modifican el dispositivo** y
deben ejecutarse sólo cuando se autorice la imagen, puerto y mapa concretos.

### 9.1. Actualización habitual de la aplicación: flujo local existente

Requiere que ya haya un SBL OSPI compatible en `0x0`. Con la placa en UART
BOOT, reiniciada y con el monitor serie cerrado, desde la raíz del proyecto:

```bash
just check-zephyr
just flash-zephyr /dev/ttyACM0
```

El puerto es un ejemplo; usar el dispositivo real. `just ports` enumera sus
metadatos sin abrirlo. La selección de UART ROM sí abre el puerto y algunos
drivers pueden alterar DTR/RTS al hacerlo.

El CFG fijo `tools/sbls-am243x-lp/zephyr_hellw_sbl_ospi.cfg` realiza:

1. Cargar el flash writer del SDK instalado por UART.
2. `flash` de `hello_world.mcelf.hs_fs` en `0x80000`.
3. `flashverify` de la misma imagen en el mismo offset.

No escribe el SBL en `0x0`, no escribe una imagen XIP y no borra toda la flash.
El archivo contiene rutas absolutas reales; no es un heredoc ni se pega en la
terminal. `$SDK` y `$IMAGE` literales dentro de un `.cfg` no se expanden.

### 9.2. Instalar o sustituir el SBL: operación separada

El SBL recompilado del clon **no se instala** al ejecutar el comando anterior.
Para incorporarlo hay que seleccionar expresamente su `.hs_fs.tiimage`,
verificar la procedencia y preparar una operación adicional en `0x0`.

Estructura de referencia para esa configuración, **no ejecutable tal cual**:

```text
--flash-writer=<RUTA_ABSOLUTA_FLASH_WRITER>
--file=<RUTA_ABSOLUTA_SBL_OSPI_RECOMPILADO> --operation=flash --flash-offset=0x0
--file=<RUTA_ABSOLUTA_SBL_OSPI_RECOMPILADO> --operation=flashverify --flash-offset=0x0
--file=<RUTA_ABSOLUTA_APLICACION_MCELF_FIRMADA> --operation=flash --flash-offset=0x80000
--file=<RUTA_ABSOLUTA_APLICACION_MCELF_FIRMADA> --operation=flashverify --flash-offset=0x80000
```

Sustituir todos los marcadores por rutas reales antes de invocar Uniflash.
No convertir silenciosamente el CFG habitual de aplicación en una instalación
de SBL. Revisar límites de imagen, particiones y estado de la placa.

La guía incluye `--operation=flash-phy-tuning-data`. No se añadió al flujo
local ni se ejecuta automáticamente: revisar antes su necesidad, posición y
posibles solapamientos según el SDK y la configuración del SBL elegidos.

### 9.3. Pasar de UART a QSPI

Después de que la herramienta termine correctamente, apagar la placa,
seleccionar el modo QSPI y encender. UART de consola: **115200, 8N1**.
R5F0_0 usa por defecto la UART conectada al XDS110; la MCU_UART0 del M4
en J17 es otra consola.

La guía publica para SW4 las cadenas UART `11100000` y QSPI `01000100`.
Su tabla etiqueta `[1:7]` pero muestra ocho bits: **confirmar la numeración
y orientación ON/OFF con la serigrafía y el manual de la placa**, no deducirlas
del orden visual del texto. No cambiar BOOT ni apagar durante una escritura activa.

## 10. Qué demuestra cada resultado y cómo tratar un intento incierto

| Resultado | Demuestra | No demuestra |
| --- | --- | --- |
| `Generating build files ... Done` | El generador terminó | Todas las bibliotecas compilan |
| Archivo `.lib` generado | Se creó esa biblioteca | El SBL se reenlazó con ella |
| SBL recompilado | Existe un nuevo artefacto | Está grabado en la placa |
| MCELF y firma verificados | Formato y payload local coherentes | Arranque de Zephyr |
| Uniflash completa `flash` y `flashverify` | Grabación y verificación reportadas por la herramienta | Aparición de Hello World |
| `switching to application` | El SBL anunció la entrega de control | Zephyr alcanzó `main()` o su consola funciona |

**Comportamiento vigente solicitado por David, 2026-11-12:** un fallo de
grabación no bloquea el siguiente comando. Para reintentar, preparar UART BOOT,
cerrar la consola y volver a ejecutar `just flash-hola` o `just flash-zephyr`.
No hace falta mover archivos, recompilar, volver a configurar ni usar `--force`.

La salida se muestra únicamente en terminal; **no se guardan logs, recibos ni
archivos históricos de intentos**. Los archivos de intentos anteriores a este
cambio se ignoran sin borrarlos o modificarlos. El `verification.json` del
build sigue validando la imagen: no es un historial de grabaciones.

Cada comando ejecuta una sola vez la herramienta TI, sin reintento en bucle.
Se mantienen la exclusión de operaciones simultáneas, la comprobación de
imágenes/puerto y la detección de errores. Un fallo nunca se presenta como éxito.

## 11. Diagnóstico opcional: antecedente del silencio tras el SBL

Este apartado conserva el antecedente anterior a la confirmación de David
sobre haber completado la guía. No es un requisito para crear o grabar otra app.

La guía recomienda `sbl_null` más depurador para desarrollo. Es una alternativa
para cargar el ELF y observar PC, reset y excepciones sin convertir y grabar
cada iteración. Requiere preparar/grabar ese SBL y verificar CCS/JTAG u OpenOCD;
no se ha comprobado ese recorrido en esta tarea y no se cambia el modo actual.

Conservar estas distinciones antes de otra prueba:

- El Hello World local no contiene el marcador `[Z] consola inicializada`.
  La imagen de diagnóstico preparada fuera de esta copia es otro artefacto;
  no asumir que `just build-zephyr` la compila.
- Los segmentos cargables del nuevo Hello World coincidían con los del build
  copiado anterior. Se corrigió la reproducibilidad, no se demostró un cambio
  funcional que arregle el silencio.
- El marcador, si se usa en una prueba autorizada, permite separar el arranque
  temprano de etapas posteriores. Su ausencia no distingue por sí sola un
  bloqueo del CPU de un problema de consola.
- No se ha establecido como causa MPU, FPU, vectores, temporizador o UART.
  Consultar el PC/estado del core aporta más información que cambios a ciegas.
- Se conserva el aviso de DTS `/memory@0` frente a `reg = 0x3c`; la compilación
  terminó con él, pero no se ha demostrado que explique el fallo de arranque.
- Los resets y desconexiones USB que David identificó como manuales no se
  reinterpretan como fallos espontáneos. Su éxito de GPIO multiblink se conserva.

## 12. Estado de validación y fuentes

**Verificado localmente:** revisiones actuales de los cuatro repositorios;
coincidencia de fuentes PHY y ENET con el instalador; componente OSPI presente;
parche `entryPoint` existente; reglas y bibliotecas de los dos SBL;
compilación/conversión/firma del Hello World local y `check-zephyr`;
68 pruebas sin hardware del adaptador y del programa con APIs simuladas,
incluidas las de reintento manual sin guardar historial.
Uniflash completó el reintento descrito. La nueva app `hola_zephyr` se compiló,
convirtió, firmó y pasó `check-hola`; `check-zephyr` también sigue pasando.

**No verificado aquí:** éxito de `download_components.sh`, compilación completa
de todas las bibliotecas, ejecución de la ruta reducida de SBL, despliegue y
arranque de un SBL reconstruido con el parche, Hello World en consola y
depuración por JTAG/OpenOCD. No hay aprobación de producción ni publicación.
Lo anterior distingue las comprobaciones directas del agente de la confirmación
posterior del recorrido por David. La captura más reciente alcanza Z4, pero no
Z4A. El mapa pone a continuación el init de pinctrl TI K3, que sólo ejecuta
`DEVICE_MMIO_MAP`; Z4PA-Z4PD instrumentan esa función para acotar la llamada y
su retorno. No se demuestra bloqueo ni pérdida de la traza UART. Capturas
anteriores alcanzaron fases posteriores, por lo que hay que confirmar la imagen
exacta. El recibo y las pruebas host no miden ejecución física.

## 13. Aplicación propia y persistente: `hola_zephyr`

La aplicación está en [`apps/hola_zephyr/`](apps/hola_zephyr/README.md), con
`CMakeLists.txt`, `prj.conf` y `src/main.c`, separada de `zephyr/samples/hello_world`.
Usa `printk("hola soy zephyr\n")` y `k_sleep(K_SECONDS(3))` en un bucle del hilo
principal: primer mensaje inmediato, pausa nominal de tres segundos, sin shell
ni espera ocupada. Para el diagnóstico actual se instrumentaron condicionalmente
`zephyr/arch/arm/core/cortex_a_r/prep_c.c` y `zephyr/kernel/init.c` con Z1A-Z1T
y Z2A-Z2D; el flujo original queda intacto si se desactiva
`CONFIG_HOLA_EARLY_UART_TRACE`. No se editan fuentes de placa, SDK TI o SBL.
La prueba actual habilita MPU, banner, consola temprana, assertions y diagnóstico
de fallos. Usa un overlay de la app para mapear ATCM completo y una cabecera local
para corregir la conversión de regiones MPU en ARMv7-R de este checkout. Véase
[Prueba con MPU y diagnóstico](apps/hola_zephyr/README.md#prueba-con-mpu-y-diagnóstico)
para el motivo, alcance y límites. El adaptador incluye y verifica por hash ambos
archivos; no basta con cambiar `prj.conf` y reutilizar una imagen anterior.
La flag propia `CONFIG_HOLA_EARLY_UART_TRACE=y` añade Z0-Z2 antes del kernel,
Z1A-Z1T durante `z_prep_c`, Z2A-Z2D dentro de `z_cstart`, Z3-Z8 hasta `main()`
y Z1M-A...Z1M-P dentro de la inicialización del VIM y sus wrappers, ZR1-ZR13
dentro del reset, Z4PA-Z4PD dentro de pinctrl y Z4A-Z4C tras los drivers
PRE_KERNEL_1, directamente por UART. La última captura llega a Z4, pero no
Z4A; falta observar las trazas nuevas de pinctrl. Conserva los vectores y el
primer marcador en el mismo segmento ELF desde cero. Detalles y límites:
[trazas de arranque](apps/hola_zephyr/README.md#flag-de-trazas-anteriores-al-kernel).

Desde la raíz del proyecto:

```bash
just build-hola && just check-hola
```

Artefactos fijos:

```text
build/hola_zephyr/
├── zephyr/zephyr.elf
├── boot-image/hola_zephyr.mcelf
├── boot-image/hola_zephyr.mcelf.hs_fs
├── boot-image/verification.json
├── sbl_uart_uniflash.release.hs_fs.tiimage
└── flash-hola-zephyr.cfg
```

Para conversión y firma se reutiliza el SDK 12.01 de `.zephyr.local.json`.
Para grabación se seleccionan expresamente Uniflash y el flash writer del
clon `mcu_plus_sdk/`. El build **copia** el writer compilado de
`mcu_plus_sdk/tools/boot/sbl_prebuilt/am243x-lp/` al nuevo directorio de trabajo,
como pide la guía remota; no omite ese paso ni lo sustituye por un enlace.
El CFG referencia esa copia por nombre y la imagen por su ruta local real;
Uniflash se ejecuta desde `build/hola_zephyr/`. No hay variables sin expandir.

Para una escritura explícita, con UART BOOT preparado y la consola cerrada:

```bash
just flash-hola /dev/ttyACM0
```

Usar el puerto real. Este comando **sí escribe**: sólo `flash` y `flashverify`
de `hola_zephyr.mcelf.hs_fs` en `0x80000`. Conserva el SBL de `0x0` y los datos
PHY; no ejecuta de nuevo el CFG que instala todo. Tras terminar correctamente,
apagar, seleccionar QSPI y encender con consola a 115200, 8N1.

El writer es temporal en RAM durante la grabación, pero **la aplicación queda
en flash**. Los fuentes, recetas y rutas de build son permanentes y no están
en carpetas temporales de diagnóstico. `build/` continúa ignorado por Git.
Los comandos `*-zephyr` siguen seleccionando Hello World; los `*-hola`, esta app.

Fuentes para contrastar o actualizar esta guía:

- [Guía oficial Zephyr LP-AM243](https://docs.zephyrproject.org/latest/boards/ti/lp_am243/doc/index.html), secciones citadas en la introducción y a lo largo del documento.
- [README del MCU+ SDK de esta copia](mcu_plus_sdk/README.md), componentes externos, preparación y construcción.
- [Notas TI 12.01](mcu_plus_sdk/docs_src/docs/api_guide/device/am64x_am243x/release_notes_12_01_00.md), versiones y migración RPRC/MCELF.
- [Manifiesto AM243x usado](mcupsdk-manifests.git/am243x/dev.yml) y [manifiesto general](mcupsdk-manifests.git/all/dev.yml), contrastados con los repositorios y el instalador, no tomados como garantía de compatibilidad.
- [Makefile AM243x](mcu_plus_sdk/makefile.am243x), selección de bibliotecas.
- [Makefile de SBL OSPI](mcu_plus_sdk/examples/drivers/boot/sbl_ospi/am243x-lp/r5fss0-0_nortos/ti-arm-clang/makefile) y [makefile del flash writer](mcu_plus_sdk/examples/drivers/boot/sbl_uart_uniflash/am243x-lp/r5fss0-0_nortos/ti-arm-clang/makefile), bibliotecas y generación de imágenes.
- [Adaptador local](scripts/zephyr_local.py), [pruebas](tests/test_zephyr_local.py) y [README, sección 12](Readme.md#12-hello-world-de-la-copia-local-de-zephyr-sin-export), comandos actuales sin `export`.
- Salidas compartidas por David y comprobaciones locales del 2026-11-12. El detalle de errores está condensado en la sección 4, no reproducido como un volcado de logs.
