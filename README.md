# Sistema de Gestión de Agua Potable - Aldea Pancho de León

## 📋 Descripción

Sistema web desarrollado en Flask para la gestión integral del servicio de agua potable de la Aldea Pancho de León, Santa Rosa, Guatemala. Permite el registro de clientes, lecturas de consumo, facturación automática, gestión de pagos y generación de reportes.

## ✨ Características Principales

- **Gestión de Clientes**: Registro y administración de abonados por sectores
- **Registro de Lecturas**: Captura de lecturas mensuales del consumo de agua
- **Facturación Automática**: Cálculo automático basado en tarifas configurables
- **Gestión de Pagos**: Registro y seguimiento de pagos de facturas
- **Reportes**: Generación de reportes de ingresos, morosidad y consumo
- **Sectores**: Organización de clientes por zonas geográficas
- **Roles y Permisos**: Sistema de autenticación con diferentes niveles de acceso

## 🛠️ Tecnologías Utilizadas

- **Backend**: Python 3.8+ con Flask
- **Base de Datos**: MySQL 8.0+
- **Frontend**: HTML5, CSS3, Bootstrap 5.3
- **Dependencias**: Flask, mysql-connector-python, Werkzeug, ReportLab

## 📦 Requisitos del Sistema

- Python 3.8 o superior
- MySQL 8.0 o superior
- pip (gestor de paquetes de Python)
- Navegador web moderno (Chrome, Firefox, Edge)

## 🚀 Instalación

### 1. Clonar o descargar el proyecto
```bash
cd sistema_agua
```

### 2. Crear entorno virtual (recomendado)
```bash
# En Windows
python -m venv venv
venv\Scripts\activate

# En Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar la base de datos

1. Iniciar MySQL y acceder al cliente:
```bash
mysql -u root -p
```

2. Ejecutar el script de base de datos:
```sql
source database.sql
```

O importar desde la consola:
```bash
mysql -u root -p < database.sql
```

3. Verificar que la base de datos se haya creado:
```sql
SHOW DATABASES;
USE gestion_agua;
SHOW TABLES;
```

### 5. Configurar las credenciales

Editar el archivo `config.py` con las credenciales de tu base de datos:
```python
DB_HOST = '127.0.0.1'
DB_USER = 'root'
DB_PASSWORD = 'tu_contraseña'  # Cambiar por tu contraseña de MySQL
DB_NAME = 'gestion_agua'
```

También puedes usar variables de entorno:
```bash
# Windows
set DB_PASSWORD=tu_contraseña
set SECRET_KEY=una_clave_secreta_segura

# Linux/Mac
export DB_PASSWORD=tu_contraseña
export SECRET_KEY=una_clave_secreta_segura
```

### 6. Ejecutar la aplicación
```bash
python app.py
```

La aplicación estará disponible en: `http://localhost:5000`

## 🔐 Credenciales por Defecto

**Usuario Administrador:**
- Email: `admin@gestionagua.com`
- Contraseña: `admin123`

**Usuario Lector:**
- Email: `lector@gestionagua.com`
- Contraseña: `admin123`

⚠️ **IMPORTANTE**: Cambiar estas contraseñas después del primer inicio de sesión.

## 📁 Estructura del Proyecto
```
sistema_agua/
│
├── app.py                  # Aplicación principal Flask
├── config.py               # Configuración de la aplicación
├── requirements.txt        # Dependencias del proyecto
├── database.sql           # Script de creación de base de datos
├── README.md              # Este archivo
│
├── static/                # Archivos estáticos
│   └── css/
│       └── style.css      # Estilos personalizados
│
└── templates/             # Plantillas HTML
    ├── base.html          # Plantilla base
    ├── index.html         # Página de login
    ├── dashboard.html     # Panel principal
    │
    ├── clientes/
    │   └── registro.html  # Registro de clientes
    │
    ├── procesos/
    │   ├── lectura.html   # Registro de lecturas
    │   └── pago.html      # Gestión de pagos
    │
    ├── reportes/
    │   ├── generador.html # Generador de reportes
    │   └── resultado.html # Resultados de reportes
    │
    └── sectores/
        ├── lista.html     # Lista de sectores
        └── detalle.html   # Detalle de sector
```

## 📖 Manual de Uso

### Para Administradores

1. **Registrar Nuevos Clientes**
   - Ir a "Registrar Cliente"
   - Completar el formulario con los datos del cliente
   - Asignar sector y número de contador único

2. **Gestionar Sectores**
   - Ver distribución de clientes por sector
   - Identificar sectores con mayor morosidad
   - Revisar clientes de cada sector

### Para Lectores

1. **Registrar Lecturas**
   - Seleccionar cliente
   - Ingresar lectura actual del contador
   - El sistema calcula automáticamente el consumo y genera la factura

2. **Gestionar Pagos**
   - Ver lista de facturas pendientes
   - Registrar pagos recibidos
   - Las facturas se marcan automáticamente como pagadas

### Para Todos los Usuarios

1. **Generar Reportes**
   - Seleccionar tipo de reporte (Ingresos, Morosos, Consumo)
   - Definir rango de fechas
   - Visualizar e imprimir resultados

## 🔧 Configuración de Tarifas

