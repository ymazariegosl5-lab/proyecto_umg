# 🚂 Guía de Despliegue en Railway

Esta guía te ayudará a desplegar el Sistema de Gestión de Agua Potable en Railway paso a paso.

## 📋 Requisitos Previos

- ✅ Cuenta en [Railway](https://railway.app) (gratis con GitHub)
- ✅ Repositorio Git (GitHub, GitLab, Bitbucket)
- ✅ Base de datos MySQL (Railway MySQL o externa)

## 🚀 Pasos para Desplegar

### 1. Preparar el Repositorio Git

Si aún no tienes un repositorio Git:

```bash
# Inicializar repositorio
git init

# Agregar todos los archivos
git add .

# Hacer commit inicial
git commit -m "Initial commit - Sistema de Gestión de Agua"

# Conectar con GitHub (reemplaza con tu URL)
git remote add origin https://github.com/tu-usuario/tu-repositorio.git

# Subir cambios
git push -u origin main
```

### 2. Crear Proyecto en Railway

1. Ve a [railway.app](https://railway.app)
2. Inicia sesión con tu cuenta de GitHub
3. Haz clic en **"New Project"**
4. Selecciona **"Deploy from GitHub repo"**
5. Autoriza Railway a acceder a tus repositorios
6. Selecciona el repositorio del proyecto
7. Railway comenzará a detectar automáticamente el tipo de proyecto

### 3. Configurar Base de Datos MySQL

#### Opción A: MySQL en Railway (Recomendado)

1. En tu proyecto de Railway, haz clic en **"+ New"**
2. Selecciona **"Database"** → **"Add MySQL"**
3. Railway creará automáticamente una base de datos MySQL
4. Se crearán automáticamente estas variables:
   - `MYSQLHOST`
   - `MYSQLUSER`
   - `MYSQLPASSWORD`
   - `MYSQLDATABASE`
   - `MYSQLPORT`

#### Opción B: Base de Datos Externa

Si prefieres usar una base de datos externa (PlanetScale, AWS RDS, etc.), necesitarás configurar manualmente las variables de entorno.

### 4. Configurar Variables de Entorno

En Railway, ve a tu servicio → **"Variables"** y agrega:

#### Si usas MySQL de Railway:
```env
SECRET_KEY=tu_clave_secreta_muy_segura_genera_una_aleatoria
DB_HOST=${{MySQL.MYSQLHOST}}
DB_USER=${{MySQL.MYSQLUSER}}
DB_PASSWORD=${{MySQL.MYSQLPASSWORD}}
DB_NAME=${{MySQL.MYSQLDATABASE}}
FLASK_DEBUG=False
```

#### Si usas Base de Datos Externa:
```env
SECRET_KEY=tu_clave_secreta_muy_segura_genera_una_aleatoria
DB_HOST=tu-host-mysql.com
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=gestion_agua
FLASK_DEBUG=False
```

**Generar SECRET_KEY seguro:**
```python
import secrets
print(secrets.token_hex(32))
```

### 5. Inicializar la Base de Datos

Necesitas ejecutar los scripts SQL para crear las tablas:

1. **Conectar a la base de datos MySQL de Railway:**
   - En Railway, ve a tu base de datos MySQL
   - Haz clic en **"Query"** o usa un cliente MySQL externo
   - Usa las credenciales de las variables de entorno

2. **Ejecutar los scripts SQL:**
   - Ejecuta primero `database.sql` (si existe)
   - Luego ejecuta `database_permisos.sql`
   - O ejecuta ambos manualmente copiando el contenido

**Alternativa: Usar Railway CLI**

```bash
# Instalar Railway CLI
npm i -g @railway/cli

# Iniciar sesión
railway login

# Conectar al proyecto
railway link

# Ejecutar script SQL (si tienes acceso)
railway run mysql < database.sql
```

### 6. Verificar el Despliegue

1. Railway proporcionará una URL pública automáticamente
2. La URL será algo como: `tu-proyecto.up.railway.app`
3. Accede a la URL y verifica que la aplicación cargue
4. Inicia sesión con las credenciales por defecto:
   - Email: `admin@gestionagua.com`
   - Contraseña: `admin123` (o la que tengas configurada)

### 7. Configurar Dominio Personalizado (Opcional)

1. En Railway, ve a tu servicio → **"Settings"**
2. En **"Domains"**, haz clic en **"Generate Domain"** o agrega tu dominio personalizado
3. Sigue las instrucciones para configurar DNS

## 📁 Archivos de Configuración

El proyecto incluye estos archivos necesarios para Railway:

- **`Procfile`**: Define cómo iniciar la aplicación (`gunicorn app:app`)
- **`runtime.txt`**: Especifica la versión de Python (3.11.9)
- **`railway.json`**: Configuración adicional de Railway
- **`requirements.txt`**: Incluye todas las dependencias, incluyendo `gunicorn`

## 🔧 Solución de Problemas

### Error: "No module named 'gunicorn'"

**Solución:**
- Verifica que `gunicorn==21.2.0` esté en `requirements.txt`
- Railway debería instalarlo automáticamente durante el build
- Si persiste, revisa los logs de build en Railway

### Error de Conexión a la Base de Datos

**Solución:**
1. Verifica que las variables de entorno estén configuradas correctamente
2. Si usas MySQL de Railway, asegúrate de usar la sintaxis `${{MySQL.VARIABLE}}`
3. Verifica que la base de datos esté activa y funcionando
4. Revisa los logs de la aplicación en Railway para ver el error específico

### La Aplicación No Inicia

**Solución:**
1. Revisa los logs en Railway Dashboard → tu servicio → "Deployments" → "View Logs"
2. Verifica que el `Procfile` esté correcto: `web: gunicorn app:app`
3. Asegúrate de que `app.py` sea el archivo principal
4. Verifica que todas las dependencias estén en `requirements.txt`

### Base de Datos No Existe o Tablas Faltantes

**Solución:**
1. Conéctate a la base de datos MySQL usando las credenciales de Railway
2. Ejecuta manualmente los scripts SQL:
   ```sql
   -- Ejecutar database.sql primero
   -- Luego ejecutar database_permisos.sql
   ```
3. Verifica que las tablas se hayan creado:
   ```sql
   USE gestion_agua;
   SHOW TABLES;
   ```

### Error 502 Bad Gateway

**Solución:**
1. Verifica que la aplicación esté escuchando en el puerto correcto
2. Railway proporciona automáticamente el puerto en la variable `PORT`
3. El código ya está configurado para usar `os.environ.get('PORT', 5000)`
4. Revisa los logs para ver si hay errores de inicio

### Variables de Entorno No Se Aplican

**Solución:**
1. Asegúrate de hacer clic en **"Save"** después de agregar variables
2. Railway puede requerir un nuevo despliegue para aplicar cambios
3. Verifica que no haya espacios extra en los nombres de variables
4. Si usas referencias a otros servicios (`${{MySQL.VARIABLE}}`), verifica la sintaxis

## 🔒 Seguridad en Producción

1. **Cambiar SECRET_KEY**: Usa una clave aleatoria y segura
2. **Cambiar Contraseñas por Defecto**: Actualiza las contraseñas de los usuarios admin
3. **FLASK_DEBUG=False**: Asegúrate de que esté desactivado en producción
4. **HTTPS**: Railway proporciona HTTPS automáticamente
5. **Variables Sensibles**: Nunca subas el archivo `.env` al repositorio (ya está en `.gitignore`)

## 📊 Monitoreo y Logs

- **Ver Logs**: Railway Dashboard → tu servicio → "Deployments" → "View Logs"
- **Métricas**: Railway proporciona métricas básicas de CPU y memoria
- **Alertas**: Configura alertas en Railway para errores críticos

## 🔄 Actualizar la Aplicación

Para actualizar la aplicación después de hacer cambios:

```bash
# Hacer cambios en tu código local
git add .
git commit -m "Descripción de los cambios"
git push origin main

# Railway detectará automáticamente los cambios y desplegará
```

Railway desplegará automáticamente cada vez que hagas push a la rama principal.

## 💰 Costos

- **Railway Free Tier**: Incluye $5 de crédito gratis al mes
- **MySQL en Railway**: Cuenta como servicio adicional
- **Uso**: Monitorea tu uso en Railway Dashboard → "Usage"

## 📞 Soporte

- **Documentación de Railway**: [docs.railway.app](https://docs.railway.app)
- **Comunidad**: [Discord de Railway](https://discord.gg/railway)
- **Logs de Errores**: Revisa los logs en Railway Dashboard

---

¡Listo! Tu aplicación debería estar funcionando en Railway. 🎉

