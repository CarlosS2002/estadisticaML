"""
Analizador de Puntos de Minería - Versión Web LIGERA
Usa pytesseract en lugar de EasyOCR para reducir memoria
Ideal para despliegue en Render/Railway con plan gratuito
"""

from flask import Flask, render_template_string, request, jsonify
import re
import os
from io import BytesIO
from datetime import datetime

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

# Intentar importar pytesseract, si no está disponible usar modo manual
try:
    import pytesseract
    OCR_DISPONIBLE = True
    print("✅ Tesseract OCR disponible")
except ImportError:
    OCR_DISPONIBLE = False
    print("⚠️ Tesseract no disponible - modo entrada manual activado")

app = Flask(__name__)
app.secret_key = 'mineria_analyzer_2024'

# Almacén de datos de sesiones
datos_almacenados = {
    'anterior': None,
    'historial': []
}

# Correcciones de nombres comunes
CORRECCIONES = {
    'morningstar': 'MorningStar7',
    'morningstar7': 'MorningStar7',
    'morningstarz': 'MorningStar7',
    'morningstar?': 'MorningStar7',
    'morning5tar7': 'MorningStar7',
    'carloqwert': 'carloquert',
    'carloquert': 'carloquert',
    'carl0quert': 'carloquert',
    'besttoxico': 'BestToxico',
    'bestt0xico': 'BestToxico',
    'nighteye': '_Nighteye',
    '_nighteye': '_Nighteye',
    'getrix': 'Getrix',
    '6etrix': 'Getrix',
    'minic_efe': 'MiniC_EFE',
    'minicefe': 'MiniC_EFE',
    'milena00': 'Milena00',
    'milena0o': 'Milena00',
    'ilucia_': 'Ilucia_',
    'ilucia': 'Ilucia_',
    'athaoblen55': 'AthaOblen55',
    'athaoblenss': 'AthaOblen55',
    'quark': 'Quark',
}

def corregir_nombre(nombre):
    nombre_lower = nombre.lower().replace(' ', '')
    if nombre_lower in CORRECCIONES:
        return CORRECCIONES[nombre_lower]
    for key, value in CORRECCIONES.items():
        if key in nombre_lower or nombre_lower in key:
            return value
    return nombre


