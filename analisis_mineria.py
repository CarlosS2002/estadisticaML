"""
Programa de Análisis de Puntos de Minería
Compara datos entre dos sesiones y genera estadísticas
"""

# Datos extraídos de las imágenes (Sesión Anterior y Sesión Actual)

# SESIÓN ANTERIOR (Primera imagen de datos)
datos_sesion_anterior = {
    "carloquert": 52256804,
    "MorningStar7": 43660122,
    "BestToxico": 40957832,
    "_Nighteye": 39018066,
    "Getrix": 34606944,
    "MiniC_EFE": 26799920,
    "Milena00": 24813354,
    "Ilucia_": 23524246,
    "AthaOblen55": 14572096,
    "Quark": 8583724
}

# SESIÓN ACTUAL (Segunda imagen de datos)
datos_sesion_actual = {
    "carloquert": 52658920,
    "MorningStar7": 43978444,
    "BestToxico": 41354616,
    "_Nighteye": 39018066,
    "Getrix": 34824074,
    "MiniC_EFE": 26799920,
    "Milena00": 24813354,
    "Ilucia_": 23524246,
    "AthaOblen55": 14852780,
    "Quark": 8698926
}

def analizar_datos():
    print("=" * 70)
    print("📊 ANÁLISIS DE PUNTOS DE MINERÍA - COMPARATIVA DE SESIONES")
    print("=" * 70)
    print()
    
    # Calcular diferencias
    print("🔄 CAMBIOS ENTRE SESIONES:")
    print("-" * 70)
    print(f"{'Rango':<6} {'Jugador':<15} {'Anterior':>12} {'Actual':>12} {'Ganados':>12} {'%Cambio':>10}")
    print("-" * 70)
    
    total_anterior = 0
    total_actual = 0
    jugadores_activos = []
    jugadores_inactivos = []
    
    for rango, (jugador, puntos_actual) in enumerate(datos_sesion_actual.items(), 1):
        puntos_anterior = datos_sesion_anterior.get(jugador, 0)
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
    print(f"  • Promedio ganado por jugador:  {total_ganado/len(datos_sesion_actual):,.0f}")
    print()
    
    # Top jugadores activos
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
    
    # Líder
    lider = list(datos_sesion_actual.keys())[0]
    puntos_lider = datos_sesion_actual[lider]
    print(f"  👑 Líder actual: {lider} con {puntos_lider:,} puntos")
    
    # Distancia al primer lugar para cada jugador
    print()
    print("  📏 Distancia al 1er lugar:")
    for rango, (jugador, puntos) in enumerate(datos_sesion_actual.items(), 1):
        if rango > 1:
            distancia = puntos_lider - puntos
            print(f"     {rango}. {jugador}: -{distancia:,} puntos del líder")
    
    # Distancia al rango superior
    print()
    print("  📏 Distancia al rango superior:")
    jugadores_lista = list(datos_sesion_actual.items())
    for i in range(1, len(jugadores_lista)):
        jugador_actual = jugadores_lista[i][0]
        puntos_actual = jugadores_lista[i][1]
        jugador_superior = jugadores_lista[i-1][0]
        puntos_superior = jugadores_lista[i-1][1]
        distancia = puntos_superior - puntos_actual
        print(f"     {i+1}. {jugador_actual}: -{distancia:,} puntos de {jugador_superior}")
    
    print()
    print("=" * 70)
    print("✅ Análisis completado")
    print("=" * 70)

def calcular_proyeccion():
    print()
    print("=" * 70)
    print("🔮 PROYECCIÓN (Si mantienen el mismo ritmo):")
    print("=" * 70)
    
    for jugador, puntos_actual in datos_sesion_actual.items():
        puntos_anterior = datos_sesion_anterior.get(jugador, 0)
        ganado = puntos_actual - puntos_anterior
        
        if ganado > 0:
            proyeccion_7_dias = puntos_actual + (ganado * 7)
            proyeccion_30_dias = puntos_actual + (ganado * 30)
            print(f"  {jugador}:")
            print(f"     • En 7 días:  {proyeccion_7_dias:,} puntos")
            print(f"     • En 30 días: {proyeccion_30_dias:,} puntos")
            print()

if __name__ == "__main__":
    analizar_datos()
    calcular_proyeccion()
