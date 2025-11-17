# app.py - Sistema de Gestión de Agua Potable
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date
from config import Config

# Importaciones para generar PDFs
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)
app.config.from_object(Config)

# Procesador de contexto para inyectar datetime en templates
@app.context_processor
def inject_now():
    """Inyectar función datetime en todos los templates"""
    from datetime import datetime
    return {'now': datetime.now}

# Procesador de contexto para verificar permisos en templates
@app.context_processor
def inject_permisos():
    """Inyectar función para verificar permisos en templates"""
    def tiene_permiso_template(codigo_permiso):
        """Verifica si el usuario actual tiene un permiso específico"""
        if 'user_id' not in session:
            return False
        
        user_id = session.get('user_id')
        user_rol = session.get('rol')
        
        # Si es ADMIN, tiene todos los permisos
        if user_rol == 'ADMIN':
            return True
        
        # Verificar siempre en la BD para asegurar que los permisos estén actualizados
        # Esto es importante porque los permisos pueden cambiar mientras el usuario está logueado
        try:
            return tiene_permiso(user_id, codigo_permiso)
        except Exception as e:
            print(f"Error al verificar permiso en template: {e}")
            # Fallback: verificar en sesión si hay error de BD
            permisos_sesion = session.get('permisos', [])
            return codigo_permiso in permisos_sesion
    return {'tiene_permiso_template': tiene_permiso_template}

# --- Funciones de Conexión a la Base de Datos ---
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=app.config['DB_HOST'],
            port=app.config['DB_PORT'],        
            user=app.config['DB_USER'],         
            password=app.config['DB_PASSWORD'], 
            database=app.config['DB_NAME']
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error al conectar a MySQL: {err}")
        flash("Error de conexión a la base de datos.", "danger")
        return None

