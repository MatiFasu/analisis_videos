#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generar_apunte.py
Automatización para la generación de apuntes estructurados a partir de videos de YouTube.
Organiza el material por materias/carpetas y asigna identificadores numéricos correlativos.
"""

import os
import sys
import re
import json
import argparse
import unicodedata
import subprocess
import urllib.request
import urllib.error

# Forzar codificación UTF-8 en stdout y stderr para Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


def extraer_id_video(url_o_id: str) -> str:
    """Extrae el ID del video de YouTube a partir de una URL o ID crudo."""
    url_o_id = url_o_id.strip()
    patrones = [
        r'(?:v=|\/vi\/|youtu\.be\/|\/v\/|\/embed\/|\/shorts\/)([0-9A-Za-z_-]{11})',
        r'^([0-9A-Za-z_-]{11})$'
    ]
    for patron in patrones:
        match = re.search(patron, url_o_id)
        if match:
            return match.group(1)
    raise ValueError(f"No se pudo identificar un ID de video válido en: '{url_o_id}'")


def obtener_titulo_video(video_id: str) -> str:
    """Obtiene el título oficial del video mediante la API oEmbed o fallback con yt-dlp."""
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            titulo = data.get("title")
            if titulo:
                return titulo
    except Exception:
        pass

    # Fallback con yt-dlp si está instalado
    try:
        res = subprocess.run(
            ["yt-dlp", "--print", "title", "--skip-download", f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, encoding='utf-8', timeout=15
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    return f"Video_{video_id}"


def obtener_transcripcion(video_id: str) -> str:
    """Descarga la transcripción del video en español o traduce si está en otro idioma."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise RuntimeError("La librería 'youtube-transcript-api' no está instalada. Ejecutá: pip install -r requirements.txt")

    api = YouTubeTranscriptApi()
    
    try:
        tl = api.list(video_id)
        # Intentar obtener español (manual o autogenerado), o inglés
        try:
            transcript = tl.find_transcript(['es-419', 'es', 'en'])
        except Exception:
            # Si no está en español o inglés directo, tomar el primero y traducir a español si es posible
            transcript = next(iter(tl))
            if transcript.is_translatable:
                transcript = transcript.translate('es')
                
        datos = transcript.fetch().to_raw_data()
        lineas = [item['text'].strip() for item in datos if item.get('text')]
        texto_completo = " ".join(lineas)
        return texto_completo
    except Exception as e:
        # Fallback con yt-dlp si la API de transcripciones falla
        print(f"Aviso: Falló youtube-transcript-api ({e}). Intentando con yt-dlp...")
        try:
            vtt_file = f"sub_temp_{video_id}.es.vtt"
            subprocess.run([
                "yt-dlp", "--write-auto-sub", "--write-sub", "--sub-lang", "es,en",
                "--skip-download", "-o", f"sub_temp_{video_id}.%(ext)s",
                f"https://www.youtube.com/watch?v={video_id}"
            ], capture_output=True, text=True, timeout=30)
            
            # Buscar archivo de subtítulos generado
            for arch in os.listdir("."):
                if arch.startswith(f"sub_temp_{video_id}"):
                    with open(arch, "r", encoding="utf-8", errors="ignore") as f:
                        contenido = f.read()
                    os.remove(arch)
                    # Limpieza básica de formato VTT
                    lineas_vtt = re.sub(r'<[^>]+>', '', contenido)
                    lineas_vtt = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', '', lineas_vtt)
                    lineas_vtt = [l.strip() for l in lineas_vtt.splitlines() if l.strip() and not l.strip().isdigit() and 'WEBVTT' not in l]
                    return " ".join(lineas_vtt)
        except Exception as fallback_error:
            raise RuntimeError(f"No se pudo obtener la transcripción del video: {fallback_error}")

    raise RuntimeError("No se encontraron subtítulos ni transcripción disponibles para este video.")


def sanitizar_nombre(texto: str, max_len: int = 50) -> str:
    """Convierte un texto en un slug seguro para nombres de archivos y carpetas."""
    # Quitar tildes y caracteres especiales
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^\w\s-]', '', texto).strip().lower()
    texto = re.sub(r'[-\s]+', '_', texto)
    return texto[:max_len].rstrip('_')


def obtener_siguiente_id(directorio_materia: str) -> str:
    """Escanea los archivos existentes en la carpeta de la materia y devuelve el siguiente ID formateado."""
    if not os.path.exists(directorio_materia):
        return "01"
    
    patron = re.compile(r'^(\d+)_')
    ids_encontrados = []
    
    for nombre in os.listdir(directorio_materia):
        m = patron.match(nombre)
        if m:
            ids_encontrados.append(int(m.group(1)))
            
    siguiente_numero = max(ids_encontrados, default=0) + 1
    return f"{siguiente_numero:02d}"


