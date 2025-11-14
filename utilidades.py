#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Utilidades para el Sistema de Gestión de Agua
Permite crear usuarios, generar hashes de contraseñas y otras tareas administrativas
"""

from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from config import Config

def get_db_connection():
    """Conectar a la base de datos"""
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Error al conectar a MySQL: {err}")
        return None

def crear_usuario():
    """Crear un nuevo usuario en el sistema"""
    print("\n" + "="*60)
    print("CREAR NUEVO USUARIO")
    print("="*60)
    
    # Solicitar datos
    nombre = input("Nombre: ").strip()
    apellido = input("Apellido: ").strip()
    email = input("Correo electrónico: ").strip()
    password = input("Contraseña: ").strip()
    
    print("\nRoles disponibles:")
    print("1. ADMIN - Acceso completo")
    print("2. LECTOR - Registro de lecturas y pagos")
    print("3. TESORERO - Gestión de pagos y reportes")
    print("4. PRESIDENTE - Acceso a reportes")
    
    rol_opcion = input("\nSeleccione rol (1-4): ").strip()
    roles = {'1': 'ADMIN', '2': 'LECTOR', '3': 'TESORERO', '4': 'PRESIDENTE'}
    rol = roles.get(rol_opcion, 'LECTOR')
    
    # Confirmar
    print(f"\n📋 Resumen:")
    print(f"Nombre: {nombre} {apellido}")
    print(f"Email: {email}")
    print(f"Rol: {rol}")
    
    confirmar = input("\n¿Crear usuario? (s/n): ").strip().lower()
    
    if confirmar != 's':
        print("❌ Operación cancelada")
        return
    
    # Generar hash de contraseña
    password_hash = generate_password_hash(password)
    
    # Insertar en base de datos
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuario (nombre, apellido, correo_electronico, contrasena_hash, rol)
            VALUES (%s, %s, %s, %s, %s)
        """, (nombre, apellido, email, password_hash, rol))
        conn.commit()
        print(f"\n✅ Usuario creado exitosamente con ID: {cursor.lastrowid}")
        print(f"📧 Email: {email}")
        print(f"🔑 Contraseña: {password}")
        print(f"👤 Rol: {rol}")
    except mysql.connector.Error as err:
        print(f"\n❌ Error al crear usuario: {err}")
    finally:
        cursor.close()
        conn.close()

def listar_usuarios():
    """Listar todos los usuarios del sistema"""
    print("\n" + "="*60)
    print("USUARIOS DEL SISTEMA")
    print("="*60)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_usuario, nombre, apellido, correo_electronico, rol, activo, fecha_creacion
            FROM usuario
            ORDER BY id_usuario
        """)
        usuarios = cursor.fetchall()
        
        if not usuarios:
            print("\nNo hay usuarios registrados")
            return
        
        print(f"\n{'ID':<5} {'Nombre':<25} {'Email':<30} {'Rol':<12} {'Estado':<10}")
        print("-" * 90)
        
        for user in usuarios:
            nombre_completo = f"{user['nombre']} {user['apellido']}"
            estado = "✅ Activo" if user['activo'] else "❌ Inactivo"
            print(f"{user['id_usuario']:<5} {nombre_completo:<25} {user['correo_electronico']:<30} {user['rol']:<12} {estado:<10}")
        
        print(f"\nTotal: {len(usuarios)} usuarios")
        
    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")
    finally:
        cursor.close()
        conn.close()

def cambiar_contraseña():
    """Cambiar contraseña de un usuario"""
    print("\n" + "="*60)
    print("CAMBIAR CONTRASEÑA")
    print("="*60)
    
    email = input("Correo electrónico del usuario: ").strip()
    nueva_password = input("Nueva contraseña: ").strip()
    
    confirmar = input(f"\n¿Cambiar contraseña para {email}? (s/n): ").strip().lower()
    if confirmar != 's':
        print("❌ Operación cancelada")
        return
    
    password_hash = generate_password_hash(nueva_password)
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE usuario 
            SET contrasena_hash = %s, ultima_actualizacion = CURRENT_TIMESTAMP
            WHERE correo_electronico = %s
        """, (password_hash, email))
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"\n✅ Contraseña actualizada para {email}")
        else:
            print(f"\n❌ Usuario no encontrado: {email}")
            
    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")
    finally:
        cursor.close()
        conn.close()

def generar_hash():
    """Generar hash de una contraseña"""
    print("\n" + "="*60)
    print("GENERAR HASH DE CONTRASEÑA")
    print("="*60)
    
    password = input("Ingrese contraseña: ").strip()
    password_hash = generate_password_hash(password)
    
    print(f"\n🔐 Hash generado:")
    print(password_hash)
    print(f"\nLongitud: {len(password_hash)} caracteres")

def verificar_conexion():
    """Verificar conexión a la base de datos"""
    print("\n" + "="*60)
    print("VERIFICAR CONEXIÓN A BASE DE DATOS")
    print("="*60)
    
    print(f"\n📊 Configuración:")
    print(f"Host: {Config.DB_HOST}")
    print(f"Usuario: {Config.DB_USER}")
    print(f"Base de datos: {Config.DB_NAME}")
    
    conn = get_db_connection()
    if not conn:
        print("\n❌ No se pudo conectar a la base de datos")
        return
    
    try:
        cursor = conn.cursor()
        
        # Verificar versión de MySQL
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        print(f"\n✅ Conexión exitosa!")
        print(f"MySQL versión: {version}")
        
        # Contar registros en tablas principales
        tablas = ['usuario', 'cliente', 'sector', 'lectura', 'pago']
        print(f"\n📈 Estadísticas:")
        for tabla in tablas:
            cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
            count = cursor.fetchone()[0]
            print(f"{tabla.capitalize()}: {count} registros")
            
    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")
    finally:
        cursor.close()
        conn.close()

def menu_principal():
    """Menú principal del script de utilidades"""
    while True:
        print("\n" + "="*60)
        print("SISTEMA DE GESTIÓN DE AGUA - UTILIDADES")
        print("="*60)
        print("\n1. Crear nuevo usuario")
        print("2. Listar usuarios")
        print("3. Cambiar contraseña")
        print("4. Generar hash de contraseña")
        print("5. Verificar conexión a base de datos")
        print("0. Salir")
        
        opcion = input("\nSeleccione una opción: ").strip()
        
        if opcion == '1':
            crear_usuario()
        elif opcion == '2':
            listar_usuarios()
        elif opcion == '3':
            cambiar_contraseña()
        elif opcion == '4':
            generar_hash()
        elif opcion == '5':
            verificar_conexion()
        elif opcion == '0':
            print("\n👋 ¡Hasta luego!")
            break
        else:
            print("\n❌ Opción no válida")
        
        input("\nPresione Enter para continuar...")

if __name__ == '__main__':
    try:
        menu_principal()
    except KeyboardInterrupt:
        print("\n\n👋 ¡Hasta luego!")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")