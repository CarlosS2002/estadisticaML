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
    Extrae datos usando Tesseract (más ligero que EasyOCR)
    """
    if not OCR_DISPONIBLE:
        return {'datos': {}, 'textos': [], 'exito': False, 'error': 'OCR no disponible'}
    
    try:
        imagen = Image.open(BytesIO(imagen_bytes))
        if imagen.mode == 'RGBA':
            imagen = imagen.convert('RGB')
        
        # Preprocesamiento
        width, height = imagen.size
        imagen = imagen.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        
        enhancer = ImageEnhance.Contrast(imagen)
        imagen = enhancer.enhance(2.0)
        
        # Convertir a escala de grises
        imagen_gray = imagen.convert('L')
        
        # Binarizar
        imagen_np = np.array(imagen_gray)
        threshold = 100
        imagen_np = np.where(imagen_np > threshold, 255, 0).astype(np.uint8)
        imagen_bin = Image.fromarray(imagen_np)
        
        # OCR con Tesseract
        texto = pytesseract.image_to_string(imagen_bin, config='--psm 6')
        
        lineas = texto.strip().split('\n')
        textos_detectados = [l.strip() for l in lineas if l.strip()]
        
        print(f"📝 Textos: {textos_detectados}")
        
        # Parsear
        datos = {}
        jugador_actual = None
        
        for texto in textos_detectados:
            texto_limpio = re.sub(r'^[\d]+[.\s\-:]*', '', texto).strip()
            texto_limpio = re.sub(r'[?!.,;:]+$', '', texto_limpio).strip()
            
            # Solo número grande
            solo_numero = texto.replace(' ', '').replace('.', '').replace(',', '')
            if re.match(r'^[\d]+$', solo_numero) and len(solo_numero) >= 6:
                puntos = int(solo_numero)
                if jugador_actual and puntos > 100000:
                    datos[jugador_actual] = puntos
                    jugador_actual = None
                continue
            
            # Nombre de jugador
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', texto_limpio) and len(texto_limpio) > 2:
                jugador_actual = corregir_nombre(texto_limpio)
        
        return {'datos': datos, 'textos': textos_detectados, 'exito': len(datos) > 0}
        
    except Exception as e:
        print(f"Error OCR: {e}")
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
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; font-size: 2em; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #00d4ff; margin-bottom: 20px; }
        
        .tabs { display: flex; justify-content: center; margin-bottom: 20px; }
        .tab { padding: 10px 30px; background: rgba(255,255,255,0.1); cursor: pointer; border-radius: 10px 10px 0 0; }
        .tab.active { background: rgba(0,212,255,0.3); }
        
        .input-section { background: rgba(255,255,255,0.1); padding: 20px; border-radius: 15px; margin-bottom: 20px; }
        
        .upload-zone {
            border: 3px dashed #00d4ff;
            border-radius: 15px;
            padding: 30px;
            text-align: center;
            cursor: pointer;
            margin-bottom: 15px;
        }
        .upload-zone:hover { background: rgba(0,212,255,0.1); }
        
        .manual-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .manual-row {
            display: flex;
            gap: 10px;
            margin-bottom: 8px;
        }
        .manual-row input {
            flex: 1;
            padding: 8px;
            border: none;
            border-radius: 5px;
            background: rgba(255,255,255,0.9);
            color: #333;
        }
        .manual-row input:first-child { flex: 0.6; }
        
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            margin: 5px;
        }
        .btn-primary { background: linear-gradient(45deg, #00d4ff, #0099ff); color: white; }
        .btn-danger { background: linear-gradient(45deg, #ff4757, #ff3838); color: white; }
        .btn-success { background: linear-gradient(45deg, #00ff88, #00cc6a); color: white; }
        
        .status-box {
            background: rgba(0,212,255,0.2);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 20px;
        }
        .status-box.success { background: rgba(0,255,136,0.2); border: 1px solid #00ff88; }
        
        .results { display: none; }
        .results.show { display: block; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-value { font-size: 1.5em; font-weight: bold; color: #00ff88; }
        .stat-label { color: #aaa; font-size: 0.9em; }
        
        table { width: 100%; border-collapse: collapse; background: rgba(255,255,255,0.05); border-radius: 10px; overflow: hidden; }
        th, td { padding: 12px; text-align: left; }
        th { background: rgba(0,212,255,0.3); }
        tr:nth-child(even) { background: rgba(255,255,255,0.05); }
        
        .positive { color: #00ff88; }
        .negative { color: #ff4757; }
        .neutral { color: #ffc107; }
        
        .section-title { font-size: 1.3em; margin: 25px 0 15px; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }
        
        .top-players { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
        .player-card { background: rgba(0,212,255,0.2); padding: 12px; border-radius: 8px; display: flex; align-items: center; gap: 10px; }
        .player-rank { font-size: 1.5em; }
        
        #file-input { display: none; }
        
        .loading { display: none; text-align: center; padding: 30px; }
        .loading.show { display: block; }
        .spinner { border: 4px solid rgba(255,255,255,0.3); border-top: 4px solid #00d4ff; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 15px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>⛏️ Analizador de Puntos de Minería</h1>
        <p class="subtitle">Compara tu progreso entre sesiones</p>
        
        <div id="status-box" class="status-box">
            <span id="status-text">📝 Ingresa los datos de la <strong>SESIÓN ANTERIOR</strong></span>
        </div>
        
        <div class="tabs">
            <div class="tab active" onclick="cambiarTab('manual')">📝 Entrada Manual</div>
            <div class="tab" onclick="cambiarTab('imagen')" {% if not ocr_disponible %}style="opacity:0.5"{% endif %}>📷 Subir Imagen</div>
        </div>
        
        <div id="tab-manual" class="input-section">
            <h3 style="margin-bottom: 15px;">Ingresa los datos del ranking:</h3>
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
            <div style="text-align: center; margin-top: 15px;">
                <button class="btn btn-success" onclick="enviarManual()">✅ Guardar Datos</button>
            </div>
        </div>
        
        <div id="tab-imagen" class="input-section" style="display: none;">
            <div class="upload-zone" onclick="document.getElementById('file-input').click()">
                <div style="font-size: 3em;">📤</div>
                <div>Haz clic para subir imagen</div>
                <input type="file" id="file-input" accept="image/*">
            </div>
            {% if not ocr_disponible %}
            <p style="color: #ffc107; text-align: center;">⚠️ OCR no disponible en este servidor. Usa entrada manual.</p>
            {% endif %}
        </div>
        
        <div style="text-align: center;">
            <button class="btn btn-danger" onclick="reiniciar()">🔄 Reiniciar</button>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Procesando...</p>
        </div>
        
        <div class="results" id="results">
            <h2 class="section-title">📊 Resumen</h2>
            <div class="stats-grid" id="stats-grid"></div>
            
            <h2 class="section-title">🏆 Top Activos</h2>
            <div class="top-players" id="top-players"></div>
            
            <h2 class="section-title">📋 Tabla Comparativa</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Jugador</th>
                        <th>Puntos</th>
                        <th>Ganados</th>
                        <th>Déficit vs Max</th>
                        <th>Dist. Líder</th>
                        <th>Estado</th>
                    </tr>
                </thead>
                <tbody id="table-body"></tbody>
            </table>
        </div>
    </div>
    
    <script>
        let tieneAnterior = {{ 'true' if tiene_anterior else 'false' }};
        
        function cambiarTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.input-section').forEach(s => s.style.display = 'none');
            event.target.classList.add('active');
            document.getElementById('tab-' + tab).style.display = 'block';
        }
        
        function enviarManual() {
            const datos = {};
            for (let i = 1; i <= 10; i++) {
                const jugador = document.getElementById('j' + i).value.trim();
                const puntos = document.getElementById('p' + i).value.trim();
                if (jugador && puntos) {
                    datos[jugador] = puntos;
                }
            }
            
            if (Object.keys(datos).length < 3) {
                alert('Ingresa al menos 3 jugadores');
                return;
            }
            
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
                    document.getElementById('status-text').innerHTML = '✅ Sesión anterior guardada. Ingresa la <strong>SESIÓN ACTUAL</strong>';
                    document.getElementById('status-box').className = 'status-box success';
                    limpiarCampos();
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
        
        document.getElementById('file-input').addEventListener('change', function(e) {
            if (e.target.files[0]) {
                const formData = new FormData();
                formData.append('imagen', e.target.files[0]);
                formData.append('tipo', tieneAnterior ? 'nueva' : 'anterior');
                
                document.getElementById('loading').classList.add('show');
                
                fetch('/subir', { method: 'POST', body: formData })
                .then(r => r.json())
                .then(data => {
                    document.getElementById('loading').classList.remove('show');
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    if (data.necesita_actual) {
                        tieneAnterior = true;
                        document.getElementById('status-text').innerHTML = '✅ Guardado. Ingresa <strong>SESIÓN ACTUAL</strong>';
                        document.getElementById('status-box').className = 'status-box success';
                    } else {
                        mostrarResultados(data.analisis);
                    }
                });
            }
        });
        
        function mostrarResultados(analisis) {
            document.getElementById('results').classList.add('show');
            
            document.getElementById('stats-grid').innerHTML = `
                <div class="stat-card"><div class="stat-value">${formatNumber(analisis.resumen.total_actual)}</div><div class="stat-label">Puntos Totales</div></div>
                <div class="stat-card"><div class="stat-value positive">+${formatNumber(analisis.resumen.total_ganado)}</div><div class="stat-label">Ganados</div></div>
                <div class="stat-card"><div class="stat-value">👑 ${analisis.lider ? analisis.lider[0] : ''}</div><div class="stat-label">Líder</div></div>
                <div class="stat-card"><div class="stat-value">🏆 ${analisis.resumen.ganador_sesion || ''}</div><div class="stat-label">Más Ganó (+${formatNumber(analisis.resumen.max_ganado)})</div></div>
            `;
            
            document.getElementById('top-players').innerHTML = analisis.top_activos.map((p, i) => 
                `<div class="player-card"><div class="player-rank">${['🥇','🥈','🥉','4️⃣','5️⃣'][i]}</div><div><strong>${p.jugador}</strong><br><span class="positive">+${formatNumber(p.ganado)}</span></div></div>`
            ).join('');
            
            document.getElementById('table-body').innerHTML = analisis.tabla.map(row => `
                <tr>
                    <td>${row.rango}</td>
                    <td><strong>${row.jugador}</strong></td>
                    <td>${formatNumber(row.actual)}</td>
                    <td class="${row.ganado_sesion > 0 ? 'positive' : 'neutral'}">${row.ganado_sesion > 0 ? '+' : ''}${formatNumber(row.ganado_sesion)}</td>
                    <td class="${row.deficit_vs_maximo < 0 ? 'negative' : 'positive'}">${formatNumber(row.deficit_vs_maximo)}</td>
                    <td class="negative">${row.distancia_lider > 0 ? '-' : ''}${formatNumber(row.distancia_lider)}</td>
                    <td>${row.estado === 'activo' ? '📈' : '⏸️'}</td>
                </tr>
            `).join('');
            
            document.getElementById('status-text').innerHTML = '✅ ¡Listo! Ingresa otra sesión para comparar';
        }
        
        function formatNumber(n) { return n.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ","); }
        
        function reiniciar() {
            fetch('/reiniciar', { method: 'POST' }).then(() => {
                tieneAnterior = false;
                document.getElementById('status-text').innerHTML = '📝 Ingresa los datos de la <strong>SESIÓN ANTERIOR</strong>';
                document.getElementById('status-box').className = 'status-box';
                document.getElementById('results').classList.remove('show');
                limpiarCampos();
            });
        }
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
