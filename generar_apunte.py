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
import random
import logging
import argparse
import unicodedata
import subprocess
import tempfile
import time
from typing import Optional, Tuple, List, Dict, Callable, Any, Union
import urllib.request
import urllib.error
import enriquecedor_visual

# Forzar codificación UTF-8 en stdout y stderr para Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Logger global
logger = logging.getLogger("generar_apunte")


def configurar_logging(verbose: bool = False, archivo_log: Optional[str] = None):
    """Configura logging estructurado con marcas de tiempo y niveles."""
    nivel = logging.DEBUG if verbose else logging.INFO
    formato = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"

    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if archivo_log:
        handlers.append(logging.FileHandler(archivo_log, encoding="utf-8"))

    logging.basicConfig(
        level=nivel,
        format=formato,
        datefmt=datefmt,
        handlers=handlers,
        force=True
    )


def reintentar_con_backoff(
    func: Callable[[], Any],
    max_intentos: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 25.0,
    descripcion: str = "operación",
    excepciones_reintentables: Tuple[type, ...] = (Exception,)
) -> Any:
    """
    Ejecuta una función reintentando con retroceso exponencial y jitter si falla.
    """
    ultimo_error = None
    for intento in range(1, max_intentos + 1):
        try:
            return func()
        except excepciones_reintentables as e:
            ultimo_error = e
            if intento == max_intentos:
                logger.error(f"❌ Falló '{descripcion}' tras {max_intentos} intentos: {e}")
                raise
            demora = min(max_delay, base_delay * (2 ** (intento - 1))) + random.uniform(0.1, 0.8)
            logger.warning(
                f"⚠️ Intento {intento}/{max_intentos} de '{descripcion}' falló ({e}). "
                f"Reintentando en {demora:.1f}s..."
            )
            time.sleep(demora)
    raise ultimo_error


def decodificar_bytes_salida(datos: Union[bytes, str, None]) -> str:
    """Decodifica bytes a texto probando utf-8, cp1252 y fallback con reemplazo."""
    if not datos:
        return ""
    if isinstance(datos, str):
        return datos
    for codificacion in ("utf-8", "cp1252", "latin-1"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("utf-8", errors="replace")


def ejecutar_subproceso_texto(
    cmd: List[str],
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None
) -> Tuple[int, str, str]:
    """
    Ejecuta un subproceso de forma segura contra problemas de decodificación en Windows.
    Captura bytes crudos para evitar que _readerthread de Python falle con UnicodeDecodeError.
    Devuelve (returncode, stdout_str, stderr_str).
    """
    entorno = os.environ.copy()
    entorno["PYTHONIOENCODING"] = "utf-8"
    if env:
        entorno.update(env)

    proceso = subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        env=entorno
    )
    salida = decodificar_bytes_salida(proceso.stdout)
    error = decodificar_bytes_salida(proceso.stderr)
    return proceso.returncode, salida, error


def es_url_playlist(url: str) -> bool:
    """Detecta si la URL provista corresponde a una lista de reproducción (contiene list=)."""
    if not url:
        return False
    return bool(re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url.strip()))


def extraer_id_playlist(url: str) -> Optional[str]:
    """Extrae el identificador de la playlist (parámetro list=)."""
    m = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url.strip())
    return m.group(1) if m else None


def parsear_salida_playlist_ytdlp(salida_texto: str) -> List[Tuple[int, str, str]]:
    """
    Parsea la salida de `yt-dlp --flat-playlist --print "%(playlist_index)s|%(id)s|%(title)s"`.
    Devuelve lista de tuplas ordenadas (indice_playlist, video_id, titulo).
    """
    videos = []
    for linea in salida_texto.strip().splitlines():
        linea = linea.strip()
        if not linea or "|" not in linea:
            continue
        partes = linea.split("|", 2)
        if len(partes) == 3:
            raw_idx, vid, tit = partes
            try:
                idx = int(raw_idx)
            except ValueError:
                idx = len(videos) + 1
            vid = vid.strip()
            tit = tit.strip() or f"Video_{vid}"
            if len(vid) == 11:
                videos.append((idx, vid, tit))
    videos.sort(key=lambda x: x[0])
    return videos


