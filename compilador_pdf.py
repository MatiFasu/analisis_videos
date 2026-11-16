#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
compilador_pdf.py
Motor unificado de compilación de apuntes Markdown a PDF profesional.
Soporta:
1. Motor principal: WeasyPrint (maquetación editorial con CSS paged media,
   portada de cortesía, encabezados, "Página X de Y", TOC con números de página y break-inside: avoid).
2. Motor de respaldo (fallback): markdown-pdf / PyMuPDF cuando las bibliotecas nativas de GTK3
   no están presentes en el sistema operativo.
"""

import os
import sys
import re
import datetime
from typing import Optional, Tuple, Dict, Any

# Forzar codificación UTF-8 en stdout/stderr
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import enriquecedor_visual


# ==============================================================================
# 1. DETECCIÓN Y CONFIGURACIÓN DE GTK3 EN WINDOWS
# ==============================================================================

_GTK_CONFIGURADO = False
_WEASYPRINT_DISPONIBLE: Optional[bool] = None
_WEASYPRINT_ERROR: Optional[str] = None


def configurar_entorno_dll() -> Optional[str]:
    """
    Detecta y registra las carpetas de DLLs nativas de GTK3/MSYS2 en Windows
    mediante os.add_dll_directory y PATH antes de importar WeasyPrint.
    """
    global _GTK_CONFIGURADO
    if _GTK_CONFIGURADO:
        return None

    _GTK_CONFIGURADO = True
    if sys.platform != "win32":
        return None

    rutas_candidatas = [
        os.environ.get("WEASYPRINT_DLL_DIRECTORIES"),
        os.environ.get("GTK_BASEPATH"),
        r"C:\Program Files\GTK3-Runtime-Win64\bin",
        r"C:\Program Files (x86)\GTK3-Runtime-Win64\bin",
        r"C:\msys64\ucrt64\bin",
        r"C:\msys64\mingw64\bin",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gtk3", "bin"),
    ]

    for ruta in rutas_candidatas:
        if ruta and os.path.isdir(ruta):
            # Registrar en el buscador de DLLs de Python 3.8+
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(ruta)
                except Exception:
                    pass
            # Asegurar en PATH del entorno actual
            if ruta not in os.environ.get("PATH", ""):
                os.environ["PATH"] = ruta + os.pathsep + os.environ.get("PATH", "")
            return ruta

    return None


def verificar_motor_disponible() -> Tuple[str, str]:
    """
    Comprueba si WeasyPrint está completamente operativo con sus librerías nativas.
    Devuelve ('weasyprint', version) o ('pymupdf', motivo_fallback).
    """
    global _WEASYPRINT_DISPONIBLE, _WEASYPRINT_ERROR

    if _WEASYPRINT_DISPONIBLE is not None:
        if _WEASYPRINT_DISPONIBLE:
            return ("weasyprint", "disponible")
        return ("pymupdf", _WEASYPRINT_ERROR or "GTK3 no disponible")

    configurar_entorno_dll()

    try:
        import io
        import contextlib
        buffer_silencioso = io.StringIO()
        with contextlib.redirect_stderr(buffer_silencioso):
            import weasyprint
        _WEASYPRINT_DISPONIBLE = True
        _WEASYPRINT_ERROR = None
        return ("weasyprint", getattr(weasyprint, "__version__", "ok"))
    except Exception as e:
        _WEASYPRINT_DISPONIBLE = False
        _WEASYPRINT_ERROR = str(e)
        return ("pymupdf", _WEASYPRINT_ERROR)


# ==============================================================================
# 2. ESTILOS CSS EDITORIALES PARA WEASYPRINT
# ==============================================================================

CSS_EDITORIAL_WEASYPRINT = """
@page {
    size: A4 portrait;
    margin: 24mm 18mm 22mm 18mm;
    
    @top-left {
        content: string(doc-title);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 8pt;
        color: #64748b;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 4px;
        vertical-align: bottom;
    }
    
    @bottom-left {
        content: "Apunte de Estudio — Generado con Asistente IA";
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 8pt;
        color: #94a3b8;
        border-top: 1px solid #e2e8f0;
        padding-top: 4px;
        vertical-align: top;
    }
    
    @bottom-right {
        content: "Página " counter(page) " de " counter(pages);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 8pt;
        font-weight: 600;
        color: #2563eb;
        border-top: 1px solid #e2e8f0;
        padding-top: 4px;
        vertical-align: top;
    }
}

