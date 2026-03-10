"""
Analizador de Puntos de Minería - Versión Optimizada para Railway
Usa Tesseract OCR (ligero) en lugar de EasyOCR
"""

from flask import Flask, render_template, request, jsonify
import re
import os
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageEnhance
import pytesseract

app = Flask(__name__)
app.secret_key = 'mineria_analyzer_2024'

# Almacén de datos de sesiones
datos_almacenados = {
    'anterior': None,
    'historial': []
}

print("✅ Tesseract OCR listo (versión ligera)")


def _limpiar_numero(numero_texto):
    """Convierte valores OCR con separadores a entero seguro."""
    solo_digitos = re.sub(r'\D', '', numero_texto)
    if not solo_digitos:
        return None
    return int(solo_digitos)


def _corregir_puntaje_pegado_con_rango(puntaje, rango):
    """Corrige casos OCR donde junta rango+puntaje (ej: 5 + 36897354 => 536897354)."""
    texto = str(puntaje)

    def _es_puntaje_plausible(valor_txt):
        if not valor_txt or not valor_txt.isdigit():
            return False
        # En este tablero los puntajes reales están en millones (7-8 dígitos).
        return len(valor_txt) in (7, 8) and 1_000_000 <= int(valor_txt) <= 99_999_999

    # Si ya es plausible, no tocar.
    if _es_puntaje_plausible(texto):
        return puntaje

    candidatos = []

    # Caso guiado por rango OCR detectado.
    if rango is not None:
        rango_txt = str(rango)
        if texto.startswith(rango_txt):
            candidatos.append(texto[len(rango_txt):])

    # Casos sin rango confiable: recortar 1 o 2 dígitos de prefijo espurio.
    if len(texto) >= 9:
        candidatos.append(texto[1:])
    if len(texto) >= 10:
        candidatos.append(texto[2:])

    for cand in candidatos:
        if _es_puntaje_plausible(cand):
            return int(cand)

    # Último recurso: tomar sufijos plausibles de 8 o 7 dígitos.
    if len(texto) > 8:
        for n in (8, 7):
            suf = texto[-n:]
            if _es_puntaje_plausible(suf):
                return int(suf)

    return puntaje


def _extraer_puntajes_agresivo(imagen):
    """Fallback multipase para recuperar filas faltantes del ranking."""
    candidatos = []

    # Variante binaria para mejorar separación de dígitos en texto pequeño.
    gris = imagen.convert('L')
    bw = gris.point(lambda p: 255 if p > 150 else 0)

    variantes = [imagen, bw]
    psm_list = [6, 4, 11]

    for var in variantes:
        for psm in psm_list:
            config = f'--oem 3 --psm {psm}'
            texto = pytesseract.image_to_string(var, config=config)
            for linea in texto.split('\n'):
                # Extraer secuencias largas que parezcan puntaje.
                for token in re.findall(r'\d[\d\.,]{6,}', linea):
                    valor = _limpiar_numero(token)
                    if valor is None:
                        continue
                    valor = _corregir_puntaje_pegado_con_rango(valor, None)
                    if 1_000_000 <= valor <= 99_999_999:
                        candidatos.append(valor)

    # Únicos, orden descendente (ranking por puntaje)
    return sorted(set(candidatos), reverse=True)


