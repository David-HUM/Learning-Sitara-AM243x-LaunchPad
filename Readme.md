** INICIO BASICO

La pagina de inicio de la placa se encuentra en: https://www.ti.com/tool/LP-AM243

la guia de incio basico para el SDK proporcionada por TI se encuentra en: https://software-dl.ti.com/mcu-plus-sdk/esd/AM243X/latest/exports/docs/api_guide_am243x/index.html

Los ejecutables aqui mencionados requieren permisos de ejecucion antes de abrirlos (chmod +x {FILE_NAME})

python3, openssl, dfu-util, mono-runtime son necesarios, todos disponibles en apt.

En la instalacion de CCS se debe seleccionar la placa AM2x high... .

Se necesita ejecutar un installation script para tener el driver funcionando, el instalador esta en <CCS_INSTALL_DIR>/ccs/install_scripts

Se debe lanzar sudo ./install_drivers.sh

Para la ejecucion de ccs 21.0.1 se necesita dar permisos de admin a la aplicacion, son los siguientes comandos

cd ~/ti/ccs2101/ccs/theia
sudo chown root chrome-sandbox
sudo chmod 4755 chrome-sandbox
 
Aqui se debe saltar a la siguiente pagina: https://software-dl.ti.com/ccs/esd/documents/users_guide_ccs_21.0.1/index_getting-started.html
esta contiene la info actualizada de ccstudio


Para el chequeo de las configuraciones, las herramientas detectadas estan en file>Preferences>CCStudio IDE Settings
Ver que TI clang este en compilers y Sysconfig en products.

Los templates descargan las herramientas de sysconfig y Clang.

sudo apt update && sudo apt install -y python3-pyelftools python3-construct python3-setuptools
es necesario para poder compilar losproyectos desde el CCS

click derecho build configuration release -Para henerar el mcelf.hs_fs
Modificar el default_sbl_ospi.cfg y darle la ubicacion del mcelf

Una carpeta de lo especificado en el .cfg no encuentra los archivos que requiere, para eso hay que ir a la carpeta y darle make desde el terminal.

El siguiente paso es ejecutar con el uniflash.py el archivo de configuracion, ademas de especificarle el puerto en el que esta conectada la placa.

python3 uart_uniflash.py -p /dev/ttyACM0 --cfg=sbl_prebuilt/am243x-lp/default_sbl_ospi.cfg
"Nota importante: El ejemplo que se modifique de default_sbl_xxxx.cfg define con que metodo booteara el codigo."