@page :first {
    margin: 0;
    @top-left { content: none; }
    @bottom-left { content: none; }
    @bottom-right { content: none; }
}

@page portada {
    margin: 0;
    @top-left { content: none; }
    @bottom-left { content: none; }
    @bottom-right { content: none; }
}

/* Portada de cortesía */
.portada-cortesia {
    page: portada;
    break-after: page;
    page-break-after: always;
    padding: 70px 50px 50px 50px;
    background: linear-gradient(145deg, #eff6ff 0%, #dbeafe 45%, #f8fafc 100%);
    box-sizing: border-box;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.portada-header {
    margin-bottom: 25px;
}

.portada-badge {
    display: inline-block;
    background-color: #2563eb;
    color: #ffffff;
    font-size: 9pt;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 6px 14px;
    border-radius: 20px;
    text-transform: uppercase;
}

.portada-titulo {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e3a8a;
    font-size: 26pt;
    line-height: 1.25;
    margin: 15px 0 12px 0;
    border-bottom: 3px solid #3b82f6;
    padding-bottom: 12px;
}

.portada-subtitulo {
    font-size: 12pt;
    color: #334155;
    line-height: 1.5;
    margin-bottom: 25px;
}

.portada-miniatura-wrap {
    text-align: center;
    margin: 15px auto;
    max-width: 90%;
}

.portada-miniatura-img {
    max-width: 100%;
    max-height: 260px;
    border-radius: 8px;
    border: 1px solid #cbd5e1;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.portada-footer {
    margin-top: 30px;
    border-top: 1px solid #cbd5e1;
    padding-top: 18px;
}

.portada-meta-grid {
    font-size: 9.5pt;
    color: #475569;
    line-height: 1.6;
}

.portada-meta-grid strong {
    color: #1e293b;
}

/* Cuerpo del documento */
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #1a202c;
    margin: 0;
    padding: 0;
}

.documento-cuerpo {
    padding-top: 5px;
}

.documento-titulo-running {
    string-set: doc-title content();
}

/* Encabezados */
h1 {
    color: #1e3a8a;
    font-size: 18pt;
    border-bottom: 2px solid #3b82f6;
    padding-bottom: 6px;
    margin-top: 24px;
    margin-bottom: 14px;
    break-after: avoid;
    page-break-after: avoid;
}

h2 {
    color: #2563eb;
    font-size: 13.5pt;
    margin-top: 20px;
    margin-bottom: 10px;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
    break-after: avoid;
    page-break-after: avoid;
}

h3 {
    color: #334155;
    font-size: 11.5pt;
    margin-top: 16px;
    margin-bottom: 8px;
    break-after: avoid;
    page-break-after: avoid;
}

/* Tabla de Contenidos (TOC) con números de página automáticos */
.seccion-toc {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 14px 20px;
    margin: 18px 0 24px 0;
    break-inside: avoid;
    page-break-inside: avoid;
}

.seccion-toc h2 {
    margin-top: 0;
    border-bottom: 2px solid #93c5fd;
    color: #1e3a8a;
}

.seccion-toc ul, .seccion-toc ol {
    list-style: none;
    padding-left: 0;
    margin: 8px 0;
}

.seccion-toc li {
    margin-bottom: 6px;
    font-size: 9.5pt;
    line-height: 1.4;
}

.seccion-toc li li {
    padding-left: 16px;
    font-size: 9pt;
    margin-bottom: 4px;
}

.seccion-toc a {
    text-decoration: none;
    color: #1e3a8a;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
}

.seccion-toc a::after {
    content: leader('.') " " target-counter(attr(href), page);
    color: #64748b;
    font-weight: 500;
    font-size: 9pt;
    margin-left: 8px;
}

/* Prevención de rupturas de página en elementos clave */
.figura-diagrama-contenedor,
figure,
img,
table,
pre,
blockquote,
.card {
    break-inside: avoid;
    page-break-inside: avoid;
}

/* Diagramas y Figuras */
.figura-diagrama-contenedor {
    text-align: center;
    margin: 18px auto;
}

.figura-diagrama-img {
    max-width: 95%;
    height: auto;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    display: block;
    margin: 0 auto;
}

.figure-caption {
    text-align: center;
    font-size: 8.5pt;
    color: #64748b;
    font-style: italic;
    margin-top: 6px;
    margin-bottom: 12px;
}

/* Bloques de código */
code {
    background-color: #f1f5f9;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: Consolas, "Cascadia Code", Monaco, "Courier New", monospace;
    font-size: 9pt;
    color: #0f172a;
}

pre {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 14px;
    overflow-x: auto;
    margin: 12px 0;
}

pre code {
    background-color: transparent;
    padding: 0;
    font-size: 8.5pt;
}

/* Citas y Callouts */
blockquote {
    background-color: #eff6ff;
    border-left: 4px solid #3b82f6;
    padding: 10px 16px;
    margin: 14px 0;
    border-radius: 0 6px 6px 0;
    color: #1e3a8a;
}

blockquote p {
    margin: 4px 0;
}

/* Tablas */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 9.5pt;
}