def extraer_datos_imagen(imagen_bytes):
    """
    Extrae solo los números de la imagen y los asigna a Pos1-Pos10.
    No depende de detectar nombres, lo que lo hace mucho más fiable.
    """
    try:
        imagen = Image.open(BytesIO(imagen_bytes))
        if imagen.mode == 'RGBA':
            imagen = imagen.convert('RGB')

        # Preprocesamiento
        width, height = imagen.size
        imagen = imagen.resize((width * 3, height * 3), Image.Resampling.LANCZOS)

        enhancer = ImageEnhance.Contrast(imagen)
        imagen = enhancer.enhance(1.8)
        enhancer = ImageEnhance.Sharpness(imagen)
        imagen = enhancer.enhance(1.5)

        todos_los_numeros = []

        if OCR_DISPONIBLE:
            # Intentar con pytesseract
            try:
                imagen_gray = imagen.convert('L')
                imagen_np = np.array(imagen_gray)
                imagen_np = np.where(imagen_np > 100, 255, 0).astype(np.uint8)
                imagen_bin = Image.fromarray(imagen_np)

                # Configuración que extrae dígitos más fácilmente
                configs = [
                    '--psm 6 -c tessedit_char_whitelist=0123456789',
                    '--psm 11 -c tessedit_char_whitelist=0123456789',
                    '--psm 6',
                ]
                texto_total = ''
                for cfg in configs:
                    try:
                        texto_total += pytesseract.image_to_string(imagen_bin, config=cfg) + '\n'
                    except Exception:
                        pass

                print(f"📝 Texto OCR raw: {texto_total[:300]}")

                for num_str in re.findall(r'\d+', texto_total):
                    if len(num_str) >= 6:
                        n = int(num_str)
                        if n >= 100000:
                            todos_los_numeros.append(n)

            except Exception as e:
                print(f"⚠️ pytesseract falló: {e}")

        # Si pytesseract no funcionó, intentar con datos de píxeles (fallback)
        if not todos_los_numeros:
            print("⚠️ OCR sin resultados, intentando método alternativo...")
            # Guardar imagen temporalmente y releer con configuración diferente
            from io import BytesIO as BIO
            buf = BIO()
            imagen.save(buf, format='PNG')
            buf.seek(0)
            if OCR_DISPONIBLE:
                try:
                    texto = pytesseract.image_to_string(
                        Image.open(buf),
                        config='--oem 3 --psm 4'
                    )
                    for num_str in re.findall(r'\d{6,}', texto):
                        n = int(num_str)
                        if n >= 100000:
                            todos_los_numeros.append(n)
                except Exception as e2:
                    print(f"⚠️ Fallback OCR falló: {e2}")

        # Eliminar duplicados manteniendo orden
        vistos = set()
        numeros_unicos = []
        for n in todos_los_numeros:
            if n not in vistos:
                vistos.add(n)
                numeros_unicos.append(n)

        # Ordenar de mayor a menor (ranking) y tomar los 10 primeros
        numeros_unicos.sort(reverse=True)

        datos = {}
        for i, puntos in enumerate(numeros_unicos[:10], 1):
            datos[f'Pos{i}'] = puntos

        print(f"📊 Números encontrados: {numeros_unicos}")
        print(f"✅ Datos: {datos}")

        return {'datos': datos, 'textos': list(map(str, numeros_unicos)), 'exito': len(datos) > 0}

    except Exception as e:
        print(f"❌ Error extracción: {e}")
        return {'datos': {}, 'textos': [], 'exito': False, 'error': str(e)}


def analizar_comparativa(datos_anterior, datos_actual):
    """Genera análisis comparativo entre dos sesiones"""
    resultados = []
    total_anterior = 0
    total_actual = 0
    jugadores_activos = []
    jugadores_inactivos = []
    
    datos_ordenados = sorted(datos_actual.items(), key=lambda x: x[1], reverse=True)
    puntos_lider = datos_ordenados[0][1] if datos_ordenados else 0
    
    diferencias = {}
    for jugador, puntos_actual in datos_actual.items():
        puntos_anterior = datos_anterior.get(jugador, 0)
        diferencias[jugador] = puntos_actual - puntos_anterior
    
    max_ganado = max(diferencias.values()) if diferencias else 0
    
    for rango, (jugador, puntos_actual) in enumerate(datos_ordenados, 1):
        puntos_anterior = datos_anterior.get(jugador, 0)
        ganado_sesion = puntos_actual - puntos_anterior
        deficit_vs_maximo = ganado_sesion - max_ganado
        distancia_lider = puntos_lider - puntos_actual
        
        total_anterior += puntos_anterior
        total_actual += puntos_actual
        
        if ganado_sesion > 0:
            estado = 'activo'
            jugadores_activos.append({'jugador': jugador, 'ganado': ganado_sesion})
        elif ganado_sesion == 0:
            estado = 'inactivo'
            jugadores_inactivos.append(jugador)
        else:
            estado = 'bajada'
        
        resultados.append({
            'rango': rango,
            'jugador': jugador,
            'actual': puntos_actual,
            'ganado_sesion': ganado_sesion,
            'deficit_vs_maximo': deficit_vs_maximo,
            'distancia_lider': distancia_lider,
            'estado': estado
        })
    
    jugadores_activos.sort(key=lambda x: x['ganado'], reverse=True)
    ganador_sesion = max(diferencias.items(), key=lambda x: x[1]) if diferencias else (None, 0)
    
    return {
        'tabla': resultados,
        'resumen': {
            'total_actual': total_actual,
            'total_ganado': total_actual - total_anterior,
            'max_ganado': max_ganado,
            'ganador_sesion': ganador_sesion[0]
        },
        'top_activos': jugadores_activos[:5],
        'inactivos': jugadores_inactivos,
        'lider': datos_ordenados[0] if datos_ordenados else None
    }


