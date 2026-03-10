"""
Analizador de Puntos de Minería - Versión Web
Sube imágenes y obtén análisis visual comparativo
"""

from flask import Flask, render_template, request, jsonify, session
import re
import os
from io import BytesIO
from datetime import datetime

from PIL import Image

app = Flask(__name__)
app.secret_key = 'mineria_analyzer_2024'

reader = None
ocr_status = {
    'ok': False,
    'error': None
}


def inicializar_ocr():
    """Inicializa OCR bajo demanda para evitar caídas al boot en PaaS."""
    global reader

    if reader is not None:
        return True

    if ocr_status['error'] is not None:
        return False

    try:
        print("🔄 Iniciando motor OCR (lazy init)...")
        import easyocr
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        ocr_status['ok'] = True
        print("✅ Motor OCR listo!")
        return True
    except Exception as e:
        ocr_status['ok'] = False
        ocr_status['error'] = str(e)
        print(f"❌ OCR no disponible: {e}")
        return False

# Almacén de datos de sesiones
datos_almacenados = {
    'anterior': None,
    'historial': []
}


def extraer_datos_imagen(imagen_bytes):
    """
    Extrae solo los puntos de una imagen y los asigna a posiciones 1-10
    Simplificado para evitar errores de OCR con nombres
    """
    try:
        if not inicializar_ocr():
            return {
                'datos': {},
                'textos': [],
                'exito': False,
                'error': f"OCR no disponible en el servidor: {ocr_status['error']}"
            }

        # Guardar imagen temporalmente
        imagen = Image.open(BytesIO(imagen_bytes))
        if imagen.mode == 'RGBA':
            imagen = imagen.convert('RGB')
        
        # === PREPROCESAMIENTO SIMPLE ===
        import numpy as np
        from PIL import ImageEnhance
        
        # 1. Aumentar tamaño solo si la imagen es pequeña
        width, height = imagen.size
        if width < 600:
            imagen_grande = imagen.resize((min(width * 2, 800), min(height * 2, 800)), Image.Resampling.LANCZOS)
        else:
            imagen_grande = imagen
        
        # 2. Aumentar contraste
        enhancer = ImageEnhance.Contrast(imagen_grande)
        imagen_contraste = enhancer.enhance(1.8)
        
        # 3. Aumentar nitidez
        enhancer = ImageEnhance.Sharpness(imagen_contraste)
        imagen_nitida = enhancer.enhance(1.5)
        
        # Guardar para OCR
        temp_path = "temp_upload_color.png"
        imagen_nitida.save(temp_path)
        
        # OCR
        resultados = reader.readtext(temp_path, paragraph=False, detail=1)
        
        textos_detectados = []
        for (bbox, texto, prob) in resultados:
            textos_detectados.append(texto.strip())
        
        print(f"📝 Textos detectados ({len(textos_detectados)}): {textos_detectados}")
        
        # Extraer SOLO números grandes (puntos) - ordenados por aparición
        todos_los_numeros = []
        
        for texto in textos_detectados:
            # Limpiar caracteres que el OCR confunde con números
            texto_limpio = texto.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
            
            # Buscar secuencias de dígitos en el texto
            numeros_encontrados = re.findall(r'\d+', texto_limpio)
            
            for num_str in numeros_encontrados:
                if len(num_str) >= 6:  # Al menos 6 dígitos
                    puntos = int(num_str)
                    if puntos >= 100000:  # Puntos válidos de minería (>= para incluir 100000)
                        todos_los_numeros.append(puntos)
                        print(f"  ✓ Encontrado: {texto} -> {puntos}")
        
        # Asignar a posiciones 1-10
        datos = {}
        for i, puntos in enumerate(todos_los_numeros[:10], 1):
            datos[f"Pos{i}"] = puntos
        
        # Limpiar archivos temporales
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        print(f"📊 Números encontrados: {len(todos_los_numeros)}")
        print(f"✅ Datos extraídos: {datos}")
        
        return {
            'datos': datos,
            'textos': textos_detectados,
            'exito': len(datos) > 0
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            'datos': {},
            'textos': [],
            'exito': False,
            'error': str(e)
        }