th, td {
    border: 1px solid #cbd5e1;
    padding: 8px 12px;
    text-align: left;
}

th {
    background-color: #f1f5f9;
    font-weight: 600;
    color: #1e293b;
    border-bottom: 2px solid #94a3b8;
}

tr:nth-child(even) {
    background-color: #f8fafc;
}

/* Enlaces */
a {
    color: #2563eb;
    text-decoration: underline;
}

hr {
    border: 0;
    height: 1px;
    background-color: #e2e8f0;
    margin: 20px 0;
}
"""


# ==============================================================================
# 3. EXTRACCIÓN DE METADATOS Y ENSAMBLAJE HTML
# ==============================================================================

def extraer_metadatos_documento(contenido_md: str) -> Dict[str, Any]:
    """
    Extrae el título principal, portada, sinopsis y estructura básica del Markdown.
    """
    metadatos = {
        "titulo": "Apunte de Estudio",
        "subtitulo": "",
        "imagen_portada": None,
        "caption_portada": ""
    }

    # 1. Título H1
    m_h1 = re.search(r'^#\s+(.+)$', contenido_md, re.MULTILINE)
    if m_h1:
        metadatos["titulo"] = m_h1.group(1).strip()

    # 2. Portada en contenedor HTML si existe
    m_portada = re.search(
        r'<div class="portada-contenedor"[^>]*>\s*<img [^>]*src="([^"]+)"[^>]*alt="([^"]*)"',
        contenido_md
    )
    if m_portada:
        metadatos["imagen_portada"] = m_portada.group(1)
        metadatos["caption_portada"] = m_portada.group(2)
    else:
        # Buscar primera imagen estándar si es portada
        m_img = re.search(r'!\[([^\]]*)\]\(([^)]+(?:portada|thumbnail)[^)]*)\)', contenido_md, re.IGNORECASE)
        if m_img:
            metadatos["caption_portada"] = m_img.group(1)
            metadatos["imagen_portada"] = m_img.group(2)

    # 3. Subtítulo o bloque de sinopsis inicial (blockquote tras H1)
    m_sinopsis = re.search(r'^>\s*\*\*([^*]+)\*\*\s*\n>\s*(.+?)(?=\n\n|\n---|\n#)', contenido_md, re.MULTILINE | re.DOTALL)
    if m_sinopsis:
        tipo = m_sinopsis.group(1).strip()
        detalle = re.sub(r'>\s*', '', m_sinopsis.group(2)).strip()
        detalle = re.sub(r'\s+', ' ', detalle)
        metadatos["subtitulo"] = f"{tipo}: {detalle}"[:250]

    return metadatos


def envolver_tabla_contenidos_en_html(html_contenido: str) -> str:
    """
    Detecta la sección de Tabla de Contenidos en el HTML generado y la envuelve
    en <div class="seccion-toc"> para que apliquen los números de página automáticos CSS.
    """
    patron_toc = re.compile(
        r'(<h2[^>]*id="tabla-de-contenidos"[^>]*>.*?</h2>\s*<(?:ul|ol)>.*?</(?:ul|ol)>)',
        re.DOTALL | re.IGNORECASE
    )
    if patron_toc.search(html_contenido):
        return patron_toc.sub(r'<div class="seccion-toc">\1</div>', html_contenido)

    # Fallback si el ID no es tabla-de-contenidos pero el texto lo es
    patron_toc_texto = re.compile(
        r'(<h2[^>]*>(?:Tabla de Contenidos|Índice|Contenidos)</h2>\s*<(?:ul|ol)>.*?</(?:ul|ol)>)',
        re.DOTALL | re.IGNORECASE
    )
    return patron_toc_texto.sub(r'<div class="seccion-toc">\1</div>', html_contenido)


def construir_documento_html_completo(
    contenido_md: str,
    titulo: str,
    materia: str = "General",
    subtitulo: str = "",
    url_fuente: str = "",
    fecha: str = ""
) -> str:
    """
    Convierte el Markdown procesado a un documento HTML completo con:
    1. Portada de cortesía inicial.
    2. Tabla de contenidos adaptada a CSS Paged Media.
    3. Running headers / footers y estilos editoriales.
    """
    try:
        import markdown
    except ImportError:
        raise RuntimeError("La librería 'markdown' no está instalada. Ejecutá: pip install markdown")

    # Extraer metadatos del documento
    meta = extraer_metadatos_documento(contenido_md)
    titulo_final = titulo or meta["titulo"]
    subtitulo_final = subtitulo or meta["subtitulo"]
    imagen_portada = meta["imagen_portada"]
    fecha_final = fecha or datetime.date.today().strftime("%d/%m/%Y")

    # Si hay portada en el cuerpo Markdown original, removerla del cuerpo
    # para que no aparezca duplicada (ya estará en la portada de cortesía)
    md_sin_portada_duplicada = re.sub(
        r'<div class="portada-contenedor"[^>]*>.*?</div>\s*',
        '',
        contenido_md,
        flags=re.DOTALL
    )

    # Convertir Markdown a HTML
    html_cuerpo = markdown.markdown(
        md_sin_portada_duplicada,
        extensions=['tables', 'fenced_code', 'toc', 'sane_lists']
    )

    # Envolver la tabla de contenidos para formato CSS leader
    html_cuerpo = envolver_tabla_contenidos_en_html(html_cuerpo)

    # Marcar el primer H1 del cuerpo como generador del header running
    html_cuerpo = re.sub(
        r'<h1([^>]*)>(.*?)</h1>',
        r'<h1\1 class="documento-titulo-running">\2</h1>',
        html_cuerpo,
        count=1
    )

    # Construir HTML de la Portada de Cortesía
    bloque_miniatura = ""
    if imagen_portada:
        bloque_miniatura = f"""
        <div class="portada-miniatura-wrap">
            <img src="{imagen_portada}" alt="Portada oficial" class="portada-miniatura-img" />
        </div>
        """

    bloque_subtitulo = f'<p class="portada-subtitulo">{subtitulo_final}</p>' if subtitulo_final else ""
    bloque_fuente = f'<div class="portada-meta-item"><strong>Fuente:</strong> <a href="{url_fuente}">{url_fuente}</a></div>' if url_fuente else ""

    html_completo = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>{titulo_final}</title>
    <style>
{CSS_EDITORIAL_WEASYPRINT}
    </style>
</head>
<body>
    <!-- Portada de Cortesía -->
    <div class="portada-cortesia">
        <div class="portada-header">
            <span class="portada-badge">MATERIAL DE ESTUDIO ACADÉMICO</span>
        </div>
        <div class="portada-cuerpo">
            <h1 class="portada-titulo">{titulo_final}</h1>
            {bloque_subtitulo}
            {bloque_miniatura}
        </div>
        <div class="portada-footer">
            <div class="portada-meta-grid">
                <div class="portada-meta-item"><strong>Materia / Curso:</strong> {materia}</div>
                <div class="portada-meta-item"><strong>Fecha de generación:</strong> {fecha_final}</div>
                {bloque_fuente}
            </div>
        </div>
    </div>

    <!-- Contenido del Apunte -->
    <div class="documento-cuerpo">
        {html_cuerpo}
    </div>
</body>
</html>
"""
    return html_completo


