# Primer ejemplo en la TI AM243x LaunchPad

**Fuente:** notas del procedimiento utilizado y confirmación de David del 2026-11-11.
**Resultado confirmado por David:** el ejemplo **GPIO multiblink LED funcionó siguiendo esos pasos**.

Esta guía conserva ese resultado. No exige repetir pruebas ni revisar la
placa. Los pendientes son datos que conviene dejar escritos para poder consultar
y repetir el procedimiento, no dudas nuevas sobre si el ejemplo funcionó.

Las secciones 3 a 9 describen el procedimiento manual. Para preparar los
perfiles con comandos, usar la [automatización con `just`](#11-automatizar-con-just).
Son alternativas: no es necesario ejecutar ambos recorridos para una grabación.

Para Zephyr en LP-AM243 con MCU+ SDK 12.01, consultar también
[From guide: adaptación de la guía oficial](from%20guide.md), con las
dependencias corregidas y una ruta de construcción reducida para los SBL.

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

La herramienta TI se ejecuta una sola vez. Su salida y un recibo local quedan
en `operation.log` y `receipt.json`, dentro de la preparación. Un código de salida
cero no basta: debe existir la señal final de ejecución y no haberse reportado
errores. Esto indica finalización de la herramienta, **no verificación física
del arranque**.

Un fallo, interrupción o salida incompleta deja el resultado como incierto y
bloquea el reintento con esa preparación. Revisar el registro y el estado antes
de usar `just config` para preparar un nuevo intento deliberado. No hay reintentos
ni cambios automáticos a otro puerto. `Ctrl+C` solicita detener el grupo de
procesos de la herramienta; la flash puede quedar parcialmente escrita.

**Validación del adaptador:** pruebas sintéticas y recetas de `just` comprobadas
sin abrir puertos reales ni ejecutar las herramientas TI sobre la placa.
La integración física de estos perfiles está pendiente. Esto no cambia el éxito
de GPIO multiblink confirmado por David con el procedimiento original.

## 12. Hello World de la copia local de Zephyr, sin `export`

Este flujo es independiente de los perfiles genéricos de la sección 11. No usa
`APP_IMAGE`, `SDK`, `UART_PORT` ni la preparación antigua de `.sitara.local.json`.
Ejecutar desde la raíz de `Learning-Sitara-AM243x-LaunchPad`:

```bash
just build-zephyr
just check-zephyr
```

`build-zephyr` compila **`zephyr/samples/hello_world` de esta copia**, para
`lp_am243/am2434/r5f0_0`, convierte el ELF a MCELF con core `4` y lo firma para
HS-FS con la clave de desarrollo de aplicación del MCU+ SDK. No agrega el
marcador de diagnóstico ni modifica el ejemplo original, el kernel o el SDK.
Ni `build-zephyr` ni `check-zephyr` abren UART ni graban la placa.

### Archivos y herramientas utilizados

- Build fijo: `build/zephyr_hello/`. No se reutiliza ni borra el caché copiado
  de `zephyr/build/am243_hello`, porque conserva referencias al workspace anterior.
- ELF: `build/zephyr_hello/zephyr/zephyr.elf`.
- MCELF: `build/zephyr_hello/boot-image/hello_world.mcelf`.
- Imagen que se graba: `build/zephyr_hello/boot-image/hello_world.mcelf.hs_fs`.
- CFG fijo: `tools/sbls-am243x-lp/zephyr_hellw_sbl_ospi.cfg`.
- Verificación local: `build/zephyr_hello/boot-image/verification.json`.

Las rutas absolutas de este equipo están en **`.zephyr.local.json`**, ignorado
por Git: Python del entorno virtual existente, Zephyr SDK `1.0.1`, MCU+ SDK
`12.01.00.33` y los módulos externos ya instalados `cmsis`, `cmsis_6` y `ti`.
Los módulos se reutilizan desde el workspace anterior; **la aplicación, el
kernel y las definiciones de placa se compilan desde el árbol local**.
No se ejecuta `west update` ni se instala o descarga nada automáticamente.
En otra computadora hay que proporcionar esas cuatro entradas locales.

Las recetas nuevas usan `/usr/bin/python3` del Ubuntu verificado para ejecutar
el adaptador y Uniflash; CMake, el generador MCELF y el firmador usan el Python
configurado en el JSON. No hace falta activar el entorno virtual ni introducir
`export`. CMake recibe explícitamente el origen, SDK, módulos y configuración.

Después de una compilación y empaquetado correctos, se actualiza el CFG con
**rutas absolutas reales**, sin `$SDK` ni `$IMAGE`: Uniflash no expande variables
de shell al leer un archivo `.cfg`. Ese CFG es local, está ignorado por Git y
se conserva en el mismo sitio en cada ejecución. No se utiliza un bloque `EOF`.
Se mantienen fuera de publicación el JSON, el CFG, los binarios y los recibos.

### Flasheo explícito, separado de la compilación

Con la placa en **UART BOOT**, reiniciada y con el monitor serie cerrado:

```bash
just flash-zephyr /dev/ttyACM0
```

Adaptar el puerto al dispositivo real; puede consultarse con `just ports`.
Sin argumento se conserva la selección controlada de un único XDS110 listo
para UART ROM. La selección abre el puerto y puede afectar DTR/RTS, como se
explica en la sección 11.5. No hay reintento ni cambio automático de puerto.

**Este comando sí escribe flash.** Carga el flash writer del MCU+ SDK, graba
la aplicación en `0x80000` y hace `flashverify` del mismo archivo y offset.
Requiere un SBL OSPI compatible previamente instalado: **no escribe el SBL en
`0x0`, no borra toda la flash y no configura XIP**. Después de terminar sin
errores, apagar la placa, seleccionar QSPI/OSPI y arrancar observando UART a
115200, 8N1.

Los perfiles y recetas antiguos (`just config`, `just flash`, `just boot`)
siguen disponibles, pero **no seleccionan este build nuevo automáticamente**.
Para esta copia usar los comandos que terminan en `-zephyr`.

### Alcance de la comprobación

`check-zephyr` verifica el origen del caché, placa y SDK, los segmentos
cargables conservados, primer segmento `PT_NOTE`, core `4`, entrada `0`,
payload MCELF después del certificado DER, tamaño de ranura y hashes guardados.
Detecta cambios posteriores de imágenes, CFG, configuración local, `main.c`,
`prj.conf` y herramientas TI usadas. No sustituye la compilación para detectar
cambios de cualquier otra fuente o módulo: ejecutar `build-zephyr` tras editar.
La clave incluida por TI es sólo de desarrollo; estas comprobaciones no
certifican autenticación segura ni aprobación de producción.

Un build fallido deja la preparación incompleta y bloquea el flasheo. Un
intento de flasheo incierto deja `operation.log` y `receipt.json` en el build
y bloquea el reintento; recompilar no borra ese estado ni acredita que el
intento anterior haya terminado. Revisar el registro y la placa antes de actuar.

**Validación local:** compilación, conversión, firma y comprobación realizadas;
pruebas sintéticas del adaptador sin hardware mediante `just test`.
Se conserva el aviso del DTS de la placa sobre `/memory@0` frente a `reg = 0x3c`;
la compilación termina correctamente, pero no se ha investigado ese aviso.
**Arranque físico de esta imagen: pendiente.** Una compilación correcta no
resuelve por sí sola el silencio después de `switching to application`.

## Referencias

- [TI LP-AM243](https://www.ti.com/tool/LP-AM243).
- [TI MCU+ SDK para AM243x](https://software-dl.ti.com/mcu-plus-sdk/esd/AM243X/latest/exports/docs/api_guide_am243x/index.html).
- [Instalación de CCS 21.0.1, incluido el paso posterior en Linux](https://software-dl.ti.com/ccs/esd/documents/users_guide_ccs_21.0.1/ccs_installation.html).
- [Primeros pasos de CCS 21.0.1](https://software-dl.ti.com/ccs/esd/documents/users_guide_ccs_21.0.1/index_getting-started.html).
- [TI: herramientas de grabación](https://software-dl.ti.com/mcu-plus-sdk/esd/AM243X/latest/exports/docs/api_guide_am243x/TOOLS_FLASH.html).

Las referencias `latest` son móviles; registrar también la versión del SDK que
se utilizó para que el procedimiento conserve su contexto.
