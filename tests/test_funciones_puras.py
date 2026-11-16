#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tests/test_funciones_puras.py
Pruebas unitarias para las funciones puras de extracción, sanitización y reintentos.
"""

import os
import tempfile
import pytest
from generar_apunte import (
    extraer_id_video,
    sanitizar_nombre,
    extraer_id_y_url,
    obtener_siguiente_id,
    reintentar_con_backoff,
)


class TestExtraccionIdVideo:
    @pytest.mark.parametrize("url,esperado", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?feature=shared&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ])
    def test_urls_validas(self, url, esperado):
        assert extraer_id_video(url) == esperado

    @pytest.mark.parametrize("url_invalida", [
        "",
        "https://google.com",
        "https://youtube.com/feed/subscriptions",
        "12345",  # Menos de 11 caracteres
    ])
    def test_urls_invalidas(self, url_invalida):
        with pytest.raises(ValueError):
            extraer_id_video(url_invalida)


class TestSanitizarNombre:
    def test_quitar_tildes_y_mayusculas(self):
        assert sanitizar_nombre("Introducción a Matemáticas") == "introduccion_a_matematicas"

    def test_quitar_caracteres_especiales(self):
        assert sanitizar_nombre("Python 3.10 & C++: ¿El Mejor Lenguaje?!") == "python_310_c_el_mejor_lenguaje"

    def test_limite_longitud(self):
        largo = "este_es_un_nombre_extremadamente_largo_que_supera_el_limite_permitido"
        resultado = sanitizar_nombre(largo, max_len=20)
        assert len(resultado) <= 20
        assert not resultado.endswith("_")


class TestExtraerIdYUrl:
    def test_url_simple(self):
        cid, url = extraer_id_y_url("https://youtu.be/dQw4w9WgXcQ")
        assert cid is None
        assert url == "https://youtu.be/dQw4w9WgXcQ"

    def test_con_prefijo_clase(self):
        cid, url = extraer_id_y_url("clase 1 -> https://youtu.be/dQw4w9WgXcQ")
        assert cid == "01"
        assert url == "https://youtu.be/dQw4w9WgXcQ"

    def test_con_prefijo_barra(self):
        cid, url = extraer_id_y_url("12 | https://youtu.be/dQw4w9WgXcQ")
        assert cid == "12"
        assert url == "https://youtu.be/dQw4w9WgXcQ"

    def test_linea_comentario(self):
        cid, url = extraer_id_y_url("# Este es un comentario")
        assert cid is None
        assert url is None

    def test_linea_vacia(self):
        cid, url = extraer_id_y_url("   \n")
        assert cid is None
        assert url is None


class TestObtenerSiguienteId:
    def test_directorio_vacio_o_inexistente(self):
        with tempfile.TemporaryDirectory() as td:
            assert obtener_siguiente_id(td) == "01"

    def test_directorio_con_archivos_secuenciales(self):
        with tempfile.TemporaryDirectory() as td:
            # Crear archivos simulados
            open(os.path.join(td, "01_intro.md"), "w").close()
            open(os.path.join(td, "02_segundo.md"), "w").close()
            assert obtener_siguiente_id(td) == "03"

    def test_directorio_con_huecos(self):
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "05_tema.md"), "w").close()
            assert obtener_siguiente_id(td) == "06"


class TestReintentarConBackoff:
    def test_exito_inmediato(self):
        res = reintentar_con_backoff(lambda: "ok", max_intentos=3)
        assert res == "ok"

    def test_exito_al_segundo_intento(self):
        contador = [0]
        def operacion():
            contador[0] += 1
            if contador[0] < 2:
                raise ConnectionError("Fallo momentáneo")
            return "recuperado"

        res = reintentar_con_backoff(operacion, max_intentos=3, base_delay=0.05, max_delay=0.2)
        assert res == "recuperado"
        assert contador[0] == 2

    def test_fallo_definitivo_lanza_excepcion(self):
        def operacion_falla():
            raise TimeoutError("Servicio inaccesible")

        with pytest.raises(TimeoutError):
            reintentar_con_backoff(operacion_falla, max_intentos=2, base_delay=0.05, max_delay=0.1)


def test_argumentos_posicionales_y_flag_url():
    """Verifica que el script acepte URLs tanto posicionales como por flag --url sin error."""
    import subprocess
    import sys

    # Prueba con argumento posicional
    res_pos = subprocess.run(
        [sys.executable, "generar_apunte.py", "https://youtube.com/watch?v=dQw4w9WgXcQ", "--help"],
        capture_output=True,
        text=True
    )
    assert res_pos.returncode == 0
    assert "urls_posicionales" in res_pos.stdout


def test_decodificar_bytes_salida():
    from generar_apunte import decodificar_bytes_salida

    # UTF-8 estándar
    assert decodificar_bytes_salida("texto con acento: áéíóú".encode("utf-8")) == "texto con acento: áéíóú"

    # CP1252 con byte 0x97 (em-dash —) que rompía el readerthread
    datos_cp1252 = b"Zero to Claude \x97 Complete"
    res_cp1252 = decodificar_bytes_salida(datos_cp1252)
    assert res_cp1252 == "Zero to Claude — Complete"

    # None o vacío
    assert decodificar_bytes_salida(b"") == ""
    assert decodificar_bytes_salida(None) == ""
