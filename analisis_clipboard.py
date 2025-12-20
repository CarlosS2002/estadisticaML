"""
Programa de Análisis de Puntos de Minería con OCR
Lee datos directamente del PORTAPAPELES (clipboard)
Solo haz Ctrl+C en la imagen o captura de pantalla y ejecuta el programa
"""

import re
import sys
from pathlib import Path

print("🔄 Cargando librerías...")

try:
    from PIL import Image, ImageGrab
    import easyocr
except ImportError:
    print("❌ Instalando librerías necesarias...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "easyocr"])
    from PIL import Image, ImageGrab
    import easyocr

# Crear el lector OCR (solo una vez)
print("🔄 Iniciando motor OCR (primera vez descarga modelos ~100MB)...")
reader = easyocr.Reader(['es', 'en'], gpu=False, verbose=False)
print("✅ Motor OCR listo!\n")


def obtener_imagen_portapapeles():
    """
    Obtiene una imagen del portapapeles
    """
    try:
        imagen = ImageGrab.grabclipboard()
        
        if imagen is None:
            print("   ⚠️ No hay imagen en el portapapeles")
            return None
            
        # Si es una lista de archivos (rutas)
        if isinstance(imagen, list):
            if len(imagen) > 0:
                ruta = imagen[0]
                print(f"   📁 Archivo detectado: {ruta}")
                return Image.open(ruta)
            return None
            
        if isinstance(imagen, Image.Image):
            print(f"   ✅ Imagen capturada: {imagen.size[0]}x{imagen.size[1]} pixels")
            return imagen
            
        return None
    except Exception as e:
        print(f"❌ Error al obtener imagen del portapapeles: {e}")
        return None


def extraer_datos_imagen(imagen, nombre="imagen", temp_id=1):
    """
    Extrae los datos de jugadores y puntos de una imagen usando EasyOCR
    """
    print(f"\n📷 Procesando {nombre}...")
    
    try:
        # Si es una imagen PIL, guardarla temporalmente
        if isinstance(imagen, Image.Image):
            temp_path = f"temp_imagen_{temp_id}.png"
            # Convertir a RGB si es necesario (para imágenes con transparencia)
            if imagen.mode == 'RGBA':
                imagen = imagen.convert('RGB')
            imagen.save(temp_path)
            ruta = temp_path
        else:
            ruta = imagen
        
        # Extraer texto con OCR
        resultados = reader.readtext(ruta)
        
        # Combinar todo el texto detectado
        print("📝 Texto detectado:")
        textos_detectados = []
        for (bbox, texto, prob) in resultados:
            print(f"   {texto}")
            textos_detectados.append(texto.strip())
        
        # Parsear los datos - el texto puede venir en líneas separadas
        datos = {}
        
        # Método 1: Buscar patrones en cada línea individual
        for (bbox, texto, prob) in resultados:
            texto = texto.strip()
            
            patrones = [
                r'(\d+)[.\s]+([A-Za-z_]\w*)\s*[-–—]\s*([\d]+)',  # 1. nombre - 12345
                r'([A-Za-z_]\w+)\s*[-–—]\s*([\d]+)',              # nombre - 12345
            ]
            
            for patron in patrones:
                match = re.search(patron, texto)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        jugador = groups[1]
                        puntos_str = groups[2]
                    else:
                        jugador = groups[0]
                        puntos_str = groups[1]
                    
                    puntos_str = puntos_str.replace(',', '').replace('.', '').replace(' ', '')
                    try:
                        puntos = int(puntos_str)
                        if puntos > 1000:
                            datos[jugador] = puntos
                    except ValueError:
                        pass
                    break
        
        # Método 2: Si no encontró datos, buscar nombres y números en líneas separadas
        if not datos:
            jugador_actual = None
            for texto in textos_detectados:
                texto = texto.strip()
                
                # Limpiar el texto de números de rango al inicio
                texto_limpio = re.sub(r'^[\d]+[.\s]*', '', texto).strip()
                
                # Es un nombre de jugador?
                if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', texto_limpio) and len(texto_limpio) > 2:
                    jugador_actual = texto_limpio
                # Es un número (puntos)?
                elif re.match(r'^[\d]+$', texto):
                    puntos = int(texto)
                    if jugador_actual and puntos > 100000:  # Puntos válidos
                        datos[jugador_actual] = puntos
                        jugador_actual = None
        
        print(f"\n✅ Datos extraídos de {nombre}:")
        for jugador, puntos in datos.items():
            print(f"   • {jugador}: {puntos:,}")
        
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
    
    print("🔄 CAMBIOS ENTRE SESIONES:")
    print("-" * 70)
    print(f"{'Rango':<6} {'Jugador':<15} {'Anterior':>12} {'Actual':>12} {'Ganados':>12} {'%Cambio':>10}")
    print("-" * 70)
    
    total_anterior = 0
    total_actual = 0
    jugadores_activos = []
    jugadores_inactivos = []
    
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
    
    if jugadores_activos:
        print("=" * 70)
        print("🏆 TOP JUGADORES MÁS ACTIVOS:")
        print("=" * 70)
        jugadores_activos.sort(key=lambda x: x[1], reverse=True)
        for i, (jugador, puntos, porcentaje) in enumerate(jugadores_activos, 1):
            print(f"  {i}. {jugador}: +{puntos:,} puntos (+{porcentaje:.2f}%)")
        print()
    
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
    print("🎮 ANALIZADOR DE PUNTOS DE MINERÍA")
    print("    Lee imágenes desde el PORTAPAPELES")
    print("=" * 70)
    print()
    
    # Paso 1: Imagen anterior
    print("📋 PASO 1: Copia la imagen de la SESIÓN ANTERIOR")
    print("   (Haz clic derecho > Copiar imagen, o Ctrl+C en la imagen)")
    print()
    input("   Presiona ENTER cuando hayas copiado la imagen anterior...")
    
    imagen_anterior = obtener_imagen_portapapeles()
    if imagen_anterior is None:
        print("❌ No se encontró ninguna imagen en el portapapeles")
        print("   Asegúrate de copiar la imagen (clic derecho > Copiar imagen)")
        return
    
    datos_anterior = extraer_datos_imagen(imagen_anterior, "sesión anterior", temp_id=1)
    
    # Paso 2: Imagen actual
    print()
    print("=" * 70)
    print("📋 PASO 2: Ahora copia la imagen de la SESIÓN ACTUAL")
    print()
    input("   Presiona ENTER cuando hayas copiado la imagen actual...")
    
    imagen_actual = obtener_imagen_portapapeles()
    if imagen_actual is None:
        print("❌ No se encontró ninguna imagen en el portapapeles")
        return
    
    datos_actual = extraer_datos_imagen(imagen_actual, "sesión actual", temp_id=2)
    
    # Analizar
    if datos_anterior and datos_actual:
        analizar_datos(datos_anterior, datos_actual)
    else:
        print("\n❌ No se pudieron extraer datos suficientes de las imágenes.")
        print("   Sugerencias:")
        print("   • Asegúrate de que las imágenes sean claras")
        print("   • El texto debe ser legible")


if __name__ == "__main__":
    main()
