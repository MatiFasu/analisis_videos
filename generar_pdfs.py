#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generar_pdfs.py
Convierte todos los apuntes Markdown de una carpeta a PDF.
Reutiliza enriquecedor_visual para incrustar imágenes y aplicar CSS.

Uso:
    python generar_pdfs.py <ruta_carpeta>

Ejemplo:
    python generar_pdfs.py apuntes/curso_peoplesoft
"""

import os
import re
import sys
import logging
import argparse

# Forzar codificación UTF-8 en stdout y stderr para Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import compilador_pdf


def extraer_titulo_h1(contenido_md: str) -> str:
    """Extrae el texto del primer encabezado H1 del documento Markdown."""
    match = re.search(r'^#\s+(.+)$', contenido_md, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Apunte"


def compilar_pdf(contenido_md: str, ruta_pdf: str, titulo: str, directorio_base: str) -> str:
    """
    Compila un PDF desde Markdown usando compilador_pdf.
    Aplica WeasyPrint (o fallback a markdown-pdf), portada de cortesía y maquetación editorial.
    """
    materia = os.path.basename(os.path.abspath(directorio_base))
    return compilador_pdf.compilar_pdf(
        contenido_markdown=contenido_md,
        ruta_pdf=ruta_pdf,
        titulo=titulo,
        materia=materia,
        directorio_base=directorio_base
    )


def main():
    parser = argparse.ArgumentParser(
        description="Convierte todos los apuntes Markdown de una carpeta a PDF."
    )
    parser.add_argument(
        "carpeta",
        type=str,
        help="Ruta a la carpeta que contiene los archivos .md (relativa o absoluta)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Activar registro detallado (debug)"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # Validar que la carpeta existe
    carpeta = args.carpeta
    if not os.path.isdir(carpeta):
        print(f"❌ Error: La carpeta '{carpeta}' no existe o no es un directorio válido.")
        sys.exit(1)

    # Buscar todos los archivos .md en la carpeta
    archivos_md = sorted([
        f for f in os.listdir(carpeta)
        if f.lower().endswith(".md") and os.path.isfile(os.path.join(carpeta, f))
    ])

    if not archivos_md:
        print(f"❌ Error: No se encontraron archivos .md en '{carpeta}'.")
        sys.exit(1)

    total = len(archivos_md)
    print("=" * 65)
    print(" 📄 CONVERSOR DE APUNTES MARKDOWN A PDF")
    print(f" 📂 Carpeta: {carpeta}")
    print(f" 📝 Archivos .md encontrados: {total}")
    print("=" * 65)

    exitosos = []
    fallidos = []

    for idx, nombre_md in enumerate(archivos_md, start=1):
        ruta_md = os.path.join(carpeta, nombre_md)
        nombre_base = os.path.splitext(nombre_md)[0]
        ruta_pdf = os.path.join(carpeta, f"{nombre_base}.pdf")

        print(f"\n[{idx}/{total}] Procesando: {nombre_md}")

        try:
            # Leer contenido del archivo Markdown
            with open(ruta_md, "r", encoding="utf-8") as f:
                contenido_md = f.read()

            # Extraer título del H1
            titulo = extraer_titulo_h1(contenido_md)

            # Compilar PDF (sin renderizar Mermaid vía HTTP)
            motor_usado = compilar_pdf(
                contenido_md=contenido_md,
                ruta_pdf=ruta_pdf,
                titulo=titulo,
                directorio_base=carpeta
            )

            print(f"  ✅ PDF generado [{motor_usado.upper()}]: {nombre_base}.pdf")
            exitosos.append(nombre_base)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            fallidos.append((nombre_md, str(e)))

    # Resumen final
    print("\n" + "=" * 65)
    print(" 🏁 RESUMEN DE CONVERSIÓN")
    print("=" * 65)
    print(f" ✅ Exitosos: {len(exitosos)} de {total}")

    if fallidos:
        print(f" ❌ Fallidos: {len(fallidos)} de {total}")
        for nombre, error in fallidos:
            print(f"    • {nombre} -> {error}")

    print(f"\n 📂 Los PDFs están en: {carpeta}")
    print("=" * 65)


if __name__ == "__main__":
    main()
