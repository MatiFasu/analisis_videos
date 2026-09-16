# 🎓 Automatización de Apuntes de YouTube con Gemini CLI (`agy`)

Herramienta automatizada en Python para extraer transcripciones de videos de YouTube y generar apuntes de estudio estructurados, claros y detallados en formato **Markdown (`.md`)** y **PDF**, utilizando **Gemini CLI (`agy`)**.

---

## ✨ Características

- 📥 **Extracción Automática**: Obtiene subtítulos oficiales o autogenerados mediante `youtube-transcript-api` (con respaldo de `yt-dlp`), con soporte multilingüe y traducción automática al español.
- 📁 **Organización por Carpetas**: Clasifica los apuntes según la materia o tema especificado (ej. `matematica`, `fisica`, `historia`).
- 🔢 **IDs Correlativos**: Asigna automáticamente identificadores numéricos ordenados (`01_...`, `02_...`) dentro de cada carpeta.
- 🧠 **Estructura Pedagógica de Alta Calidad**: Sigue las directrices de `prompt.txt` para generar:
  - Título y resumen inicial.
  - Explicación detallada por secciones temáticas.
  - Cajas destacadas de aclaración (`📌 Nota aclaratoria`) para conceptos complejos.
  - Conclusiones y resumen ejecutivo en viñetas.
  - Preguntas de autoevaluación / repaso.
- 📄 **Exportación a PDF Estilizado**: Conversión opcional a PDF con diseño académico maquetado, tablas, notas destacadas y tipografía limpia.
- 🖥️ **Fácil de Usar**: Ejecución mediante consola de comandos o con doble clic asistido interactivo (`iniciar.bat`).

---

## 📂 Estructura del Proyecto

```text
analisis_videos/
├── generar_apunte.py               # Script principal de automatización
├── iniciar.bat                     # Acceso directo para Windows (doble clic)
├── prompt.txt                      # Plantilla con directrices pedagógicas para Gemini
├── requirements.txt                # Dependencias del proyecto
├── plan_de_accion_automatizacion.md# Especificación técnica y plan de desarrollo
├── .gitignore
│
└── <materia>/                      # Carpeta generada automáticamente según el tema
    ├── 01_<titulo>_transcripcion.txt
    ├── 01_<titulo>.md
    └── 01_<titulo>.pdf
```

---

## 🛠️ Requisitos e Instalación

### 1. Requisitos Previos
- **Python 3.10+**
- **Gemini CLI (`agy`)** instalado y autenticado en tu sistema (o variable de entorno `GEMINI_API_KEY`).

### 2. Instalar Dependencias
```bash
pip install -r requirements.txt
```

---

## 🚀 Modos de Uso

### Modo 1: Asistido con Doble Clic (Windows)
1. Hacé doble clic en `iniciar.bat`.
2. Ingresá la URL del video de YouTube cuando te lo solicite.
3. Indicá la materia o categoría (ej: `matematica`).
4. Seleccioná si deseás generar también el archivo en PDF (`s/n`).

### Modo 2: Línea de Comandos
```powershell
python generar_apunte.py --url "https://www.youtube.com/watch?v=XXXXXX" --materia "matematica" --pdf
```

### Argumentos Opcionales:
- `--url`, `-u`: URL o ID del video de YouTube.
- `--materia`, `-m`: Nombre de la carpeta/materia donde guardar el material.
- `--pdf`: Genera además la versión compilada en formato PDF.
- `--model`: Permite elegir un modelo específico (ej. `gemini-3.8-flash-low`, `gemini-2.5-flash`).