def obtener_videos_de_playlist(
    url_playlist: str,
    desde: Optional[int] = None,
    hasta: Optional[int] = None
) -> Tuple[str, List[Tuple[int, str, str]]]:
    """
    Llama a `yt-dlp --flat-playlist --print "%(playlist_title)s|%(playlist_index)s|%(id)s|%(title)s"`
    sin descargar videos ni audio, y devuelve el título de la playlist y la lista ordenada
    de videos [(indice_playlist, video_id, titulo), ...].
    """
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(playlist_title)s|%(playlist_index)s|%(id)s|%(title)s"
    ]

    # Aplicar rango directo en yt-dlp si se especificó
    if desde is not None or hasta is not None:
        d_str = str(desde) if desde is not None else "1"
        h_str = str(hasta) if hasta is not None else ""
        cmd.extend(["--playlist-items", f"{d_str}:{h_str}"])

    cmd.append(url_playlist)

    logger.debug(f"Ejecutando yt-dlp para playlist: {' '.join(cmd)}")
    try:
        retcode, salida, err = ejecutar_subproceso_texto(cmd, timeout=45)
    except subprocess.TimeoutExpired:
        raise TimeoutError("La consulta de la playlist a YouTube excedió el tiempo límite (45s).")

    if retcode != 0:
        err = err.strip()
        if "private" in err.lower():
            raise ValueError("La playlist es privada o requiere inicio de sesión.")
        elif "does not exist" in err.lower() or "not found" in err.lower():
            raise ValueError("La playlist no existe o fue eliminada.")
        raise ValueError(f"No se pudo consultar la playlist con yt-dlp: {err}")

    salida = salida.strip()
    if not salida:
        raise ValueError("La playlist no contiene videos accesibles o está vacía.")

    titulo_playlist = "Playlist"
    videos: List[Tuple[int, str, str]] = []

    for linea in salida.splitlines():
        linea = linea.strip()
        if not linea or "|" not in linea:
            continue
        partes = linea.split("|", 3)
        if len(partes) == 4:
            pltit, raw_idx, vid, tit = partes
            if pltit and pltit.strip() and pltit.strip() != "NA":
                titulo_playlist = pltit.strip()
            try:
                idx = int(raw_idx)
            except ValueError:
                idx = len(videos) + 1
            vid = vid.strip()
            tit = tit.strip() or f"Video_{vid}"
            if len(vid) == 11:
                videos.append((idx, vid, tit))

    # Filtrar en memoria por consistencia
    if desde is not None:
        videos = [v for v in videos if v[0] >= desde]
    if hasta is not None:
        videos = [v for v in videos if v[0] <= hasta]

    videos.sort(key=lambda x: x[0])
    return titulo_playlist, videos


def parsear_rango_interactivo(entrada: str, total_disponible: int) -> Tuple[bool, Optional[Tuple[int, int]]]:
    """
    Parsea la selección de cantidad o rango de videos en modo interactivo.
    Devuelve (continuar: bool, rango: Optional[Tuple[desde, hasta]]).
    Si continuar es False, se cancela la operación.
    """
    texto = entrada.strip().lower()
    if not texto or texto in ["s", "si", "sí", "y", "yes", "todos", "todas", "t"]:
        return True, (1, total_disponible)

    if texto in ["n", "no", "cancelar", "cancel", "salir", "exit", "q"]:
        return False, None

    # Caso: rango con separadores "-", "a", "al", ":", ".."
    m_rango = re.match(r'^(\d+)\s*(?:-|a|al|:|\.\.)\s*(\d+)$', texto)
    if m_rango:
        d = int(m_rango.group(1))
        h = int(m_rango.group(2))
        d = max(1, d)
        h = min(total_disponible, h)
        if d > h:
            d, h = h, d
        return True, (d, h)

    # Caso: "desde X"
    if texto.startswith("desde"):
        m = re.match(r'^desde\s*(\d+)$', texto)
        if m:
            d = max(1, min(int(m.group(1)), total_disponible))
            return True, (d, total_disponible)

    # Caso: "hasta X"
    if texto.startswith("hasta"):
        m = re.match(r'^hasta\s*(\d+)$', texto)
        if m:
            h = max(1, min(int(m.group(1)), total_disponible))
            return True, (1, h)

    # Caso: un único número N (cantidad de videos a procesar desde el 1)
    if texto.isdigit():
        n = int(texto)
        if n <= 0:
            return False, None
        h = min(total_disponible, n)
        return True, (1, h)

    return True, (1, total_disponible)


