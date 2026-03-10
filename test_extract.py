"""Test con todas las imágenes"""
from app_web import extraer_datos_imagen
import os

imagenes = [f for f in os.listdir('.') if f.endswith('.png') and not f.startswith('temp_upload')]
for img_path in imagenes:
    print(f"\n{'='*60}")
    print(f"Probando: {img_path}")
    print('='*60)
    with open(img_path, 'rb') as f:
        resultado = extraer_datos_imagen(f.read())
    print(f"Exito: {resultado['exito']}, Posiciones: {len(resultado['datos'])}")
    for k, v in sorted(resultado['datos'].items(), key=lambda x: int(x[0].replace('Pos',''))):
        print(f"  {k}: {v:,}")