# ==============================================================================
# 4. COMPILACIÓN DE PDF (WEASYPRINT / FALLBACK)
# ==============================================================================

def compilar_pdf(
    contenido_markdown: str,
    ruta_pdf: str,
    titulo: str = "Apunte",
    materia: str = "General",
    subtitulo: str = "",
    url_fuente: str = "",
    directorio_base: str = ".",
    forzar_motor: Optional[str] = None
) -> str:
    """
    Compila el apunte a PDF aplicando automáticamente:
    1. Renderizado de diagramas Mermaid a imágenes Base64 y miniaturización de portadas locales.
    2. Portada de cortesía, encabezados dinámicos y "Página X de Y".
    3. Si WeasyPrint (GTK3) está disponible, compila con calidad editorial en 1 sola pasada.
    4. Si GTK3 no está instalado, degrada limpiamente a markdown-pdf sin romper la ejecución.

    Retorna el nombre del motor utilizado ('weasyprint' o 'pymupdf').
    """
    motor, detalle = verificar_motor_disponible()

    if forzar_motor:
        motor = forzar_motor.lower()

    # Preparar Markdown: incrustar imágenes locales y procesar Mermaid
    md_preparado = enriquecedor_visual.preparar_markdown_para_pdf(
        contenido_markdown,
        directorio_base=directorio_base
    )

    if motor == "weasyprint":
        try:
            import weasyprint
            html_doc = construir_documento_html_completo(
                contenido_md=md_preparado,
                titulo=titulo,
                materia=materia,
                subtitulo=subtitulo,
                url_fuente=url_fuente
            )
            # Compilar con WeasyPrint (resolviendo rutas relativas si las hubiera)
            base_url = os.path.abspath(directorio_base)
            wp = weasyprint.HTML(string=html_doc, base_url=base_url)
            wp.write_pdf(ruta_pdf)
            return "weasyprint"
        except Exception as e:
            print(f"⚠️ [AVISO] Falló el motor WeasyPrint ({e}). Utilizando motor de respaldo (markdown-pdf)...")
            motor = "pymupdf"

    # ================= MOTOR DE RESPALDO (markdown-pdf / PyMuPDF) =================
    try:
        from markdown_pdf import MarkdownPdf, Section
    except ImportError:
        raise RuntimeError("Las librerías 'markdown-pdf' o 'pymupdf' no están instaladas.")

    # Sanitizar enlaces ancla internos (#seccion) para que no rompan PyMuPDF
    md_para_pymupdf = re.sub(r'\[([^\]]+)\]\(#[^\)]+\)', r'\1', md_preparado)

    pdf = MarkdownPdf(toc_level=2, optimize=True)
    pdf.meta["title"] = titulo
    pdf.meta["creator"] = "Generador de Apuntes (Modo Compatibilidad)"
    seccion = Section(
        md_para_pymupdf,
        toc=True,
        paper_size="A4",
        borders=(36, 36, -36, -36)
    )
    pdf.add_section(seccion, user_css=enriquecedor_visual.CSS_VISUAL_ACADEMICO)
    pdf.save(ruta_pdf)
    return "pymupdf"