def cargar_prompt_base() -> str:
    """Lee el archivo prompt.txt si existe, o retorna una directriz predeterminada."""
    ruta_prompt = os.path.join(os.path.dirname(__file__), "prompt.txt")
    if os.path.exists(ruta_prompt):
        with open(ruta_prompt, "r", encoding="utf-8") as f:
            return f.read().strip()
    return """Actuá como un asistente experto en generar apuntes de estudio a partir de transcripciones de video.
Transformá la transcripción en un apunte claro, completo y bien organizado en formato Markdown, con título, secciones por temas, notas aclaratorias (📌 Nota aclaratoria), resumen y preguntas de repaso."""


def generar_apunte_gemini(titulo_video: str, transcripcion: str, modelo: str = None, esfuerzo: str = "low") -> str:
    """Envía el prompt ensamblado a Gemini CLI (agy) o SDK para procesar el apunte."""
    prompt_base = cargar_prompt_base()
    prompt_completo = f"""{prompt_base}

---
Título del video: {titulo_video}

Transcripción del video:
{transcripcion}
"""
    # Si GEMINI_API_KEY está configurada, usar google-genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            print("[INFO] Generando apunte con SDK google-genai (GEMINI_API_KEY detectada)...")
            client = genai.Client(api_key=api_key)
            model_name = modelo or "gemini-2.5-flash"
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_completo
            )
            return response.text
        except Exception as e:
            print(f"[AVISO] Falló el SDK directo ({e}). Intentando con agy CLI...")

    # Por defecto, invocar agy CLI
    print(f"[INFO] Generando apunte con Gemini CLI (`agy`)...")
    
    # Manejar límite de longitud de línea de comandos en Windows (32KB max)
    if len(prompt_completo) > 28000:
        print("[AVISO] La transcripción es muy extensa. Optimizando texto para la consola...")
        # Recortar si supera ampliamente el búfer de comandos
        limite_transcripcion = 28000 - len(prompt_base) - 500
        transcripcion_recortada = transcripcion[:limite_transcripcion] + "\n[...transcripción truncada por extensión...]"
        prompt_completo = f"""{prompt_base}

---
Título del video: {titulo_video}

Transcripción del video:
{transcripcion_recortada}
"""

    cmd = ["agy", "-p", prompt_completo, "--disable-slash-commands"]
    if modelo:
        cmd.extend(["--model", modelo])
    if esfuerzo:
        cmd.extend(["--effort", esfuerzo])

    proceso = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    
    if proceso.returncode != 0:
        raise RuntimeError(f"Error al ejecutar agy: {proceso.stderr.strip()}")
    
    resultado = proceso.stdout.strip()
    if not resultado:
        raise RuntimeError("La llamada a Gemini CLI no devolvió contenido.")
    
    # Limpiar bloques envolventes de markdown si los hubiera
    if resultado.startswith("```markdown") and resultado.endswith("```"):
        resultado = resultado[11:-3].strip()
    elif resultado.startswith("```md") and resultado.endswith("```"):
        resultado = resultado[5:-3].strip()

    return resultado


def exportar_a_pdf(contenido_markdown: str, ruta_salida_pdf: str, titulo: str = "Apunte"):
    """Convierte el apunte Markdown a PDF con diseño académico utilizando markdown-pdf."""
    try:
        from markdown_pdf import MarkdownPdf, Section
    except ImportError:
        raise RuntimeError("La librería 'markdown-pdf' no está instalada. Ejecutá: pip install -r requirements.txt")

    css_academico = """
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 10.5pt;
        line-height: 1.55;
        color: #1a202c;
    }
    h1 {
        color: #1e3a8a;
        font-size: 18pt;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 6px;
        margin-top: 0;
        margin-bottom: 12px;
    }
    h2 {
        color: #2563eb;
        font-size: 14pt;
        margin-top: 18px;
        margin-bottom: 8px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 4px;
    }
    h3 {
        color: #334155;
        font-size: 12pt;
        margin-top: 14px;
        margin-bottom: 6px;
    }
    blockquote {
        background-color: #f0f9ff;
        border-left: 4px solid #0284c7;
        padding: 8px 14px;
        margin: 12px 0;
        border-radius: 4px;
        color: #0c4a6e;
    }
    code {
        background-color: #f1f5f9;
        padding: 2px 4px;
        border-radius: 3px;
        font-family: Consolas, Monaco, "Courier New", monospace;
        font-size: 9.5pt;
        color: #0f172a;
    }
    pre code {
        display: block;
        padding: 10px;
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 5px;
        overflow-x: auto;
    }
    ul, ol {
        padding-left: 22px;
        margin-top: 6px;
        margin-bottom: 10px;
    }
    li {
        margin-bottom: 4px;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 14px 0;
    }
    th, td {
        border: 1px solid #cbd5e1;
        padding: 6px 10px;
        text-align: left;
    }
    th {
        background-color: #f1f5f9;
        font-weight: bold;
    }
    """

    pdf = MarkdownPdf(toc_level=2)
    pdf.meta["title"] = titulo
    pdf.meta["creator"] = "Generador de Apuntes con Gemini CLI"
    
    seccion = Section(contenido_markdown, toc=True, paper_size="A4", borders=(36, 36, -36, -36))
    pdf.add_section(seccion, user_css=css_academico)
    pdf.save(ruta_salida_pdf)


