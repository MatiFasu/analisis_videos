# Plan de Acción: Automatización de Apuntes de YouTube con Gemini CLI (`agy`)

Este documento detalla la arquitectura, las fases de desarrollo y los componentes necesarios para automatizar el flujo de trabajo de generación de apuntes de estudio a partir de videos de YouTube.

---

## 🎯 Objetivo

Crear una herramienta (script ejecutable por consola o interfaz sencilla) que reciba la **URL de un video de YouTube** y la **materia o categoría** (ej: `matematica`, `fisica`):
1. Extraiga automáticamente la transcripción del video de YouTube.
2. Organice todo en una carpeta dedicada a dicha materia (si no existe, se crea automáticamente).
3. Asigne un **ID correlativo/secuencial** a cada apunte (ej: `01_titulo.md`, `02_titulo.md`).
4. Ensamble las instrucciones de `prompt.txt` con el texto de la transcripción.
5. Invoque a **Gemini CLI (`agy`)** para generar un apunte detallado y estructurado en Markdown.
6. Opcionalmente exporte el resultado a documento **PDF** estilizado dentro de la misma carpeta.

---

## 🔄 Flujo del Sistema

```
                  [ URL de YouTube + Materia (ej: matematica) ]
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │ PASO 0: Gestión de Carpeta e ID                 │
             │ - Crea carpeta: ./matematica/ (si no existe)    │
             │ - Calcula el próximo ID: ej. 01, 02, 03...      │
             └────────────────────────┬────────────────────────┘
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │ PASO 1: Extracción Transcripción y Título       │
             │ (youtube-transcript-api / yt-dlp)               │
             └────────────────────────┬────────────────────────┘
                                      │ Genera: [ID]_[titulo]_transcripcion.txt
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │ PASO 2: Procesamiento con agy                   │
             │ - Une prompt.txt + transcripcion                │
             │ - Invoca agy -p (print mode)                    │
             └────────────────────────┬────────────────────────┘
                                      │ Genera: ./matematica/[ID]_[titulo].md
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │ PASO 3: Conversión PDF (Opcional)               │
             │ - Markdown -> HTML -> PDF                       │
             │ - Aplica estilos CSS académicos                 │
             └────────────────────────┬────────────────────────┘
                                      │ Genera: ./matematica/[ID]_[titulo].pdf
                                      ▼
             [ Salidas Listas dentro de ./<materia>/ ]
```

---

## 🧱 Arquitectura y Componentes Técnicos

### 1. Extractor de Transcripciones (`extractor.py`)
* **Biblioteca Principal**: `youtube-transcript-api` (Python).
  * Permite descargar subtítulos/transcripciones oficiales y autogeneradas en segundos, sin necesidad de descargar el archivo de video o audio.
  * Soporta selección de idioma prioritario (`es`, `en`, etc.) y traducción automática de subtítulos.
* **Mecanismo de Respaldo (*Fallback*)**: `yt-dlp` en caso de videos con formatos o restricciones particulares.
* **Extracción de Metadatos**: Obtención del título del video para nombrar los archivos de salida de forma limpia y ordenada.

### 2. Procesador e Integración con Gemini CLI (`generador.py`)
* **Ensamblador de Prompt**: Lee la plantilla de directrices pedagógicas (`prompt.txt`) y concatena la transcripción completa obtenida en el Paso 1.
* **Invocación de `agy`**:
  * Ejecución por consola en modo no interactivo (`--print` / `-p`):
    ```powershell
    agy -p --model gemini-2.5-flash --prompt "<prompt_ensamblado>"
    ```
  * O canalización por entrada estándar (*stdin*):
    ```powershell
    Get-Content prompt_completo.txt | agy -p --model gemini-2.5-flash > apunte_generado.md
    ```
  * Opción alternativa: Integración directa mediante el SDK oficial `google-genai` en Python para ejecución autocontenida.