def resolver_y_expandir_entradas(
    entradas_crudas: List[Tuple[Optional[str], str]],
    video_only: bool = False,
    desde: Optional[int] = None,
    hasta: Optional[int] = None,
    es_interactivo: bool = False
) -> Tuple[Optional[str], List[Tuple[Optional[str], str]]]:
    """
    Auto-detecta playlists en cualquier entrada y las expande a sus videos ordenados,
    respetando playlist_index para la numeración y rangos (--desde / --hasta).
    Devuelve (materia_sugerida, lista_expandida_de_pares_id_url).
    """
    lista_final: List[Tuple[Optional[str], str]] = []
    materia_sugerida: Optional[str] = None

    for cid_orig, url in entradas_crudas:
        if not url:
            continue

        if es_url_playlist(url) and not video_only:
            try:
                print("🔍 Consultando playlist en YouTube...")
                titulo_pl, videos_pl = obtener_videos_de_playlist(url, desde=desde, hasta=hasta)
                if not materia_sugerida and titulo_pl:
                    materia_sugerida = titulo_pl

                total_pl = len(videos_pl)
                rango_txt = f"{desde or 1} al {hasta or total_pl}" if (desde or hasta) else f"1 al {total_pl}"
                print(f"\n📋 Se detectaron {total_pl} videos en la playlist '{titulo_pl}' (rango: {rango_txt}).")

                if es_interactivo and len(entradas_crudas) == 1 and (desde is None and hasta is None):
                    try:
                        print("\n👉 ¿Cuántos videos querés procesar de la playlist?")
                        print(f"   • Presioná [Enter] para procesar todos (1 al {total_pl})")
                        print("   • O ingresá una cantidad (ej: 3 para procesar del 1 al 3)")
                        print("   • O un rango específico (ej: 1-5 o 10 al 20)")
                        print("   • 'n' para cancelar")
                        resp = input(f"Opción [Enter = todos ({total_pl})]: ").strip()
                        continuar, rango_sel = parsear_rango_interactivo(resp, total_pl)
                        if not continuar or not rango_sel:
                            print("Operación cancelada por el usuario.")
                            return None, []
                        d_sel, h_sel = rango_sel
                        if d_sel != 1 or h_sel != total_pl:
                            videos_pl = [v for v in videos_pl if d_sel <= v[0] <= h_sel]
                            print(f"🎯 Selección aplicada: {len(videos_pl)} videos (del {d_sel} al {h_sel}).")
                    except (KeyboardInterrupt, EOFError):
                        print("\nOperación cancelada.")
                        return None, []
                elif es_interactivo and len(entradas_crudas) == 1:
                    try:
                        pregunta = f"👉 ¿Procesar los {total_pl} videos detectados en el rango {rango_txt}? (S/n): "
                        resp = input(pregunta).strip().lower()
                        if resp not in ["", "s", "si", "sí", "y", "yes"]:
                            print("Operación cancelada por el usuario.")
                            return None, []
                    except (KeyboardInterrupt, EOFError):
                        print("\nOperación cancelada.")
                        return None, []

                max_pos = max([v[0] for v in videos_pl], default=total_pl)
                ancho = 3 if max_pos >= 100 else 2

                for p_idx, vid, _ in videos_pl:
                    prefix_id = f"{p_idx:0{ancho}d}"
                    video_url = f"https://www.youtube.com/watch?v={vid}"
                    lista_final.append((prefix_id, video_url))

            except Exception as e:
                logger.error(f"Error al procesar playlist '{url}': {e}")
                try:
                    single_id = extraer_id_video(url)
                    print(f"⚠️ Falló la playlist ({e}). Procesando únicamente el video individual detectado: {single_id}")
                    lista_final.append((cid_orig, f"https://www.youtube.com/watch?v={single_id}"))
                except Exception:
                    print(f"❌ No se pudo procesar la URL de playlist: {e}")
        else:
            lista_final.append((cid_orig, url))

    return materia_sugerida, lista_final


