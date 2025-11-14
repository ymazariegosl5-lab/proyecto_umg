# config.py
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

class Config:
    """Configuración de la aplicación Flask"""
    
    # Configuración de la Aplicación
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Configuración de la Base de Datos MySQL
    # Ajusta estos valores según tu configuración local
    DB_HOST = os.environ.get('DB_HOST') 
    DB_USER = os.environ.get('DB_USER') 
    DB_PASSWORD = os.environ.get('DB_PASSWORD') 
    DB_NAME = os.environ.get('DB_NAME')
    
    # Configuraciones adicionales
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'  # Cambiar a True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE') or 'Lax'
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('PERMANENT_SESSION_LIFETIME') or 3600)  # 1 hora