Las tarifas están definidas en la función `calcular_factura()` en `app.py`:
```python
TARIFA_BASE = 0.50       # Q0.50 por m³ (0-25 m³)
CARGO_FIJO = 15.00       # Q15.00 cargo fijo mensual
LIMITE_CONSUMO = 25      # 25 m³
TARIFA_EXCESO = 0.75     # Q0.75 por m³ (más de 25 m³)
```

También puedes modificarlas en la tabla `tarifa` de la base de datos.

## 🐛 Solución de Problemas

### Error de conexión a la base de datos

**Problema**: "Error al conectar a MySQL"

**Solución**:
1. Verificar que MySQL esté ejecutándose
2. Confirmar credenciales en `config.py`
3. Verificar que la base de datos existe:
```sql
   SHOW DATABASES;
```

### Error de importación de módulos

**Problema**: "ModuleNotFoundError: No module named 'flask'"

**Solución**:
```bash
pip install -r requirements.txt
```

### Puerto 5000 ya en uso

**Problema**: "Address already in use"

**Solución**: Cambiar el puerto en `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

### Contraseña incorrecta en primer login

**Problema**: No puedes iniciar sesión

**Solución**: Verificar que el hash de contraseña se generó correctamente. 
Si es necesario, generar nuevo hash:
```python
from werkzeug.security import generate_password_hash
print(generate_password_hash('admin123'))
```

Y actualizar en la base de datos:
```sql
UPDATE usuario SET contrasena_hash = 'nuevo_hash' WHERE correo_electronico = 'admin@gestionagua.com';
```

## 📊 Base de Datos

### Tablas Principales

- **usuario**: Usuarios del sistema con roles y permisos
- **cliente**: Abonados del servicio de agua
- **sector**: Sectores geográficos
- **lectura**: Registro de lecturas y facturas
- **pago**: Registro de pagos recibidos
- **tarifa**: Configuración de tarifas

### Vistas Disponibles

- `v_clientes_completo`: Clientes con información completa
- `v_resumen_facturas`: Resumen de facturas con estados
- `v_historial_pagos`: Historial completo de pagos

### Procedimientos Almacenados

- `sp_actualizar_facturas_vencidas()`: Marca facturas vencidas
- `sp_estadisticas_mes(mes, anio)`: Estadísticas mensuales

## 🔒 Seguridad

- Contraseñas hasheadas con Werkzeug (PBKDF2-SHA256)
- Sesiones seguras con cookies HttpOnly
- Decoradores de autenticación para rutas protegidas
- Validación de datos en formularios
- Protección contra inyección SQL con queries parametrizadas

## 🚀 Despliegue en Producción

### Recomendaciones

1. **Cambiar SECRET_KEY**: Usar una clave aleatoria y segura
2. **Desactivar DEBUG**: Establecer `debug=False` en `app.py`
3. **Usar HTTPS**: Configurar SSL/TLS
4. **Servidor WSGI**: Usar Gunicorn o uWSGI
5. **Reverse Proxy**: Configurar Nginx o Apache
6. **Backup Regular**: Programar respaldos de la base de datos

### Ejemplo con Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## 📝 Notas Adicionales

- El sistema calcula automáticamente el consumo restando lectura anterior de la actual
- Las facturas se marcan como "VENCIDAS" automáticamente después de 60 días
- Los reportes pueden imprimirse directamente desde el navegador
- El sistema soporta múltiples usuarios simultáneos

## 👤 Autor

**Ader**
- Sistema desarrollado para el Comité de Agua de Aldea Pancho de León
- Santa Rosa, Guatemala

## 📄 Licencia

Este proyecto es de uso interno para la comunidad de Aldea Pancho de León.

## 🆘 Soporte

Para reportar problemas o solicitar funcionalidades adicionales, contactar al administrador del sistema.

---

**Versión**: 1.0.0  
**Fecha**: Noviembre 2024
```

---

## 🎉 RESUMEN FINAL

Ya tienes **TODOS los 20 archivos** listos para copiar y pegar:

### ✅ **Archivos Python (5)**
1. app.py
2. config.py  
3. utilidades.py
4. requirements.txt
5. database.sql

### ✅ **Templates HTML (10)**
6. base.html
7. index.html
8. dashboard.html
9. clientes/registro.html
10. procesos/lectura.html
11. procesos/pago.html
12. reportes/generador.html
13. reportes/resultado.html
14. sectores/lista.html
15. sectores/detalle.html

### ✅ **Estilos y Scripts (3)**
16. static/css/style.css
17. iniciar.bat
18. iniciar.sh

### ✅ **Configuración y Docs (2)**
19. .gitignore
20. README.md

## 📝 ESTRUCTURA DE CARPETAS A CREAR
```
sistema_agua/
├── app.py
├── config.py
├── utilidades.py
├── requirements.txt
├── database.sql
├── iniciar.bat
├── iniciar.sh
├── .gitignore
├── README.md
├── static/
│   └── css/
│       └── style.css
└── templates/
    ├── base.html
    ├── index.html
    ├── dashboard.html
    ├── clientes/
    │   └── registro.html
    ├── procesos/
    │   ├── lectura.html
    │   └── pago.html
    ├── reportes/
    │   ├── generador.html
    │   └── resultado.html
    └── sectores/
        ├── lista.html
        └── detalle.html