def escanear_videos_procesados(directorio_materia: str) -> Dict[str, str]:
    """
    Escanea la carpeta destino buscando qué video_id ya fueron procesados.
    Revisa archivos *_transcripcion.txt y *.md.
    Devuelve diccionario {video_id: nombre_archivo}.
    """
    if not os.path.exists(directorio_materia):
        return {}

    procesados: Dict[str, str] = {}
    patron_id_url = re.compile(r'watch\?v=([0-9A-Za-z_-]{11})|youtu\.be\/([0-9A-Za-z_-]{11})')

    for nombre in os.listdir(directorio_materia):
        ruta = os.path.join(directorio_materia, nombre)
        if not os.path.isfile(ruta):
            continue

        if nombre.endswith("_transcripcion.txt") or nombre.endswith(".md"):
            try:
                with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                    primeras_lineas = "".join([f.readline() for _ in range(30)])
                    m = patron_id_url.search(primeras_lineas)
                    if m:
                        vid = m.group(1) or m.group(2)
                        procesados[vid] = nombre
            except Exception:
                pass

    return procesados


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
        retcode, stdout_tit, _ = ejecutar_subproceso_texto(
            ["yt-dlp", "--print", "title", "--skip-download", f"https://www.youtube.com/watch?v={video_id}"],
            timeout=15
        )
        if retcode == 0 and stdout_tit.strip():
            return stdout_tit.strip()
    except Exception:
        pass

    return f"Video_{video_id}"


def obtener_transcripcion(video_id: str) -> str:
    """Descarga la transcripción del video en español o traduce si está en otro idioma con reintentos."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise RuntimeError("La librería 'youtube-transcript-api' no está instalada. Ejecutá: pip install -r requirements.txt")

    api = YouTubeTranscriptApi()

    def _descargar_api() -> str:
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
        return " ".join(lineas)

    try:
        return reintentar_con_backoff(
            _descargar_api,
            max_intentos=2,
            base_delay=2.0,
            descripcion=f"obtención de transcripción API ({video_id})"
        )
    except Exception as e:
        # Fallback con yt-dlp si la API de transcripciones falla
        logger.warning(f"Aviso: Falló youtube-transcript-api ({e}). Intentando con yt-dlp...")
        try:
            ejecutar_subproceso_texto([
                "yt-dlp", "--write-auto-sub", "--write-sub", "--sub-lang", "es,en",
                "--skip-download", "-o", f"sub_temp_{video_id}.%(ext)s",
                f"https://www.youtube.com/watch?v={video_id}"
            ], timeout=30)
            
            # Buscar archivo de subtítulos generado
            for arch in os.listdir("."):
                if arch.startswith(f"sub_temp_{video_id}"):
                    with open(arch, "r", encoding="utf-8", errors="ignore") as f:
                        contenido = f.read()
                    os.remove(arch)
                    # Limpieza básica de formato VTT
                    lineas_vtt = re.sub(r'<[^>]+>', '', contenido)
                    lineas_vtt = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}', '', lineas_vtt)
                    lineas_filtradas = [linea.strip() for linea in lineas_vtt.splitlines() if linea.strip() and not linea.strip().isdigit() and 'WEBVTT' not in linea]
                    return " ".join(lineas_filtradas)
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


def generar_apunte_gemini(
    titulo_video: str,
    transcripcion: str,
    modelo: Optional[str] = None,
    esfuerzo: str = "low",
    timeout_segundos: int = 300,
    max_reintentos: int = 3
) -> str:
    """
    Envía el prompt ensamblado a Gemini CLI (agy) o SDK para procesar el apunte.
    Implementa control de esfuerzo (--effort), timeout configurable y reintentos con backoff exponencial.
    """
    prompt_base = cargar_prompt_base()
    prompt_completo = f"""{prompt_base}

---
Título del video: {titulo_video}

