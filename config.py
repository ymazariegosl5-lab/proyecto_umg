# config.py
import os

class Config:
    """Configuración de la aplicación Flask"""
    
    # Configuración de la Aplicación
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'Una_Clave_Muy_Segura_Para_Tu_Sesion_2024_SPL'

    # Configuración de la Base de Datos MySQL
    # Ajusta estos valores según tu configuración local
    DB_HOST = os.environ.get('DB_HOST') or '127.0.0.1'
    DB_USER = os.environ.get('DB_USER') or 'root'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or ''
    DB_NAME = os.environ.get('DB_NAME') or 'gestion_agua'
    
    # Configuraciones adicionales
    SESSION_COOKIE_SECURE = False  # Cambiar a True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hora