def analizar_comparativa(datos_anterior, datos_actual):
    """
    Genera análisis comparativo entre dos sesiones
    """
    resultados = []
    total_anterior = 0
    total_actual = 0
    jugadores_activos = []
    jugadores_inactivos = []
    
    # Ordenar por puntos actuales
    datos_ordenados = sorted(datos_actual.items(), key=lambda x: x[1], reverse=True)
    
    # Obtener puntos del líder para calcular distancia al líder
    puntos_lider = datos_ordenados[0][1] if datos_ordenados else 0
    
    # Primero calcular todas las diferencias para encontrar el máximo ganado
    diferencias = {}
    for jugador, puntos_actual in datos_actual.items():
        puntos_anterior = datos_anterior.get(jugador, 0)
        diferencias[jugador] = puntos_actual - puntos_anterior
    
    # Máximo ganado en la sesión (para calcular déficit vs máximo)
    max_ganado = max(diferencias.values()) if diferencias else 0
    
    for rango, (jugador, puntos_actual) in enumerate(datos_ordenados, 1):
        puntos_anterior = datos_anterior.get(jugador, 0)
        ganado_sesion = puntos_actual - puntos_anterior
        
        # Déficit vs Máximo = diferencia entre lo que ganó este jugador y el que más ganó
        deficit_vs_maximo = ganado_sesion - max_ganado
        
        # Distancia al líder (en puntos totales)
        distancia_lider = puntos_lider - puntos_actual
        
        # Diferencia al siguiente (lo que le falta para alcanzar al de arriba)
        if rango == 1:
            diferencia_siguiente = 0
        else:
            diferencia_siguiente = datos_ordenados[rango - 2][1] - puntos_actual
        
        if puntos_anterior > 0:
            porcentaje = (ganado_sesion / puntos_anterior) * 100
        else:
            porcentaje = 0
        
        total_anterior += puntos_anterior
        total_actual += puntos_actual
        
        if ganado_sesion > 0:
            estado = 'activo'
            jugadores_activos.append({
                'jugador': jugador,
                'ganado': ganado_sesion,
                'porcentaje': porcentaje
            })
        elif ganado_sesion == 0:
            estado = 'inactivo'
            jugadores_inactivos.append(jugador)
        else:
            estado = 'bajada'
        
        resultados.append({
            'rango': rango,
            'jugador': jugador,
            'anterior': puntos_anterior,
            'actual': puntos_actual,
            'ganado_sesion': ganado_sesion,
            'deficit_vs_maximo': deficit_vs_maximo,
            'distancia_lider': distancia_lider,
            'diferencia_siguiente': diferencia_siguiente,
            'porcentaje': round(porcentaje, 2),
            'estado': estado
        })
    
    # Ordenar activos por puntos ganados
    jugadores_activos.sort(key=lambda x: x['ganado'], reverse=True)
    
    # Encontrar quién ganó más en la sesión
    ganador_sesion = max(diferencias.items(), key=lambda x: x[1]) if diferencias else (None, 0)
    
    return {
        'tabla': resultados,
        'resumen': {
            'total_anterior': total_anterior,
            'total_actual': total_actual,
            'total_ganado': total_actual - total_anterior,
            'promedio': (total_actual - total_anterior) // len(datos_actual) if datos_actual else 0,
            'max_ganado': max_ganado,
            'ganador_sesion': ganador_sesion[0]
        },
        'top_activos': jugadores_activos[:5],
        'inactivos': jugadores_inactivos,
        'lider': datos_ordenados[0] if datos_ordenados else None
    }