# --- Funciones de Gestión de Permisos ---
def tiene_permiso(id_usuario, codigo_permiso):
    """Verifica si un usuario tiene un permiso específico"""
    conn = get_db_connection()
    if conn is None:
        print(f"ERROR tiene_permiso: No se pudo conectar a la BD")
        return False
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Verificar si el usuario es ADMIN (tiene todos los permisos)
        cursor.execute("SELECT rol FROM usuario WHERE id_usuario = %s AND activo = TRUE", (id_usuario,))
        usuario = cursor.fetchone()
        
        if not usuario:
            print(f"DEBUG tiene_permiso: Usuario {id_usuario} no encontrado o inactivo")
            cursor.close()
            conn.close()
            return False
        
        if usuario and usuario['rol'] == 'ADMIN':
            print(f"DEBUG tiene_permiso: Usuario {id_usuario} es ADMIN, tiene permiso {codigo_permiso}")
            cursor.close()
            conn.close()
            return True
        
        # Verificar permiso específico
        cursor.execute("""
            SELECT COUNT(*) as tiene_permiso
            FROM usuario_permiso up
            JOIN permiso p ON up.id_permiso = p.id_permiso
            WHERE up.id_usuario = %s 
            AND p.codigo_permiso = %s
            AND p.activo = TRUE
        """, (id_usuario, codigo_permiso))
        
        resultado = cursor.fetchone()
        tiene = resultado['tiene_permiso'] > 0 if resultado else False
        
        print(f"DEBUG tiene_permiso: Usuario {id_usuario}, permiso {codigo_permiso}, resultado: {tiene}")
        
        cursor.close()
        conn.close()
        return tiene
    except Exception as e:
        print(f"ERROR al verificar permiso: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
        return False

def obtener_permisos_usuario(id_usuario):
    """Obtiene todos los permisos de un usuario"""
    conn = get_db_connection()
    if conn is None:
        print(f"ERROR obtener_permisos_usuario: No se pudo conectar a la BD")
        return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Si es ADMIN, retornar todos los permisos
        cursor.execute("SELECT rol FROM usuario WHERE id_usuario = %s", (id_usuario,))
        usuario = cursor.fetchone()
        
        if not usuario:
            print(f"DEBUG obtener_permisos_usuario: Usuario {id_usuario} no encontrado")
            cursor.close()
            conn.close()
            return []
        
        if usuario and usuario['rol'] == 'ADMIN':
            cursor.execute("SELECT codigo_permiso FROM permiso WHERE activo = TRUE")
            permisos = [row['codigo_permiso'] for row in cursor.fetchall()]
            print(f"DEBUG obtener_permisos_usuario: Usuario {id_usuario} es ADMIN, tiene {len(permisos)} permisos")
        else:
            cursor.execute("""
                SELECT p.codigo_permiso
                FROM usuario_permiso up
                JOIN permiso p ON up.id_permiso = p.id_permiso
                WHERE up.id_usuario = %s AND p.activo = TRUE
            """, (id_usuario,))
            permisos = [row['codigo_permiso'] for row in cursor.fetchall()]
            print(f"DEBUG obtener_permisos_usuario: Usuario {id_usuario} tiene {len(permisos)} permisos: {permisos}")
        
        cursor.close()
        conn.close()
        return permisos
    except Exception as e:
        print(f"ERROR al obtener permisos: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
        return []

# --- Decoradores de Seguridad (R2: Gestión de roles y permisos) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Necesitas iniciar sesión para acceder.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'rol' not in session or session['rol'] != 'ADMIN':
            flash("Acceso denegado. Se requiere rol de Administrador.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    """Decorador para verificar si el usuario tiene uno de los roles permitidos"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'rol' not in session or session['rol'] not in roles:
                flash("No tienes permisos para acceder a esta sección.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def permiso_required(codigo_permiso):
    """Decorador para verificar si el usuario tiene un permiso específico"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Necesitas iniciar sesión para acceder.", "warning")
                return redirect(url_for('login'))
            
            if not tiene_permiso(session['user_id'], codigo_permiso):
                flash(f"No tienes permiso para realizar esta acción. Se requiere: {codigo_permiso}", "danger")
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Funciones de Lógica de Negocio ---
def calcular_factura(consumo):
    """Calcula el monto total de la factura según el consumo y tarifas."""
    TARIFA_BASE = 2.00      # Q2 por m³ dentro del límite
    CARGO_FIJO = 0.00
    LIMITE_CONSUMO = 25     # m³
    TARIFA_EXCESO = 4.00    # Q4 por m³ después del límite

    # Si el consumo es negativo (lectura menor), generar crédito
    if consumo < 0:
        # El cargo fijo sigue aplicándose, pero se resta el valor del "consumo negativo"
        consumo_abs = abs(consumo)
        if consumo_abs <= LIMITE_CONSUMO:
            descuento = consumo_abs * TARIFA_BASE
        else:
            descuento = (LIMITE_CONSUMO * TARIFA_BASE) + ((consumo_abs - LIMITE_CONSUMO) * TARIFA_EXCESO)
        
        monto_total = CARGO_FIJO - descuento
        return round(monto_total, 2)
    
    # Si el consumo es 0, solo cobrar el cargo fijo
    if consumo == 0:
        return CARGO_FIJO
    
    # Consumo positivo normal
    monto_total = CARGO_FIJO

    if consumo <= LIMITE_CONSUMO:
        monto_total += consumo * TARIFA_BASE
    else:
        monto_total += (LIMITE_CONSUMO * TARIFA_BASE)
        exceso = consumo - LIMITE_CONSUMO
        monto_total += exceso * TARIFA_EXCESO

    return round(monto_total, 2)


# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/', methods=['GET', 'POST'])
def login():
    """Ruta para el inicio de sesión (Login)."""
    if request.method == 'POST':
        email = request.form['usuario']
        password = request.form['contrasena']

        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('login'))

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_usuario, nombre, apellido, rol, contrasena_hash FROM usuario WHERE correo_electronico = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['contrasena_hash'], password):
            session['logged_in'] = True
            session['user_id'] = user['id_usuario']
            session['rol'] = user['rol']
            session['nombre'] = f"{user['nombre']} {user['apellido']}"
            # Cargar permisos del usuario en la sesión
            session['permisos'] = obtener_permisos_usuario(user['id_usuario'])
            flash(f"Bienvenido, {user['nombre']} ({user['rol']})", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")
            return render_template('index.html')

    return render_template('index.html')


@app.route('/logout')
@login_required
def logout():
    """Cerrar Sesión."""
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('login'))


# --- RUTAS PRINCIPALES ---

@app.route('/dashboard')
@login_required
def dashboard():
    """Menú Principal de Opciones."""
    # Obtener estadísticas para el dashboard
    conn = get_db_connection()
    if conn is None: 
        return render_template('dashboard.html', stats={})
    
    cursor = conn.cursor(dictionary=True)
    
    # Estadísticas
    cursor.execute("SELECT COUNT(*) as total FROM cliente WHERE activo = TRUE")
    total_clientes = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM lectura WHERE estado_pago = 'PENDIENTE'")
    facturas_pendientes = cursor.fetchone()['total']
    
    cursor.execute("SELECT COALESCE(SUM(monto_total), 0) as total FROM lectura WHERE estado_pago = 'PENDIENTE'")
    monto_pendiente = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM sector")
    total_sectores = cursor.fetchone()['total']
    
    cursor.close()
    conn.close()
    
    stats = {
        'total_clientes': total_clientes,
        'facturas_pendientes': facturas_pendientes,
        'monto_pendiente': float(monto_pendiente),
        'total_sectores': total_sectores
    }
    
    return render_template('dashboard.html', stats=stats)


# --- RUTAS DE GESTIÓN DE CLIENTES ---

@app.route('/clientes/registro', methods=['GET', 'POST'])
@login_required
@admin_required # Solo el ADMIN puede registrar nuevos clientes (R1)
def registrar_cliente():
    """Registrar Nuevo Cliente (R1)."""
    conn = get_db_connection()
    if conn is None: return redirect(url_for('dashboard'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        id_sector = request.form['id_sector']
        telefono = request.form.get('telefono', '')
        no_contador = request.form['no_contador']

        try:
            cursor.execute("""
                INSERT INTO cliente (nombre, apellido, id_sector, telefono, no_contador)
                VALUES (%s, %s, %s, %s, %s)
            """, (nombre, apellido, id_sector, telefono, no_contador))
            conn.commit()
            flash("Cliente registrado exitosamente.", "success")
            return redirect(url_for('registrar_cliente'))
        except mysql.connector.Error as err:
            flash(f"Error al registrar cliente: {err}", "danger")
            conn.rollback()

    # Listar sectores para el formulario
    cursor.execute("SELECT id_sector, nombre_sector FROM sector")
    sectores = cursor.fetchall()
    
    # Listar clientes recientes para la tabla
    cursor.execute("""
        SELECT c.id_cliente, c.nombre, c.apellido, s.nombre_sector, c.no_contador, c.telefono
        FROM cliente c JOIN sector s ON c.id_sector = s.id_sector
        WHERE c.activo = TRUE
        ORDER BY c.id_cliente DESC LIMIT 10
    """)
    clientes_recientes = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('clientes/registro.html', sectores=sectores, clientes_recientes=clientes_recientes)


@app.route('/api/clientes/<int:id_cliente>', methods=['GET'])
@login_required
def obtener_cliente(id_cliente):
    """Obtener datos de un cliente para editar"""
    if not (session.get('rol') == 'ADMIN' or tiene_permiso(session.get('user_id'), 'clientes.editar')):
        return jsonify({'error': 'No tienes permiso para esta acción'}), 403
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.id_cliente, c.nombre, c.apellido, c.id_sector, c.telefono, c.no_contador, s.nombre_sector
        FROM cliente c
        JOIN sector s ON c.id_sector = s.id_sector
        WHERE c.id_cliente = %s AND c.activo = TRUE
    """, (id_cliente,))
    cliente = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not cliente:
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    return jsonify(cliente)


@app.route('/api/clientes/<int:id_cliente>', methods=['PUT'])
@login_required
def actualizar_cliente(id_cliente):
    """Actualizar datos de un cliente"""
    if not (session.get('rol') == 'ADMIN' or tiene_permiso(session.get('user_id'), 'clientes.editar')):
        return jsonify({'error': 'No tienes permiso para esta acción'}), 403
    
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE cliente 
            SET nombre = %s, apellido = %s, id_sector = %s, telefono = %s, no_contador = %s,
                ultima_actualizacion = CURRENT_TIMESTAMP
            WHERE id_cliente = %s AND activo = TRUE
        """, (data['nombre'], data['apellido'], data['id_sector'], data.get('telefono', ''), 
              data['no_contador'], id_cliente))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Cliente actualizado exitosamente'})
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400


@app.route('/api/lecturas/<int:id_lectura>', methods=['GET'])
@login_required
def obtener_lectura(id_lectura):
    """Obtener datos de una lectura para editar"""
    if not (session.get('rol') == 'ADMIN' or tiene_permiso(session.get('user_id'), 'lecturas.editar')):
        return jsonify({'error': 'No tienes permiso para esta acción'}), 403
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT l.id_lectura, l.id_cliente, l.fecha_lectura, l.lectura_anterior, 
               l.lectura_actual, l.consumo_m3, l.monto_total, l.estado_pago,
               c.nombre, c.apellido, c.no_contador
        FROM lectura l
        JOIN cliente c ON l.id_cliente = c.id_cliente
        WHERE l.id_lectura = %s
    """, (id_lectura,))
    lectura = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not lectura:
        return jsonify({'error': 'Lectura no encontrada'}), 404
    
    return jsonify(lectura)


@app.route('/api/lecturas/<int:id_lectura>', methods=['PUT'])
@login_required
def actualizar_lectura(id_lectura):
    """Actualizar datos de una lectura"""
    if not (session.get('rol') == 'ADMIN' or tiene_permiso(session.get('user_id'), 'lecturas.editar')):
        return jsonify({'error': 'No tienes permiso para esta acción'}), 403
    
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor()
    
    try:
        lectura_anterior = float(data['lectura_anterior'])
        lectura_actual = float(data['lectura_actual'])
        fecha_lectura = data['fecha_lectura']
        
        # El consumo_m3 se calcula automáticamente por la columna GENERATED
        # Pero necesitamos recalcular el monto_total
        consumo = lectura_actual - lectura_anterior
        monto_total = calcular_factura(consumo)
        
        cursor.execute("""
            UPDATE lectura 
            SET fecha_lectura = %s, lectura_anterior = %s, lectura_actual = %s, monto_total = %s
            WHERE id_lectura = %s
        """, (fecha_lectura, lectura_anterior, lectura_actual, monto_total, id_lectura))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Lectura actualizada exitosamente'})
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400


# --- RUTAS DE PROCESOS (Lectura y Pago) ---

@app.route('/procesos/lectura', methods=['GET', 'POST'])
@login_required
@roles_required('ADMIN', 'LECTOR', 'TESORERO')
def registro_lectura():
    """Registro de Lectura y Facturación (R1, R2, R3, R4)."""
    conn = get_db_connection()
    if conn is None: return redirect(url_for('dashboard'))
    cursor = conn.cursor(dictionary=True)
    
    # Obtener clientes activos
    cursor.execute("""
        SELECT c.id_cliente, c.nombre, c.apellido, c.no_contador, s.nombre_sector 
        FROM cliente c 
        JOIN sector s ON c.id_sector = s.id_sector
        WHERE c.activo = TRUE
        ORDER BY c.nombre, c.apellido
    """)
    clientes = cursor.fetchall()

    if request.method == 'POST':
        id_cliente = request.form['id_cliente']
        fecha_lectura = request.form['fecha_lectura']
        lectura_actual = float(request.form['lectura_actual'].replace(',', '.'))
        
        # Obtener la última lectura del cliente
        cursor.execute("""
            SELECT lectura_actual 
            FROM lectura 
            WHERE id_cliente = %s 
            ORDER BY fecha_lectura DESC 
            LIMIT 1
        """, (id_cliente,))
        ultima_lectura = cursor.fetchone()
        
        if ultima_lectura:
            lectura_anterior = float(ultima_lectura['lectura_actual'])
        else:
            lectura_anterior = 0  # Primera lectura

        consumo = lectura_actual - lectura_anterior
        
        # YA NO HAY VALIDACIÓN QUE RECHACE CONSUMO NEGATIVO
        
        monto_total = calcular_factura(consumo)

        try:
            cursor.execute("""
                INSERT INTO lectura (id_cliente, id_usuario_lector, fecha_lectura, lectura_anterior, lectura_actual, monto_total)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (id_cliente, session['user_id'], fecha_lectura, lectura_anterior, lectura_actual, monto_total))
            conn.commit()
            flash(f"Lectura registrada. Factura generada por Q{monto_total:.2f}.", "success")
        except mysql.connector.Error as err:
            flash(f"Error al registrar lectura: {err}", "danger")
            conn.rollback()

        cursor.close()
        conn.close()
        return redirect(url_for('registro_lectura'))

    # Obtener últimas lecturas registradas - INCLUYE LECTURA_ACTUAL
    cursor.execute("""
        SELECT l.id_lectura, c.nombre, c.apellido, c.no_contador, 
               l.fecha_lectura, l.lectura_anterior, l.lectura_actual, l.consumo_m3, l.monto_total, l.estado_pago
        FROM lectura l
        JOIN cliente c ON l.id_cliente = c.id_cliente
        ORDER BY l.fecha_lectura DESC
        LIMIT 10
    """)
    ultimas_lecturas = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('procesos/lectura.html', clientes=clientes, ultimas_lecturas=ultimas_lecturas)


@app.route('/api/buscar-clientes')
@login_required
def buscar_clientes():
    """API para buscar clientes (autocompletado)"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify({'clientes': []})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'clientes': []})
    
    cursor = conn.cursor(dictionary=True)
    
    # Buscar por nombre, apellido o número de contador
    cursor.execute("""
        SELECT 
            c.id_cliente, 
            c.nombre, 
            c.apellido, 
            c.no_contador, 
            s.nombre_sector,
            COALESCE(
                (SELECT lectura_actual 
                 FROM lectura 
                 WHERE id_cliente = c.id_cliente 
                 ORDER BY fecha_lectura DESC 
                 LIMIT 1), 
                0
            ) as ultima_lectura
        FROM cliente c
        JOIN sector s ON c.id_sector = s.id_sector
        WHERE c.activo = TRUE
        AND (
            c.nombre LIKE %s 
            OR c.apellido LIKE %s 
            OR c.no_contador LIKE %s
            OR CONCAT(c.nombre, ' ', c.apellido) LIKE %s
        )
        ORDER BY c.nombre, c.apellido
        LIMIT 10
    """, (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
    
    clientes = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Convertir a formato JSON-friendly
    resultado = []
    for cliente in clientes:
        resultado.append({
            'id': cliente['id_cliente'],
            'nombre': cliente['nombre'],
            'apellido': cliente['apellido'],
            'nombre_completo': f"{cliente['nombre']} {cliente['apellido']}",
            'no_contador': cliente['no_contador'],
            'sector': cliente['nombre_sector'],
            'ultima_lectura': float(cliente['ultima_lectura'])
        })
    
    return jsonify({'clientes': resultado})


@app.route('/procesos/pago', methods=['GET'])
@login_required
@roles_required('ADMIN', 'TESORERO')
def ver_facturas_pendientes():
    """Ver facturas pendientes de pago."""
    conn = get_db_connection()
    if conn is None: return redirect(url_for('dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    
    # Obtener todas las facturas pendientes
    cursor.execute("""
        SELECT l.id_lectura, c.nombre, c.apellido, c.no_contador, s.nombre_sector,
               l.fecha_lectura, l.consumo_m3, l.monto_total, 
               DATEDIFF(CURDATE(), l.fecha_lectura) as dias_mora
        FROM lectura l
        JOIN cliente c ON l.id_cliente = c.id_cliente
        JOIN sector s ON c.id_sector = s.id_sector
        WHERE l.estado_pago = 'PENDIENTE'
        ORDER BY l.fecha_lectura ASC
    """)
    facturas_pendientes = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('procesos/pago.html', facturas=facturas_pendientes)


@app.route('/procesos/pago/<int:id_lectura>', methods=['POST'])
@login_required
def registrar_pago(id_lectura):
    """Registrar Pago de una Factura (R2)."""
    conn = get_db_connection()
    if conn is None: 
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('ver_facturas_pendientes'))
    
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Obtener información completa de la lectura y cliente
        cursor.execute("""
            SELECT l.*, c.nombre, c.apellido, c.no_contador, s.nombre_sector
            FROM lectura l
            JOIN cliente c ON l.id_cliente = c.id_cliente
            JOIN sector s ON c.id_sector = s.id_sector
            WHERE l.id_lectura = %s AND l.estado_pago = 'PENDIENTE'
        """, (id_lectura,))
        lectura = cursor.fetchone()
        
        if not lectura:
            flash("Factura no encontrada o ya pagada.", "warning")
            cursor.close()
            conn.close()
            return redirect(url_for('ver_facturas_pendientes'))
        
        monto_factura = lectura['monto_total']

        # 2. Registrar el pago
        cursor.execute("""
            INSERT INTO pago (id_lectura, monto_pagado, id_usuario_receptor)
            VALUES (%s, %s, %s)
        """, (id_lectura, monto_factura, session['user_id']))
        
        id_pago = cursor.lastrowid

        # 3. Marcar la factura como PAGADA (R3)
        cursor.execute("UPDATE lectura SET estado_pago = 'PAGADO' WHERE id_lectura = %s", (id_lectura,))
        
        conn.commit()
        
        # Guardar información en sesión para el recibo
        session['ultimo_pago'] = {
            'id_pago': id_pago,
            'id_lectura': id_lectura,
            'nombre_cliente': f"{lectura['nombre']} {lectura['apellido']}",
            'no_contador': lectura['no_contador'],
            'monto': float(monto_factura),
            'fecha_lectura': lectura['fecha_lectura'].strftime('%Y-%m-%d'),
            'lectura_anterior': float(lectura['lectura_anterior']),
            'lectura_actual': float(lectura['lectura_actual']),
            'consumo': float(lectura['consumo_m3'])
        }
        
        flash(f"Pago registrado exitosamente por Q{monto_factura:.2f}.", "success")
    
    except mysql.connector.Error as err:
        flash(f"Error al registrar el pago: {err}", "danger")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('confirmacion_pago'))


@app.route('/procesos/pago/confirmacion')
@login_required
def confirmacion_pago():
    """Mostrar confirmación de pago con opción de imprimir recibo"""
    if 'ultimo_pago' not in session:
        flash("No hay información de pago reciente.", "warning")
        return redirect(url_for('ver_facturas_pendientes'))
    
    pago_info = session['ultimo_pago']
    return render_template('procesos/confirmacion_pago.html', pago=pago_info)


@app.route('/procesos/pago/imprimir/<int:id_lectura>')
@login_required
def imprimir_recibo(id_lectura):
    """Generar e imprimir recibo en PDF"""
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión.", "danger")
        return redirect(url_for('ver_facturas_pendientes'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener información completa del pago
        cursor.execute("""
            SELECT 
                l.id_lectura,
                l.fecha_lectura,
                l.lectura_anterior,
                l.lectura_actual,
                l.consumo_m3,
                l.monto_total,
                c.nombre,
                c.apellido,
                c.no_contador,
                s.nombre_sector,
                p.fecha_pago,
                p.monto_pagado
            FROM lectura l
            JOIN cliente c ON l.id_cliente = c.id_cliente
            JOIN sector s ON c.id_sector = s.id_sector
            JOIN pago p ON l.id_lectura = p.id_lectura
            WHERE l.id_lectura = %s
            ORDER BY p.fecha_pago DESC
            LIMIT 1
        """, (id_lectura,))
        
        datos = cursor.fetchone()
        
        if not datos:
            flash("No se encontró información del recibo.", "danger")
            return redirect(url_for('ver_facturas_pendientes'))
        
        # Generar PDF
        buffer = io.BytesIO()
        generar_recibo_pdf(buffer, datos)
        buffer.seek(0)
        
        nombre_archivo = f"Recibo_{datos['no_contador']}_{datos['fecha_pago'].strftime('%Y-%m-%d')}.pdf"
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nombre_archivo
        )
        
    except Exception as e:
        flash(f"Error al generar recibo: {str(e)}", "danger")
        return redirect(url_for('ver_facturas_pendientes'))
    finally:
        cursor.close()
        conn.close()


def generar_recibo_pdf(buffer, datos):
    """Generar recibo PDF con dos copias"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    
    # Crear canvas
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Función auxiliar para dibujar una copia del recibo
    def dibujar_recibo(y_start, tipo_copia):
        y = y_start
        
        # Encabezado
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, y, "COMITE DE AGUA POTABLE CORINTO S.L")
        y -= 20
        
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, y, f"({tipo_copia})")
        y -= 10
        
        # Línea separadora
        c.line(50, y, width-50, y)
        y -= 25
        
        # Información del lado izquierdo
        c.setFont("Helvetica", 10)
        fecha_emision = datos['fecha_pago'].strftime('%Y-%m-%d')
        c.drawString(50, y, f"Fecha Emisión: {fecha_emision}")
        y -= 15
        c.drawString(50, y, f"No. Contador: {datos['no_contador']}")
        y -= 15
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"Nombre: {datos['nombre']} {datos['apellido']}")
        y -= 25
        
        # Información del lado derecho (lecturas)
        y_right = y_start - 65
        c.setFont("Helvetica", 10)
        c.drawRightString(width-50, y_right, f"Lectura Anterior: {datos['lectura_anterior']:.2f} m³")
        y_right -= 15
        c.drawRightString(width-50, y_right, f"Lectura Actual: {datos['lectura_actual']:.2f} m³")
        y_right -= 15
        
        consumo = datos['consumo_m3']
        if consumo >= 0:
            c.drawRightString(width-50, y_right, f"CONSUMO: {consumo:.2f} m³")
        else:
            c.drawRightString(width-50, y_right, f"CONSUMO: {consumo:.2f} m³")
        
        y = y_right - 25
        
        # Cuadro de total/crédito
        monto = datos['monto_total']
        
        # Dibujar rectángulo para el monto
        rect_width = 250
        rect_height = 40
        rect_x = (width - rect_width) / 2
        rect_y = y - rect_height + 10
        
        c.setLineWidth(2)
        c.rect(rect_x, rect_y, rect_width, rect_height)
        
        c.setFont("Helvetica-Bold", 14)
        if monto < 0:
            texto_monto = "CRÉDITO A FAVOR:"
            valor_monto = f"Q{abs(monto):.2f}"
            c.setFillColorRGB(0, 0.5, 0)
        else:
            texto_monto = "TOTAL A PAGAR:"
            valor_monto = f"Q{monto:.2f}"
            c.setFillColorRGB(0, 0, 0)
        
        c.drawString(rect_x + 10, rect_y + rect_height/2 - 5, texto_monto)
        c.drawRightString(rect_x + rect_width - 10, rect_y + rect_height/2 - 5, valor_monto)
        
        y = rect_y - 20
        
        # Mensaje de pago
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(width/2, y, "Favor de pagar antes del 5 del siguiente mes.")
        y -= 30
        
        # Línea para firma
        c.line(width/2 - 100, y, width/2 + 100, y)
        y -= 15
        c.setFont("Helvetica", 9)
        c.drawCentredString(width/2, y, "Firma/Sello")
        
        return y
    
    # Dibujar primera copia (Usuario)
    y_usuario = height - 80
    y_final = dibujar_recibo(y_usuario, "COPIA PARA EL CLIENTE")
    
    # Línea de corte
    y_corte = y_final - 40
    c.setFont("Helvetica", 9)
    c.setDash(3, 3)
    c.line(50, y_corte, width-50, y_corte)
    c.setDash()
    c.drawCentredString(width/2, y_corte - 10, "----------- Línea de Corte -----------")
    
    # Dibujar segunda copia (Cooperativa)
    y_cooperativa = y_corte - 60
    dibujar_recibo(y_cooperativa, "COPIA PARA EL COMITE")
    
    # Finalizar PDF
    c.showPage()
    c.save()


def generar_pdf_reporte_ingresos(buffer, datos, fecha_inicio, fecha_fin):
    """Generar PDF profesional para reporte de ingresos"""
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a472a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#2d5016'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    
    # Contenido
    story = []
    
    # Encabezado
    story.append(Paragraph("COMITÉ DE AGUA POTABLE CORINTO S.L", title_style))
    story.append(Paragraph("REPORTE DE INGRESOS", heading_style))
    story.append(Spacer(1, 12))
    
    # Información del reporte
    info_text = f"""
    <b>Período:</b> {fecha_inicio} al {fecha_fin}<br/>
    <b>Fecha de Generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>
    <b>Total de Registros:</b> {len(datos)}
    """
    story.append(Paragraph(info_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Calcular total
    total_ingresos = sum(registro['total'] for registro in datos)
    
    # Tabla de datos
    table_data = [['Fecha', 'Monto (Q)']]
    
    for registro in datos:
        fecha_str = registro['fecha'].strftime('%d/%m/%Y') if isinstance(registro['fecha'], date) else str(registro['fecha'])
        table_data.append([
            fecha_str,
            f"{registro['total']:.2f}"
        ])
    
    # Fila de total
    table_data.append([
        Paragraph('<b>TOTAL INGRESOS</b>', normal_style),
        Paragraph(f'<b>Q{total_ingresos:.2f}</b>', normal_style)
    ])
    
    # Crear tabla
    table = Table(table_data, colWidths=[4*inch, 2*inch])
    table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d5016')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        # Filas de datos
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f5f5')]),
        # Fila de total
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#155724')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 12),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Pie de página
    footer_text = f"<i>Reporte generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}</i>"
    story.append(Paragraph(footer_text, normal_style))
    
    # Construir PDF
    doc.build(story)


def generar_pdf_reporte_morosos(buffer, datos):
    """Generar PDF profesional para reporte de clientes morosos"""
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#721c24'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 9
    
    # Contenido
    story = []
    
    # Encabezado
    story.append(Paragraph("COMITÉ DE AGUA POTABLE CORINTO S.L", title_style))
    story.append(Paragraph("REPORTE DE CLIENTES MOROSOS", 
                          ParagraphStyle('Heading', parent=styles['Heading2'], 
                                        fontSize=12, textColor=colors.HexColor('#721c24'),
                                        spaceAfter=12, alignment=TA_CENTER, fontName='Helvetica-Bold')))
    story.append(Spacer(1, 12))
    
    # Información del reporte
    total_deuda = sum(registro['deuda_total'] for registro in datos)
    total_facturas = sum(registro['facturas_pendientes'] for registro in datos)
    
    info_text = f"""
    <b>Fecha de Generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>
    <b>Total de Clientes Morosos:</b> {len(datos)}<br/>
    <b>Total de Facturas Pendientes:</b> {total_facturas}<br/>
    <b>Deuda Total:</b> Q{total_deuda:.2f}
    """
    story.append(Paragraph(info_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Tabla de datos
    table_data = [['Cliente', 'Contador', 'Sector', 'Facturas', 'Deuda (Q)', 'Fecha Antigua']]
    
    for registro in datos:
        fecha_antigua = registro['fecha_mas_antigua'].strftime('%d/%m/%Y') if isinstance(registro['fecha_mas_antigua'], date) else str(registro['fecha_mas_antigua'])
        table_data.append([
            f"{registro['nombre']} {registro['apellido']}",
            registro['no_contador'],
            registro['nombre_sector'],
            str(registro['facturas_pendientes']),
            f"{registro['deuda_total']:.2f}",
            fecha_antigua
        ])
    
    # Fila de total
    table_data.append([
        Paragraph('<b>TOTALES</b>', normal_style),
        '',
        '',
        Paragraph(f'<b>{total_facturas}</b>', normal_style),
        Paragraph(f'<b>Q{total_deuda:.2f}</b>', normal_style),
        ''
    ])
    
    # Crear tabla
    table = Table(table_data, colWidths=[2*inch, 1*inch, 1.2*inch, 0.8*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#721c24')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        # Filas de datos
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#fff3cd')),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fff3cd')]),
        # Fila de total
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8d7da')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#721c24')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 10),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 12),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Pie de página
    footer_text = f"<i>Reporte generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}</i>"
    story.append(Paragraph(footer_text, normal_style))
    
    # Construir PDF
    doc.build(story)


def generar_pdf_reporte_consumo(buffer, datos, fecha_inicio, fecha_fin):
    """Generar PDF profesional para reporte de consumo"""
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#004085'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 9
    
    # Contenido
    story = []
    
    # Encabezado
    story.append(Paragraph("COMITÉ DE AGUA POTABLE CORINTO S.L", title_style))
    story.append(Paragraph("REPORTE DE CONSUMO DE AGUA", 
                          ParagraphStyle('Heading', parent=styles['Heading2'], 
                                        fontSize=12, textColor=colors.HexColor('#004085'),
                                        spaceAfter=12, alignment=TA_CENTER, fontName='Helvetica-Bold')))
    story.append(Spacer(1, 12))
    
    # Información del reporte
    info_text = f"""
    <b>Período:</b> {fecha_inicio} al {fecha_fin}<br/>
    <b>Fecha de Generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>
    <b>Total de Clientes:</b> {len(datos)}
    """
    story.append(Paragraph(info_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Tabla de datos
    table_data = [['Cliente', 'Contador', 'Sector', 'Promedio (m³)', 'Máximo (m³)', 'Mínimo (m³)']]
    
    for registro in datos:
        table_data.append([
            f"{registro['nombre']} {registro['apellido']}",
            registro['no_contador'],
            registro['nombre_sector'],
            f"{registro['consumo_promedio']:.2f}",
            f"{registro['consumo_maximo']:.2f}",
            f"{registro['consumo_minimo']:.2f}"
        ])
    
    # Crear tabla
    table = Table(table_data, colWidths=[2*inch, 1*inch, 1.2*inch, 1*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004085')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        # Filas de datos
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#cce5ff')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#cce5ff')]),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Pie de página
    footer_text = f"<i>Reporte generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}</i>"
    story.append(Paragraph(footer_text, normal_style))
    
    # Construir PDF
    doc.build(story)


def generar_pdf_reporte_individual(buffer, cliente, lecturas, pagos, estadisticas, facturas_pendientes):
    """Generar PDF profesional para reporte individual de cliente"""
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a472a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#2d5016'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    
    # Contenido
    story = []
    
    # Encabezado
    story.append(Paragraph("COMITÉ DE AGUA POTABLE CORINTO S.L", title_style))
    story.append(Paragraph("REPORTE INDIVIDUAL DE CLIENTE", heading_style))
    story.append(Spacer(1, 20))
    
    # Información del cliente
    story.append(Paragraph("INFORMACIÓN DEL CLIENTE", heading_style))
    cliente_text = f"""
    <b>Nombre:</b> {cliente['nombre']} {cliente['apellido']}<br/>
    <b>Número de Contador:</b> {cliente['no_contador']}<br/>
    <b>Sector:</b> {cliente['nombre_sector']}<br/>
    <b>Teléfono:</b> {cliente.get('telefono', 'No registrado')}<br/>
    <b>Estado:</b> {'Activo' if cliente.get('activo', True) else 'Inactivo'}
    """
    story.append(Paragraph(cliente_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Estadísticas
    story.append(Paragraph("ESTADÍSTICAS", heading_style))
    stats_text = f"""
    <b>Total de Lecturas:</b> {estadisticas['total_lecturas']}<br/>
    <b>Consumo Promedio:</b> {estadisticas['consumo_promedio']:.2f} m³<br/>
    <b>Consumo Máximo:</b> {estadisticas['consumo_maximo']:.2f} m³<br/>
    <b>Consumo Mínimo:</b> {estadisticas['consumo_minimo']:.2f} m³<br/>
    <b>Total Pagado:</b> Q{estadisticas['total_pagado']:.2f}<br/>
    <b>Deuda Actual:</b> Q{estadisticas['deuda_total']:.2f}
    """
    story.append(Paragraph(stats_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Facturas pendientes
    if facturas_pendientes:
        story.append(Paragraph("FACTURAS PENDIENTES", heading_style))
        table_data = [['Fecha Lectura', 'Consumo (m³)', 'Monto (Q)', 'Días Mora']]
        
        for factura in facturas_pendientes:
            fecha_str = factura['fecha_lectura'].strftime('%d/%m/%Y') if isinstance(factura['fecha_lectura'], date) else str(factura['fecha_lectura'])
            table_data.append([
                fecha_str,
                f"{factura['consumo_m3']:.2f}",
                f"{factura['monto_total']:.2f}",
                str(factura.get('dias_mora', 0))
            ])
        
        table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#721c24')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fff3cd')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
    
    # Historial de lecturas
    if lecturas:
        story.append(Paragraph("HISTORIAL DE LECTURAS", heading_style))
        table_data = [['Fecha', 'Lect. Ant.', 'Lect. Act.', 'Consumo (m³)', 'Monto (Q)', 'Estado']]
        
        for lectura in lecturas[:20]:  # Limitar a 20 para no hacer el PDF muy largo
            fecha_str = lectura['fecha_lectura'].strftime('%d/%m/%Y') if isinstance(lectura['fecha_lectura'], date) else str(lectura['fecha_lectura'])
            estado = 'Pagado' if lectura['estado_pago'] == 'PAGADO' else 'Pendiente'
            table_data.append([
                fecha_str,
                f"{lectura['lectura_anterior']:.2f}",
                f"{lectura['lectura_actual']:.2f}",
                f"{lectura['consumo_m3']:.2f}",
                f"{lectura['monto_total']:.2f}",
                estado
            ])
        
        table = Table(table_data, colWidths=[1*inch, 1*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004085')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#cce5ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#cce5ff')]),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
    
    # Historial de pagos
    if pagos:
        story.append(Paragraph("HISTORIAL DE PAGOS", heading_style))
        table_data = [['Fecha Pago', 'Período', 'Consumo (m³)', 'Monto (Q)']]
        
        for pago in pagos[:20]:  # Limitar a 20
            fecha_pago_str = pago['fecha_pago'].strftime('%d/%m/%Y') if isinstance(pago['fecha_pago'], date) else str(pago['fecha_pago'])
            fecha_lectura_str = pago['fecha_lectura'].strftime('%d/%m/%Y') if isinstance(pago['fecha_lectura'], date) else str(pago['fecha_lectura'])
            table_data.append([
                fecha_pago_str,
                fecha_lectura_str,
                f"{pago['consumo_m3']:.2f}",
                f"{pago['monto_pagado']:.2f}"
            ])
        
        table = Table(table_data, colWidths=[2*inch, 2*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#155724')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d4edda')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#d4edda')]),
        ]))
        story.append(table)
    
    # Pie de página
    story.append(Spacer(1, 20))
    footer_text = f"<i>Reporte generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}</i>"
    story.append(Paragraph(footer_text, normal_style))
    
    # Construir PDF
    doc.build(story)


# --- RUTAS DE REPORTES ---

@app.route('/reportes/generador')
@login_required
@roles_required('ADMIN', 'TESORERO', 'PRESIDENTE')
def generador_reportes():
    """Generador de reportes."""
    return render_template('reportes/generador.html')


@app.route('/reportes/generar', methods=['POST'])
@login_required
@roles_required('ADMIN', 'TESORERO', 'PRESIDENTE')
def generar_reporte():
    """Generar reporte específico."""
    tipo_reporte = request.form.get('tipo_reporte')
    fecha_inicio = request.form.get('fecha_inicio')
    fecha_fin = request.form.get('fecha_fin')
    
    conn = get_db_connection()
    if conn is None: 
        flash("Error de conexión", "danger")
        return redirect(url_for('generador_reportes'))
    
    cursor = conn.cursor(dictionary=True)
    
    if tipo_reporte == 'ingresos':
        cursor.execute("""
            SELECT DATE(p.fecha_pago) as fecha, SUM(p.monto_pagado) as total
            FROM pago p
            WHERE p.fecha_pago BETWEEN %s AND %s
            GROUP BY DATE(p.fecha_pago)
            ORDER BY fecha DESC
        """, (fecha_inicio, fecha_fin))
        datos = cursor.fetchall()
        titulo = "Reporte de Ingresos"
        
    elif tipo_reporte == 'morosos':
        cursor.execute("""
            SELECT c.nombre, c.apellido, c.no_contador, s.nombre_sector,
                   COUNT(l.id_lectura) as facturas_pendientes,
                   SUM(l.monto_total) as deuda_total,
                   MIN(l.fecha_lectura) as fecha_mas_antigua
            FROM cliente c
            JOIN lectura l ON c.id_cliente = l.id_cliente
            JOIN sector s ON c.id_sector = s.id_sector
            WHERE l.estado_pago = 'PENDIENTE'
            GROUP BY c.id_cliente
            ORDER BY deuda_total DESC
        """)
        datos = cursor.fetchall()
        titulo = "Reporte de Clientes Morosos"
        
    elif tipo_reporte == 'consumo':
        cursor.execute("""
            SELECT c.nombre, c.apellido, c.no_contador, s.nombre_sector,
                   AVG(l.consumo_m3) as consumo_promedio,
                   MAX(l.consumo_m3) as consumo_maximo,
                   MIN(l.consumo_m3) as consumo_minimo
            FROM cliente c
            JOIN lectura l ON c.id_cliente = l.id_cliente
            JOIN sector s ON c.id_sector = s.id_sector
            WHERE l.fecha_lectura BETWEEN %s AND %s
            GROUP BY c.id_cliente
            ORDER BY consumo_promedio DESC
        """, (fecha_inicio, fecha_fin))
        datos = cursor.fetchall()
        titulo = "Reporte de Consumo de Agua"
        
    else:
        flash("Tipo de reporte no válido", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('generador_reportes'))
    
    cursor.close()
    conn.close()
    
    # Pasar fecha_generacion al template
    return render_template('reportes/resultado.html', 
                         datos=datos, 
                         titulo=titulo, 
                         tipo=tipo_reporte,
                         fecha_inicio=fecha_inicio,
                         fecha_fin=fecha_fin,
                         fecha_generacion=datetime.now())


@app.route('/reportes/exportar-pdf/<tipo_reporte>')
@login_required
@roles_required('ADMIN', 'TESORERO', 'PRESIDENTE')
def exportar_reporte_pdf(tipo_reporte):
    """Exportar reporte en formato PDF profesional"""
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    # Solo validar fechas si el reporte las requiere
    if tipo_reporte != 'morosos' and (not fecha_inicio or not fecha_fin):
        flash("Fechas no especificadas", "danger")
        return redirect(url_for('generador_reportes'))
    
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión", "danger")
        return redirect(url_for('generador_reportes'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        if tipo_reporte == 'ingresos':
            cursor.execute("""
                SELECT DATE(p.fecha_pago) as fecha, SUM(p.monto_pagado) as total
                FROM pago p
                WHERE p.fecha_pago BETWEEN %s AND %s
                GROUP BY DATE(p.fecha_pago)
                ORDER BY fecha DESC
            """, (fecha_inicio, fecha_fin))
            datos = cursor.fetchall()
            
            buffer = io.BytesIO()
            generar_pdf_reporte_ingresos(buffer, datos, fecha_inicio, fecha_fin)
            buffer.seek(0)
            
            nombre_archivo = f"Reporte_Ingresos_{fecha_inicio}_{fecha_fin}.pdf"
            
        elif tipo_reporte == 'morosos':
            cursor.execute("""
                SELECT c.nombre, c.apellido, c.no_contador, s.nombre_sector,
                       COUNT(l.id_lectura) as facturas_pendientes,
                       SUM(l.monto_total) as deuda_total,
                       MIN(l.fecha_lectura) as fecha_mas_antigua
                FROM cliente c
                JOIN lectura l ON c.id_cliente = l.id_cliente
                JOIN sector s ON c.id_sector = s.id_sector
                WHERE l.estado_pago = 'PENDIENTE'
                GROUP BY c.id_cliente
                ORDER BY deuda_total DESC
            """)
            datos = cursor.fetchall()
            
            buffer = io.BytesIO()
            generar_pdf_reporte_morosos(buffer, datos)
            buffer.seek(0)
            
            nombre_archivo = f"Reporte_Morosos_{datetime.now().strftime('%Y%m%d')}.pdf"
            
        elif tipo_reporte == 'consumo':
            cursor.execute("""
                SELECT c.nombre, c.apellido, c.no_contador, s.nombre_sector,
                       AVG(l.consumo_m3) as consumo_promedio,
                       MAX(l.consumo_m3) as consumo_maximo,
                       MIN(l.consumo_m3) as consumo_minimo
                FROM cliente c
                JOIN lectura l ON c.id_cliente = l.id_cliente
                JOIN sector s ON c.id_sector = s.id_sector
                WHERE l.fecha_lectura BETWEEN %s AND %s
                GROUP BY c.id_cliente
                ORDER BY consumo_promedio DESC
            """, (fecha_inicio, fecha_fin))
            datos = cursor.fetchall()
            
            buffer = io.BytesIO()
            generar_pdf_reporte_consumo(buffer, datos, fecha_inicio, fecha_fin)
            buffer.seek(0)
            
            nombre_archivo = f"Reporte_Consumo_{fecha_inicio}_{fecha_fin}.pdf"
            
        else:
            flash("Tipo de reporte no válido", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('generador_reportes'))
        
        cursor.close()
        conn.close()
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nombre_archivo
        )
        
    except Exception as e:
        flash(f"Error al generar PDF: {str(e)}", "danger")
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return redirect(url_for('generador_reportes'))


@app.route('/reportes/individual')
@login_required
@roles_required('ADMIN', 'TESORERO', 'PRESIDENTE')
def reporte_individual_form():
    """Formulario para seleccionar cliente para reporte individual"""
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión", "danger")
        return redirect(url_for('generador_reportes'))
    
    cursor = conn.cursor(dictionary=True)
    
    # Obtener todos los clientes activos
    cursor.execute("""
        SELECT c.id_cliente, c.nombre, c.apellido, c.no_contador, s.nombre_sector
        FROM cliente c
        JOIN sector s ON c.id_sector = s.id_sector
        WHERE c.activo = TRUE
        ORDER BY c.nombre, c.apellido
    """)
    clientes = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('reportes/individual_form.html', clientes=clientes)


@app.route('/reportes/individual/<int:id_cliente>')
@login_required
@roles_required('ADMIN', 'TESORERO', 'PRESIDENTE')
def reporte_individual_cliente(id_cliente):
    """Generar reporte individual de un cliente"""
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión", "danger")
        return redirect(url_for('generador_reportes'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Información del cliente
        cursor.execute("""
            SELECT c.*, s.nombre_sector
            FROM cliente c
            JOIN sector s ON c.id_sector = s.id_sector
            WHERE c.id_cliente = %s
        """, (id_cliente,))
        cliente = cursor.fetchone()
        
        if not cliente:
            flash("Cliente no encontrado", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('reporte_individual_form'))
        
        # Historial de lecturas
        cursor.execute("""
            SELECT 
                l.id_lectura,
                l.fecha_lectura,
                l.lectura_anterior,
                l.lectura_actual,
                l.consumo_m3,
                l.monto_total,
                l.estado_pago,
                CONCAT(u.nombre, ' ', u.apellido) as lector
            FROM lectura l
            JOIN usuario u ON l.id_usuario_lector = u.id_usuario
            WHERE l.id_cliente = %s
            ORDER BY l.fecha_lectura DESC
        """, (id_cliente,))
        lecturas = cursor.fetchall()
        
        # Historial de pagos
        cursor.execute("""
            SELECT 
                p.id_pago,
                p.fecha_pago,
                p.monto_pagado,
                l.fecha_lectura,
                l.consumo_m3,
                CONCAT(u.nombre, ' ', u.apellido) as receptor
            FROM pago p
            JOIN lectura l ON p.id_lectura = l.id_lectura
            JOIN usuario u ON p.id_usuario_receptor = u.id_usuario
            WHERE l.id_cliente = %s
            ORDER BY p.fecha_pago DESC
        """, (id_cliente,))
        pagos = cursor.fetchall()
        
        # Estadísticas del cliente
        cursor.execute("""
            SELECT 
                COUNT(*) as total_lecturas,
                COALESCE(AVG(consumo_m3), 0) as consumo_promedio,
                COALESCE(MAX(consumo_m3), 0) as consumo_maximo,
                COALESCE(MIN(consumo_m3), 0) as consumo_minimo,
                COALESCE(SUM(CASE WHEN estado_pago = 'PENDIENTE' THEN monto_total ELSE 0 END), 0) as deuda_total,
                COALESCE(SUM(CASE WHEN estado_pago = 'PAGADO' THEN monto_total ELSE 0 END), 0) as total_pagado
            FROM lectura
            WHERE id_cliente = %s
        """, (id_cliente,))
        estadisticas = cursor.fetchone()
        
        # Facturas pendientes
        cursor.execute("""
            SELECT 
                id_lectura,
                fecha_lectura,
                consumo_m3,
                monto_total,
                DATEDIFF(CURDATE(), fecha_lectura) as dias_mora
            FROM lectura
            WHERE id_cliente = %s AND estado_pago = 'PENDIENTE'
            ORDER BY fecha_lectura ASC
        """, (id_cliente,))
        facturas_pendientes = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('reportes/individual_resultado.html',
                             cliente=cliente,
                             lecturas=lecturas,
                             pagos=pagos,
                             estadisticas=estadisticas,
                             facturas_pendientes=facturas_pendientes,
                             fecha_generacion=datetime.now())
        
    except Exception as e:
        flash(f"Error al generar reporte: {str(e)}", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('reporte_individual_form'))


@app.route('/reportes/individual/<int:id_cliente>/pdf')
@login_required
@roles_required('ADMIN', 'TESORERO', 'PRESIDENTE')
def exportar_reporte_individual_pdf(id_cliente):
    """Exportar reporte individual en formato PDF profesional"""
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión", "danger")
        return redirect(url_for('generador_reportes'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Información del cliente
        cursor.execute("""
            SELECT c.*, s.nombre_sector
            FROM cliente c
            JOIN sector s ON c.id_sector = s.id_sector
            WHERE c.id_cliente = %s
        """, (id_cliente,))
        cliente = cursor.fetchone()
        
        if not cliente:
            flash("Cliente no encontrado", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('reporte_individual_form'))
        
        # Historial de lecturas
        cursor.execute("""
            SELECT 
                l.id_lectura,
                l.fecha_lectura,
                l.lectura_anterior,
                l.lectura_actual,
                l.consumo_m3,
                l.monto_total,
                l.estado_pago,
                CONCAT(u.nombre, ' ', u.apellido) as lector
            FROM lectura l
            JOIN usuario u ON l.id_usuario_lector = u.id_usuario
            WHERE l.id_cliente = %s
            ORDER BY l.fecha_lectura DESC
        """, (id_cliente,))
        lecturas = cursor.fetchall()
        
        # Historial de pagos
        cursor.execute("""
            SELECT 
                p.id_pago,
                p.fecha_pago,
                p.monto_pagado,
                l.fecha_lectura,
                l.consumo_m3,
                CONCAT(u.nombre, ' ', u.apellido) as receptor
            FROM pago p
            JOIN lectura l ON p.id_lectura = l.id_lectura
            JOIN usuario u ON p.id_usuario_receptor = u.id_usuario
            WHERE l.id_cliente = %s
            ORDER BY p.fecha_pago DESC
        """, (id_cliente,))
        pagos = cursor.fetchall()
        
        # Estadísticas del cliente
        cursor.execute("""
            SELECT 
                COUNT(*) as total_lecturas,
                COALESCE(AVG(consumo_m3), 0) as consumo_promedio,
                COALESCE(MAX(consumo_m3), 0) as consumo_maximo,
                COALESCE(MIN(consumo_m3), 0) as consumo_minimo,
                COALESCE(SUM(CASE WHEN estado_pago = 'PENDIENTE' THEN monto_total ELSE 0 END), 0) as deuda_total,
                COALESCE(SUM(CASE WHEN estado_pago = 'PAGADO' THEN monto_total ELSE 0 END), 0) as total_pagado
            FROM lectura
            WHERE id_cliente = %s
        """, (id_cliente,))
        estadisticas = cursor.fetchone()
        
        # Facturas pendientes
        cursor.execute("""
            SELECT 
                id_lectura,
                fecha_lectura,
                consumo_m3,
                monto_total,
                DATEDIFF(CURDATE(), fecha_lectura) as dias_mora
            FROM lectura
            WHERE id_cliente = %s AND estado_pago = 'PENDIENTE'
            ORDER BY fecha_lectura ASC
        """, (id_cliente,))
        facturas_pendientes = cursor.fetchall()
        
        # Generar PDF
        buffer = io.BytesIO()
        generar_pdf_reporte_individual(buffer, cliente, lecturas, pagos, estadisticas, facturas_pendientes)
        buffer.seek(0)
        
        nombre_archivo = f"Reporte_Individual_{cliente['no_contador']}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        cursor.close()
        conn.close()
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nombre_archivo
        )
        
    except Exception as e:
        flash(f"Error al generar PDF: {str(e)}", "danger")
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return redirect(url_for('reporte_individual_form'))


# --- RUTAS DE SECTORES ---

@app.route('/sectores')
@login_required
def ver_sectores():
    """Ver clientes por sector."""
    conn = get_db_connection()
    if conn is None: return redirect(url_for('dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    
    # Obtener sectores con conteo de clientes
    cursor.execute("""
        SELECT s.id_sector, s.nombre_sector, s.descripcion,
               COUNT(c.id_cliente) as total_clientes,
               SUM(CASE WHEN l.estado_pago = 'PENDIENTE' THEN 1 ELSE 0 END) as clientes_morosos
        FROM sector s
        LEFT JOIN cliente c ON s.id_sector = c.id_sector AND c.activo = TRUE
        LEFT JOIN lectura l ON c.id_cliente = l.id_cliente AND l.estado_pago = 'PENDIENTE'
        GROUP BY s.id_sector
        ORDER BY s.nombre_sector
    """)
    sectores = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('sectores/lista.html', sectores=sectores)


@app.route('/api/sectores', methods=['GET'])
@login_required
def obtener_sectores_api():
    """Obtener todos los sectores para uso en API"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_sector, nombre_sector FROM sector ORDER BY nombre_sector")
    sectores = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(sectores)


@app.route('/sectores/<int:id_sector>')
@login_required
def ver_clientes_sector(id_sector):
    """Ver clientes de un sector específico."""
    conn = get_db_connection()
    if conn is None: return redirect(url_for('ver_sectores'))
    
    cursor = conn.cursor(dictionary=True)
    
    # Obtener información del sector
    cursor.execute("SELECT * FROM sector WHERE id_sector = %s", (id_sector,))
    sector = cursor.fetchone()
    
    if not sector:
        flash("Sector no encontrado", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('ver_sectores'))
    
    # Obtener clientes del sector
    cursor.execute("""
        SELECT c.id_cliente, c.nombre, c.apellido, c.no_contador, c.telefono,
               COALESCE(SUM(CASE WHEN l.estado_pago = 'PENDIENTE' THEN l.monto_total ELSE 0 END), 0) as deuda
        FROM cliente c
        LEFT JOIN lectura l ON c.id_cliente = l.id_cliente
        WHERE c.id_sector = %s AND c.activo = TRUE
        GROUP BY c.id_cliente
        ORDER BY c.nombre, c.apellido
    """, (id_sector,))
    clientes = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('sectores/detalle.html', sector=sector, clientes=clientes)


# --- RUTAS DE ADMINISTRACIÓN DE USUARIOS ---

@app.route('/admin/usuarios')
@login_required
@admin_required
def listar_usuarios():
    """Listar todos los usuarios del sistema (Solo ADMIN)"""
    conn = get_db_connection()
    if conn is None: 
        return redirect(url_for('dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    
    # Obtener todos los usuarios
    cursor.execute("""
        SELECT id_usuario, nombre, apellido, correo_electronico, rol, activo, fecha_creacion
        FROM usuario
        ORDER BY fecha_creacion DESC
    """)
    usuarios = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/usuarios.html', usuarios=usuarios)


@app.route('/admin/usuarios/nuevo', methods=['GET'])
@login_required
@admin_required
def nuevo_usuario_form():
    """Mostrar formulario para crear nuevo usuario (Solo ADMIN)"""
    return render_template('admin/nuevo_usuario.html')


@app.route('/admin/usuarios/crear', methods=['POST'])
@login_required
@admin_required
def crear_usuario():
    """Crear nuevo usuario (Solo ADMIN)"""
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('nuevo_usuario_form'))
    
    cursor = conn.cursor()
    
    # Obtener datos del formulario
    nombre = request.form['nombre'].strip()
    apellido = request.form['apellido'].strip()
    email = request.form['email'].strip()
    password = request.form['password']
    password_confirm = request.form['password_confirm']
    rol = request.form['rol']
    
    # Validaciones
    if not nombre or not apellido or not email or not password:
        flash("Todos los campos son obligatorios.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('nuevo_usuario_form'))
    
    if password != password_confirm:
        flash("Las contraseñas no coinciden.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('nuevo_usuario_form'))
    
    if len(password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('nuevo_usuario_form'))
    
    if rol not in ['ADMIN', 'LECTOR', 'TESORERO', 'PRESIDENTE']:
        flash("Rol no válido.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('nuevo_usuario_form'))
    
    # Verificar si el email ya existe
    cursor.execute("SELECT id_usuario FROM usuario WHERE correo_electronico = %s", (email,))
    if cursor.fetchone():
        flash(f"El correo electrónico {email} ya está registrado.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('nuevo_usuario_form'))
    
    # Generar hash de contraseña
    password_hash = generate_password_hash(password)
    
    try:
        # Insertar nuevo usuario
        cursor.execute("""
            INSERT INTO usuario (nombre, apellido, correo_electronico, contrasena_hash, rol)
            VALUES (%s, %s, %s, %s, %s)
        """, (nombre, apellido, email, password_hash, rol))
        
        conn.commit()
        
        flash(f"Usuario {nombre} {apellido} creado exitosamente con rol {rol}.", "success")
        cursor.close()
        conn.close()
        return redirect(url_for('listar_usuarios'))
        
    except mysql.connector.Error as err:
        flash(f"Error al crear usuario: {err}", "danger")
        conn.rollback()
        cursor.close()
        conn.close()
        return redirect(url_for('nuevo_usuario_form'))


@app.route('/admin/usuarios/toggle/<int:id_usuario>', methods=['POST'])
@login_required
@admin_required
def toggle_usuario(id_usuario):
    """Activar/Desactivar usuario (Solo ADMIN)"""
    # Evitar que el admin se desactive a sí mismo
    if id_usuario == session['user_id']:
        flash("No puedes desactivar tu propia cuenta.", "warning")
        return redirect(url_for('listar_usuarios'))
    
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('listar_usuarios'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener estado actual
        cursor.execute("SELECT nombre, apellido, activo FROM usuario WHERE id_usuario = %s", (id_usuario,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash("Usuario no encontrado.", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('listar_usuarios'))
        
        # Cambiar estado
        nuevo_estado = not usuario['activo']
        cursor.execute("UPDATE usuario SET activo = %s WHERE id_usuario = %s", (nuevo_estado, id_usuario))
        conn.commit()
        
        estado_texto = "activado" if nuevo_estado else "desactivado"
        flash(f"Usuario {usuario['nombre']} {usuario['apellido']} {estado_texto} exitosamente.", "success")
        
    except mysql.connector.Error as err:
        flash(f"Error al cambiar estado del usuario: {err}", "danger")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('listar_usuarios'))


@app.route('/api/usuarios/<int:id_usuario>', methods=['GET'])
@login_required
def obtener_usuario(id_usuario):
    """Obtener datos de un usuario para editar"""
    if not (session.get('rol') == 'ADMIN' or tiene_permiso(session.get('user_id'), 'usuarios.editar')):
        return jsonify({'error': 'No tienes permiso para esta acción'}), 403
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_usuario, nombre, apellido, correo_electronico, rol
        FROM usuario
        WHERE id_usuario = %s
    """, (id_usuario,))
    usuario = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    return jsonify(usuario)


@app.route('/api/usuarios/<int:id_usuario>', methods=['PUT'])
@login_required
def actualizar_usuario(id_usuario):
    """Actualizar datos de un usuario"""
    if not (session.get('rol') == 'ADMIN' or tiene_permiso(session.get('user_id'), 'usuarios.editar')):
        return jsonify({'error': 'No tienes permiso para esta acción'}), 403
    
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Error de conexión'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Validar campos requeridos
        if not all(key in data for key in ['nombre', 'apellido', 'correo_electronico', 'rol']):
            return jsonify({'error': 'Faltan campos requeridos'}), 400
        
        # Verificar que el rol sea válido
        if data['rol'] not in ['ADMIN', 'LECTOR', 'TESORERO', 'PRESIDENTE']:
            return jsonify({'error': 'Rol no válido'}), 400
        
        # Verificar si el email ya existe en otro usuario
        cursor.execute("""
            SELECT id_usuario FROM usuario 
            WHERE correo_electronico = %s AND id_usuario != %s
        """, (data['correo_electronico'], id_usuario))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'El correo electrónico ya está registrado en otro usuario'}), 400
        
        # Actualizar usuario (sin cambiar contraseña)
        cursor.execute("""
            UPDATE usuario 
            SET nombre = %s, apellido = %s, correo_electronico = %s, rol = %s,
                ultima_actualizacion = CURRENT_TIMESTAMP
            WHERE id_usuario = %s
        """, (data['nombre'], data['apellido'], data['correo_electronico'], 
              data['rol'], id_usuario))
        
        # Si el usuario modificado es el mismo que está logueado y cambió su rol, actualizar sesión
        if id_usuario == session.get('user_id'):
            session['rol'] = data['rol']
            # Recargar permisos si es necesario
            session['permisos'] = obtener_permisos_usuario(id_usuario)
            print(f"DEBUG: Sesión actualizada para usuario {id_usuario} (rol: {data['rol']})")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Usuario actualizado exitosamente'})
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500


@app.route('/admin/usuarios/cambiar-password/<int:id_usuario>', methods=['GET', 'POST'])
@login_required
@admin_required
def cambiar_password_usuario(id_usuario):
    """Cambiar contraseña de un usuario (Solo ADMIN)"""
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('listar_usuarios'))
    
    cursor = conn.cursor(dictionary=True)
    
    # Obtener información del usuario
    cursor.execute("SELECT id_usuario, nombre, apellido, correo_electronico FROM usuario WHERE id_usuario = %s", (id_usuario,))
    usuario = cursor.fetchone()
    
    if not usuario:
        flash("Usuario no encontrado.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('listar_usuarios'))
    
    if request.method == 'POST':
        nueva_password = request.form['password']
        password_confirm = request.form['password_confirm']
        
        # Validaciones
        if nueva_password != password_confirm:
            flash("Las contraseñas no coinciden.", "danger")
            cursor.close()
            conn.close()
            return render_template('admin/cambiar_password.html', usuario=usuario)
        
        if len(nueva_password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", "danger")
            cursor.close()
            conn.close()
            return render_template('admin/cambiar_password.html', usuario=usuario)
        
        # Actualizar contraseña
        password_hash = generate_password_hash(nueva_password)
        
        try:
            cursor.execute("""
                UPDATE usuario 
                SET contrasena_hash = %s, ultima_actualizacion = CURRENT_TIMESTAMP
                WHERE id_usuario = %s
            """, (password_hash, id_usuario))
            conn.commit()
            
            flash(f"Contraseña actualizada para {usuario['nombre']} {usuario['apellido']}.", "success")
            cursor.close()
            conn.close()
            return redirect(url_for('listar_usuarios'))
            
        except mysql.connector.Error as err:
            flash(f"Error al actualizar contraseña: {err}", "danger")
            conn.rollback()
            cursor.close()
            conn.close()
            return render_template('admin/cambiar_password.html', usuario=usuario)
    
    cursor.close()
    conn.close()
    return render_template('admin/cambiar_password.html', usuario=usuario)


# --- RUTAS DE GESTIÓN DE PERMISOS ---

@app.route('/admin/usuarios/<int:id_usuario>/permisos', methods=['GET'])
@login_required
@admin_required
def gestionar_permisos_usuario(id_usuario):
    """Gestionar permisos de un usuario específico"""
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('listar_usuarios'))
    
    cursor = conn.cursor(dictionary=True)
    
    # Obtener información del usuario
    cursor.execute("SELECT id_usuario, nombre, apellido, correo_electronico, rol FROM usuario WHERE id_usuario = %s", (id_usuario,))
    usuario = cursor.fetchone()
    
    if not usuario:
        flash("Usuario no encontrado.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('listar_usuarios'))
    
    # Obtener todos los permisos agrupados por módulo
    cursor.execute("""
        SELECT id_permiso, codigo_permiso, nombre_permiso, descripcion, modulo
        FROM permiso
        WHERE activo = TRUE
        ORDER BY modulo, nombre_permiso
    """)
    todos_permisos = cursor.fetchall()
    
    # Obtener permisos del usuario
    cursor.execute("""
        SELECT p.id_permiso, p.codigo_permiso
        FROM usuario_permiso up
        JOIN permiso p ON up.id_permiso = p.id_permiso
        WHERE up.id_usuario = %s AND p.activo = TRUE
    """, (id_usuario,))
    permisos_usuario = {row['id_permiso']: row['codigo_permiso'] for row in cursor.fetchall()}
    
    # Agrupar permisos por módulo
    permisos_por_modulo = {}
    for permiso in todos_permisos:
        modulo = permiso['modulo']
        if modulo not in permisos_por_modulo:
            permisos_por_modulo[modulo] = []
        permiso['tiene_permiso'] = permiso['id_permiso'] in permisos_usuario
        permisos_por_modulo[modulo].append(permiso)
    
    cursor.close()
    conn.close()
    
    return render_template('admin/permisos.html', 
                         usuario=usuario, 
                         permisos_por_modulo=permisos_por_modulo,
                         permisos_usuario=permisos_usuario)


@app.route('/admin/usuarios/<int:id_usuario>/permisos', methods=['POST'])
@login_required
@admin_required
def actualizar_permisos_usuario(id_usuario):
    """Actualizar permisos de un usuario"""
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('listar_usuarios'))
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener permisos seleccionados del formulario
        permisos_seleccionados = request.form.getlist('permisos')
        
        print(f"DEBUG: Permisos recibidos: {permisos_seleccionados}")
        print(f"DEBUG: Usuario ID: {id_usuario}")
        
        # Verificar que el usuario existe
        cursor.execute("SELECT id_usuario, nombre, apellido, rol FROM usuario WHERE id_usuario = %s", (id_usuario,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash("Usuario no encontrado.", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('listar_usuarios'))
        
        # Eliminar todos los permisos actuales del usuario
        cursor.execute("DELETE FROM usuario_permiso WHERE id_usuario = %s", (id_usuario,))
        deleted_count = cursor.rowcount
        print(f"DEBUG: Permisos eliminados: {deleted_count}")
        
        # Insertar nuevos permisos
        if permisos_seleccionados:
            valores = [(id_usuario, int(permiso_id), session['user_id']) for permiso_id in permisos_seleccionados]
            cursor.executemany("""
                INSERT INTO usuario_permiso (id_usuario, id_permiso, asignado_por)
                VALUES (%s, %s, %s)
            """, valores)
            inserted_count = cursor.rowcount
            print(f"DEBUG: Permisos insertados: {inserted_count}")
        else:
            print("DEBUG: No se seleccionaron permisos")
        
        conn.commit()
        
        # Actualizar sesión de TODOS los usuarios que puedan estar logueados
        # Si el usuario modificado es el mismo que está logueado, actualizar su sesión
        if id_usuario == session.get('user_id'):
            session['permisos'] = obtener_permisos_usuario(id_usuario)
            print(f"DEBUG: Sesión actualizada para usuario {id_usuario}")
        
        # Verificar si algún otro usuario tiene permisos que necesiten actualizarse
        # (Esto se manejará automáticamente con la verificación en BD)
        
        flash(f"Permisos actualizados exitosamente para {usuario['nombre']} {usuario['apellido']}. {len(permisos_seleccionados) if permisos_seleccionados else 0} permiso(s) asignado(s).", "success")
        
    except mysql.connector.Error as err:
        flash(f"Error al actualizar permisos: {err}", "danger")
        conn.rollback()
        print(f"ERROR: {err}")
    except Exception as e:
        flash(f"Error inesperado: {str(e)}", "danger")
        conn.rollback()
        print(f"ERROR INESPERADO: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('gestionar_permisos_usuario', id_usuario=id_usuario))




# --- Ejecución de la Aplicación ---
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)