Transcripción del video:
{transcripcion}
"""

    def _invocar() -> str:
        # Si GEMINI_API_KEY está configurada, usar google-genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                logger.info("Generando apunte con SDK google-genai (GEMINI_API_KEY detectada)...")
                client = genai.Client(api_key=api_key)
                model_name = modelo or "gemini-2.5-flash"
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_completo
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.warning(f"Aviso: Falló el SDK directo ({e}). Intentando con agy CLI...")

        # Por defecto, invocar agy CLI
        logger.info(f"Generando apunte con Gemini CLI (`agy`)... (timeout: {timeout_segundos}s, effort: {esfuerzo})")
        
        # Usar archivo temporal para pasar el prompt completo a agy con @archivo
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tf:
            tf.write(prompt_completo)
            temp_prompt_path = tf.name

        try:
            cmd = ["agy", "-p", f"@{temp_prompt_path}", "--disable-slash-commands"]
            if modelo:
                cmd.extend(["--model", modelo])
            if esfuerzo and esfuerzo.lower() != "none":
                cmd.extend(["--effort", esfuerzo])

            retcode, salida, err = ejecutar_subproceso_texto(cmd, timeout=timeout_segundos)
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout al ejecutar agy superó el límite de {timeout_segundos} segundos.")
            raise TimeoutError(f"agy CLI no respondió dentro del límite de {timeout_segundos}s.")
        finally:
            if os.path.exists(temp_prompt_path):
                try:
                    os.remove(temp_prompt_path)
                except OSError:
                    pass
        
        if retcode != 0:
            raise RuntimeError(f"Error al ejecutar agy (código {retcode}): {err.strip()}")
        
        resultado = salida.strip()
        if not resultado:
            raise RuntimeError("La llamada a Gemini CLI no devolvió contenido.")
        
        # Limpiar bloques envolventes de markdown si los hubiera
        if resultado.startswith("```markdown") and resultado.endswith("```"):
            resultado = resultado[11:-3].strip()
        elif resultado.startswith("```md") and resultado.endswith("```"):
            resultado = resultado[5:-3].strip()

        return resultado

    return reintentar_con_backoff(
        _invocar,
        max_intentos=max_reintentos,
        base_delay=3.0,
        max_delay=30.0,
        descripcion=f"generación de apunte IA ({titulo_video[:30]})",
        excepciones_reintentables=(RuntimeError, TimeoutError, Exception)
    )


def exportar_a_pdf(
    contenido_markdown: str,
    ruta_salida_pdf: str,
    titulo: str = "Apunte",
    directorio_base: str = ".",
    materia: str = "General",
    url_fuente: str = ""
) -> str:
    """
    Convierte el apunte Markdown a PDF profesional mediante compilador_pdf.
    Aplica WeasyPrint (o fallback transparente a markdown-pdf si GTK3 no está disponible),
    portada de cortesía, encabezados dinámicos, 'Página X de Y', TOC y reglas anti-rotura.
    """
    import compilador_pdf
    return compilador_pdf.compilar_pdf(
        contenido_markdown=contenido_markdown,
        ruta_pdf=ruta_salida_pdf,
        titulo=titulo,
        materia=materia,
        url_fuente=url_fuente,
        directorio_base=directorio_base
    )


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
    esfuerzo: str = "low",
    timeout: int = 300,
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
        else:
            print("      (Omitiendo guardado de archivo de transcripción por --no-transcripcion)")

        # 5. Generar apunte con Gemini
        print("[5/5] Procesando apunte con Gemini...")
        contenido_md = generar_apunte_gemini(
            titulo_video=titulo_video,
            transcripcion=transcripcion,
            modelo=modelo,
            esfuerzo=esfuerzo,
            timeout_segundos=timeout
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
                motor_usado = exportar_a_pdf(
                    contenido_md,
                    ruta_pdf,
                    titulo=f"{id_apunte} - {titulo_video}",
                    directorio_base=carpeta_destino,
                    materia=os.path.basename(carpeta_destino),
                    url_fuente=url
                )
                print(f"✅ Archivo PDF generado exitosamente [{motor_usado.upper()}]: {ruta_pdf}")
            except Exception as e:
                print(f"⚠️ No se pudo generar el PDF: {e}")

        return {"status": "ok", "nombre_base": nombre_base, "titulo": titulo_video, "url": url}

    except Exception as e:
        print(f"❌ Error al procesar '{url}': {e}")
        return {"status": "error", "url": url, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Generador automatizado de apuntes desde videos de YouTube.")
    parser.add_argument("urls_posicionales", nargs="*", default=[], help="Una o más URLs o IDs de videos de YouTube o playlists (opcional, argumento posicional)")
    parser.add_argument("--url", "-u", nargs="*", type=str, help="Una o más URLs o IDs de videos de YouTube o playlists")
    parser.add_argument("--urls-file", "--file", "-f", type=str, default=None, help="Ruta a archivo .txt con lista de URLs")
    parser.add_argument("--materia", "--tema", "--apunte", "-m", dest="materia", type=str, help="Nombre del apunte o materia (ej. matematica, fisica)")
    parser.add_argument("--dir-apuntes", "--output-dir", type=str, default="apuntes", help="Directorio base para los apuntes (por defecto: apuntes)")
    parser.add_argument("--pdf", action="store_true", help="Generar también el apunte en formato PDF")
    parser.add_argument("--model", type=str, default=None, help="Modelo de Gemini a utilizar (ej. gemini-3.8-flash-low)")
    parser.add_argument("--effort", type=str, choices=["low", "medium", "high", "none"], default="low", help="Nivel de esfuerzo de razonamiento para agy (low, medium, high, none; por defecto: low)")
    parser.add_argument("--timeout", type=int, default=300, help="Tiempo máximo de espera en segundos para la llamada a agy / IA (por defecto: 300)")
    parser.add_argument("--desde", type=int, default=None, help="Índice inicial de la playlist a procesar (ej. --desde 11)")
    parser.add_argument("--hasta", type=int, default=None, help="Índice final de la playlist a procesar (ej. --hasta 20)")
    parser.add_argument("--video-only", action="store_true", help="Forzar el procesamiento de solo un video si la URL incluye parámetro list=")
    parser.add_argument("--no-transcripcion", dest="guardar_transcripcion", action="store_false", help="Omitir el guardado del archivo de transcripción (.txt)")
    parser.add_argument("--guardar-transcripcion", dest="guardar_transcripcion", action="store_true", default=True, help="Guardar la transcripción original en texto (activo por defecto)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Activar registro detallado (debug)")

    args = parser.parse_args()

    configurar_logging(verbose=args.verbose)

    print("=" * 65)
    print(" 🎓 GENERADOR DE APUNTES DE YOUTUBE CON GEMINI CLI (AGY)")
    print("=" * 65)

    directorio_script = os.path.dirname(os.path.abspath(__file__))
    ruta_urls_txt = os.path.join(directorio_script, "urls.txt")
    lista_cruda: List[Tuple[Optional[str], str]] = []
    es_interactivo_directo = False

    # 1. Determinar lista de videos (CLI o interactivo)
    urls_cli: List[str] = []
    if args.url:
        urls_cli.extend(args.url)
    if args.urls_posicionales:
        urls_cli.extend(args.urls_posicionales)

    if args.urls_file:
        lista_cruda = leer_urls_desde_archivo(args.urls_file)
        if not lista_cruda:
            print(f"❌ Error: No se encontraron URLs válidas en '{args.urls_file}'.")
            return
    elif urls_cli:
        for item in urls_cli:
            cid, curl = extraer_id_y_url(item)
            if curl:
                lista_cruda.append((cid, curl))
    else:
        # Modo interactivo
        es_interactivo_directo = True
        urls_en_archivo = leer_urls_desde_archivo(ruta_urls_txt)
        usar_urls_txt = False
        if urls_en_archivo:
            print(f"\n📄 Se detectaron {len(urls_en_archivo)} entrada(s) configurada(s) en 'urls.txt':")
            for i, (cid, curl) in enumerate(urls_en_archivo[:5], 1):
                pref = f"[{cid}] " if cid else ""
                print(f"   {i}. {pref}{curl}")
            if len(urls_en_archivo) > 5:
                print(f"   ... y {len(urls_en_archivo) - 5} más.")

            try:
                opc = input("\n👉 ¿Deseás procesar las entradas de 'urls.txt'? (S/n): ").strip().lower()
                if opc in ["", "s", "si", "sí", "y", "yes"]:
                    lista_cruda = urls_en_archivo
                    usar_urls_txt = True
            except (KeyboardInterrupt, EOFError):
                print("\nOperación cancelada.")
                return

        if not usar_urls_txt:
            print("\n👉 Ingresá la URL del video o de la Playlist de YouTube.")
            print("   (Podés ingresar una URL, una playlist, varias separadas por coma,")
            print("    la ruta a un archivo .txt, o incluir número ej: 'clase 1 -> https://...'):")
            try:
                entrada_usuario = input("🔗 URL o archivo: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nOperación cancelada.")
                return

            if not entrada_usuario:
                print("❌ Error: No se ingresó ninguna URL.")
                return

            if os.path.isfile(entrada_usuario):
                lista_cruda = leer_urls_desde_archivo(entrada_usuario)
            elif "\n" in entrada_usuario:
                for linea in entrada_usuario.splitlines():
                    cid, curl = extraer_id_y_url(linea)
                    if curl:
                        lista_cruda.append((cid, curl))
            elif "," in entrada_usuario:
                for linea in entrada_usuario.split(","):
                    cid, curl = extraer_id_y_url(linea)
                    if curl:
                        lista_cruda.append((cid, curl))
            else:
                cid, curl = extraer_id_y_url(entrada_usuario)
                if curl:
                    lista_cruda.append((cid, curl))

    if not lista_cruda:
        print("❌ Error: No se pudieron extraer URLs válidas para procesar.")
        return

    # Expandir playlists a videos si corresponde
    materia_sugerida, lista_videos = resolver_y_expandir_entradas(
        entradas_crudas=lista_cruda,
        video_only=args.video_only,
        desde=args.desde,
        hasta=args.hasta,
        es_interactivo=es_interactivo_directo
    )

    if not lista_videos:
        print("❌ Error: No hay videos seleccionados para procesar.")
        return

    # 2. Solicitar nombre de la categoría o materia
    materia_input = args.materia
    if not materia_input:
        if materia_sugerida:
            sug_slug = sanitizar_nombre(materia_sugerida, max_len=30)
            if not es_interactivo_directo:
                materia_input = sug_slug
            else:
                try:
                    prompt_mat = f"\n👉 Ingresá el nombre del apunte o materia [Enter para usar '{sug_slug}']: "
                    materia_input = input(prompt_mat).strip()
                    if not materia_input:
                        materia_input = sug_slug
                except (KeyboardInterrupt, EOFError):
                    print("\nOperación cancelada.")
                    return
        else:
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

    # Escaneo de videos ya existentes en carpeta destino (Deduplicación)
    ya_procesados = escanear_videos_procesados(carpeta_destino)
    if ya_procesados:
        logger.info(f"📂 Archivos existentes detectados en carpeta: {len(ya_procesados)}")

    exitosos = []
    salteados = []
    fallidos = []

    for idx, (cid, curl) in enumerate(lista_videos, start=1):
        try:
            vid = extraer_id_video(curl)
        except Exception:
            vid = None

        if vid and vid in ya_procesados:
            arch_existente = ya_procesados[vid]
            tag_id = f"[{cid}] " if cid else ""
            print(f"\n⏭️ [{idx}/{total_videos}] {tag_id}Ya procesado anteriormente ({vid} -> {arch_existente}), salteando...")
            salteados.append({"url": curl, "video_id": vid, "archivo": arch_existente, "id_apunte": cid})
            continue

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
            esfuerzo=args.effort,
            timeout=args.timeout,
            guardar_transcripcion=args.guardar_transcripcion,
            es_lote=es_lote
        )

        if resultado["status"] == "ok":
            exitosos.append(resultado)
            if vid:
                ya_procesados[vid] = f"{resultado['nombre_base']}.md"
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

        if salteados:
            print(f"\n ⏭️ Salteados (ya existían): {len(salteados)} de {total_videos}")
            for item in salteados:
                print(f"    • [{item.get('id_apunte') or '-'}] {item['video_id']} ({item['archivo']})")

        if fallidos:
            print(f"\n ❌ Fallidos: {len(fallidos)} de {total_videos}")
            for item in fallidos:
                print(f"    • {item['url']} -> {item['error']}")

        print(f"\n 📂 Todo el material guardado en: ./{ruta_mostrar}/")
    else:
        if exitosos:
            print(f" 🎉 ¡Proceso finalizado! Los archivos están listos en: ./{ruta_mostrar}/")
        elif salteados:
            print(f" ⏭️ El video ya había sido procesado previamente en: ./{ruta_mostrar}/{salteados[0]['archivo']}")
        else:
            print(" ❌ No se pudo completar el apunte.")
    print("=" * 65)


if __name__ == "__main__":
    main()
