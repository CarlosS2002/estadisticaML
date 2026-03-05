import easyocr
reader = easyocr.Reader(['es', 'en'], gpu=False, verbose=False)
from PIL import Image, ImageEnhance
import re
import sys

# Leer la imagen (usar argumento o default)
imagen_path = sys.argv[1] if len(sys.argv) > 1 else 'temp_imagen_1.png'
print(f'Analizando: {imagen_path}')

img = Image.open(imagen_path)
if img.mode == 'RGBA':
    img = img.convert('RGB')

# Preprocesamiento
width, height = img.size
img_grande = img.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
enhancer = ImageEnhance.Contrast(img_grande)
img_contraste = enhancer.enhance(1.8)
enhancer = ImageEnhance.Sharpness(img_contraste)
img_nitida = enhancer.enhance(1.5)
img_nitida.save('temp_test.png')

# OCR
resultados = reader.readtext('temp_test.png', paragraph=False, detail=1)

print('=== TODOS LOS TEXTOS DETECTADOS ===')
for i, (bbox, texto, prob) in enumerate(resultados):
    y_pos = bbox[0][1]  # posición Y
    print(f'{i}: [{prob:.2f}] Y={y_pos:.0f} "{texto}"')

print('\n=== NUMEROS EXTRAIDOS (en orden) ===')
numeros = []
for (bbox, texto, prob) in resultados:
    # Limpiar caracteres que el OCR confunde
    texto_limpio = texto.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
    numeros_encontrados = re.findall(r'\d+', texto_limpio)
    
    for num_str in numeros_encontrados:
        if len(num_str) >= 6:
            puntos = int(num_str)
            if puntos >= 100000:
                y_pos = bbox[0][1]
                numeros.append((y_pos, puntos, texto))

# Ordenar por posición Y
numeros.sort(key=lambda x: x[0])

for i, (y, puntos, texto_orig) in enumerate(numeros, 1):
    print(f'  Pos{i}: {puntos:,} (de "{texto_orig}")')

print(f'\nTotal numeros: {len(numeros)}')
