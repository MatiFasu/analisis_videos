# 🎓 Automatización de Apuntes de YouTube con Asistente IA (`agy`)

Herramienta profesional en Python para extraer transcripciones de videos y **playlists completas** de YouTube y transformarlas en apuntes de estudio estructurados, pedagógicos y exhaustivos en formatos **Markdown (`.md`)** y **PDF de calidad editorial**, utilizando **Gemini CLI (`agy`)** o la API de Google Gemini.

---

## ✨ Características Principales

- 📋 **Soporte Integral de Playlists**:
  - Auto-detección inteligente de cualquier URL con parámetro `list=`.
  - Extracción ultraligera vía `yt-dlp` sin descargar audio ni video.
  - Sub-rangos con `--desde N` y `--hasta M` (ej. procesar solo de la clase 11 a la 20).
  - Numeración correlativa anclada al orden oficial del curso (`01_...`, `11_...`).
  - Flag de seguridad `--video-only` para procesar únicamente el video puntual cuando una URL viene con playlist asociada.
- ⏭️ **Deduplicación Inteligente (Salteo de ya procesados)**:
  - Escaneo automático de la carpeta destino antes de descargar o consultar la IA.
  - Saltea videos ya generados (`*_transcripcion.txt` o `.md`), ahorrando tiempo y tokens de API sin alterar la numeración.
- 📄 **Motor de PDF Profesional (WeasyPrint + Fallback)**:
  - **Portada de cortesía**: Tarjeta de metadatos con título, subtítulo pedagógico, miniatura HD enmarcada, fecha, curso y enlace de origen.
  - **Paginación y Encabezados**: `"Página X de Y"` dinámico en pie de página y encabezados superiores continuos con CSS Paged Media.
  - **Tabla de Contenidos (TOC)**: Enlaces con números de página reales y líneas punteadas (`leader('.')`).
  - **Reglas anti-rotura**: Directivas `break-inside: avoid` en diagramas Mermaid, tablas, cajas de código y citas.
  - **Motor híbrido**: Si WeasyPrint (GTK3) no está instalado, degrada de forma transparente y sin errores a `markdown-pdf` (PyMuPDF).
- 🛡️ **Robustez y Resiliencia**:
  - Control de esfuerzo de razonamiento con `--effort {low,medium,high,none}`.
  - Timeout configurable con `--timeout TIMEOUT` (300 segundos por defecto) para prevenir bloqueos.
  - Control de guardado de transcripción con `--no-transcripcion`.
  - Reintentos automáticos con retroceso exponencial y jitter aleatorio (`reintentar_con_backoff`) en APIs y descargas.
  - Sistema de logging estructurado con marcas de tiempo y modo depuración (`--verbose`).
- 🎨 **Enriquecimiento Visual**:
  - Descarga automática de miniaturas oficiales en máxima resolución (1080p/720p).
  - Renderizado automático de bloques ````mermaid```` a diagramas PNG nítidos con epígrafes académicos numerados.

---

## 📂 Estructura del Proyecto

```text
analisis_videos/
├── apuntes/                        # Directorio de salida organizado por cursos/materias
│   └── <nombre_materia>/           # Carpeta asignada para cada apunte o playlist
│       ├── 01_<titulo>_transcripcion.txt
│       ├── 01_<titulo>_portada.jpg
│       ├── 01_<titulo>.md
│       └── 01_<titulo>.pdf
├── compilador_pdf.py               # Motor unificado de compilación PDF (WeasyPrint / PyMuPDF)
├── enriquecedor_visual.py          # Renderizado de Mermaid, portadas HD y estilos CSS
├── generar_apunte.py               # Script principal de automatización y orquestación
├── generar_pdfs.py                 # Conversor masivo de carpetas Markdown a PDF
├── iniciar.bat                     # Acceso rápido por doble clic para Windows
├── prompt.txt                      # Directivas pedagógicas y estructura requerida para la IA
├── requirements.txt                # Dependencias base de producción
├── requirements-dev.txt            # Dependencias de desarrollo y testing (pytest, ruff)
├── ruff.toml                       # Configuración de linting y formateo de código
└── tests/                          # Suite de pruebas automatizadas con pytest
    ├── test_compilador_pdf.py      # Tests de metadatos y detección de motor
    ├── test_funciones_puras.py     # Tests de sanitización, IDs, parseo y backoff
    └── test_playlist.py            # Tests de detección, yt-dlp mockeado y deduplicación
```