def generar_analisis_ia(analisis):
    """
    Agente IA basado en reglas que analiza patrones y genera conclusiones inteligentes.
    """
    conclusiones = []
    alertas = []
    predicciones = []

    tabla = analisis['tabla']
    resumen = analisis['resumen']

    if not tabla:
        return {'conclusiones': [], 'alertas': [], 'predicciones': []}

    max_ganado = resumen['max_ganado']
    total_jugadores = len(tabla)
    activos = [r for r in tabla if r['estado'] == 'activo']
    inactivos = [r for r in tabla if r['estado'] == 'inactivo']

    # ── CONCLUSIONES GENERALES ──────────────────────────────────────────────
    pct_activos = len(activos) / total_jugadores * 100
    if pct_activos >= 80:
        conclusiones.append(f"💪 Sesión muy activa: {len(activos)} de {total_jugadores} jugadores farmaron puntos ({pct_activos:.0f}% participación).")
    elif pct_activos >= 50:
        conclusiones.append(f"⚡ Sesión moderada: {len(activos)} de {total_jugadores} jugadores fueron activos ({pct_activos:.0f}%).")
    else:
        conclusiones.append(f"😴 Sesión baja: solo {len(activos)} de {total_jugadores} jugadores activos. Alta inactividad general.")

    if activos and len(activos) > 1:
        max_act = max(activos, key=lambda x: x['ganado_sesion'])
        min_act = min(activos, key=lambda x: x['ganado_sesion'])
        brecha = max_act['ganado_sesion'] - min_act['ganado_sesion']
        if max_ganado > 0 and brecha > max_ganado * 0.4:
            conclusiones.append(
                f"📊 Gran disparidad de rendimiento: {max_act['jugador']} ganó {max_act['ganado_sesion']:,} pts "
                f"vs {min_act['jugador']} con {min_act['ganado_sesion']:,} pts."
            )
        else:
            conclusiones.append("📈 Rendimiento parejo entre los jugadores activos esta sesión.")

    if inactivos:
        conclusiones.append(f"⏸️ Jugadores sin actividad esta sesión: {', '.join(inactivos)}.")

    # ── ALERTAS Y PREDICCIONES POR JUGADOR ─────────────────────────────────
    for row in tabla:
        jugador = row['jugador']
        rango = row['rango']
        ganado = row['ganado_sesion']
        dif_siguiente = row['diferencia_siguiente']
        puntos_actuales = row['actual']

        # Peligro de perder posición ante el de abajo
        if rango < total_jugadores:
            jugador_abajo = tabla[rango]  # rango es 1-based, índice es rango
            ganado_abajo = jugador_abajo['ganado_sesion']
            diferencia_actual = puntos_actuales - jugador_abajo['actual']

            if diferencia_actual > 0:
                if ganado == 0 and ganado_abajo > 0:
                    sesiones = diferencia_actual / ganado_abajo
                    if sesiones < 6:
                        alertas.append({
                            'tipo': 'peligro',
                            'mensaje': f"⚠️ {jugador} (#{rango}) está en peligro: estuvo inactivo y "
                                       f"{jugador_abajo['jugador']} (#{rango+1}) lo alcanzaría en ~{sesiones:.0f} sesión(es)."
                        })
                elif ganado > 0 and ganado_abajo > ganado:
                    ritmo_diff = ganado_abajo - ganado
                    sesiones = diferencia_actual / ritmo_diff
                    if sesiones < 8:
                        alertas.append({
                            'tipo': 'peligro',
                            'mensaje': f"⚠️ {jugador} (#{rango}) pierde terreno: {jugador_abajo['jugador']} "
                                       f"gana {ritmo_diff:,} pts/sesión más y lo alcanzaría en ~{sesiones:.0f} sesión(es)."
                        })

        # Potencial de subir posición
        if rango > 1 and ganado > 0 and dif_siguiente > 0:
            jugador_arriba = tabla[rango - 2]
            ganado_arriba = jugador_arriba['ganado_sesion']
            ventaja_ritmo = ganado - ganado_arriba
            if ventaja_ritmo > 0:
                sesiones = dif_siguiente / ventaja_ritmo
                if sesiones <= 12:
                    predicciones.append({
                        'tipo': 'overtake',
                        'mensaje': f"🚀 {jugador} (#{rango}) podría superar a {jugador_arriba['jugador']} "
                                   f"(#{rango-1}) en ~{sesiones:.0f} sesión(es) si mantiene el ritmo."
                    })

        # Inactivo con ventaja pequeña sobre el de abajo
        if ganado == 0 and rango > 1 and max_ganado > 0 and dif_siguiente < max_ganado * 0.6:
            alertas.append({
                'tipo': 'advertencia',
                'mensaje': f"😴 {jugador} (#{rango}) estuvo inactivo y su ventaja sobre el siguiente "
                           f"es solo de {dif_siguiente:,} pts — vulnerable si sigue sin farmar."
            })

    # Amenaza al liderazgo
    lider = tabla[0]
    if lider['ganado_sesion'] == 0 and activos:
        for activo in sorted(activos, key=lambda x: -x['ganado_sesion']):
            if activo['rango'] > 1 and activo['distancia_lider'] > 0:
                sesiones = activo['distancia_lider'] / activo['ganado_sesion']
                if sesiones <= 15:
                    predicciones.append({
                        'tipo': 'liderazgo',
                        'mensaje': f"👑 Si el líder sigue inactivo, {activo['jugador']} "
                                   f"(#{activo['rango']}) podría tomar el liderazgo en ~{sesiones:.0f} sesión(es)."
                    })
                    break

    return {
        'conclusiones': conclusiones,
        'alertas': alertas[:6],
        'predicciones': predicciones[:6]
    }