@app.route('/')
def index():
    tiene_anterior = datos_almacenados['anterior'] is not None
    return render_template_string(HTML_TEMPLATE, tiene_anterior=tiene_anterior, ocr_disponible=OCR_DISPONIBLE)


@app.route('/subir', methods=['POST'])
def subir_imagen():
    if 'imagen' not in request.files:
        return jsonify({'error': 'No se recibió imagen'}), 400
    
    archivo = request.files['imagen']
    tipo = request.form.get('tipo', 'nueva')
    
    if archivo.filename == '':
        return jsonify({'error': 'Archivo vacío'}), 400
    
    imagen_bytes = archivo.read()
    resultado = extraer_datos_imagen(imagen_bytes)
    
    if not resultado['exito']:
        return jsonify({
            'error': 'No se pudieron extraer datos. Usa entrada manual.',
            'textos': resultado['textos']
        }), 400
    
    if tipo == 'anterior' or datos_almacenados['anterior'] is None:
        datos_almacenados['anterior'] = resultado['datos']
        return jsonify({
            'mensaje': 'Sesión anterior guardada',
            'datos': resultado['datos'],
            'jugadores': len(resultado['datos']),
            'necesita_actual': True
        })
    else:
        datos_actual = resultado['datos']
        datos_anterior = datos_almacenados['anterior']
        analisis = analizar_comparativa(datos_anterior, datos_actual)
        datos_almacenados['anterior'] = datos_actual
        
        return jsonify({
            'mensaje': 'Análisis completado',
            'analisis': analisis,
            'datos_actual': datos_actual
        })


@app.route('/manual', methods=['POST'])
def entrada_manual():
    """Recibe datos ingresados manualmente"""
    data = request.get_json()
    datos = data.get('datos', {})
    tipo = data.get('tipo', 'nueva')
    
    if not datos:
        return jsonify({'error': 'No hay datos'}), 400
    
    # Convertir puntos a enteros
    datos_parsed = {}
    for jugador, puntos in datos.items():
        try:
            datos_parsed[jugador] = int(str(puntos).replace(',', '').replace('.', ''))
        except:
            pass
    
    if tipo == 'anterior' or datos_almacenados['anterior'] is None:
        datos_almacenados['anterior'] = datos_parsed
        return jsonify({
            'mensaje': 'Sesión anterior guardada',
            'jugadores': len(datos_parsed),
            'necesita_actual': True
        })
    else:
        analisis = analizar_comparativa(datos_almacenados['anterior'], datos_parsed)
        datos_almacenados['anterior'] = datos_parsed
        return jsonify({
            'mensaje': 'Análisis completado',
            'analisis': analisis
        })


