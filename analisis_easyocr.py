"""
Programa de Análisis de Puntos de Minería con EasyOCR
Lee datos directamente de imágenes y genera estadísticas
NO requiere instalar Tesseract - todo está incluido en Python
"""

import re
import sys
from pathlib import Path

print("🔄 Cargando librerías (primera vez puede tardar)...")

try:
    from PIL import Image
    import easyocr
except ImportError:
    print("❌ Instalando librerías necesarias (esto puede tardar unos minutos)...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "easyocr"])
    from PIL import Image
    import easyocr

# Crear el lector OCR (solo una vez)
print("🔄 Iniciando motor OCR...")
reader = easyocr.Reader(['es', 'en'], gpu=False)
print("✅ Motor OCR listo!\n")


def extraer_datos_imagen(ruta_imagen):
    """
    Extrae los datos de jugadores y puntos de una imagen usando EasyOCR
    """
    print(f"\n📷 Procesando imagen: {ruta_imagen}")
    
    try:
        # Verificar que el archivo existe
        if not Path(ruta_imagen).exists():
            print(f"❌ Error: No se encontró la imagen: {ruta_imagen}")
            return {}
        
        # Extraer texto con OCR
        resultados = reader.readtext(ruta_imagen)
        
        # Combinar todo el texto detectado
        texto_completo = ""
        for (bbox, texto, prob) in resultados:
            texto_completo += texto + "\n"
            
        print(f"📝 Texto detectado:\n{texto_completo}")
        
        # Parsear los datos
        datos = {}
        
        # Buscar patrones de jugadores y puntos
        # El texto puede venir en diferentes formatos
        lineas = texto_completo.split('\n')
        
        jugador_actual = None
        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue
            
            # Patrón 1: "1. nombre - 12345678" o "1 nombre - 12345678"
            patron1 = r'(\d+)[.\s]+([A-Za-z_]\w*)\s*[-–—]\s*([\d,\.]+)'
            match = re.search(patron1, linea)
            
            if match:
                jugador = match.group(2)
                puntos_str = match.group(3).replace(',', '').replace('.', '').replace(' ', '')
                try:
                    puntos = int(puntos_str)
                    datos[jugador] = puntos
                    print(f"  ✅ {jugador}: {puntos:,}")
                except ValueError:
                    pass
                continue
            
            # Patrón 2: nombre solo (guardarlo para la siguiente línea con números)
            patron_nombre = r'^([A-Za-z_]\w+)$'
            match_nombre = re.search(patron_nombre, linea)
            if match_nombre:
                jugador_actual = match_nombre.group(1)
                continue
            
            # Patrón 3: solo número (asociar con jugador anterior)
            patron_numero = r'^([\d,\.]+)$'
            match_numero = re.search(patron_numero, linea.replace(' ', ''))
            if match_numero and jugador_actual:
                puntos_str = match_numero.group(1).replace(',', '').replace('.', '')
                try:
                    puntos = int(puntos_str)
                    datos[jugador_actual] = puntos
                    print(f"  ✅ {jugador_actual}: {puntos:,}")
                    jugador_actual = None
                except ValueError:
                    pass
                continue
            
            # Patrón 4: "nombre - número" sin el rango
            patron4 = r'([A-Za-z_]\w*)\s*[-–—]\s*([\d,\.]+)'
            match4 = re.search(patron4, linea)
            if match4:
                jugador = match4.group(1)
                puntos_str = match4.group(2).replace(',', '').replace('.', '').replace(' ', '')
                try:
                    puntos = int(puntos_str)
                    datos[jugador] = puntos
                    print(f"  ✅ {jugador}: {puntos:,}")
                except ValueError:
                    pass
        
        if not datos:
            print("  ⚠️ No se pudieron extraer datos estructurados")
            print("  💡 Tip: Asegúrate de que la imagen sea clara y tenga buen contraste")
        
        return datos
        
    except Exception as e:
        print(f"❌ Error al procesar imagen: {e}")
        return {}


def analizar_datos(datos_anterior, datos_actual):
    """
    Analiza y compara los datos de dos sesiones
    """
    print("\n" + "=" * 70)
    print("📊 ANÁLISIS DE PUNTOS DE MINERÍA - COMPARATIVA DE SESIONES")
    print("=" * 70)
    print()
    
    if not datos_anterior or not datos_actual:
        print("❌ Error: No hay suficientes datos para analizar")
        return
    
    # Calcular diferencias
    print("🔄 CAMBIOS ENTRE SESIONES:")
    print("-" * 70)
    print(f"{'Rango':<6} {'Jugador':<15} {'Anterior':>12} {'Actual':>12} {'Ganados':>12} {'%Cambio':>10}")
    print("-" * 70)
    
    total_anterior = 0
    total_actual = 0
    jugadores_activos = []
    jugadores_inactivos = []
    
    # Ordenar por puntos actuales
    datos_ordenados = sorted(datos_actual.items(), key=lambda x: x[1], reverse=True)
    
    for rango, (jugador, puntos_actual) in enumerate(datos_ordenados, 1):
        puntos_anterior = datos_anterior.get(jugador, 0)
        diferencia = puntos_actual - puntos_anterior
        
        if puntos_anterior > 0:
            porcentaje = (diferencia / puntos_anterior) * 100
        else:
            porcentaje = 0
        
        total_anterior += puntos_anterior
        total_actual += puntos_actual
        
        if diferencia > 0:
            jugadores_activos.append((jugador, diferencia, porcentaje))
            estado = "📈"
        elif diferencia == 0:
            jugadores_inactivos.append(jugador)
            estado = "⏸️"
        else:
            estado = "📉"
        
        print(f"{rango:<6} {jugador:<15} {puntos_anterior:>12,} {puntos_actual:>12,} {diferencia:>+12,} {porcentaje:>+9.2f}% {estado}")
    
    print("-" * 70)
    
    # Resumen general
    total_ganado = total_actual - total_anterior
    print()
    print("=" * 70)
    print("📈 RESUMEN GENERAL:")
    print("=" * 70)
    print(f"  • Total puntos sesión anterior: {total_anterior:,}")
    print(f"  • Total puntos sesión actual:   {total_actual:,}")
    print(f"  • Total puntos ganados:         {total_ganado:+,}")
    if len(datos_actual) > 0:
        print(f"  • Promedio ganado por jugador:  {total_ganado/len(datos_actual):,.0f}")
    print()
    
    # Top jugadores activos
    if jugadores_activos:
        print("=" * 70)
        print("🏆 TOP JUGADORES MÁS ACTIVOS (Por puntos ganados):")
        print("=" * 70)
        jugadores_activos.sort(key=lambda x: x[1], reverse=True)
        for i, (jugador, puntos, porcentaje) in enumerate(jugadores_activos, 1):
            print(f"  {i}. {jugador}: +{puntos:,} puntos (+{porcentaje:.2f}%)")
        print()
    
    # Jugadores inactivos
    if jugadores_inactivos:
        print("=" * 70)
        print("⏸️ JUGADORES SIN ACTIVIDAD:")
        print("=" * 70)
        for jugador in jugadores_inactivos:
            print(f"  • {jugador}")
        print()
    
    print("=" * 70)
    print("✅ Análisis completado")
    print("=" * 70)


def main():
    print("=" * 70)
    print("🎮 ANALIZADOR DE PUNTOS DE MINERÍA - VERSIÓN OCR")
    print("=" * 70)
    print()
    print("Este programa lee datos de imágenes automáticamente.")
    print()
    
    # Verificar argumentos de línea de comandos
    if len(sys.argv) == 3:
        ruta_anterior = sys.argv[1]
        ruta_actual = sys.argv[2]
    else:
        # Solicitar rutas de imágenes
        print("📁 Ingresa la ruta de la imagen de la SESIÓN ANTERIOR:")
        print("   (Arrastra el archivo aquí o escribe la ruta)")
        ruta_anterior = input("   > ").strip().strip('"').strip("'")
        
        print()
        print("📁 Ingresa la ruta de la imagen de la SESIÓN ACTUAL:")
        print("   (Arrastra el archivo aquí o escribe la ruta)")
        ruta_actual = input("   > ").strip().strip('"').strip("'")
    
    # Extraer datos de las imágenes
    datos_anterior = extraer_datos_imagen(ruta_anterior)
    datos_actual = extraer_datos_imagen(ruta_actual)
    
    # Analizar y comparar
    if datos_anterior and datos_actual:
        analizar_datos(datos_anterior, datos_actual)
    else:
        print("\n❌ No se pudieron extraer datos suficientes de las imágenes.")
        print("   Sugerencias:")
        print("   • Asegúrate de que las imágenes sean claras")
        print("   • El texto debe ser legible")
        print("   • Prueba con capturas de pantalla de mejor calidad")


if __name__ == "__main__":
    main()
