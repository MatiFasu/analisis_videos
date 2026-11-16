#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tests/test_compilador_pdf.py
Pruebas para extracción de metadatos del documento y verificación del motor PDF.
"""

import pytest
from compilador_pdf import (
    extraer_metadatos_documento,
    envolver_tabla_contenidos_en_html,
    verificar_motor_disponible,
)


class TestMetadatosDocumento:
    def test_extraccion_titulo_h1(self):
        md = "# Título Principal de la Clase\n\nContenido de prueba."
        meta = extraer_metadatos_documento(md)
        assert meta["titulo"] == "Título Principal de la Clase"

    def test_extraccion_portada_y_subtitulo(self):
        md = """# Microservicios con Python

<div class="portada-contenedor">
  <img src="01_portada.jpg" alt="Portada oficial del video" class="portada-img" />
  <p class="figure-caption">Portada: Microservicios</p>
</div>

> **Documento de Referencia Técnica**  
> Basado en la obra fundamental de arquitectura distribuida.

## 1. Introducción
"""
        meta = extraer_metadatos_documento(md)
        assert meta["titulo"] == "Microservicios con Python"
        assert meta["imagen_portada"] == "01_portada.jpg"
        assert meta["caption_portada"] == "Portada oficial del video"
        assert "Documento de Referencia Técnica" in meta["subtitulo"]


class TestEnvolverTOC:
    def test_envoltura_toc_con_id(self):
        html_input = '<h2 id="tabla-de-contenidos">Tabla de Contenidos</h2>\n<ul>\n<li><a href="#tema-1">Tema 1</a></li>\n</ul>'
        html_out = envolver_tabla_contenidos_en_html(html_input)
        assert '<div class="seccion-toc">' in html_out
        assert '</div>' in html_out

    def test_sin_toc_permanece_inalterado(self):
        html_input = '<h2 id="otro">Otra Sección</h2>\n<p>Texto</p>'
        html_out = envolver_tabla_contenidos_en_html(html_input)
        assert '<div class="seccion-toc">' not in html_out


class TestVerificacionMotor:
    def test_motor_devuelve_tupla_valida(self):
        motor, detalle = verificar_motor_disponible()
        assert motor in ["weasyprint", "pymupdf"]
        assert isinstance(detalle, str)