@app.route('/reiniciar', methods=['POST'])
def reiniciar():
    datos_almacenados['anterior'] = None
    return jsonify({'mensaje': 'Reiniciado'})


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⛏️ Analizador de Puntos de Minería</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
        .subtitle { text-align: center; color: #00d4ff; margin-bottom: 30px; }

        .status-box {
            background: rgba(0,212,255,0.2);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
        }
        .status-box.success { background: rgba(0,255,136,0.2); border: 1px solid #00ff88; }
        .status-box.warning { background: rgba(255,193,7,0.2); border: 1px solid #ffc107; }

        .methods-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        @media (max-width: 768px) { .methods-container { grid-template-columns: 1fr; } }

        .upload-zone {
            background: rgba(255,255,255,0.1);
            border: 3px dashed #00d4ff;
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-zone:hover { background: rgba(0,212,255,0.2); transform: scale(1.02); }
        .upload-zone.dragover { background: rgba(0,212,255,0.3); border-color: #00ff88; }
        .upload-icon { font-size: 4em; margin-bottom: 20px; }
        .upload-text { font-size: 1.3em; margin-bottom: 10px; }
        .upload-hint { color: #888; }

        .paste-zone {
            background: linear-gradient(135deg, rgba(255,193,7,0.2), rgba(255,152,0,0.1));
            border: 3px dashed #ffc107;
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        .paste-zone:hover { background: rgba(255,193,7,0.3); transform: scale(1.02); }
        .paste-zone:focus { outline: none; border-color: #00ff88; background: rgba(0,255,136,0.2); }
        .paste-icon { font-size: 3em; margin-bottom: 15px; }
        .paste-text { font-size: 1.2em; color: #ffc107; margin-bottom: 8px; }
        .paste-hint { color: #888; font-size: 0.9em; }
        .keyboard-hint { background: rgba(0,0,0,0.3); padding: 3px 10px; border-radius: 5px; font-family: monospace; display: inline-block; margin: 3px; }

        .manual-section {
            background: rgba(255,255,255,0.07);
            border: 2px solid rgba(255,255,255,0.15);
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
        }
        .manual-toggle {
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            font-size: 1.1em;
            color: #00d4ff;
            margin-bottom: 0;
        }
        .manual-toggle.open { margin-bottom: 20px; }
        .manual-body { display: none; }
        .manual-body.open { display: block; }
        .manual-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        @media (max-width: 600px) { .manual-grid { grid-template-columns: 1fr; } }
        .manual-row { display: flex; gap: 8px; margin-bottom: 8px; }
        .manual-row input {
            flex: 1; padding: 8px 12px; border: none; border-radius: 8px;
            background: rgba(255,255,255,0.9); color: #333; font-size: 0.95em;
        }
        .manual-row input:first-child { flex: 0.7; }

        .btn {
            padding: 12px 30px; border: none; border-radius: 25px;
            cursor: pointer; font-size: 1em; margin: 5px; transition: all 0.3s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
        .btn-primary { background: linear-gradient(45deg, #00d4ff, #0099ff); color: white; }
        .btn-success { background: linear-gradient(45deg, #00ff88, #00cc6a); color: white; }
        .btn-danger { background: linear-gradient(45deg, #ff4757, #ff3838); color: white; }

        #preview-img { max-width: 300px; max-height: 200px; border-radius: 10px; margin-top: 15px; display: none; }

        .loading { display: none; text-align: center; padding: 40px; }
        .loading.show { display: block; }
        .spinner { border: 4px solid rgba(255,255,255,0.3); border-top: 4px solid #00d4ff; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 0 auto 20px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        .results { display: none; }
        .results.show { display: block; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

        .section-title { font-size: 1.5em; margin: 30px 0 15px; padding-bottom: 10px; border-bottom: 2px solid #00d4ff; }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: rgba(255,255,255,0.1); border-radius: 15px; padding: 20px; text-align: center; }
        .stat-value { font-size: 1.8em; font-weight: bold; color: #00ff88; }
        .stat-label { color: #aaa; margin-top: 5px; }

        table { width: 100%; border-collapse: collapse; background: rgba(255,255,255,0.05); border-radius: 15px; overflow: hidden; }
        th, td { padding: 15px; text-align: left; }
        th { background: rgba(0,212,255,0.3); font-weight: bold; }
        tr:nth-child(even) { background: rgba(255,255,255,0.05); }
        tr:hover { background: rgba(0,212,255,0.1); }

        .positive { color: #00ff88; }
        .negative { color: #ff4757; }
        .neutral { color: #ffc107; }

        .badge { display: inline-block; padding: 3px 10px; border-radius: 15px; font-size: 0.85em; }
        .badge-active { background: rgba(0,255,136,0.3); color: #00ff88; }
        .badge-inactive { background: rgba(255,193,7,0.3); color: #ffc107; }

        .top-players { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-top: 20px; }
        .player-card { background: linear-gradient(135deg, rgba(0,212,255,0.2), rgba(0,153,255,0.1)); border-radius: 10px; padding: 15px; display: flex; align-items: center; gap: 15px; }
        .player-rank { font-size: 2em; font-weight: bold; color: #ffd700; }
        .player-points { color: #00ff88; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⛏️ Analizador de Puntos de Minería</h1>
        <p class="subtitle">Sube o pega capturas de pantalla y compara tu progreso</p>

        <div id="status-box" class="status-box">
            <span id="status-text">📷 Sube o pega la imagen de la <strong>SESIÓN ANTERIOR</strong> para comenzar</span>
        </div>

        <!-- Métodos de entrada de imagen -->
        <div class="methods-container">
            <div class="paste-zone" id="paste-zone" tabindex="0">
                <div class="paste-icon">📋</div>
                <div class="paste-text">Pegar desde Portapapeles</div>
                <div class="paste-hint">
                    Haz clic aquí y presiona <span class="keyboard-hint">Ctrl+V</span><br>
                    o usa <span class="keyboard-hint">Win+Shift+S</span> para capturar
                </div>
            </div>
            <div class="upload-zone" id="upload-zone">
                <div class="upload-icon">📤</div>
                <div class="upload-text">Subir Archivo</div>
                <div class="upload-hint">Arrastra o haz clic para seleccionar</div>
                <input type="file" id="file-input" accept="image/*" style="display:none;">
            </div>
        </div>

        <div style="text-align:center; margin-bottom: 15px;">
            <img id="preview-img" src="" alt="Preview">
        </div>

        <!-- Entrada manual (colapsable) -->
        <div class="manual-section">
            <div class="manual-toggle" id="manual-toggle" onclick="toggleManual()">
                <span>📝</span>
                <span>Entrada Manual (sin imagen)</span>
                <span id="toggle-arrow">▼</span>
            </div>
            <div class="manual-body" id="manual-body">
                <div class="manual-grid">
                    <div>
                        <div class="manual-row"><input type="text" id="j1" placeholder="1. Jugador"><input type="text" id="p1" placeholder="Puntos"></div>
                        <div class="manual-row"><input type="text" id="j2" placeholder="2. Jugador"><input type="text" id="p2" placeholder="Puntos"></div>
                        <div class="manual-row"><input type="text" id="j3" placeholder="3. Jugador"><input type="text" id="p3" placeholder="Puntos"></div>
                        <div class="manual-row"><input type="text" id="j4" placeholder="4. Jugador"><input type="text" id="p4" placeholder="Puntos"></div>
                        <div class="manual-row"><input type="text" id="j5" placeholder="5. Jugador"><input type="text" id="p5" placeholder="Puntos"></div>
                    </div>
                    <div>
                        <div class="manual-row"><input type="text" id="j6" placeholder="6. Jugador"><input type="text" id="p6" placeholder="Puntos"></div>
                        <div class="manual-row"><input type="text" id="j7" placeholder="7. Jugador"><input type="text" id="p7" placeholder="Puntos"></div>
                        <div class="manual-row"><input type="text" id="j8" placeholder="8. Jugador"><input type="text" id="p8" placeholder="Puntos"></div>
                        <div class="manual-row"><input type="text" id="j9" placeholder="9. Jugador"><input type="text" id="p9" placeholder="Puntos"></div>
                        <div class="manual-row"><input type="text" id="j10" placeholder="10. Jugador"><input type="text" id="p10" placeholder="Puntos"></div>
                    </div>
                </div>
                <div style="text-align:center; margin-top: 15px;">
                    <button class="btn btn-success" onclick="enviarManual()">✅ Guardar Datos Manuales</button>
                </div>
            </div>
        </div>

        <div style="text-align:center; margin-bottom: 20px;">
            <button class="btn btn-danger" onclick="reiniciar()">🔄 Reiniciar</button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Procesando...</p>
        </div>

        <div class="results" id="results">
            <h2 class="section-title">📊 Resumen General</h2>
            <div class="stats-grid" id="stats-grid"></div>

            <h2 class="section-title">🏆 Top Activos</h2>
            <div class="top-players" id="top-players"></div>

            <h2 class="section-title">📋 Tabla Comparativa</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Jugador</th>
                        <th>Puntos Totales</th>
                        <th>Ganados (Sesión)</th>
                        <th>Déficit vs. Máximo</th>
                        <th>Dist. al Líder</th>
                        <th>Estado</th>
                    </tr>
                </thead>
                <tbody id="table-body"></tbody>
            </table>

            <h2 class="section-title" id="inactive-title" style="display:none;">⏸️ Sin Actividad</h2>
            <div id="inactive-list"></div>
        </div>
    </div>

    <script>
        let tieneAnterior = {{ 'true' if tiene_anterior else 'false' }};

        function actualizarEstado() {
            const box = document.getElementById('status-box');
            const txt = document.getElementById('status-text');
            if (tieneAnterior) {
                txt.innerHTML = '✅ Sesión anterior cargada. Ahora sube o pega la <strong>SESIÓN ACTUAL</strong>';
                box.className = 'status-box success';
            } else {
                txt.innerHTML = '📷 Sube o pega la imagen de la <strong>SESIÓN ANTERIOR</strong> para comenzar';
                box.className = 'status-box';
            }
        }
        actualizarEstado();

        // Toggle entrada manual
        function toggleManual() {
            const body = document.getElementById('manual-body');
            const arrow = document.getElementById('toggle-arrow');
            const toggle = document.getElementById('manual-toggle');
            body.classList.toggle('open');
            toggle.classList.toggle('open');
            arrow.textContent = body.classList.contains('open') ? '▲' : '▼';
        }

        // Pegar Ctrl+V en toda la página
        document.addEventListener('paste', (e) => {
            for (let item of e.clipboardData.items) {
                if (item.type.indexOf('image') !== -1) {
                    procesarArchivo(item.getAsFile());
                    e.preventDefault();
                    break;
                }
            }
        });

        document.getElementById('paste-zone').addEventListener('click', () => {
            document.getElementById('paste-zone').focus();
            alert('✅ Zona activa. Presiona Ctrl+V para pegar la imagen.');
        });

        // Drag & drop
        const uploadZone = document.getElementById('upload-zone');
        uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault(); uploadZone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) procesarArchivo(file);
        });
        uploadZone.addEventListener('click', () => document.getElementById('file-input').click());
        document.getElementById('file-input').addEventListener('change', (e) => {
            if (e.target.files[0]) procesarArchivo(e.target.files[0]);
        });

        function procesarArchivo(file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = document.getElementById('preview-img');
                img.src = e.target.result;
                img.style.display = 'block';
            };
            reader.readAsDataURL(file);
            subirImagen(file);
        }

        function subirImagen(file) {
            document.getElementById('loading').classList.add('show');
            document.getElementById('results').classList.remove('show');
            const formData = new FormData();
            formData.append('imagen', file);
            formData.append('tipo', tieneAnterior ? 'nueva' : 'anterior');
            fetch('/subir', { method: 'POST', body: formData })
            .then(r => r.json())
            .then(data => {
                document.getElementById('loading').classList.remove('show');
                if (data.error) { alert('Error: ' + data.error); return; }
                if (data.necesita_actual) {
                    tieneAnterior = true;
                    actualizarEstado();
                    document.getElementById('preview-img').style.display = 'none';
                    alert('✅ Sesión anterior guardada con ' + data.jugadores + ' jugadores.\\n\\nAhora pega o sube la sesión ACTUAL.');
                } else {
                    mostrarResultados(data.analisis);
                }
            })
            .catch(err => { document.getElementById('loading').classList.remove('show'); alert('Error: ' + err); });
        }

        function enviarManual() {
            const datos = {};
            for (let i = 1; i <= 10; i++) {
                const j = document.getElementById('j' + i).value.trim();
                const p = document.getElementById('p' + i).value.trim();
                if (j && p) datos[j] = p;
            }
            if (Object.keys(datos).length < 3) { alert('Ingresa al menos 3 jugadores'); return; }
            document.getElementById('loading').classList.add('show');
            fetch('/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ datos, tipo: tieneAnterior ? 'nueva' : 'anterior' })
            })
            .then(r => r.json())
            .then(data => {
                document.getElementById('loading').classList.remove('show');
                if (data.necesita_actual) {
                    tieneAnterior = true;
                    actualizarEstado();
                    limpiarCampos();
                    alert('✅ Sesión anterior guardada. Ahora ingresa la SESIÓN ACTUAL.');
                } else {
                    mostrarResultados(data.analisis);
                }
            });
        }

        function limpiarCampos() {
            for (let i = 1; i <= 10; i++) {
                document.getElementById('j' + i).value = '';
                document.getElementById('p' + i).value = '';
            }
        }

        function mostrarResultados(analisis) {
            document.getElementById('results').classList.add('show');
            document.getElementById('preview-img').style.display = 'none';

            document.getElementById('stats-grid').innerHTML = `
                <div class="stat-card"><div class="stat-value">${formatNumber(analisis.resumen.total_actual)}</div><div class="stat-label">Puntos Totales</div></div>
                <div class="stat-card"><div class="stat-value positive">+${formatNumber(analisis.resumen.total_ganado)}</div><div class="stat-label">Puntos Ganados (Total)</div></div>
                <div class="stat-card"><div class="stat-value">👑 ${analisis.lider ? analisis.lider[0] : 'N/A'}</div><div class="stat-label">Líder</div></div>
                <div class="stat-card"><div class="stat-value">🏆 ${analisis.resumen.ganador_sesion || 'N/A'}</div><div class="stat-label">Más Ganó (+${formatNumber(analisis.resumen.max_ganado)})</div></div>
            `;

            document.getElementById('top-players').innerHTML = analisis.top_activos.map((p, i) =>
                `<div class="player-card"><div class="player-rank">${['🥇','🥈','🥉','4️⃣','5️⃣'][i]}</div><div><strong>${p.jugador}</strong><br><span class="player-points">+${formatNumber(p.ganado)} pts</span></div></div>`
            ).join('');

            document.getElementById('table-body').innerHTML = analisis.tabla.map(row => `
                <tr>
                    <td>${row.rango}</td>
                    <td><strong>${row.jugador}</strong></td>
                    <td>${formatNumber(row.actual)}</td>
                    <td class="${row.ganado_sesion > 0 ? 'positive' : row.ganado_sesion < 0 ? 'negative' : 'neutral'}">${row.ganado_sesion > 0 ? '+' : ''}${formatNumber(row.ganado_sesion)}</td>
                    <td class="${row.deficit_vs_maximo < 0 ? 'negative' : 'positive'}">${formatNumber(row.deficit_vs_maximo)}</td>
                    <td class="${row.distancia_lider > 0 ? 'negative' : 'positive'}">${row.distancia_lider > 0 ? '-' : ''}${formatNumber(row.distancia_lider)}</td>
                    <td><span class="badge ${row.estado === 'activo' ? 'badge-active' : 'badge-inactive'}">${row.estado === 'activo' ? '📈 Activo' : '⏸️ Inactivo'}</span></td>
                </tr>
            `).join('');

            if (analisis.inactivos && analisis.inactivos.length > 0) {
                document.getElementById('inactive-title').style.display = 'block';
                document.getElementById('inactive-list').innerHTML = analisis.inactivos.map(j =>
                    `<span class="badge badge-inactive" style="margin:5px;">${j}</span>`
                ).join('');
            } else {
                document.getElementById('inactive-title').style.display = 'none';
            }

            actualizarEstado();
        }

        function formatNumber(n) { return n.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ","); }

        function reiniciar() {
            if (confirm('¿Reiniciar todo? Se perderán los datos guardados.')) {
                fetch('/reiniciar', { method: 'POST' }).then(() => {
                    tieneAnterior = false;
                    actualizarEstado();
                    document.getElementById('results').classList.remove('show');
                    document.getElementById('preview-img').style.display = 'none';
                    document.getElementById('inactive-title').style.display = 'none';
                    limpiarCampos();
                });
            }
        }
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
