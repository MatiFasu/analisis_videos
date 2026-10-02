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
├── apuntes/                        # Directorio principal donde se almacenan todos los apuntes
│   └── <nombre_del_apunte>/        # Carpeta creada para cada materia o tema de apunte
│       ├── 01_<titulo>_transcripcion.txt
│       ├── 01_<titulo>_portada.jpg
│       ├── 01_<titulo>.md
│       └── 01_<titulo>.pdf
├── enriquecedor_visual.py          # Renderizado de diagramas Mermaid y portadas HD
├── generar_apunte.py               # Script principal de automatización
├── iniciar.bat                     # Acceso directo para Windows (doble clic)
├── prompt.txt                      # Plantilla con directrices pedagógicas para Gemini
├── requirements.txt                # Dependencias del proyecto
├── plan_de_accion_automatizacion.md# Especificación técnica y plan de desarrollo
└── .gitignore
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
1. Hacé doble clic en [`iniciar.bat`](file:///C:/Users/matia/Downloads/analisis_videos/iniciar.bat).
2. Podés procesar videos de dos formas:
   - **Video único:** Pegás la URL directamente.
   - **Múltiples videos (Lote):**
     - O pegás la lista de URLs en el archivo [`urls.txt`](file:///C:/Users/matia/Downloads/analisis_videos/urls.txt) (una por línea). Al iniciar, el programa te preguntará si querés procesarlas automáticamente.
     - O ingresás por consola la ruta a un archivo de texto (ej. `clases.txt`) o varias URLs separadas por coma.
3. **IDs manuales o automáticos:**
   - Si ponés `clase 1 -> URL` o `clase 2 URL`, se asignará el número exacto (`01`, `02`, etc.).
   - Si no ponés nada antes de la URL, el sistema asigna la numeración correlativa automáticamente.
4. Indicá el nombre de la materia/carpeta (ej: `teoria_de_juegos`). Todos los videos del lote irán a esa misma carpeta.
5. Seleccioná si deseás generar también el archivo en PDF (`s/n`).
6. ¡Listo! El material quedará organizado dentro de `apuntes/<nombre_del_apunte>/`.

### Modo 2: Línea de Comandos
```powershell
# Un solo video con ID automático:
python generar_apunte.py --url "https://www.youtube.com/watch?v=XXXXXX" --apunte "teoria_de_juegos" --pdf

# Múltiples videos desde urls.txt o archivo personalizado:
python generar_apunte.py --urls-file "urls.txt" --apunte "teoria_de_juegos" --pdf

# Varios videos indicados en línea de comandos (con o sin clase):
python generar_apunte.py --url "clase 1 -> https://..." "clase 2 -> https://..." --apunte "teoria_de_juegos" --pdf
```

### Argumentos Opcionales:
- `--url`, `-u`: Una o varias URLs / IDs de videos de YouTube (acepta prefijo `clase X ->`).
- `--urls-file`, `--file`, `-f`: Ruta a un archivo `.txt` con lista de URLs.
- `--apunte`, `--materia`, `-m`: Nombre de la carpeta/apunte dentro de `apuntes/`.
- `--dir-apuntes`: Directorio base para los apuntes (por defecto: `apuntes`).
- `--pdf`: Genera además la versión compilada en formato PDF.
- `--model`: Permite elegir un modelo específico (ej. `gemini-3.8-flash-low`, `gemini-2.5-flash`).
