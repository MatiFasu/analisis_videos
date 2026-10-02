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
import tempfile
import base64
import time
from typing import Optional, Tuple, List, Dict
import urllib.request
import urllib.error
import requests
import enriquecedor_visual

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
        r'(?:v=|\/vi\/|youtu\.be\/|\/v\/|\/embed\/|\/shorts\/|\/live\/)([0-9A-Za-z_-]{11})',
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

    raise RuntimeError(
        "No se encontraron subtítulos ni transcripción disponibles para este video. "
        "Si se trata de una transmisión en vivo que terminó hace poco o sigue en curso, "
        "YouTube suele demorar varias horas en procesar y habilitar los subtítulos automáticos."
    )


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
    
    # Usar archivo temporal para pasar el prompt completo a agy con @archivo
    # Esto evita el límite de 32KB en la línea de comandos de Windows sin truncar texto
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tf:
        tf.write(prompt_completo)
        temp_prompt_path = tf.name

    try:
        cmd = ["agy", "-p", f"@{temp_prompt_path}", "--disable-slash-commands"]
        if modelo:
            cmd.extend(["--model", modelo])
        if esfuerzo:
            cmd.extend(["--effort", esfuerzo])

        proceso = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    finally:
        if os.path.exists(temp_prompt_path):
            try:
                os.remove(temp_prompt_path)
            except OSError:
                pass
    
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


def exportar_a_pdf(contenido_markdown: str, ruta_salida_pdf: str, titulo: str = "Apunte", directorio_base: str = "."):
    """
    Convierte el apunte Markdown a PDF con maquetación visual profesional mediante enriquecedor_visual.
    Implementa un compilador inteligente de dos pasadas:
    1. Compila un borrador y analiza la geometría de cada figura con PyMuPDF.
    2. Si detecta que una figura quedó comprimida contra el borde inferior de una página (ancho < 320pt),
       inyecta automáticamente un salto de página para esa figura específica y compila la versión final.
    """
    try:
        from markdown_pdf import MarkdownPdf, Section
        import fitz
    except ImportError:
        raise RuntimeError("Las librerías 'markdown-pdf' o 'pymupdf' no están instaladas.")

    # Procesar diagramas Mermaid con tema visual pro e incrustar todas las imágenes en Base64
    md_para_pdf = enriquecedor_visual.preparar_markdown_para_pdf(contenido_markdown, directorio_base=directorio_base)

    def _compilar(md_texto: str, destino_path: str):
        pdf = MarkdownPdf(toc_level=2, optimize=True)
        pdf.meta["title"] = titulo
        pdf.meta["creator"] = "Generador de Apuntes con Gemini CLI y Enriquecedor Visual"
        seccion = Section(
            md_texto,
            toc=True,
            paper_size="A4",
            borders=(36, 36, -36, -36)
        )
        pdf.add_section(seccion, user_css=enriquecedor_visual.CSS_VISUAL_ACADEMICO)
        pdf.save(destino_path)

    # Identificador de figuras en el markdown procesado
    patron_figura = re.compile(
        r'(<div class="figura-diagrama-contenedor"[^>]*>\s*<img [^>]*alt="Figura (\d+):)'
    )

    # Si no hay figuras con diagramas en el contenido, compilar directo
    if not patron_figura.search(md_para_pdf):
        _compilar(md_para_pdf, ruta_salida_pdf)
        return

    # Bucle de optimización de saltos de página (hasta 5 pasadas para convergencia total)
    todas_aplastadas = set()
    md_actual = md_para_pdf
    MAX_PASADAS = 5

    for pasada in range(1, MAX_PASADAS + 1):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            temp_pdf_path = tf.name

        try:
            _compilar(md_actual, temp_pdf_path)

            doc = fitz.open(temp_pdf_path)
            nuevas_aplastadas = set()
            img_counter = 0

            for p_idx in range(len(doc)):
                page = doc[p_idx]
                imgs = page.get_images()
                for img in imgs:
                    xref = img[0]
                    rects = page.get_image_rects(xref)
                    if not rects:
                        continue
                    w = rects[0].width
                    # Ignorar la portada oficial en la primera página
                    if p_idx == 0 and img_counter == 0:
                        img_counter += 1
                        continue
                    img_counter += 1
                    # Si el ancho renderizado es menor a 350pt (en una página de 500pt utilizable),
                    # la figura fue estrangulada verticalmente por el pie de página
                    if w < 350:
                        nuevas_aplastadas.add(img_counter - 1)

            doc.close()

            # Si no hay nuevas figuras aplastadas o alcanzamos el límite, este PDF es el definitivo
            if not nuevas_aplastadas or pasada == MAX_PASADAS:
                if os.path.exists(ruta_salida_pdf):
                    try:
                        os.remove(ruta_salida_pdf)
                    except OSError:
                        pass
                os.replace(temp_pdf_path, ruta_salida_pdf)
                break

            todas_aplastadas.update(nuevas_aplastadas)
            print(f"[INFO] Optimizador visual (Pasada {pasada}): Reajustando saltos de página en figuras: {sorted(todas_aplastadas)}")

            # Inyectar saltos de página antes de las figuras afectadas
            def _inyectar_salto(match):
                num_fig = int(match.group(2))
                bloque = match.group(1)
                if num_fig in todas_aplastadas:
                    return f'<div style="page-break-before: always; break-before: page;"></div>\n{bloque}'
                return bloque

            md_actual = patron_figura.sub(_inyectar_salto, md_para_pdf)

        finally:
            if os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except OSError:
                    pass