def main():
    parser = argparse.ArgumentParser(description="Generador automatizado de apuntes desde videos de YouTube.")
    parser.add_argument("--url", "-u", type=str, help="URL o ID del video de YouTube")
    parser.add_argument("--materia", "-m", type=str, help="Nombre de la materia o tema (ej. matematica, fisica)")
    parser.add_argument("--pdf", action="store_true", help="Generar también el apunte en formato PDF")
    parser.add_argument("--model", type=str, default=None, help="Modelo de Gemini a utilizar (ej. gemini-3.8-flash-low)")
    parser.add_argument("--guardar-transcripcion", action="store_true", default=True, help="Guardar la transcripción original en texto")

    args = parser.parse_args()

    print("=" * 65)
    print(" 🎓 GENERADOR DE APUNTES DE YOUTUBE CON GEMINI CLI (AGY)")
    print("=" * 65)

    # Modo interactivo si faltan argumentos principales
    url_input = args.url
    if not url_input:
        try:
            url_input = input("👉 Ingresá la URL del video de YouTube: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            return

    materia_input = args.materia
    if not materia_input:
        try:
            materia_input = input("👉 Ingresá la Materia o Carpeta (ej: matematica, fisica): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            return

    generar_pdf = args.pdf
    if not args.pdf and not args.url:
        try:
            opc_pdf = input("👉 ¿Querés generar también el archivo PDF? (s/N): ").strip().lower()
            generar_pdf = opc_pdf in ["s", "si", "sí", "y", "yes"]
        except (KeyboardInterrupt, EOFError):
            pass

    if not url_input:
        print("❌ Error: Se requiere la URL de un video.")
        return
    if not materia_input:
        materia_input = "general"

    # 1. Extraer ID del video
    try:
        video_id = extraer_id_video(url_input)
        print(f"\n[1/5] ID del video detectado: {video_id}")
    except Exception as e:
        print(f"❌ Error al procesar URL: {e}")
        return

    # 2. Obtener título del video
    print("[2/5] Obteniendo título del video...")
    titulo_video = obtener_titulo_video(video_id)
    print(f"      Título: '{titulo_video}'")

    # 3. Preparar carpeta de materia y calcular ID correlativo
    carpeta_materia = sanitizar_nombre(materia_input, max_len=30)
    os.makedirs(carpeta_materia, exist_ok=True)
    
    id_apunte = obtener_siguiente_id(carpeta_materia)
    titulo_slug = sanitizar_nombre(titulo_video, max_len=45)
    nombre_base = f"{id_apunte}_{titulo_slug}"
    
    print(f"[3/5] Carpeta destino: ./{carpeta_materia}/")
    print(f"      ID asignado: {id_apunte}  ->  Nombre base: {nombre_base}")

    # 4. Descargar transcripción
    print("[4/5] Extrayendo transcripción del video...")
    try:
        transcripcion = obtener_transcripcion(video_id)
        print(f"      Transcripción obtenida ({len(transcripcion.split())} palabras aprox.)")
    except Exception as e:
        print(f"❌ Error al obtener subtítulos: {e}")
        return

    # Guardar transcripción de respaldo si se requiere
    if args.guardar_transcripcion:
        ruta_transcripcion = os.path.join(carpeta_materia, f"{nombre_base}_transcripcion.txt")
        with open(ruta_transcripcion, "w", encoding="utf-8") as f:
            f.write(f"Título: {titulo_video}\nURL: https://www.youtube.com/watch?v={video_id}\n\n{transcripcion}")
        print(f"      Transcripción guardada en: {ruta_transcripcion}")

    # 5. Generar apunte con Gemini
    print("[5/5] Procesando apunte con Gemini...")
    try:
        contenido_md = generar_apunte_gemini(
            titulo_video=titulo_video,
            transcripcion=transcripcion,
            modelo=args.model,
            esfuerzo="low"
        )
    except Exception as e:
        print(f"❌ Error al generar apunte con Gemini: {e}")
        return

    # Guardar archivo Markdown
    ruta_md = os.path.join(carpeta_materia, f"{nombre_base}.md")
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(contenido_md)
    print(f"\n✅ Apunte Markdown creado exitosamente: {ruta_md}")

    # Generar PDF si fue solicitado
    if generar_pdf:
        ruta_pdf = os.path.join(carpeta_materia, f"{nombre_base}.pdf")
        print(f"📄 Compilando PDF estilizado: {ruta_pdf}...")
        try:
            exportar_a_pdf(contenido_md, ruta_pdf, titulo=f"{id_apunte} - {titulo_video}")
            print(f"✅ Archivo PDF generado exitosamente: {ruta_pdf}")
        except Exception as e:
            print(f"⚠️ No se pudo generar el PDF: {e}")

    print("\n" + "=" * 65)
    print(f" 🎉 ¡Proceso finalizado! Los archivos están listos en: ./{carpeta_materia}/")
    print("=" * 65)


if __name__ == "__main__":
    main()