### 3. Módulo de Conversión a PDF Opcional (`conversor_pdf.py`)
* Activación mediante argumento de consola: `--pdf` o flag interactivo `[s/n]`.
* **Herramientas evaluadas**:
  * **Opción A (Recomendada por estética)**: Conversión Markdown a HTML con estilos CSS (estilo reporte/académico con cajas para las `📌 Notas aclaratorias`) y renderizado a PDF mediante `weasyprint` o `playwright`.
  * **Opción B (Ligera)**: `markdown-pdf` o utilitarios CLI como `md-to-pdf` / `pandoc`.

### 4. Orquestador y Wrapper de Ejecución (`generar_apunte.py` / `run.bat` / `run.ps1`)
* Entrada de comando limpia con soporte para materias:
  ```powershell
  python generar_apunte.py --url "https://www.youtube.com/watch?v=XXXXXX" --materia "matematica" --pdf
  ```
* **Modo Interactivo**: Si no se pasan argumentos por consola (por ejemplo, al ejecutar haciendo doble clic en un script `.bat` o `.ps1`), el sistema pregunta paso a paso:
  1. URL del video de YouTube.
  2. Materia o tema (ej. `matematica`, `fisica`, `programacion`).
  3. ¿Exportar también a PDF? (`s/n`).
* **Estructura resultante**:
  ```text
  analisis_videos/
  ├── matematica/
  │   ├── 01_calculo_diferencial.md
  │   ├── 01_calculo_diferencial.pdf
  │   └── 02_integrales_definidas.md
  └── fisica/
      ├── 01_leyes_de_newton.md
      └── 01_leyes_de_newton.pdf
  ```

---

## 📅 Fases de Implementación

### Fase 1: Preparación del Entorno y Dependencias
- [x] Crear entorno de trabajo / virtualenv (si aplica).
- [x] Instalar paquetes de Python: `youtube-transcript-api`, `yt-dlp`, `markdown-pdf`.
- [x] Validar la disponibilidad y autenticación de `agy` en el PATH de la terminal.

### Fase 2: Módulo de Descarga, Organización y Asignación de ID
- [x] Función para validar y sanitizar el nombre de la materia/carpeta (ej. `matematica`).
- [x] Lógica de asignación automática de ID: escanear la carpeta de la materia y calcular el siguiente número correlativo (`01`, `02`, `03`...).
- [x] Extracción del `video_id` y título limpio del video (para armar nombres como `01_limites_y_continuidad.md`).
- [x] Descarga y concatenación limpia de la transcripción (`youtube-transcript-api` / `yt-dlp`).
- [x] Guardado de la transcripción sin procesar en la carpeta correspondiente.

### Fase 3: Integración y Ejecución con `agy`
- [x] Combinar directrices de `prompt.txt` con la transcripción del video.
- [x] Llamada segura a `agy` (Gemini CLI) en modo no interactivo (`-p`) con `--disable-slash-commands`.
- [x] Guardado del archivo generado directamente en `[materia]/[ID]_[titulo].md` en codificación UTF-8.

### Fase 4: Exportación Opcional a PDF
- [x] Estilos CSS limpios y legibles para apuntes académicos.
- [x] Conversión a PDF guardando en `[materia]/[ID]_[titulo].pdf` si se solicita (`--pdf` o interactivo).

### Fase 5: Interfaz de Usuario y Accesos Directos
- [x] CLI con `argparse` (`--url`, `--materia`, `--pdf`).
- [x] Modo interactivo asistido si se ejecuta sin parámetros (pide URL, materia y confirmación de PDF).
- [x] Archivo `iniciar.bat` para ejecutar en Windows con doble clic de forma sencilla.

### Fase 6: Pruebas de Punta a Punta
- [x] Prueba de extremo a extremo completada con éxito (`01_rick_astley_never_gonna_give_you_up_official`).
- [x] Validación de los archivos generados (`.txt`, `.md` y `.pdf`) en su respectiva carpeta.