# ==============================================================================
# 5. CLI DIRECTO PARA PRUEBAS INDIVIDUALES
# ==============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compilador unificado de apuntes Markdown a PDF")
    parser.add_argument("archivo_md", nargs="?", default=None, help="Ruta al archivo Markdown (.md)")
    parser.add_argument("--pdf", help="Ruta de salida del PDF (opcional)")
    parser.add_argument("--materia", default="General", help="Nombre de la materia o curso")
    parser.add_argument("--info-motor", action="store_true", help="Informa qué motor de PDF está activo")

    args = parser.parse_args()

    motor, info = verificar_motor_disponible()
    print(f"🔍 Estado del Motor PDF: {motor.upper()} ({info})")

    if args.info_motor:
        sys.exit(0)

    if not args.archivo_md or not os.path.exists(args.archivo_md):
        print("❌ Error: Debe especificar un archivo Markdown válido existente.")
        sys.exit(1)

    ruta_salida = args.pdf or os.path.splitext(args.archivo_md)[0] + ".pdf"
    directorio_origen = os.path.dirname(os.path.abspath(args.archivo_md))

    with open(args.archivo_md, "r", encoding="utf-8") as f:
        md_raw = f.read()

    meta = extraer_metadatos_documento(md_raw)
    print(f"📄 Compilando '{meta['titulo']}' a '{ruta_salida}'...")
    motor_usado = compilar_pdf(
        contenido_markdown=md_raw,
        ruta_pdf=ruta_salida,
        titulo=meta["titulo"],
        materia=args.materia,
        directorio_base=directorio_origen
    )
    print(f"✅ ¡PDF generado con éxito usando motor: {motor_usado.upper()}!")
