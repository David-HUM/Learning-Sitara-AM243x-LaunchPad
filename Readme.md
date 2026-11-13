# Primer ejemplo en la TI AM243x LaunchPad

**Fuente:** notas del procedimiento utilizado y confirmación de David del 2026-11-11.
**Resultado confirmado por David:** el ejemplo **GPIO multiblink LED funcionó siguiendo esos pasos**.

Esta guía conserva ese resultado. No exige repetir pruebas ni revisar la
placa. Los pendientes son datos que conviene dejar escritos para poder consultar
y repetir el procedimiento, no dudas nuevas sobre si el ejemplo funcionó.

Las secciones 3 a 9 describen el procedimiento manual. Para preparar los
perfiles con comandos, usar la [automatización con `just`](#11-automatizar-con-just).
Son alternativas: no es necesario ejecutar ambos recorridos para una grabación.

Para Zephyr, el flujo actual del workspace y sus dos aplicaciones está en la
[sección 12](#12-workspace-zephyr-y-aplicaciones-locales). Como antecedente de
LP-AM243 con MCU+ SDK 12.01, se conserva
[From guide: adaptación de la guía oficial](from%20guide.md), con las
dependencias corregidas y una ruta reducida para construir los SBL. Sus rutas,
cachés y comandos de preparación antiguos no sustituyen el flujo actual.
La app propia que saluda cada tres segundos está en
[`apps/hola_zephyr`](apps/hola_zephyr/README.md), con comandos y artefactos separados.
El estado y los problemas conocidos de su arranque están resumidos en
[SUMMARY.md](SUMMARY.md).

## 1. Objetivo y alcance

Documentar la preparación de las herramientas de TI en Ubuntu, la compilación
del ejemplo GPIO multiblink LED en CCS y su grabación mediante UART para arrancar
desde la memoria flash con el SBL correspondiente.

Este recorrido utiliza **TI MCU+ SDK y CCS**. La guía muestra el contenido
de la configuración que se edita manualmente, sin reproducir ni modificar los
scripts del SDK o del proyecto y sin exponer la estructura de carpetas del autor.

## 2. Entorno utilizado

| Elemento | Dato disponible |
| --- | --- |
| Sistema operativo | Ubuntu; versión por registrar |
| Placa de referencia de las notas | TI AM243x LaunchPad, LP-AM243 |
| IDE | CCS 21.0.1, según las notas del procedimiento utilizado |
| MCU+ SDK | Versión y directorio por registrar |
| TI Arm Clang | Versión por registrar |
| SysConfig | Versión por registrar |
| Python utilizado por las herramientas | Versión por registrar |
| Ejemplo | GPIO multiblink LED, confirmado por David |
| Ruta o identificador exacto del ejemplo en el SDK | Por registrar |
| Núcleo y variante del ejemplo, por ejemplo NoRTOS o FreeRTOS | Por registrar, sin asumirlos |
| Configuración de compilación | Release, según las notas |

Usar las versiones que funcionaron. Los enlaces `latest` sirven de referencia,
pero no reemplazan el registro de la versión instalada.

## 3. Variables de entorno y enlaces simbólicos

### 3.1. Para qué sirve `export`

En Bash, `export NOMBRE="valor"` define una variable de entorno y permite que
los programas lanzados desde esa terminal la reciban. En esta guía sirve para
escribir una sola vez las ubicaciones de las herramientas y de la imagen, y
referirse después a ellas por un nombre común.

Sustituir los textos entre `<...>` antes de ejecutar los comandos. Las rutas
de CCS, SDK e imagen deben ser absolutas; no se muestra ninguna ubicación
personal como referencia obligatoria.

```bash
export CCS_INSTALL_DIR="<DIRECTORIO_RAIZ_DE_CCS>"
export SDK_INSTALL_PATH="<DIRECTORIO_RAIZ_DEL_MCU_PLUS_SDK>"
export APP_IMAGE="<ARCHIVO_GPIO_MULTIBLINK_RELEASE.mcelf.hs_fs>"
export UART_PORT="<PUERTO_UART>"
```

- `CCS_INSTALL_DIR`: directorio que contiene la carpeta `ccs` de la instalación.
- `SDK_INSTALL_PATH`: directorio que contiene `tools`, `source` y `examples` del SDK.
- `APP_IMAGE`: ubicación del archivo generado para GPIO multiblink LED.
- `UART_PORT`: dispositivo serie correspondiente, por ejemplo `/dev/ttyACM0`;
  el nombre puede cambiar entre equipos.

`export` no instala herramientas, no mueve archivos, no cambia permisos y
**no crea un enlace simbólico**. Estas variables duran en esa sesión de terminal
y en los procesos que hereden su entorno; no quedan guardadas automáticamente
para la próxima terminal. Las comillas conservan el valor como una sola cadena.

### 3.2. Para qué sirven los enlaces simbólicos

Un enlace simbólico es un nombre de archivo que apunta a otro archivo, sin
copiar su contenido. Se crea con `ln -s`. Aquí permitirá que la configuración
use nombres sencillos en lugar de rutas particulares de una computadora.

Los enlaces se preparan localmente: no se deben publicar enlaces absolutos que
apunten a carpetas privadas del autor. Cada persona los crea con sus variables.

## 4. Preparar las dependencias e instalar las herramientas

### 4.1. Dependencias del sistema

Las notas identifican `python3`, `openssl`, `dfu-util` y `mono-runtime` como
dependencias de las herramientas utilizadas. Conviene distinguir su finalidad:

- **Python:** scripts de compilación, preparación de imágenes y grabación.
- **OpenSSL:** operaciones de firma de imágenes realizadas por las herramientas.
- **Mono:** requerido por herramientas de generación de imágenes según la guía de TI.
- **dfu-util:** corresponde al flujo USB DFU; no confundirlo con el transporte UART usado aquí.

Para los instaladores que lo requieran, dar permiso de ejecución al archivo
específico antes de abrirlo, por ejemplo `chmod +x nombre_del_instalador.run`.
No aplicar permisos de ejecución indiscriminadamente a todos los archivos.

### 4.2. Instalar CCS y MCU+ SDK

1. Instalar CCS como usuario normal.
2. Seleccionar la familia **AM2x Arm-based high performance microcontrollers**.
3. Instalar el MCU+ SDK para AM243x y registrar su versión y ubicación.
4. Conservar las versiones de TI Arm Clang y SysConfig utilizadas por el ejemplo.

El nombre del instalador del MCU+ SDK y su versión quedan por completar a partir
de la instalación utilizada, sin inventarlos en esta guía.

### 4.3. Instalar los drivers de CCS

Ejecutar el script oficial desde la instalación correspondiente:

```bash
cd "$CCS_INSTALL_DIR/ccs/install_scripts"
sudo ./install_drivers.sh
```

Este paso requiere privilegios para instalar los drivers. No implica que CCS
deba ejecutarse habitualmente con `sudo`.

### 4.4. Verificar las herramientas detectadas

En CCS, abrir:

```text
File > Preferences > CCStudio IDE Settings
```

Comprobar TI Arm Clang en **Compilers** y SysConfig en **Products**. Las notas
indican que los templates descargaron herramientas; registrar qué versiones
quedaron seleccionadas, en lugar de asumir que cualquier versión es equivalente.

## 5. Importar y compilar GPIO multiblink LED

1. Importar el ejemplo correspondiente a `am243x-lp`.
2. Documentar aquí su ruta exacta en el SDK y el núcleo/variante seleccionados.
3. Seleccionar la configuración **Release**, como en el procedimiento que funcionó.
4. Compilar y registrar el nombre y la ubicación de la imagen generada.

Las notas mencionan una imagen **`.mcelf.hs_fs`**. Mantener ese formato en esta
guía y no reemplazarlo por `.elf`, `.bin` o `.appimage` como si fueran
intercambiables. La extensión y el formato deben corresponder al bootloader y a
la versión del SDK utilizados.

### Dependencias adicionales que se anotaron para compilar desde CCS

```bash
sudo apt update
sudo apt install -y python3-pyelftools python3-construct python3-setuptools
```

Conservar estos paquetes como parte del procedimiento documentado. Si se dispone
del mensaje original de dependencia faltante, añadirlo a la sección de problemas.
No sustituir este paso automáticamente por un entorno virtual que CCS quizá no use.

## 6. Mostrar y preparar el archivo que se modifica a mano

El archivo editable es la configuración `.cfg`. No hace falta copiar el código
de `uart_uniflash.py`, modificar scripts del SDK ni editar scripts del proyecto.

La plantilla de TI utilizada en las notas se encuentra, dentro del SDK, en:

```text
tools/boot/sbl_prebuilt/am243x-lp/default_sbl_ospi.cfg
```

Para esta versión portable se propone conservar la plantilla original y escribir
una configuración propia, `flash-gpio-multiblink.cfg`, junto a los enlaces.
El ejemplo ya funcionó con los pasos originales; esta variante documental con
enlaces simbólicos **todavía no se ha ejecutado**.

### 6.1. Preparar nombres simbólicos para las imágenes

Desde una carpeta de trabajo elegida por cada persona y con las variables de la
sección 3 ya definidas, los comandos propuestos son:

```bash
ln -sT -- \
  "$SDK_INSTALL_PATH/tools/boot/sbl_prebuilt/am243x-lp/sbl_uart_uniflash.release.hs_fs.tiimage" \
  flash-writer.tiimage

ln -sT -- \
  "$SDK_INSTALL_PATH/tools/boot/sbl_prebuilt/am243x-lp/sbl_ospi.release.hs_fs.tiimage" \
  sbl-ospi.tiimage

ln -sT -- "$APP_IMAGE" gpio-multiblink.mcelf.hs_fs
```

`-s` crea el enlace simbólico y `-T` trata el destino como un nombre concreto,
no como una carpeta. No se utiliza `-f`: si un nombre ya existe, revisar lo que
hay antes de reemplazarlo. Crear un enlace no comprueba que su archivo destino
exista; todos los destinos deben estar disponibles antes de grabar.

Estos nombres apuntan a los binarios reales; no son copias ni rutas de la
estructura personal del autor.

### 6.2. Contenido completo propuesto de `flash-gpio-multiblink.cfg`

Crear o editar manualmente este archivo en la misma carpeta de trabajo:

```text
# Aplicación temporal que recibe los datos y escribe la flash.
--flash-writer=flash-writer.tiimage

# Operación de ajuste PHY incluida en la plantilla de TI consultada.
--operation=flash-phy-tuning-data

# Bootloader que se ejecutará al arrancar desde la flash.
--file=sbl-ospi.tiimage --operation=flash --flash-offset=0x0

# Imagen principal de GPIO multiblink LED.
--file=gpio-multiblink.mcelf.hs_fs --operation=flash --flash-offset=0x80000

# Sólo si esta compilación genera y requiere una imagen XIP adicional:
# --file=gpio-multiblink.mcelf_xip --operation=flash-mcelf-xip
```

La configuración utiliza **los nombres de los enlaces**, no variables como
`$APP_IMAGE`. `export` no sustituye automáticamente variables dentro de un
archivo `.cfg`; los comandos `ln` sí reciben las rutas expandidas por Bash.
Las rutas relativas de este ejemplo requieren ejecutar la herramienta desde
la carpeta que contiene la configuración y los enlaces.

Los offsets `0x0` y `0x80000` corresponden a la disposición habitual documentada
por TI para este SBL; deben coincidir con la configuración del bootloader usado.

### 6.3. No reutilizar una imagen XIP de otro ejemplo

La plantilla instalada que se consultó conserva una entrada XIP del ejemplo
IPC, además de la entrada de la aplicación. No trasladar esa línea sin revisarla:
una imagen de otro ejemplo no debe acompañar automáticamente a GPIO multiblink.

Por eso la línea XIP queda comentada en el contenido propuesto. Si la compilación
de GPIO multiblink requiere su propia imagen XIP, primero crear su enlace:

```bash
ln -sT -- "<ARCHIVO_XIP_DEL_MISMO_EJEMPLO>" gpio-multiblink.mcelf_xip
```

Sólo entonces habilitar la línea correspondiente del `.cfg`. Si no se usa XIP,
mantenerla comentada. No se modificó la configuración instalada al elaborar
esta guía.

### Archivos del SBL que faltaban

Las notas registran que faltaban archivos referenciados por el `.cfg` y que se
generaron ejecutando `make` desde una carpeta del SDK.

Conservar este hallazgo, completando cuando se tenga el dato:

- Archivo o archivos faltantes.
- Directorio exacto desde el que se ejecutó la construcción.
- Comando y objetivo de `make` utilizados.

No convertirlo en «ejecutar make en cualquier carpeta» ni inventar un comando
universal mientras no esté identificado el que se utilizó.

## 7. Grabar mediante UART

**Este comando escribe en la flash según las operaciones del archivo `.cfg`.**
No es una comprobación de sólo lectura y puede reemplazar el firmware existente.

Antes de utilizarlo, seguir la configuración de arranque UART de la guía de la
LP-AM243 y liberar el puerto si está abierto en otra terminal.

```bash
# Ejecutar desde la carpeta que contiene el .cfg y los enlaces.
python3 "$SDK_INSTALL_PATH/tools/boot/uart_uniflash.py" \
  -p "$UART_PORT" \
  --cfg=flash-gpio-multiblink.cfg
```

Se invoca el script original por su ubicación en el SDK, sin copiarlo ni
modificarlo. Su contenido no forma parte del archivo que editamos a mano.

La documentación de TI enumera `pyserial`, `xmodem`, `tqdm`, `pyelftools` y
`construct` para sus herramientas Python. Registrar cómo quedaron disponibles
en el intérprete usado, sin asumir que instalar paquetes para otro Python basta.

## 8. Diferenciar grabación y arranque

La observación añadida al README sobre `default_sbl_xxxx.cfg` es útil, pero
conviene expresarla con esta distinción:

- **UART** es el transporte empleado por `uart_uniflash.py` para enviar los datos.
- El **`.cfg`** especifica qué archivos se graban, las operaciones y sus destinos.
- El **SBL grabado** determina cómo se carga después la aplicación.
- El **modo de arranque de la placa** determina qué fuente utiliza la ROM al encender.

Por tanto, seleccionar un `.cfg` que graba el SBL OSPI no cambia por sí solo el modo físico de
arranque de la placa. El flujo documentado por TI contempla grabar en modo UART
y después apagar, seleccionar el modo de arranque desde flash y volver a encender.
En esta LaunchPad la flash es QSPI, aunque las herramientas y el ejemplo de TI
utilicen el nombre `ospi`.

**Resultado de este ejemplo:** David confirmó que GPIO multiblink LED funcionó
con sus pasos. Esta propuesta no añade ni exige una nueva comprobación física,
ni atribuye a Zero una prueba independiente del hardware.

## 9. Problemas encontrados y soluciones

### Ajuste de `chrome-sandbox` en CCS 21.0.1

Las notas recogen estos comandos:

```bash
cd "$CCS_INSTALL_DIR/ccs/theia"
sudo chown root chrome-sandbox
sudo chmod 4755 chrome-sandbox
```

Son un ajuste del auxiliar del sandbox, no una instrucción para ejecutar todo
CCS como administrador. Modifican propietario y permisos de un ejecutable:
aplicarlos sólo en la instalación oficial y bajo las condiciones documentadas.

La guía de CCS 21.0.1 los contempla para Ubuntu 24.04 y aclara que no deberían
ser necesarios si `install_drivers.sh` se ejecutó correctamente. Conservarlos
como solución condicional y anotar el error que motivó su uso si se dispone de él.

### Estructura para futuras incidencias

Para cada incidencia, escribir sólo lo necesario:

1. Error observado.
2. Herramienta y versión afectadas.
3. Solución aplicada.
4. Resultado obtenido.

No presentar una solución específica como requisito de todas las instalaciones.

## 10. Cómo mantener esta guía consultable

- Este `Readme.md` es la guía principal. Mantener aquí las correcciones del
  procedimiento, sin crear versiones paralelas que puedan quedar desactualizadas.
- Registrar versiones y utilizar variables y nombres simbólicos, sin publicar
  la estructura de carpetas personal ni los destinos locales de los enlaces.
- Mostrar el contenido de los archivos que se editan a mano y mantener separados
  los comandos que se ejecutan. No reproducir los scripts del SDK o del proyecto.
- Separar resultados confirmados por David, instrucciones de TI y propuestas no ejecutadas.
- Completar los datos documentales pendientes sin volver a cuestionar el resultado
  ya confirmado del ejemplo.
- Consultar el archivo actualizado al retomar el trabajo; no depender sólo del
  recuerdo del chat ni asumir acceso a esta carpeta desde otro equipo.

## 11. Automatizar con `just`

El `justfile` utiliza `scripts/sitara.py` para preparar configuraciones y llamar
a las herramientas originales de TI, sin modificarlas ni importar sus módulos.
No instala dependencias, no compila el proyecto o el SBL y no modifica permisos.
La instalación e importación del ejemplo en CCS siguen siendo pasos separados.

### 11.1. Inicio rápido

Requiere `just` y Python 3.11 o posterior, además de las dependencias del perfil.
Se comprobaron `just 1.45.0`, Python 3.14.4 y las interfaces de las herramientas
del MCU+ SDK AM243x **12.01.00.33**. El adaptador no certifica versiones distintas
por el hecho de que sus archivos tengan nombres parecidos.

Desde esta carpeta, sustituir los marcadores antes de ejecutar:

```bash
just modes

export SDK_INSTALL_PATH="<DIRECTORIO_RAIZ_DEL_MCU_PLUS_SDK>"
export APP_IMAGE="<IMAGEN_GPIO_MULTIBLINK_RELEASE.mcelf.hs_fs>"

just config ospi
just check
just plan
```

`export` tiene el mismo significado explicado en la sección 3. Si no se indica
`SDK_INSTALL_PATH`, se acepta la instalación habitual sólo cuando existe un
único SDK AM243x candidato. No se selecciona automáticamente el más reciente.
**APP_IMAGE siempre se indica:** no se busca ni sustituye por un ejemplo IPC
u otra imagen encontrada en la computadora.

`just config` guarda las rutas en `.sitara.local.json`, excluido de Git. También
se puede editar ese archivo tomando `sitara.local.example.json` como referencia.
Si se ejecuta por primera vez sin indicar la aplicación, crea una plantilla local
y termina con un mensaje para completarla antes de continuar.

Los valores exportados prevalecen sobre el JSON **al ejecutar `just config`**.
En el JSON se admiten rutas absolutas, relativas a esta carpeta o con `~`,
pero no se expanden expresiones `$VARIABLE` dentro de sus cadenas.
Después, `check`, `plan`, `flash` y `boot` utilizan la preparación guardada;
cambiar `APP_IMAGE` en otra terminal no redirige una grabación ya preparada.
`UART_PORT` sí puede indicarse al ejecutar, porque selecciona el transporte,
no una imagen diferente.

### 11.2. Comandos y perfiles

| Comando | Efecto |
| --- | --- |
| `just` | Mostrar ayuda y el perfil seleccionado. |
| `just modes` | Describir los perfiles disponibles. |
| `just config ospi` | Preparar SBL OSPI y aplicación para grabación por UART. Es el perfil predeterminado de `just config`; `qspi` es un alias. |
| `just config uart` | Preparar una carga temporal en RAM con SBL UART y protocolo MCELF. |
| `just config null` | Preparar la grabación de SBL NULL para inicializar antes de usar el depurador. |
| `just config dfu` | Preparar SBL OSPI y aplicación para grabación por USB DFU. |
| `just config ospi-multipartition` | Preparar las particiones declaradas explícitamente en `PARTITION_IMAGES`. |
| `just check` | Validar el perfil, los enlaces, hashes de archivos y dependencias, sin abrir dispositivos. |
| `just plan` | Mostrar la herramienta, configuración y modo físico que requiere la operación, sin ejecutarla. |
| `just ports` | Enumerar metadatos de puertos serie, sin abrirlos ni comprobar respuesta. |
| `just flash` | **Escribir flash** según el perfil preparado, con detección de UART cuando corresponda. |
| `just flash /dev/ttyACM1` | Escribir flash por el puerto indicado, comprobando antes su disponibilidad para arrancar. |
| `just boot` | **Cargar y ejecutar en RAM**, sólo para el perfil `uart`. También acepta un puerto explícito. |
| `just test` | Ejecutar pruebas con un SDK sintético y puertos simulados. No utiliza la placa. |

El perfil `null` **reemplaza el bootloader anterior**; no graba ni ejecuta por
sí solo GPIO multiblink. La aplicación se carga después con el depurador.
El perfil `uart` no utiliza `just flash`: así se evita presentar una carga en
RAM como una escritura persistente. Este adaptador no automatiza CCS/JTAG ni
ofrece modos SD/eMMC de otras placas como si fueran de esta LaunchPad.

Seleccionar un perfil sólo prepara archivos. **Los interruptores físicos y el
encendido se realizan manualmente**, siguiendo la guía LP-AM243. Para los perfiles
que graban mediante UART, seleccionar UART BOOT y reiniciar antes de `just flash`.
Después de grabar, apagar y seleccionar arranque desde QSPI/OSPI. Para `uart`,
usar UART BOOT y `just boot`. Para `dfu`, seleccionar DFU BOOT antes de `just flash`.

### 11.3. Imágenes, enlaces y validación

Cada `just config` crea una preparación nueva dentro de `.sitara/`, con enlaces
simbólicos a los binarios, un `.cfg` y un manifest. No sobrescribe los archivos
de preparaciones anteriores, la plantilla del SDK ni los enlaces del procedimiento
manual. `.sitara/` queda fuera de Git: sus enlaces absolutos, rutas y registros
pertenecen sólo a esta computadora.

Para `ospi` y `dfu`, el `.cfg` generado utiliza estos nombres locales:

```text
--flash-writer=flash-writer.tiimage
--operation=flash-phy-tuning-data
--file=bootloader.tiimage --operation=flash --flash-offset=0x0
--file=application.mcelf.hs_fs --operation=flash --flash-offset=0x80000
```

La XIP es opcional y **no se toma de la plantilla IPC**. Si el mismo proyecto
necesita una imagen adicional, indicar `APP_XIP` y volver a preparar el perfil:

```bash
export APP_XIP="<IMAGEN_XIP_DEL_MISMO_PROYECTO.mcelf_xip>"
just config ospi
```

Así se añade al `.cfg`:

```text
--file=application.mcelf_xip --operation=flash-mcelf-xip
```

Para dejar de usarla, establecer `APP_XIP` en cadena vacía antes de repetir
`just config`. No se admite XIP en `uart` ni en multipartición en este adaptador.

Para UART directo, el contenido generado es:

```text
--soc=am64x_am243x
--bootloader=sbl-uart.tiimage
--file=application.mcelf.hs_fs
```

Se usa `--cfg`, no una conversión a `.appimage`. El SDK instalado implementa la
transferencia MCELF por segmentos para `am64x_am243x`.

Después de recompilar una imagen o cambiar un archivo enlazado, volver a ejecutar
`just config <modo>`. `check`, `flash` y `boot` rechazan cambios respecto a los hashes
guardados; no actualizan silenciosamente una preparación. No compilar ni cambiar
los archivos mientras se está grabando.

Los hashes comprueban que se utilizan los archivos preparados. **No comprueban
la firma criptográfica, la correspondencia del núcleo, la capacidad de la flash,
los segmentos XIP ni la compatibilidad real del firmware con el hardware.**
Las imágenes deben corresponder al proyecto, la placa y el SDK usados.

### 11.4. Multipartición explícita

Editar `PARTITION_IMAGES` en `.sitara.local.json`, conservando el resto de sus
campos. Por ejemplo, para dos imágenes distintas:

```json
"PARTITION_IMAGES": [
  {"image": "<IMAGEN_PRIMER_NUCLEO.mcelf.hs_fs>", "offset": "0x80000"},
  {"image": "<IMAGEN_SEGUNDO_NUCLEO.mcelf.hs_fs>", "offset": "0x100000"}
]
```

Este fragmento es una propiedad dentro del objeto JSON, no un archivo completo.
También puede proporcionarse como JSON mediante la variable `PARTITION_IMAGES`.
Los offsets admitidos son los de la plantilla TI consultada: `0x80000`,
`0x100000`, `0x180000`, `0x200000` y `0x280000`, con un máximo de `0x80000`
bytes por imagen. La correspondencia núcleo/partición debe coincidir con el SBL.
El adaptador rechaza offsets repetidos, ubicaciones fuera de esas ranuras,
imágenes demasiado grandes y la repetición del mismo archivo en varias ranuras.
No duplica `APP_IMAGE` para rellenar las particiones que falten.

### 11.5. Detección UART y selección DFU

`just ports` sólo enumera información USB. La detección automática de `flash`
y `boot` considera candidatos TI XDS110 y busca, a 115200 baudios y durante un
tiempo limitado por puerto, solicitudes XMODEM CRC repetidas de la ROM (`C`).
No transmite comandos de sondeo. El tráfico normal de una aplicación no cuenta
como preparación para grabar y esa señal no es una autenticación del dispositivo.

- Un único candidato listo: se utiliza ese puerto.
- Ninguno listo: se detiene y muestra qué revisar.
- Varios listos: hay que indicar el puerto explícitamente.
- Un candidato ocupado o inaccesible: no se elige otro silenciosamente.
- Un puerto explícito: se comprueba sólo ese dispositivo serie enumerado;
  también se acepta su enlace estable de `/dev/serial/by-id/` cuando corresponda.

La comprobación abre el puerto en modo exclusivo durante el sondeo y solicita
DTR/RTS desactivados antes de abrir. **Algunos drivers aún pueden producir cambios
de esas líneas al abrirlo.** Cerrar el monitor serie u otra aplicación que use
el puerto. La exclusividad del sondeo no reserva el puerto frente a otros programas
durante toda la ejecución de la herramienta TI.

DFU no enumera ni sondea ACM. Requiere `dfu-util` y un único dispositivo físico
DFU enumerado, de TI. Varios ajustes alternativos del mismo dispositivo no se
confunden con varias placas. Mantener conectado sólo ese dispositivo DFU durante
la operación, ya que la herramienta original de TI no fija un número de serie.

### 11.6. Dependencias, errores y estado de validación

Las recetas usan `python3` del `PATH` de la terminal. Para UART se necesitan
`pyserial`, `xmodem` y `tqdm`; la grabación UART necesita además `pyelftools`.
DFU requiere `dfu-util`. `just check` informa lo que falta, sin instalarlo,
usar `sudo` ni modificar grupos o permisos. Los SBL faltantes tampoco se compilan
automáticamente: deben generarse con las herramientas y el objetivo correctos
del SDK antes de repetir la preparación.

La herramienta TI se ejecuta una sola vez por comando. Su salida se muestra
en la terminal: **no se crean logs, recibos ni archivos históricos de intentos**.
Un código de salida cero no basta: debe existir la señal final y no haberse reportado
errores. Esto indica finalización de la herramienta, **no verificación física
del arranque**.

Tras un fallo o interrupción se puede **repetir directamente el mismo comando**,
sin `just config`, `--force`, mover archivos o desbloquear recibos. Los logs y
recibos antiguos se ignoran; no se borran ni modifican. No hay reintentos en
bucle ni cambios automáticos de puerto. Se mantiene la exclusión de operaciones
simultáneas y la comprobación de la imagen y del puerto. `Ctrl+C` solicita detener el grupo de
procesos de la herramienta; la flash puede quedar parcialmente escrita.

**Validación del adaptador:** pruebas sintéticas y recetas de `just` comprobadas
sin abrir puertos reales ni ejecutar las herramientas TI sobre la placa.
La integración física de estos perfiles está pendiente. Esto no cambia el éxito
de GPIO multiblink confirmado por David con el procedimiento original.

## 12. Workspace Zephyr y aplicaciones locales

Este flujo es independiente de los perfiles genéricos de la sección 11. No usa
`APP_IMAGE`, `SDK`, `UART_PORT` ni la preparación antigua de `.sitara.local.json`.
Desde la raíz del repositorio:

```bash
just apps
just workspace
```

El manifiesto propio es **`apps/west.yml`**: fija Zephyr al commit
`5a56224939aac71065aacd5dd69942a8e67565c6`, declara `cmsis`, `cmsis_6` y
`hal_ti`, y fija las dependencias TI a sus SHAs locales. `.west/config` usa
`manifest.path=apps`, `manifest.file=west.yml` y `zephyr.base=zephyr`.
Se declaran las entradas explícitamente, sin `import`, para conservar las
referencias `manifest-rev` existentes en los clones. Los comandos de Zephyr se
registran con `west-commands: scripts/west-commands.yml`.

Los módulos ya instalados se reutilizan mediante **copias locales independientes**
en `modules/hal/`, incluidos sus directorios Git, no mediante enlaces al workspace
anterior. `.zephyr.local.json`, ignorado por Git,
conserva el Python del entorno virtual existente, Zephyr SDK `1.0.1` y MCU+ SDK
`12.01.00.33`; su lista `modules` apunta a esas copias. Los campos son `python`,
`zephyr_sdk`, `ti_sdk` y `modules`, con rutas absolutas de cada computadora.
No hace falta activar el entorno virtual ni introducir `export`.
**No ejecutar `west update` para este recorrido:** no instala ni descarga nada.
Fijar revisiones tampoco descarta las modificaciones locales de diagnóstico
existentes en `zephyr/`; no se modifica vendor como parte de esta reorganización.

> **Pendiente de publicación:** el índice contiene gitlinks sin `.gitmodules`.
> No se han corregido ni preparado en staging: deben revisarse al preparar un
> futuro commit autorizado. El manifiesto no resuelve por sí solo ese pendiente;
> no asumir todavía que un clon limpio reproduce este workspace local.

### Compilar, empaquetar y comprobar por aplicación

Las dos aplicaciones permanentes son `apps/hello_world` y `apps/hola_zephyr`.
Cada una tiene su `justfile`; ambas usan `scripts/zephyr_local.py` y el target
`lp_am243/am2434/r5f0_0`. Hello World deja de construirse directamente desde
`zephyr/samples/hello_world`; el ejemplo original se conserva.

```bash
cd apps/hello_world
just build
just package
just check
```

- **`build`** ejecuta `west build`: sólo compila. No genera MCELF, no firma ni
  prepara la grabación, y no abre UART.
- **`package`** convierte el ELF a MCELF para core `4`, entrada `0`, firma HS-FS
  con la clave de desarrollo del MCU+ SDK, verifica y prepara el CFG local.
- **`check`** comprueba los artefactos preparados sin abrir puertos.
- **`flash`** es una operación separada y explícita de escritura.
- **`serial`** abre la consola; no compila ni graba. Requiere puerto explícito.

Desde la raíz se conservan estos alias de compatibilidad:

```bash
just build-zephyr    # build + package de apps/hello_world
just check-zephyr
just build-hola      # SBL aislado + build + package de apps/hola_zephyr
just check-hola
```

Los nuevos resultados quedan en **`apps/<app>/build/`**:

| Artefacto relativo a cada aplicación | Función |
| --- | --- |
| `build/zephyr/zephyr.elf` | ELF compilado |
| `build/boot-image/<app>.mcelf` | Imagen TI sin XIP |
| `build/boot-image/<app>.mcelf.hs_fs` | Imagen firmada para grabar |
| `build/boot-image/verification.json` | Selección de app y hashes locales |
| `build/flash.cfg` | CFG generado para grabar y verificar sólo la app |

El empaquetado también prepara el CFG de la aplicación. Usa rutas locales reales,
no `$SDK` ni `$IMAGE`: Uniflash no expande variables de shell en un `.cfg`.
JSON, CFG y resultados de build quedan fuera de publicación. El adaptador y
Uniflash usan `/usr/bin/python3`; CMake, MCELF y firma usan el Python configurado.

**Los cachés anteriores se conservan sin moverlos, borrarlos ni reutilizarlos:**
`build/zephyr_hello`, `build/hola_zephyr` y `zephyr/build/am243_hello`. También se
conserva el CFG antiguo `tools/sbls-am243x-lp/zephyr_hellw_sbl_ospi.cfg` como
artefacto histórico, no como entrada del nuevo flujo. Las instrucciones antiguas
que apunten a ellos no describen los builds actuales.

### Grabación y consola: siempre explícitas

Cuando se autorice escribir en hardware, con **UART BOOT**, placa reiniciada y
monitor serie cerrado, desde la aplicación elegida:

```bash
just flash /dev/ttyACM0
```

Sustituir el puerto por el real (`just ports` desde la raíz sólo enumera metadatos).
El puerto se pasa explícitamente al adaptador mediante `--port`; no se debe
suponer el dispositivo ni dejar otra consola abierta. La apertura puede afectar
DTR/RTS, como explica la sección 11.5. No hay reintento ni cambio automático de
puerto.

**`flash` sí escribe flash:** carga el flash writer y ejecuta `flash` y
`flashverify` de la app en **`0x80000`**. Requiere un SBL OSPI compatible ya
instalado: **no escribe `0x0`, ni datos PHY, ni XIP; no borra toda la flash**.
Después de finalizar correctamente, apagar, seleccionar QSPI/OSPI y encender.
Para observar la consola a **115200, 8N1**, desde la app:

```bash
just serial /dev/ttyACM0
```

`serial` también recibe un puerto explícito, traducido a `--port`. Cerrar el
monitor antes de volver a grabar. Los perfiles antiguos `just config`, `just flash`
y `just boot` de la raíz no seleccionan estos builds automáticamente.

### Alcance y antecedentes de la comprobación

**Reorganización validada localmente el 2026-11-13:** pasaron 80 pruebas sin
hardware. Ambas apps completaron `build` mediante west, `package` y `check` en
sus directorios nuevos. Se contrastaron los 20 SHAs del manifiesto con los
clones locales y se verificó que los cambios previos de Zephyr/TI y los builds
antiguos permanecen intactos. No se hicieron instalaciones, descargas, staging,
commits, push, apertura de puertos ni grabación. El arranque físico sigue pendiente.

`check` conserva las comprobaciones del origen del caché, placa y SDK,
segmentos cargables, primer segmento `PT_NOTE`, core `4`, entrada `0`, payload
MCELF después del certificado DER, tamaño de ranura y hashes de imágenes, CFG,
configuración y herramientas TI. Para `hola_zephyr` también controla los archivos
de diagnóstico. No detecta por sí solo cualquier cambio de cualquier módulo:
tras editar fuentes, repetir **`build`, `package` y `check`**. La clave TI es de
**desarrollo**; no acredita autenticación segura ni aprobación de producción.

Un build o empaquetado fallido bloquea una grabación incompleta. Un flasheo
fallido no bloquea el siguiente intento del mismo comando con puerto explícito;
no exige recompilar si los artefactos siguen válidos. No se guardan logs,
recibos ni archivos de intentos; los antiguos se ignoran, sin borrarlos.
Se mantienen hashes, guards y exclusión de operaciones simultáneas.

**Antecedentes, no validación nueva de esta reorganización:** se habían compilado,
convertido, firmado y comprobado las imágenes localmente, con pruebas sintéticas
sin hardware (`just test`). Hello World conserva el aviso DTS sobre `/memory@0`
frente a `reg = 0x3c`, aún sin investigar. David confirmó el 2026-11-12 que
completó `from guide.md` hasta el final; no se exige repetir el SBL por crear
otra app. Eso no confirma el arranque de `hola_zephyr` ni de los builds nuevos.

## 13. Aplicación propia: `hola soy zephyr` cada tres segundos

### SBL sin solapamiento de RAM

La comparación con VeriSOM mostró que el SBL del SDK local conservaba la pila
principal en `[0x7007f300, 0x70083300)` y otras pilas hasta `0x70084700`, dentro
de la RAM de aplicación desde `0x70080000`. El flujo de `hola_zephyr` ahora
construye una copia del SBL bajo `apps/hola_zephyr/build/sbl/`, con BSS/pilas
en `[0x70060000, 0x70080000)`, sin editar ni sustituir archivos del SDK.

Desde `apps/hola_zephyr`: `just build-sbl`, `just build`, `just package`,
`just check-boot` y `just check`. El empaquetado y la comprobación normales
también exigen el par SBL/ELF sin solapamiento, contando las pilas y BSS
`SHF_ALLOC/NOBITS`, y MPU habilitada en la configuración generada. Se mantienen
las trazas y la compatibilidad MPU de esta app; `hello_world` no se cambia.

**La comprobación es local, no identifica el SBL grabado.** `just flash` desde
la app sigue actualizando sólo `0x80000`. El nuevo
`build/sbl/ti-arm-clang/sbl_ospi.release.hs_fs.tiimage` no se instala como parte
de build/package/check. Reemplazar y verificar el SBL de `0x0` requiere una
operación expresamente autorizada; grabar sólo la app no corrige el SBL antiguo.
Detalles y archivos: [README de hola_zephyr](apps/hola_zephyr/README.md#corrección-de-ram-del-sbl-2026-11-13).

Validación local del cambio: 95 pruebas correctas; SBL aislado y app construidos
y comprobados sin solapamiento. BSS/pilas del nuevo SBL terminan en
`0x70074700`; el guard rechaza el ELF real anterior. Hello World conserva su
comprobación sin reconstrucción. Esta fase de implementación no grabó hardware.
En la instalación posterior autorizada del 2026-11-13 se escribieron y compararon
SBL y app en ACM1. Una captura posterior, con OSPI/QSPI confirmado por David,
mostró arranque desde NOR SPI FLASH, banner Zephyr, `[Z8] main` y el saludo.
Hubo dos secuencias de arranque; David confirmó que la duplicación fue causada
por él y que la aplicación funciona correctamente. No se considera evidencia
de resets espontáneos. La prueba no acredita estabilidad prolongada.
Las identidades de
las imágenes y el resultado UART están en el README de la app, sección
"Instalación autorizada y observación". No regrabar para repetir la captura.

[`apps/hola_zephyr/`](apps/hola_zephyr/README.md) usa el mismo flujo por aplicación:
`just build`, `just package` y `just check` desde su carpeta; `just build-hola`
desde la raíz sigue combinando los dos primeros pasos. Su build separado es
`apps/hola_zephyr/build/`. El empaquetado copia allí el flash writer compilado
del clon y prepara `flash.cfg`; no abre UART.

La app imprime una vez al entrar en `main()` y luego solicita un sueño de tres
segundos entre mensajes. La prueba host usa sueño simulado: no mide temporización
real ni demuestra arranque en la placa.

**Antecedente anterior al SBL corregido:** una captura llegaba a Z4 sin Z4A.
El mapa sitúa a continuación el init de pinctrl TI K3, cuyo
`pinctrl_ti_k3_init()` llama a `DEVICE_MMIO_MAP`. Se añadieron Z4PA-Z4PD dentro
del init para localizar la entrada y el retorno del mapeo. La imagen instrumentada
se compiló y pasó `just check-hola`. Esas hipótesis no establecieron una causa
del init. La prueba posterior al SBL corregido sí superó pinctrl, UART,
POST_KERNEL y APPLICATION y llegó a main. Las 81 pruebas correspondían a esa
etapa histórica; la validación local del SBL elevó la suite a 95 pruebas.

`CONFIG_HOLA_EARLY_UART_TRACE=y` activa la instrumentación directa de UART0.
El inventario de trazas, flags, overlay, adaptación ARMv7-R y hallazgos del ELF
se conserva en el [README de la app](apps/hola_zephyr/README.md#prueba-con-mpu-y-diagnóstico).
**La preparación inicial sólo compiló y comprobó la instrumentación. La captura
posterior al SBL corregido sí observó el arranque y main en la placa, con los
límites indicados arriba. No se hicieron commits ni push.**

## Referencias

- [TI LP-AM243](https://www.ti.com/tool/LP-AM243).
- [TI MCU+ SDK para AM243x](https://software-dl.ti.com/mcu-plus-sdk/esd/AM243X/latest/exports/docs/api_guide_am243x/index.html).
- [Instalación de CCS 21.0.1, incluido el paso posterior en Linux](https://software-dl.ti.com/ccs/esd/documents/users_guide_ccs_21.0.1/ccs_installation.html).
- [Primeros pasos de CCS 21.0.1](https://software-dl.ti.com/ccs/esd/documents/users_guide_ccs_21.0.1/index_getting-started.html).
- [TI: herramientas de grabación](https://software-dl.ti.com/mcu-plus-sdk/esd/AM243X/latest/exports/docs/api_guide_am243x/TOOLS_FLASH.html).

Las referencias `latest` son móviles; registrar también la versión del SDK que
se utilizó para que el procedimiento conserve su contexto.
