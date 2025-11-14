@echo off
echo ====================================
echo Sistema de Gestion de Agua Potable
echo Aldea Pancho de Leon
echo ====================================
echo.

REM Verificar si existe el entorno virtual
if not exist "venv" (
    echo Creando entorno virtual...
    python -m venv venv
    echo.
)

REM Activar entorno virtual
echo Activando entorno virtual...
call venv\Scripts\activate
echo.

REM Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt
echo.

REM Iniciar aplicacion
echo Iniciando aplicacion...
echo La aplicacion estara disponible en: http://localhost:5000
echo.
echo Presione Ctrl+C para detener el servidor
echo.
python app.py

pause