@app.route('/')
def index():
    tiene_anterior = datos_almacenados['anterior'] is not None
    return render_template('index.html', tiene_anterior=tiene_anterior)


@app.route('/subir', methods=['POST'])
def subir_imagen():
    if 'imagen' not in request.files:
        return jsonify({'error': 'No se recibió imagen'}), 400
    
    archivo = request.files['imagen']
    tipo = request.form.get('tipo', 'nueva')  # 'anterior' o 'nueva'
    
    if archivo.filename == '':
        return jsonify({'error': 'Archivo vacío'}), 400
    
    # Leer imagen
    imagen_bytes = archivo.read()
    
    # Procesar con OCR
    resultado = extraer_datos_imagen(imagen_bytes)
    
    if not resultado['exito']:
        return jsonify({
            'error': 'No se pudieron extraer datos de la imagen',
            'textos': resultado['textos']
        }), 400
    
    # Guardar según el tipo
    if tipo == 'anterior' or datos_almacenados['anterior'] is None:
        datos_almacenados['anterior'] = resultado['datos']
        return jsonify({
            'mensaje': 'Sesión anterior guardada',
            'datos': resultado['datos'],
            'jugadores': len(resultado['datos']),
            'necesita_actual': True
        })
    else:
        # Tenemos anterior, esta es la actual - hacer análisis
        datos_actual = resultado['datos']
        datos_anterior = datos_almacenados['anterior']
        
        analisis = analizar_comparativa(datos_anterior, datos_actual)
        analisis['ia'] = generar_analisis_ia(analisis)

        # Guardar en historial
        datos_almacenados['historial'].append({
            'fecha': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'anterior': datos_anterior,
            'actual': datos_actual,
            'analisis': analisis
        })
        
        # La actual pasa a ser la anterior para la próxima comparación
        datos_almacenados['anterior'] = datos_actual
        
        return jsonify({
            'mensaje': 'Análisis completado',
            'analisis': analisis,
            'datos_actual': datos_actual
        })


@app.route('/reiniciar', methods=['POST'])
def reiniciar():
    datos_almacenados['anterior'] = None
    return jsonify({'mensaje': 'Reiniciado correctamente'})


@app.route('/historial')
def historial():
    return jsonify(datos_almacenados['historial'])


# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⛏️ Analizador de Puntos de Minería</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1 {
            text-align: center;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }
        
        .subtitle {
            text-align: center;
            color: #00d4ff;
            margin-bottom: 30px;
        }
        
        .upload-zone {
            background: rgba(255,255,255,0.1);
            border: 3px dashed #00d4ff;
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 20px;
        }
        
        .upload-zone:hover {
            background: rgba(0,212,255,0.2);
            transform: scale(1.02);
        }
        
        .upload-zone.dragover {
            background: rgba(0,212,255,0.3);
            border-color: #00ff88;
        }
        
        .upload-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        
        .upload-text {
            font-size: 1.3em;
            margin-bottom: 10px;
        }
        
        .upload-hint {
            color: #888;
        }
        
        .paste-zone {
            background: linear-gradient(135deg, rgba(255,193,7,0.2), rgba(255,152,0,0.1));
            border: 3px dashed #ffc107;
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 30px;
        }
        
        .paste-zone:hover {
            background: rgba(255,193,7,0.3);
            transform: scale(1.02);
        }
        
        .paste-zone:focus {
            outline: none;
            border-color: #00ff88;
            background: rgba(0,255,136,0.2);
        }
        
        .paste-icon {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .paste-text {
            font-size: 1.2em;
            color: #ffc107;
        }
        
        .paste-hint {
            color: #888;
            font-size: 0.9em;
            margin-top: 5px;
        }
        
        .status-box {
            background: rgba(0,212,255,0.2);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .status-box.warning {
            background: rgba(255,193,7,0.2);
            border: 1px solid #ffc107;
        }
        
        .status-box.success {
            background: rgba(0,255,136,0.2);
            border: 1px solid #00ff88;
        }
        
        .btn {
            background: linear-gradient(45deg, #00d4ff, #0099ff);
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            color: white;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
            margin: 5px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,212,255,0.4);
        }
        
        .btn-danger {
            background: linear-gradient(45deg, #ff4757, #ff3838);
        }
        
        .btn-paste {
            background: linear-gradient(45deg, #ffc107, #ff9800);
            font-size: 1.2em;
            padding: 15px 40px;
        }
        
        /* Tabla de resultados */
        .results {
            display: none;
        }
        
        .results.show {
            display: block;
            animation: fadeIn 0.5s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #00ff88;
        }
        
        .stat-label {
            color: #aaa;
            margin-top: 5px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            overflow: hidden;
        }
        
        th, td {
            padding: 15px;
            text-align: left;
        }
        
        th {
            background: rgba(0,212,255,0.3);
            font-weight: bold;
        }
        
        tr:nth-child(even) {
            background: rgba(255,255,255,0.05);
        }
        
        tr:hover {
            background: rgba(0,212,255,0.1);
        }
        
        .positive {
            color: #00ff88;
        }
        
        .negative {
            color: #ff4757;
        }
        
        .neutral {
            color: #ffc107;
        }
        
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.8em;
        }
        
        .badge-active {
            background: rgba(0,255,136,0.3);
            color: #00ff88;
        }
        
        .badge-inactive {
            background: rgba(255,193,7,0.3);
            color: #ffc107;
        }
        
        .top-players {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .player-card {
            background: linear-gradient(135deg, rgba(0,212,255,0.2), rgba(0,153,255,0.1));
            border-radius: 10px;
            padding: 15px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .player-rank {
            font-size: 2em;
            font-weight: bold;
            color: #ffd700;
        }
        
        .player-info h3 {
            margin-bottom: 5px;
        }
        
        .player-points {
            color: #00ff88;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }
        
        .loading.show {
            display: block;
        }
        
        .spinner {
            border: 4px solid rgba(255,255,255,0.3);
            border-top: 4px solid #00d4ff;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        #preview-img {
            max-width: 300px;
            max-height: 200px;
            border-radius: 10px;
            margin-top: 15px;
            display: none;
        }

        .section-title {
            font-size: 1.5em;
            margin: 30px 0 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #00d4ff;
        }
        
        .keyboard-hint {
            background: rgba(0,0,0,0.3);
            padding: 5px 15px;
            border-radius: 5px;
            font-family: monospace;
            display: inline-block;
            margin: 5px;
        }
        
        .methods-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        @media (max-width: 768px) {
            .methods-container {
                grid-template-columns: 1fr;
            }
        }

        /* ── Panel IA ─────────────────────────────────────────────────────── */
        .ia-panel {
            background: linear-gradient(135deg, rgba(138,43,226,0.15), rgba(75,0,130,0.1));
            border: 1px solid rgba(138,43,226,0.4);
            border-radius: 15px;
            padding: 25px;
            margin-top: 30px;
        }

        .ia-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .ia-col-title {
            font-size: 1em;
            font-weight: bold;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid rgba(255,255,255,0.15);
        }

        .ia-item {
            background: rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 15px;
            font-size: 0.92em;
            line-height: 1.5;
            margin-bottom: 8px;
        }

        .ia-item.peligro  { border-left: 3px solid #ff4757; }
        .ia-item.advertencia { border-left: 3px solid #ffc107; }
        .ia-item.overtake { border-left: 3px solid #00ff88; }
        .ia-item.liderazgo { border-left: 3px solid #ffd700; }
        .ia-item.general  { border-left: 3px solid #00d4ff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⛏️ Analizador de Puntos de Minería</h1>
        <p class="subtitle">Sube o pega capturas de pantalla y compara tu progreso</p>
        
        <div id="status-box" class="status-box">
            <span id="status-text">📷 Sube o pega la imagen de la <strong>SESIÓN ANTERIOR</strong> para comenzar</span>
        </div>
        
        <div class="methods-container">
            <!-- Método 1: Pegar del portapapeles -->
            <div class="paste-zone" id="paste-zone" tabindex="0">
                <div class="paste-icon">📋</div>
                <div class="paste-text">Pegar desde Portapapeles</div>
                <div class="paste-hint">
                    Haz clic aquí y presiona <span class="keyboard-hint">Ctrl+V</span><br>
                    o usa captura de pantalla <span class="keyboard-hint">Win+Shift+S</span>
                </div>
            </div>
            
            <!-- Método 2: Subir archivo -->
            <div class="upload-zone" id="upload-zone">
                <div class="upload-icon">📤</div>
                <div class="upload-text">Subir Archivo</div>
                <div class="upload-hint">Arrastra o haz clic para seleccionar</div>
                <input type="file" id="file-input" accept="image/*" style="display: none;">
            </div>
        </div>
        
        <div style="text-align: center; margin-bottom: 20px;">
            <img id="preview-img" src="" alt="Preview">
        </div>
        
        <div style="text-align: center; margin-bottom: 20px;">
            <button class="btn btn-danger" onclick="reiniciar()">🔄 Reiniciar</button>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Procesando imagen con OCR...</p>
        </div>
        
        <div class="results" id="results">
            <h2 class="section-title">📊 Resumen General</h2>
            <div class="stats-grid" id="stats-grid"></div>
            
            <h2 class="section-title">🏆 Top Activos</h2>
            <div class="top-players" id="top-players"></div>
            
            <h2 class="section-title">📋 Tabla Comparativa</h2>
            <table id="results-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Posición</th>
                        <th>Puntos Totales</th>
                        <th>Ganados (Sesión)</th>
                        <th>Déficit vs. Máximo</th>
                        <th>Dist. al Líder</th>
                        <th>Dif. al Siguiente</th>
                        <th>Estado</th>
                    </tr>
                </thead>
                <tbody id="table-body"></tbody>
            </table>
            
            <h2 class="section-title" id="inactive-title" style="display:none;">⏸️ Sin Actividad</h2>
            <div id="inactive-list"></div>

            <h2 class="section-title">🤖 Análisis IA</h2>
            <div class="ia-panel" id="ia-panel">
                <div class="ia-grid">
                    <div>
                        <div class="ia-col-title">💡 Conclusiones</div>
                        <div id="ia-conclusiones"></div>
                    </div>
                    <div>
                        <div class="ia-col-title">🚨 Alertas de posición</div>
                        <div id="ia-alertas"></div>
                    </div>
                    <div>
                        <div class="ia-col-title">🔮 Predicciones</div>
                        <div id="ia-predicciones"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let tieneAnterior = {{ 'true' if tiene_anterior else 'false' }};
        
        const uploadZone = document.getElementById('upload-zone');
        const pasteZone = document.getElementById('paste-zone');
        const fileInput = document.getElementById('file-input');
        const statusBox = document.getElementById('status-box');
        const statusText = document.getElementById('status-text');
        const previewImg = document.getElementById('preview-img');
        const loading = document.getElementById('loading');
        const results = document.getElementById('results');
        
        // Actualizar estado inicial
        actualizarEstado();
        
        function actualizarEstado() {
            if (tieneAnterior) {
                statusText.innerHTML = '✅ Sesión anterior cargada. Ahora sube o pega la <strong>SESIÓN ACTUAL</strong>';
                statusBox.className = 'status-box success';
            } else {
                statusText.innerHTML = '📷 Sube o pega la imagen de la <strong>SESIÓN ANTERIOR</strong> para comenzar';
                statusBox.className = 'status-box';
            }
        }
        
        // ===== PEGAR DESDE PORTAPAPELES =====
        
        // Escuchar Ctrl+V en toda la página
        document.addEventListener('paste', (e) => {
            const items = e.clipboardData.items;
            for (let item of items) {
                if (item.type.indexOf('image') !== -1) {
                    const blob = item.getAsFile();
                    procesarArchivo(blob);
                    e.preventDefault();
                    break;
                }
            }
        });
        
        // Click en zona de pegar
        pasteZone.addEventListener('click', () => {
            pasteZone.focus();
            alert('✅ Zona activa. Ahora presiona Ctrl+V para pegar la imagen del portapapeles.');
        });
        
        // ===== ARRASTRAR Y SOLTAR =====
        
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        
        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });
        
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                procesarArchivo(file);
            }
        });
        
        uploadZone.addEventListener('click', () => {
            fileInput.click();
        });
        
        fileInput.addEventListener('change', (e) => {
            if (e.target.files[0]) {
                procesarArchivo(e.target.files[0]);
            }
        });
        
        // ===== PROCESAR ARCHIVO =====
        
        function procesarArchivo(file) {
            // Mostrar preview
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImg.src = e.target.result;
                previewImg.style.display = 'block';
            };
            reader.readAsDataURL(file);
            
            // Subir al servidor
            subirImagen(file);
        }
        
        function subirImagen(file) {
            loading.classList.add('show');
            results.classList.remove('show');
            
            const formData = new FormData();
            formData.append('imagen', file);
            formData.append('tipo', tieneAnterior ? 'nueva' : 'anterior');
            
            fetch('/subir', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                loading.classList.remove('show');
                
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }
                
                if (data.necesita_actual) {
                    // Se guardó la sesión anterior
                    tieneAnterior = true;
                    actualizarEstado();
                    previewImg.style.display = 'none';
                    alert('✅ Sesión anterior guardada con ' + data.jugadores + ' jugadores.\\n\\nAhora pega o sube la sesión ACTUAL.');
                } else {
                    // Tenemos análisis completo
                    mostrarResultados(data.analisis);
                }
            })
            .catch(error => {
                loading.classList.remove('show');
                alert('Error al procesar: ' + error);
            });
        }
        
        function mostrarResultados(analisis) {
            results.classList.add('show');
            previewImg.style.display = 'none';
            
            // Stats
            const statsGrid = document.getElementById('stats-grid');
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-value">${formatNumber(analisis.resumen.total_actual)}</div>
                    <div class="stat-label">Puntos Totales</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value positive">+${formatNumber(analisis.resumen.total_ganado)}</div>
                    <div class="stat-label">Puntos Ganados (Total)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">👑 ${analisis.lider ? analisis.lider[0] : 'N/A'}</div>
                    <div class="stat-label">Líder (Más Puntos)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">🏆 ${analisis.resumen.ganador_sesion || 'N/A'}</div>
                    <div class="stat-label">Más Ganó (+${formatNumber(analisis.resumen.max_ganado)})</div>
                </div>
            `;
            
            // Top jugadores
            const topPlayers = document.getElementById('top-players');
            topPlayers.innerHTML = analisis.top_activos.map((p, i) => `
                <div class="player-card">
                    <div class="player-rank">${['🥇','🥈','🥉','4️⃣','5️⃣'][i]}</div>
                    <div class="player-info">
                        <h3>${p.jugador}</h3>
                        <div class="player-points">+${formatNumber(p.ganado)} pts (+${p.porcentaje.toFixed(2)}%)</div>
                    </div>
                </div>
            `).join('');
            
            // Tabla
            const tableBody = document.getElementById('table-body');
            tableBody.innerHTML = analisis.tabla.map(row => `
                <tr>
                    <td>${row.rango}</td>
                    <td><strong>${row.jugador}</strong></td>
                    <td>${formatNumber(row.actual)}</td>
                    <td class="${row.ganado_sesion > 0 ? 'positive' : row.ganado_sesion < 0 ? 'negative' : 'neutral'}">
                        ${row.ganado_sesion > 0 ? '+' : ''}${formatNumber(row.ganado_sesion)}
                    </td>
                    <td class="${row.deficit_vs_maximo < 0 ? 'negative' : 'positive'}">
                        ${formatNumber(row.deficit_vs_maximo)}
                    </td>
                    <td class="${row.distancia_lider > 0 ? 'negative' : 'positive'}">
                        ${row.distancia_lider > 0 ? '-' : ''}${formatNumber(row.distancia_lider)}
                    </td>
                    <td class="${row.diferencia_siguiente > 0 ? 'negative' : 'neutral'}">
                        ${row.diferencia_siguiente > 0 ? '-' + formatNumber(row.diferencia_siguiente) : '👑'}
                    </td>
                    <td>
                        <span class="badge ${row.estado === 'activo' ? 'badge-active' : 'badge-inactive'}">
                            ${row.estado === 'activo' ? '📈 Activo' : '⏸️ Inactivo'}
                        </span>
                    </td>
                </tr>
            `).join('');
            
            // Inactivos
            if (analisis.inactivos.length > 0) {
                document.getElementById('inactive-title').style.display = 'block';
                document.getElementById('inactive-list').innerHTML = analisis.inactivos.map(j => 
                    `<span class="badge badge-inactive" style="margin: 5px;">${j}</span>`
                ).join('');
            } else {
                document.getElementById('inactive-title').style.display = 'none';
            }
            
            // Actualizar estado para próxima comparación
            statusText.innerHTML = '✅ ¡Análisis completado! Pega o sube otra imagen para comparar con esta sesión';
            statusBox.className = 'status-box success';

            // ── Análisis IA ─────────────────────────────────────────────────
            if (analisis.ia) {
                const ia = analisis.ia;

                document.getElementById('ia-conclusiones').innerHTML =
                    (ia.conclusiones.length
                        ? ia.conclusiones.map(c => `<div class="ia-item general">${c}</div>`).join('')
                        : '<div class="ia-item general">Sin datos suficientes.</div>');

                document.getElementById('ia-alertas').innerHTML =
                    (ia.alertas.length
                        ? ia.alertas.map(a => `<div class="ia-item ${a.tipo}">${a.mensaje}</div>`).join('')
                        : '<div class="ia-item general">✅ Sin alertas críticas esta sesión.</div>');

                document.getElementById('ia-predicciones').innerHTML =
                    (ia.predicciones.length
                        ? ia.predicciones.map(p => `<div class="ia-item ${p.tipo}">${p.mensaje}</div>`).join('')
                        : '<div class="ia-item general">🔮 Sin cambios de posición previstos a corto plazo.</div>');
            }
        }
        
        function formatNumber(num) {
            return num.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ",");
        }
        
        function reiniciar() {
            if (confirm('¿Reiniciar todo? Se perderán los datos guardados.')) {
                fetch('/reiniciar', { method: 'POST' })
                .then(() => {
                    tieneAnterior = false;
                    actualizarEstado();
                    results.classList.remove('show');
                    previewImg.style.display = 'none';
                    document.getElementById('inactive-title').style.display = 'none';
                });
            }
        }
    </script>
</body>
</html>
'''

# Crear carpeta templates si no existe
os.makedirs('templates', exist_ok=True)

# Guardar template
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(HTML_TEMPLATE)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎮 ANALIZADOR DE PUNTOS DE MINERÍA - VERSIÓN WEB")
    print("="*60)
    print("\n🌐 Abre tu navegador en: http://localhost:5000")
    print("\n📋 Instrucciones:")
    print("   1. Sube la imagen de la sesión ANTERIOR")
    print("   2. Sube la imagen de la sesión ACTUAL")
    print("   3. ¡Ve el análisis comparativo!")
    print("\n⏹️  Presiona Ctrl+C para detener el servidor")
    print("="*60 + "\n")
    
    import os
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
