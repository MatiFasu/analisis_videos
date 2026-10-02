#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
enriquecedor_visual.py
Módulo dedicado a la gestión visual de apuntes:
1. Descarga y procesamiento de portadas HD de YouTube.
2. Renderizado de diagramas Mermaid a imágenes PNG de alta resolución con tema profesional.
3. Asignación automática de epígrafes académicos (Figura 1, Figura 2, etc.).
4. Estilos CSS editoriales para maquetación en PDF.
"""

import os
import re
import base64
import tempfile
import urllib.request
import urllib.error
from typing import Optional
import requests


# Paleta y tema visual para diagramas Mermaid (Azul corporativo / Diseño limpio)
MERMAID_THEME_INIT = """%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#eff6ff',
    'primaryTextColor': '#1e3a8a',
    'primaryBorderColor': '#3b82f6',
    'lineColor': '#2563eb',
    'secondaryColor': '#f8fafc',
    'tertiaryColor': '#f1f5f9',
    'fontFamily': 'Segoe UI, Helvetica, Arial, sans-serif',
    'fontSize': '17px'
  }
}}%%
"""


def recortar_bordes_blancos(img_bytes: bytes, padding: int = 15) -> bytes:
    """
    Recorta automáticamente márgenes vacíos o blancos excesivos generados por Mermaid
    para que el diagrama ocupe el espacio óptimo y el texto no se vea diminuto.
    """
    try:
        from PIL import Image, ImageChops
        import io
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        bg = Image.new(im.mode, im.size, (255, 255, 255))
        diff = ImageChops.difference(im, bg)
        bbox = diff.getbbox()
        if bbox:
            left, top, right, bottom = bbox
            w, h = im.size
            bbox_padded = (
                max(0, left - padding),
                max(0, top - padding),
                min(w, right + padding),
                min(h, bottom + padding)
            )
            cropped = im.crop(bbox_padded)
            buf = io.BytesIO()
            cropped.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
    except Exception:
        pass
    return img_bytes


# Estilos CSS académicos y editoriales para el compilador de PDF
CSS_VISUAL_ACADEMICO = """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1a202c;
}

h1 {
    color: #1e3a8a;
    font-size: 19pt;
    border-bottom: 2px solid #3b82f6;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 14px;
}

h2 {
    color: #2563eb;
    font-size: 14pt;
    margin-top: 22px;
    margin-bottom: 10px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
}

h3 {
    color: #334155;
    font-size: 12pt;
    margin-top: 16px;
    margin-bottom: 8px;
}

/* Maquetación de imágenes y portadas */
img {
    display: block;
    margin: 14px auto 6px auto;
    max-width: 95%;
    height: auto;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
}

.portada-contenedor {
    text-align: center;
    margin-bottom: 22px;
}

.portada-img {
    width: 100%;
    max-width: 100%;
    border-radius: 8px;
    border: 1px solid #cbd5e1;
    margin: 0 auto 6px auto;
}

.figure-caption {
    text-align: center;
    font-size: 8.5pt;
    color: #64748b;
    font-style: italic;
    margin-top: 2px;
    margin-bottom: 18px;
}

/* Citas y notas aclaratorias */
blockquote {
    background-color: #f0f9ff;
    border-left: 4px solid #0284c7;
    padding: 10px 14px;
    margin: 14px 0;
    border-radius: 4px;
    color: #0c4a6e;
}

/* Código */
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

/* Tablas */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
}

th, td {
    border: 1px solid #cbd5e1;
    padding: 7px 10px;
    text-align: left;
}

th {
    background-color: #f1f5f9;
    font-weight: bold;
    color: #1e293b;
}

ul, ol {
    padding-left: 22px;
    margin-top: 6px;
    margin-bottom: 10px;
}

li {
    margin-bottom: 4px;
}
"""


def descargar_portada_video(video_id: str, ruta_guardado: str) -> Optional[str]:
    """
    Descarga la mejor resolución disponible de la miniatura oficial del video en YouTube.
    Intenta en cascada: maxresdefault (1080p) -> sddefault (640p) -> hqdefault (480p).
    """
    urls_candidatas = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/sddefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    ]

    for url in urls_candidatas:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    contenido = resp.read()
                    # Evitar miniaturas vacías de 1x1 pixel o placeholders de YouTube
                    if len(contenido) > 2000:
                        with open(ruta_guardado, "wb") as f:
                            f.write(contenido)
                        return ruta_guardado
        except Exception:
            continue

    return None


def insertar_portada_en_markdown(contenido_markdown: str, ruta_portada_relativa: str, titulo: str) -> str:
    """
    Inserta la imagen de portada inmediatamente después del encabezado principal H1.
    """
    if not os.path.exists(ruta_portada_relativa) and not os.path.isabs(ruta_portada_relativa):
        # Si es ruta relativa y no existe localmente, verificar si existe en la carpeta actual
        pass

    bloque_portada = f"""