---

## 🛠️ Instalación y Requisitos

### 1. Requisitos Previos
- **Python 3.10+** (64-bit recomendado).
- **Gemini CLI (`agy`)** instalado y autenticado, o definir la variable de entorno `GEMINI_API_KEY`.
- **yt-dlp**: Instalado en el sistema o mediante pip.

### 2. Instalar Dependencias de Python
Abrí tu terminal en la carpeta del proyecto y ejecutá:
```bash
pip install -r requirements.txt
```

Si deseás correr las pruebas o desarrollar:
```bash
pip install -r requirements-dev.txt
```

---

### 3. (Opcional) Activar Motor WeasyPrint en Windows

El sistema cuenta con un **motor híbrido**:
- Si no realizás ninguna configuración adicional, compilará los PDFs automáticamente con el motor de compatibilidad (`markdown-pdf`).
- Para activar el motor editorial profesional **WeasyPrint** (con portada de cortesía, encabezados `"Página X de Y"` y números de página reales en el índice), Windows requiere las librerías nativas de GTK3.

#### Opción A: Vía Winget (Recomendada y rápida)
Abrí PowerShell y ejecutá:
```powershell
winget install tschoonj.GTKForWindows
```

#### Opción B: Instalador oficial de GitHub
1. Descargá el instalador de 64 bits desde [GTK-for-Windows-Runtime-Environment-Installer](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/latest) (archivo `gtk3-runtime-*-win64.exe`).
2. Ejecutalo e instalalo en la ruta por defecto (`C:\Program Files\GTK3-Runtime-Win64`).

#### Opción C: Vía MSYS2
Si utilizás MSYS2:
```bash
pacman -S mingw-w64-ucrt-x86_64-pango
```

#### Verificar el motor activo
Podés chequear en cualquier momento qué motor está reconociendo el compilador ejecutando:
```bash
python compilador_pdf.py --info-motor
```
> Si GTK3 está presente, mostrará: `Estado del Motor PDF: WEASYPRINT`. De lo contrario, indicará `PYMUPDF` junto con el detalle.

---

## 🚀 Guía de Uso

