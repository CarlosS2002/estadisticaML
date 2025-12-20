"""
Programa de Análisis de Puntos de Minería con OCR
Lee datos directamente de imágenes y genera estadísticas
"""

import re
import sys
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
except ImportError:
    print("❌ Faltan librerías necesarias. Instalando...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "pytesseract"])
    from PIL import Image
    import pytesseract

# Configurar Tesseract automáticamente en Windows
def configurar_tesseract():
    """Busca e configura Tesseract en Windows"""
    rutas_posibles = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Tesseract-OCR\tesseract.exe',
    ]
    
    for ruta in rutas_posibles:
        if Path(ruta).exists():
            pytesseract.pytesseract.tesseract_cmd = ruta
            print(f"✅ Tesseract encontrado: {ruta}")
            return True
    
    print("=" * 70)
    print("⚠️  TESSERACT OCR NO ENCONTRADO")
    print("=" * 70)
    print()
    print("Para usar OCR necesitas instalar Tesseract:")
    print()
    print("1. Descarga desde:")
    print("   https://github.com/UB-Mannheim/tesseract/wiki")
    print()
    print("2. Instala el programa")
    print()
    print("3. Vuelve a ejecutar este script")
    print("=" * 70)
    return False

# Intentar configurar Tesseract
TESSERACT_OK = configurar_tesseract()


def extraer_datos_imagen(ruta_imagen):
    """
    Extrae los datos de jugadores y puntos de una imagen
    """
    print(f"\n📷 Procesando imagen: {ruta_imagen}")
    
    try:
        # Abrir imagen
        imagen = Image.open(ruta_imagen)
        
        # Extraer texto con OCR
        texto = pytesseract.image_to_string(imagen, config='--psm 6')
        
        print(f"📝 Texto detectado:\n{texto}\n")
        
        # Parsear los datos
        datos = {}
        lineas = texto.strip().split('\n')
        
        for linea in lineas:
            # Limpiar la línea
            linea = linea.strip()
            if not linea:
                continue
                
            # Buscar patrón: número. nombre - puntos
            # Ejemplo: "1. carloquert - 52256804"
            patron = r'(\d+)\.\s*(\w+)\s*[-—]\s*([\d,\.]+)'
            match = re.search(patron, linea)
            
            if match:
                rango = match.group(1)
                jugador = match.group(2)
                puntos_str = match.group(3).replace(',', '').replace('.', '')
                
                try:
                    puntos = int(puntos_str)
                    datos[jugador] = puntos
                    print(f"  ✅ {rango}. {jugador}: {puntos:,}")
                except ValueError:
                    print(f"  ⚠️ No se pudo convertir puntos: {puntos_str}")
            else:
                # Intentar otro patrón más flexible
                patron2 = r'(\w+)\s*[-—]\s*([\d]+)'
                match2 = re.search(patron2, linea)
                if match2:
                    jugador = match2.group(1)
                    puntos_str = match2.group(2)
                    try:
                        puntos = int(puntos_str)
                        datos[jugador] = puntos
                        print(f"  ✅ {jugador}: {puntos:,}")
                    except ValueError:
                        pass
        
        return datos
        
    except FileNotFoundError:
        print(f"❌ Error: No se encontró la imagen: {ruta_imagen}")
        return {}
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
        
        # Clasificar jugadores
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
    
    # Análisis de ranking
    print("=" * 70)
    print("📊 ANÁLISIS DE RANKING:")
    print("=" * 70)
    
    if datos_ordenados:
        lider = datos_ordenados[0][0]
        puntos_lider = datos_ordenados[0][1]
        print(f"  👑 Líder actual: {lider} con {puntos_lider:,} puntos")
        
        print()
        print("  📏 Distancia al 1er lugar:")
        for rango, (jugador, puntos) in enumerate(datos_ordenados, 1):
            if rango > 1:
                distancia = puntos_lider - puntos
                print(f"     {rango}. {jugador}: -{distancia:,} puntos del líder")
    
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
    
    # Solicitar rutas de imágenes
    print("📁 Ingresa la ruta de la imagen de la SESIÓN ANTERIOR:")
    print("   (Puedes arrastrar el archivo aquí o escribir la ruta)")
    ruta_anterior = input("   > ").strip().strip('"')
    
    print()
    print("📁 Ingresa la ruta de la imagen de la SESIÓN ACTUAL:")
    print("   (Puedes arrastrar el archivo aquí o escribir la ruta)")
    ruta_actual = input("   > ").strip().strip('"')
    
    # Extraer datos de las imágenes
    datos_anterior = extraer_datos_imagen(ruta_anterior)
    datos_actual = extraer_datos_imagen(ruta_actual)
    
    # Analizar y comparar
    if datos_anterior and datos_actual:
        analizar_datos(datos_anterior, datos_actual)
    else:
        print("\n❌ No se pudieron extraer datos suficientes de las imágenes.")
        print("   Asegúrate de que las imágenes sean claras y contengan texto legible.")


def analizar_desde_argumentos():
    """
    Permite pasar las imágenes como argumentos de línea de comandos
    """
    if len(sys.argv) == 3:
        ruta_anterior = sys.argv[1]
        ruta_actual = sys.argv[2]
        
        datos_anterior = extraer_datos_imagen(ruta_anterior)
        datos_actual = extraer_datos_imagen(ruta_actual)
        
        if datos_anterior and datos_actual:
            analizar_datos(datos_anterior, datos_actual)
        else:
            print("\n❌ No se pudieron extraer datos de las imágenes.")
    else:
        main()


if __name__ == "__main__":
    analizar_desde_argumentos()
