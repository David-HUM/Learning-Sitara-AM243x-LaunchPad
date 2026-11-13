# Hello World en LP-AM243

Copia mínima del ejemplo `zephyr/samples/hello_world`, conservando su licencia.
El kernel y los módulos son dependencias del workspace, no fuentes de esta app.

Desde esta carpeta:

```bash
just build
just package
just check
```

`build` ejecuta `west build` para `lp_am243/am2434/r5f0_0`. `package` convierte
el ELF a MCELF, firma con la herramienta TI configurada y prepara el CFG.
Las tres acciones trabajan sólo en el ordenador. Salidas bajo `build/`.

`just flash /dev/ttyACM0` es una acción separada que escribe y verifica sólo
la aplicación en `0x80000`; requiere un SBL compatible existente. El puerto
debe identificarse con `just ports` desde la raíz. `just serial /dev/ttyACM0`
abre explícitamente la consola a 115200, 8N1. No los ejecute simultáneamente.

Salida esperada al arrancar desde QSPI: banner Zephyr y
`Hello World! lp_am243/am2434/r5f0_0`, una sola vez. Una compilación, firma o
grabación correcta no demuestra el arranque. No se acredita validación física.