### Modo 1: Asistido con Doble Clic (Windows)
1. Hacé doble clic sobre [`iniciar.bat`](file:///C:/Users/matia/Downloads/analisis_videos/iniciar.bat).
2. Pegá la URL de un video individual o de una **Playlist de YouTube**.
3. Si pegás una playlist, el asistente te preguntará cuántos videos querés procesar:
   - Presioná **[Enter]** para procesar todos.
   - O escribí una cantidad (ej: `3` para procesar los primeros 3).
   - O un rango específico (ej: `1-5` o `10 al 20`).
4. Ingresá el nombre de la materia o presioná Enter para adoptar el título oficial de la playlist.
5. Seleccioná si deseás generar también la versión en PDF (`s/n`).
6. El sistema procesará los videos, salteará los que ya hayan sido generados previamente y guardará todo en `apuntes/<materia>/`.

---

### Modo 2: Línea de Comandos (`generar_apunte.py`)

#### A. Video Individual
```powershell
# Procesa un video con PDF y carpeta propia
python generar_apunte.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --materia "musica" --pdf
```

#### B. Playlist Completa de YouTube
Cualquier URL con parámetro `list=` se expande automáticamente a todos los videos en orden:
```powershell
python generar_apunte.py --url "https://www.youtube.com/playlist?list=PLBlnK6fEyqRh6isJ01MBnbNpV3ZsktSyS" --pdf
```
*(Si no indicás `--materia`, el script creará la carpeta automáticamente con el nombre de la playlist).*

#### C. Sub-rango de Playlist (`--desde` / `--hasta`)
Para procesar solo un fragmento del curso (por ejemplo, del video 11 al 20), manteniendo la numeración correlativa real (`11_...`, `12_...`):
```powershell
python generar_apunte.py --url "https://www.youtube.com/playlist?list=PLBlnK6fEyqRh6isJ01MBnbNpV3ZsktSyS" --desde 11 --hasta 20 --pdf
```

#### D. Forzar Video Individual en URL con Playlist (`--video-only`)
Si pegás un enlace que contiene tanto `v=ID` como `list=ID` pero querés procesar **únicamente** ese video puntual:
```powershell
python generar_apunte.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL12345" --video-only --pdf
```

#### E. Procesamiento por Lote desde Archivo (`urls.txt`)
Podés colocar una lista de URLs en un archivo de texto (una por línea, con o sin prefijos tipo `clase 1 -> URL`):
```powershell
python generar_apunte.py --urls-file "urls.txt" --materia "curso_completo" --pdf
```

#### F. Opciones de Robustez y Rendimiento
```powershell
# Omitir el guardado del archivo de transcripción de texto:
python generar_apunte.py --url "https://..." --no-transcripcion

# Ajustar nivel de pensamiento/effort de Gemini (low, medium, high, none):
python generar_apunte.py --url "https://..." --effort high

# Configurar timeout máximo de espera para la IA (en segundos):
python generar_apunte.py --url "https://..." --timeout 450

# Activar logging detallado (debug):
python generar_apunte.py --url "https://..." --verbose
```

---

### Modo 3: Compilación Masiva de PDFs (`generar_pdfs.py`)

Si ya tenés una carpeta con archivos `.md` generados previamente y deseás compilarlos todos a PDF (o recompilarlos tras activar WeasyPrint):
```powershell
python generar_pdfs.py apuntes/curso_peoplesoft
```

---

## 🧪 Pruebas Automatizadas y Calidad

Para ejecutar la suite completa de 52 pruebas unitarias:
```bash
pytest
```

Para verificar que el código cumple con los estándares de estilo y análisis estático:
```bash
ruff check .
```

---

## ❓ Troubleshooting (Preguntas Frecuentes y Soluciones)

### 1. `OSError: cannot load library 'libgobject-2.0-0'`
- **Causa**: Intentaste compilar un PDF en Windows pero las librerías nativas de GTK3 no están instaladas en el sistema.
- **Solución**: No te preocupes; el sistema detecta esto automáticamente y utiliza el motor de respaldo `markdown-pdf` para que el apunte se genere igual. Si querés la portada de cortesía y encabezados avanzados, instalá GTK3 ejecutando en PowerShell:
  ```powershell
  winget install tschoonj.GTKForWindows
  ```

### 2. "La playlist es privada o requiere permisos de acceso"
- **Causa**: La URL de la playlist pertenece a una lista marcada como privada o no listada con acceso restringido en YouTube.
- **Solución**: Asegurate de que la playlist esté configurada como pública o no listada accesible mediante enlace directo.

### 3. "No se encontraron subtítulos ni transcripción disponibles"
- **Causa**: El creador del video deshabilitó los subtítulos o se trata de una transmisión en vivo recién finalizada.
- **Solución**: YouTube suele tardar entre 2 y 12 horas en procesar los subtítulos automáticos tras finalizar una transmisión. Intentá nuevamente una vez que YouTube los haya generado.

### 4. `TimeoutError: agy CLI no respondió dentro del límite`
- **Causa**: Un apunte muy extenso o una congestión de red provocó que la CLI superara el tiempo límite.
- **Solución**: El script reintenta automáticamente con retroceso exponencial. Si el video es excepcionalmente largo (más de 2 horas), aumentá el tiempo límite con `--timeout 600`.

### 5. Caracteres extraños o tildes rotas en PowerShell
- **Solución**: El script reconfigura automáticamente `stdout` y `stderr` a UTF-8. Podés forzar la consola en PowerShell ejecutando:
  ```powershell
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  ```