def extraer_datos_imagen(imagen_bytes):
    """
    Extrae puntos usando Tesseract (más ligero que EasyOCR)
    """
    try:
        imagen = Image.open(BytesIO(imagen_bytes))
        if imagen.mode == 'RGBA':
            imagen = imagen.convert('RGB')
        
        # Preprocesamiento simple
        width, height = imagen.size
        if width < 900:
            imagen = imagen.resize((min(width * 3, 1800), min(height * 3, 1800)), Image.Resampling.LANCZOS)
        
        enhancer = ImageEnhance.Contrast(imagen)
        imagen = enhancer.enhance(2.0)
        
        enhancer = ImageEnhance.Sharpness(imagen)
        imagen = enhancer.enhance(1.8)
        
        # OCR estructurado por palabras para separar mejor rango y puntaje de cada fila
        ocr_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,'
        data = pytesseract.image_to_data(imagen, config=ocr_config, output_type=pytesseract.Output.DICT)

        lineas = {}
        total_boxes = len(data['text'])
        for i in range(total_boxes):
            txt = (data['text'][i] or '').strip()
            if not txt:
                continue

            conf_raw = data['conf'][i]
            try:
                conf = float(conf_raw)
            except ValueError:
                conf = -1
            if conf < 0:
                continue

            key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
            if key not in lineas:
                lineas[key] = {'tokens': [], 'top': data['top'][i]}

            lineas[key]['tokens'].append((data['left'][i], txt, conf))

        filas_detectadas = []

        for _, linea_info in sorted(lineas.items(), key=lambda item: item[1]['top']):
            tokens = sorted(linea_info['tokens'], key=lambda x: x[0])

            numeros = []
            for _, txt, _ in tokens:
                if re.search(r'\d', txt):
                    valor = _limpiar_numero(txt)
                    if valor is not None:
                        numeros.append((txt, valor))

            if not numeros:
                continue

            # Con whitelist de dígitos normalmente llegan: [rango, puntaje]
            rango = None
            for _, valor in numeros:
                if 1 <= valor <= 10:
                    rango = valor
                    break

            # Tomar el número más largo o más grande como puntaje
            puntaje_candidato = None
            puntaje_texto = None
            for txt, valor in numeros:
                if valor >= 100000:
                    if puntaje_candidato is None:
                        puntaje_candidato = valor
                        puntaje_texto = txt
                    else:
                        if len(re.sub(r'\D', '', txt)) > len(re.sub(r'\D', '', puntaje_texto or '')):
                            puntaje_candidato = valor
                            puntaje_texto = txt
                        elif valor > puntaje_candidato:
                            puntaje_candidato = valor
                            puntaje_texto = txt

            if puntaje_candidato is None:
                continue

            # Filtro de sanidad para evitar valores absurdos por OCR
            if puntaje_candidato < 100000 or puntaje_candidato > 999999999:
                continue

            puntaje_candidato = _corregir_puntaje_pegado_con_rango(puntaje_candidato, rango)

            filas_detectadas.append({
                'top': linea_info['top'],
                'rango_ocr': rango,
                'puntaje': puntaje_candidato
            })
            print(f"  ✓ Fila top={linea_info['top']} rangoOCR={rango} puntaje={puntaje_candidato}")

        # Fallback extra si image_to_data no detecta suficiente
        if len(filas_detectadas) < 3:
            texto = pytesseract.image_to_string(imagen, config='--psm 6')
            print(f"📝 Fallback texto: {texto[:200]}...")
            for linea in texto.split('\n'):
                linea = linea.strip()
                if not linea:
                    continue
                match = re.search(r'^\s*(\d{1,2})\D+.*?(\d[\d\.,]{5,})\s*$', linea)
                if not match:
                    continue
                rango = int(match.group(1))
                puntos = _limpiar_numero(match.group(2))
                if puntos and 100000 <= puntos <= 999999999 and 1 <= rango <= 10:
                    puntos = _corregir_puntaje_pegado_con_rango(puntos, rango)
                    filas_detectadas.append({'top': 100000 + rango, 'rango_ocr': rango, 'puntaje': puntos})
                    print(f"  ✓ Fallback fila rango={rango} puntaje={puntos}")

        # Quitar duplicados por puntaje conservando el de mayor confianza posicional (primer aparición)
        puntajes_vistos = set()
        filas_unicas = []
        for fila in sorted(filas_detectadas, key=lambda x: x['top']):
            p = fila['puntaje']
            if p in puntajes_vistos:
                continue
            puntajes_vistos.add(p)
            filas_unicas.append(fila)

        # Rescate: si faltan filas, extraer puntajes extra con OCR multipase.
        if len(filas_unicas) < 10:
            extras = _extraer_puntajes_agresivo(imagen)
            for p in extras:
                if p in puntajes_vistos:
                    continue
                puntajes_vistos.add(p)
                filas_unicas.append({'top': 1_000_000 + len(filas_unicas), 'rango_ocr': None, 'puntaje': p})
                if len(filas_unicas) >= 10:
                    break

        # Si hay mezcla de órdenes, normalizar por puntaje descendente.
        filas_unicas = sorted(filas_unicas, key=lambda x: x['puntaje'], reverse=True)

        # Construir datos finales: SIEMPRE renumerar secuencial para no inventar Pos8/Pos9.
        datos = {}
        for idx, fila in enumerate(filas_unicas[:10], 1):
            datos[f"Pos{idx}"] = fila['puntaje']
        
        print(f"✅ Datos extraídos: {len(datos)} posiciones")
        
        return {
            'datos': datos,
            'exito': len(datos) > 0
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            'datos': {},
            'exito': False,
            'error': str(e)
        }


def analizar_comparativa(datos_anterior, datos_actual):
    """Análisis comparativo"""
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
        
        if rango == 1:
            diferencia_siguiente = 0
        else:
            diferencia_siguiente = datos_ordenados[rango - 2][1] - puntos_actual
        
        porcentaje = (ganado_sesion / puntos_anterior * 100) if puntos_anterior > 0 else 0
        
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
    
    jugadores_activos.sort(key=lambda x: x['ganado'], reverse=True)
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
    """Agente IA para conclusiones"""
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

    # ── Conclusiones generales ──
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
                f"📊 Gran disparidad: {max_act['jugador']} ganó {max_act['ganado_sesion']:,} pts "
                f"vs {min_act['jugador']} con {min_act['ganado_sesion']:,} pts."
            )
        else:
            conclusiones.append("📈 Rendimiento parejo entre los jugadores activos esta sesión.")

    nombres_inactivos = [r['jugador'] for r in inactivos]
    if nombres_inactivos:
        conclusiones.append(f"⏸️ Sin actividad esta sesión: {', '.join(nombres_inactivos)}.")

    # ── Alertas y predicciones por jugador ──
    for row in tabla:
        jugador = row['jugador']
        rango = row['rango']
        ganado = row['ganado_sesion']
        dif_siguiente = row['diferencia_siguiente']
        puntos_actuales = row['actual']

        # Peligro de perder posición ante el de abajo
        if rango < total_jugadores:
            jugador_abajo = tabla[rango]
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

        # Inactivo con ventaja pequeña
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
    tipo = request.form.get('tipo', 'nueva')
    
    if archivo.filename == '':
        return jsonify({'error': 'Archivo vacío'}), 400
    
    imagen_bytes = archivo.read()
    resultado = extraer_datos_imagen(imagen_bytes)
    
    if not resultado['exito']:
        return jsonify({
            'error': 'No se pudieron extraer datos',
            'detalles': resultado.get('error', 'Desconocido')
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
        analisis['ia'] = generar_analisis_ia(analisis)
        
        datos_almacenados['historial'].append({
            'fecha': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'anterior': datos_anterior,
            'actual': datos_actual,
            'analisis': analisis
        })
        
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