def extraer_id_y_url(linea: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrae la URL y opcionalmente un ID / número de clase personalizado de una línea.
    Soporta formatos como:
      - 'https://youtu.be/...'
      - 'clase 1 -> https://youtu.be/...'
      - 'clase 1 https://youtu.be/...'
      - '1: https://youtu.be/...'
      - '02 | https://youtu.be/...'
    """
    linea = linea.strip()
    if not linea or linea.startswith("#"):
        return None, None

    patron_url = re.compile(r'(https?://[^\s]+|(?:www\.)?youtu(?:be\.com|\.be)/[^\s]+)')
    match = patron_url.search(linea)

    if match:
        url = match.group(1).strip()
        prefijo = linea[:match.start()].strip()
    else:
        partes = re.split(r'->|\||:|\s{2,}', linea, maxsplit=1)
        if len(partes) == 2:
            prefijo = partes[0].strip()
            url = partes[1].strip()
        else:
            prefijo = ""
            url = linea

    # Limpiar separadores sobrantes al final del prefijo
    prefijo = re.sub(r'[\s\->|:=,]+$', '', prefijo).strip()

    id_custom = None
    if prefijo:
        # Extraer número si existe para normalizarlo como '01', '02', '10'...
        num_match = re.search(r'\b\d+\b', prefijo)
        if num_match:
            numero = int(num_match.group(0))
            id_custom = f"{numero:02d}"
        else:
            id_custom = sanitizar_nombre(prefijo, max_len=15)

    return id_custom, url


def leer_urls_desde_archivo(ruta_archivo: str) -> List[Tuple[Optional[str], str]]:
    """Lee un archivo de texto y extrae una lista de pares (id_custom, url)."""
    if not os.path.exists(ruta_archivo):
        return []

    lista = []
    with open(ruta_archivo, "r", encoding="utf-8", errors="ignore") as f:
        for linea in f:
            id_custom, url = extraer_id_y_url(linea)
            if url:
                lista.append((id_custom, url))
    return lista


def procesar_un_video(
    url: str,
    id_custom: Optional[str],
    carpeta_destino: str,
    generar_pdf: bool = False,
    modelo: Optional[str] = None,
    guardar_transcripcion: bool = True,
    es_lote: bool = False
) -> Dict:
    """Procesa un único video: portada, transcripción, apunte con Gemini y PDF opcional."""
    try:
        # 1. Extraer ID del video
        video_id = extraer_id_video(url)
        print(f"\n[1/5] ID del video detectado: {video_id}")

        # 2. Obtener título del video
        print("[2/5] Obteniendo título del video...")
        titulo_video = obtener_titulo_video(video_id)
        print(f"      Título: '{titulo_video}'")

        # 3. Asignar ID correlativo (manual o automático)
        if id_custom:
            id_apunte = id_custom
            print(f"[3/5] ID asignado manualmente: {id_apunte}")
        else:
            id_apunte = obtener_siguiente_id(carpeta_destino)
            print(f"[3/5] ID asignado automáticamente: {id_apunte}")

        titulo_slug = sanitizar_nombre(titulo_video, max_len=45)
        nombre_base = f"{id_apunte}_{titulo_slug}"
        print(f"      Nombre base: {nombre_base}")

        # Descargar portada oficial en HD del video
        nombre_archivo_portada = f"{nombre_base}_portada.jpg"
        ruta_portada = os.path.join(carpeta_destino, nombre_archivo_portada)
        portada_ok = enriquecedor_visual.descargar_portada_video(video_id, ruta_portada)
        if portada_ok:
            print(f"      🖼️ Portada HD descargada: {ruta_portada}")
        else:
            ruta_portada = None

        # 4. Descargar transcripción
        print("[4/5] Extrayendo transcripción del video...")
        transcripcion = obtener_transcripcion(video_id)
        print(f"      Transcripción obtenida ({len(transcripcion.split())} palabras aprox.)")

        # Guardar transcripción de respaldo si se requiere
        if guardar_transcripcion:
            ruta_transcripcion = os.path.join(carpeta_destino, f"{nombre_base}_transcripcion.txt")
            with open(ruta_transcripcion, "w", encoding="utf-8") as f:
                f.write(f"Título: {titulo_video}\nURL: https://www.youtube.com/watch?v={video_id}\n\n{transcripcion}")
            print(f"      Transcripción guardada en: {ruta_transcripcion}")

        # 5. Generar apunte con Gemini
        print("[5/5] Procesando apunte con Gemini...")
        contenido_md = generar_apunte_gemini(
            titulo_video=titulo_video,
            transcripcion=transcripcion,
            modelo=modelo,
            esfuerzo="low"
        )

        # Insertar portada visual en el apunte si fue descargada
        if ruta_portada and os.path.exists(ruta_portada):
            contenido_md = enriquecedor_visual.insertar_portada_en_markdown(
                contenido_md, nombre_archivo_portada, titulo_video
            )

        # Guardar archivo Markdown
        ruta_md = os.path.join(carpeta_destino, f"{nombre_base}.md")
        with open(ruta_md, "w", encoding="utf-8") as f:
            f.write(contenido_md)
        print(f"\n✅ Apunte Markdown creado exitosamente: {ruta_md}")

        # Generar PDF si fue solicitado
        if generar_pdf:
            ruta_pdf = os.path.join(carpeta_destino, f"{nombre_base}.pdf")
            print(f"📄 Compilando PDF con maquetación visual: {ruta_pdf}...")
            try:
                exportar_a_pdf(
                    contenido_md,
                    ruta_pdf,
                    titulo=f"{id_apunte} - {titulo_video}",
                    directorio_base=carpeta_destino
                )
                print(f"✅ Archivo PDF generado exitosamente: {ruta_pdf}")
            except Exception as e:
                print(f"⚠️ No se pudo generar el PDF: {e}")

        return {"status": "ok", "nombre_base": nombre_base, "titulo": titulo_video, "url": url}

    except Exception as e:
        print(f"❌ Error al procesar '{url}': {e}")
        return {"status": "error", "url": url, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Generador automatizado de apuntes desde videos de YouTube.")
    parser.add_argument("--url", "-u", nargs="*", type=str, help="Una o más URLs o IDs de videos de YouTube")
    parser.add_argument("--urls-file", "--file", "-f", type=str, default=None, help="Ruta a archivo .txt con lista de URLs")
    parser.add_argument("--materia", "--tema", "--apunte", "-m", dest="materia", type=str, help="Nombre del apunte o materia (ej. matematica, fisica)")
    parser.add_argument("--dir-apuntes", "--output-dir", type=str, default="apuntes", help="Directorio base para los apuntes (por defecto: apuntes)")
    parser.add_argument("--pdf", action="store_true", help="Generar también el apunte en formato PDF")
    parser.add_argument("--model", type=str, default=None, help="Modelo de Gemini a utilizar (ej. gemini-3.8-flash-low)")
    parser.add_argument("--guardar-transcripcion", action="store_true", default=True, help="Guardar la transcripción original en texto")

    args = parser.parse_args()

    print("=" * 65)
    print(" 🎓 GENERADOR DE APUNTES DE YOUTUBE CON GEMINI CLI (AGY)")
    print("=" * 65)

    directorio_script = os.path.dirname(os.path.abspath(__file__))
    ruta_urls_txt = os.path.join(directorio_script, "urls.txt")
    lista_videos: List[Tuple[Optional[str], str]] = []

    # 1. Determinar lista de videos (CLI o interactivo)
    if args.urls_file:
        lista_videos = leer_urls_desde_archivo(args.urls_file)
        if not lista_videos:
            print(f"❌ Error: No se encontraron URLs válidas en '{args.urls_file}'.")
            return
    elif args.url:
        for item in args.url:
            cid, curl = extraer_id_y_url(item)
            if curl:
                lista_videos.append((cid, curl))
    else:
        # Modo interactivo
        # Comprobar si urls.txt tiene contenido activo
        urls_en_archivo = leer_urls_desde_archivo(ruta_urls_txt)
        usar_urls_txt = False
        if urls_en_archivo:
            print(f"\n📄 Se detectaron {len(urls_en_archivo)} video(s) configurados en 'urls.txt':")
            for i, (cid, curl) in enumerate(urls_en_archivo[:5], 1):
                pref = f"[{cid}] " if cid else ""
                print(f"   {i}. {pref}{curl}")
            if len(urls_en_archivo) > 5:
                print(f"   ... y {len(urls_en_archivo) - 5} más.")

            try:
                opc = input(f"\n👉 ¿Deseás procesar los {len(urls_en_archivo)} videos de 'urls.txt'? (S/n): ").strip().lower()
                if opc in ["", "s", "si", "sí", "y", "yes"]:
                    lista_videos = urls_en_archivo
                    usar_urls_txt = True
            except (KeyboardInterrupt, EOFError):
                print("\nOperación cancelada.")
                return

        if not usar_urls_txt:
            print("\n👉 Ingresá la URL del video de YouTube.")
            print("   (Podés ingresar una URL, varias separadas por coma, la ruta a un archivo .txt,")
            print("    o incluir número/clase ej: 'clase 1 -> https://...'):")
            try:
                entrada_usuario = input("🔗 URL o archivo: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nOperación cancelada.")
                return

            if not entrada_usuario:
                print("❌ Error: No se ingresó ninguna URL.")
                return

            # Si ingresó una ruta a un archivo de texto existente
            if os.path.isfile(entrada_usuario):
                lista_videos = leer_urls_desde_archivo(entrada_usuario)
            elif "\n" in entrada_usuario:
                for l in entrada_usuario.splitlines():
                    cid, curl = extraer_id_y_url(l)
                    if curl:
                        lista_videos.append((cid, curl))
            elif "," in entrada_usuario:
                for l in entrada_usuario.split(","):
                    cid, curl = extraer_id_y_url(l)
                    if curl:
                        lista_videos.append((cid, curl))
            else:
                cid, curl = extraer_id_y_url(entrada_usuario)
                if curl:
                    lista_videos.append((cid, curl))

    if not lista_videos:
        print("❌ Error: No se pudieron extraer URLs válidas para procesar.")
        return

    # 2. Solicitar nombre de la categoría o materia
    materia_input = args.materia
    if not materia_input:
        try:
            materia_input = input("\n👉 Ingresá el nombre del apunte o materia (ej: bettatech, teoria_de_juegos): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            return

    if not materia_input:
        materia_input = "general"

    # 3. Solicitar opción de PDF
    generar_pdf = args.pdf
    if not args.pdf and not args.url and not args.urls_file:
        try:
            opc_pdf = input("👉 ¿Querés generar también los archivos PDF? (s/N): ").strip().lower()
            generar_pdf = opc_pdf in ["s", "si", "sí", "y", "yes"]
        except (KeyboardInterrupt, EOFError):
            pass

    # 4. Preparar carpeta de destino dentro de apuntes/
    slug_apunte = sanitizar_nombre(materia_input, max_len=30)
    dir_base_apuntes = args.dir_apuntes
    if not os.path.isabs(dir_base_apuntes):
        dir_base_apuntes = os.path.join(directorio_script, dir_base_apuntes)
    carpeta_destino = os.path.join(dir_base_apuntes, slug_apunte)
    os.makedirs(carpeta_destino, exist_ok=True)

    try:
        ruta_mostrar = os.path.relpath(carpeta_destino, os.getcwd()).replace(os.sep, '/')
    except ValueError:
        ruta_mostrar = carpeta_destino.replace(os.sep, '/')

    total_videos = len(lista_videos)
    es_lote = total_videos > 1

    if es_lote:
        print("\n" + "=" * 65)
        print(f" 📦 MODO LOTE: Procesando {total_videos} videos en './{ruta_mostrar}/'")
        print("=" * 65)
    else:
        print(f"\nCarpeta destino: ./{ruta_mostrar}/")

    exitosos = []
    fallidos = []

    for idx, (cid, curl) in enumerate(lista_videos, start=1):
        if es_lote:
            tag_id = f" (ID: {cid})" if cid else " (ID: automático)"
            print("\n" + "-" * 65)
            print(f" ▶️ [{idx}/{total_videos}] Procesando video{tag_id}: {curl}")
            print("-" * 65)

        resultado = procesar_un_video(
            url=curl,
            id_custom=cid,
            carpeta_destino=carpeta_destino,
            generar_pdf=generar_pdf,
            modelo=args.model,
            guardar_transcripcion=args.guardar_transcripcion,
            es_lote=es_lote
        )

        if resultado["status"] == "ok":
            exitosos.append(resultado)
        else:
            fallidos.append(resultado)

        # Pequeña pausa preventiva entre videos si hay más de uno
        if es_lote and idx < total_videos:
            time.sleep(1.5)

    # 5. Resumen final
    print("\n" + "=" * 65)
    if es_lote:
        print(" 🏁 RESUMEN DEL PROCESAMIENTO EN LOTE")
        print("=" * 65)
        print(f" ✅ Exitosos: {len(exitosos)} de {total_videos}")
        for item in exitosos:
            print(f"    • {item['nombre_base']} ({item['titulo'][:50]})")

        if fallidos:
            print(f"\n ❌ Fallidos: {len(fallidos)} de {total_videos}")
            for item in fallidos:
                print(f"    • {item['url']} -> {item['error']}")

        print(f"\n 📂 Todo el material guardado en: ./{ruta_mostrar}/")
    else:
        if exitosos:
            print(f" 🎉 ¡Proceso finalizado! Los archivos están listos en: ./{ruta_mostrar}/")
        else:
            print(" ❌ No se pudo completar el apunte.")
    print("=" * 65)


if __name__ == "__main__":
    main()