<div class="portada-contenedor">
  <img src="{ruta_portada_relativa}" alt="Portada del video: {titulo}" class="portada-img" />
  <p class="figure-caption">📺 Portada oficial: {titulo}</p>
</div>
"""
    # Buscar el primer título # Título
    lineas = contenido_markdown.splitlines()
    nueva_lista = []
    insertada = False

    for linea in lineas:
        nueva_lista.append(linea)
        if not insertada and linea.startswith("# ") and not linea.startswith("##"):
            nueva_lista.append(bloque_portada)
            insertada = True

    if not insertada:
        return bloque_portada + "\n\n" + contenido_markdown

    return "\n".join(nueva_lista)


def sanitizar_sintaxis_mermaid(codigo: str) -> str:
    """
    Corrige automáticamente errores comunes en sintaxis Mermaid que causan fallo en el parser:
    1. Entrecomillar etiquetas en flechas con paréntesis o asteriscos: |Texto (detalle)| -> |"Texto (detalle)"|
    2. Asegurar que nodos con paréntesis no queden rotos.
    """
    lineas_limpias = []
    for linea in codigo.splitlines():
        # Envolver en comillas dobles el texto entre pipes si contiene paréntesis o asteriscos no entrecomillados
        linea_mod = re.sub(r'(\|)([^"\|\n]*[\(\)\*][^"\|\n]*)(\|)', r'\1"\2"\3', linea)
        lineas_limpias.append(linea_mod)

    return "\n".join(lineas_limpias)


def extraer_titulo_diagrama(codigo: str, indice: int, texto_previo: str = "") -> str:
    """
    Intenta deducir un título representativo para la figura a partir del código del diagrama
    o del encabezado Markdown inmediatamente anterior.
    """
    # 1. Si tiene directiva title o accTitle en el código
    match_title = re.search(r'(?:title|accTitle)[:\s]+([^\n]+)', codigo, re.IGNORECASE)
    if match_title:
        return match_title.group(1).strip().strip('"\'')

    # 2. Si el bloque de texto previo tiene un subtítulo (### Mi Título)
    if texto_previo:
        lineas_previas = [l.strip() for l in texto_previo.strip().splitlines() if l.strip()]
        if lineas_previas:
            ultima_linea = lineas_previas[-1]
            match_header = re.match(r'^#{1,6}\s*(.+)$', ultima_linea)
            if match_header:
                return match_header.group(1).strip()

    # 3. Deducir por tipo de diagrama
    primera_linea = codigo.strip().splitlines()[0].strip().lower()
    if "timeline" in primera_linea:
        return "Cronograma y fases del contenido"
    elif "sequence" in primera_linea:
        return "Diagrama de secuencia y flujo de interacciones"
    elif "flowchart" in primera_linea or "graph" in primera_linea:
        return "Diagrama de arquitectura y flujo de componentes"
    
    return f"Esquema conceptual #{indice}"


def incrustar_imagenes_locales_como_base64(contenido_markdown: str, directorio_base: str = ".") -> str:
    """
    Convierte todas las rutas a imágenes locales en Markdown o HTML a URIs base64 (data:image/...)
    para que PyMuPDF no dependa de rutas relativas o del sistema de archivos al compilar el PDF.
    """
    def reemplazar_img_html(match):
        prefijo, ruta, sufijo = match.group(1), match.group(2), match.group(3)
        if ruta.startswith("data:") or ruta.startswith("http://") or ruta.startswith("https://"):
            return match.group(0)

        candidatos = [
            ruta,
            os.path.join(directorio_base, ruta),
            os.path.abspath(ruta)
        ]
        for c in candidatos:
            if os.path.exists(c) and os.path.isfile(c):
                ext = os.path.splitext(c)[1].lower().lstrip(".")
                mime = "jpeg" if ext in ["jpg", "jpeg"] else ("png" if ext == "png" else ext)
                with open(c, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                return f'{prefijo}data:image/{mime};base64,{b64}{sufijo}'
        return match.group(0)

    # Reemplazar <img src="...">
    md = re.sub(r'(<img[^>]+src=["\'])([^"\']+)(["\'])', reemplazar_img_html, contenido_markdown)

    # Reemplazar ![alt](...)
    def reemplazar_img_md(match):
        alt, ruta = match.group(1), match.group(2)
        if ruta.startswith("data:") or ruta.startswith("http://") or ruta.startswith("https://"):
            return match.group(0)
        candidatos = [
            ruta,
            os.path.join(directorio_base, ruta),
            os.path.abspath(ruta)
        ]
        for c in candidatos:
            if os.path.exists(c) and os.path.isfile(c):
                ext = os.path.splitext(c)[1].lower().lstrip(".")
                mime = "jpeg" if ext in ["jpg", "jpeg"] else ("png" if ext == "png" else ext)
                with open(c, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                return f'![{alt}](data:image/{mime};base64,{b64})'
        return match.group(0)

    md = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', reemplazar_img_md, md)
    return md


def procesar_diagramas_mermaid(contenido_markdown: str) -> str:
    """
    Detecta todos los bloques ```mermaid, inyecta el tema visual editorial,
    los renderiza a PNG de alta resolución mediante mermaid.ink y los sustituye
    por imágenes incrustadas en Base64 con epígrafe de Figura académica.
    """
    contador_figuras = [0]
    partes = []
    last_end = 0
    patron = re.compile(r'```mermaid\s*(.*?)```', re.DOTALL)

    for match in patron.finditer(contenido_markdown):
        start, end = match.span()
        texto_previo = contenido_markdown[last_end:start]
        partes.append(texto_previo)
        last_end = end

        contador_figuras[0] += 1
        num_figura = contador_figuras[0]
        codigo_original = match.group(1).strip()
        codigo_sanitizado = sanitizar_sintaxis_mermaid(codigo_original)
        titulo_figura = extraer_titulo_diagrama(codigo_original, num_figura, texto_previo)

        # Inyectar tema base si no tiene uno explícito
        if "%%{init:" not in codigo_sanitizado:
            codigo_final = MERMAID_THEME_INIT + "\n" + codigo_sanitizado
        else:
            codigo_final = codigo_sanitizado

        reemplazo = None
        try:
            encoded = base64.urlsafe_b64encode(codigo_final.encode("utf-8")).decode("ascii")
            url = f"https://mermaid.ink/img/{encoded}"
            # Solicitar imagen PNG nítida con fondo blanco
            res = requests.get(url, params={"format": "png", "bgColor": "FFFFFF", "width": 1200}, timeout=15)

            if res.status_code == 200 and len(res.content) > 200:
                img_bytes_recortadas = recortar_bordes_blancos(res.content)
                b64_img = base64.b64encode(img_bytes_recortadas).decode("ascii")
                data_uri = f"data:image/png;base64,{b64_img}"
                reemplazo = (
                    f'\n\n<div class="figura-diagrama-contenedor" style="text-align: center; margin: 18px 0;">'
                    f'<img src="{data_uri}" alt="Figura {num_figura}: {titulo_figura}" class="figura-diagrama-img" style="max-width: 95%; height: auto; border: 1px solid #cbd5e1; border-radius: 6px;" />'
                    f'<p class="figure-caption">Figura {num_figura}: {titulo_figura}</p>'
                    f'</div>\n\n'
                )
        except Exception:
            pass

        if not reemplazo:
            reemplazo = f"\n\n```text\n{codigo_original}\n```\n<p class=\"figure-caption\">Figura {num_figura}: {titulo_figura}</p>\n\n"

        partes.append(reemplazo)

    partes.append(contenido_markdown[last_end:])
    return "".join(partes)


def preparar_markdown_para_pdf(contenido_markdown: str, directorio_base: str = ".") -> str:
    """
    Aplica todos los filtros necesarios para generar un PDF impecable con imágenes 100% incrustadas:
    1. Convierte imágenes locales (portada) a Base64.
    2. Renderiza diagramas Mermaid a PNG en Base64 con epígrafes numerados.
    3. Limpia enlaces a anclas internas (#ancla) que podrían romper PyMuPDF.
    """
    # 1. Incrustar imágenes locales (como la portada) en Base64
    md = incrustar_imagenes_locales_como_base64(contenido_markdown, directorio_base)

    # 2. Renderizar diagramas Mermaid en Base64
    md = procesar_diagramas_mermaid(md)

    # 3. Sanitizar enlaces ancla (#seccion)
    md = re.sub(r'\[([^\]]+)\]\(#[^\)]+\)', r'\1', md)

    return md
