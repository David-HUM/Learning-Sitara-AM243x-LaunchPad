set positional-arguments
set shell := ["bash", "-euo", "pipefail", "-c"]

# Ayuda y perfil seleccionado; no abre dispositivos.
default:
    @python3 scripts/sitara.py info

# Perfiles admitidos para la LP-AM243.
modes:
    @python3 scripts/sitara.py modes

# Prepara la configuración local y enlaces; no graba ni compila.
config mode="ospi":
    @python3 scripts/sitara.py config "$1"

# Valida los archivos preparados sin abrir puertos.
check:
    @python3 scripts/sitara.py check

# Enumera metadatos serie; no abre los puertos.
ports:
    @python3 scripts/sitara.py ports

# Graba flash con el perfil seleccionado. El puerto es opcional.
flash port="":
    @python3 scripts/sitara.py flash --port "$1"

# Carga temporal en RAM para el perfil uart; no graba flash.
boot port="":
    @python3 scripts/sitara.py boot --port "$1"

# Muestra el plan sin abrir dispositivos ni ejecutar herramientas TI.
plan:
    @python3 scripts/sitara.py plan

# Pruebas sintéticas: no utiliza dispositivos ni el SDK instalado.
test:
    @python3 -m unittest discover -s tests -v

# Copia local: compila Hello World, genera MCELF y firma, sin acceder a la placa.
build-zephyr:
    @/usr/bin/python3 scripts/zephyr_local.py build

# Comprueba el build, las imágenes y el cfg fijo; no abre UART.
check-zephyr:
    @/usr/bin/python3 scripts/zephyr_local.py check

# Escribe sólo la aplicación en 0x80000 y verifica; conserva el SBL existente.
flash-zephyr port="":
    @/usr/bin/python3 scripts/zephyr_local.py flash --port "$1"
