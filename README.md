# Analizador de Puntos de Minería ⛏️

Aplicación web para analizar y comparar estadísticas de puntos de minería entre sesiones.

## 🚀 Características

- 📷 Sube imágenes o pega desde el portapapeles (Ctrl+V)
- 🔍 OCR automático para extraer datos de las capturas
- 📊 Comparación visual entre sesiones
- 🏆 Ranking de jugadores más activos
- 📈 Estadísticas de progreso

## 💻 Uso Local

```bash
pip install -r requirements.txt
python app_web.py
```

Abre http://localhost:5000 en tu navegador.

## ☁️ Despliegue en la Nube

### Opción 1: Render (Recomendado - Gratis)

1. Crea cuenta en https://render.com
2. Conecta tu repositorio de GitHub
3. Crea un nuevo "Web Service"
4. Selecciona este repositorio
5. ¡Listo! Se despliega automáticamente

### Opción 2: Railway

1. Crea cuenta en https://railway.app
2. Conecta GitHub
3. Despliega desde el repositorio

## 📋 Cómo Usar

1. Sube o pega la imagen de la **sesión anterior**
2. Sube o pega la imagen de la **sesión actual**
3. ¡Ve el análisis comparativo!
4. Cada nueva imagen se compara con la anterior automáticamente

## 🛠️ Tecnologías

- Python + Flask
- EasyOCR para reconocimiento de texto
- HTML/CSS/JavaScript para la interfaz
