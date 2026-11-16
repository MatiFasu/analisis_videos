#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tests/test_playlist.py
Pruebas unitarias para las funciones de detección, parseo, obtención y deduplicación de playlists.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock
import pytest
from generar_apunte import (
    es_url_playlist,
    extraer_id_playlist,
    parsear_salida_playlist_ytdlp,
    escanear_videos_procesados,
    obtener_videos_de_playlist,
    resolver_y_expandir_entradas,
)


class TestDeteccionPlaylist:
    @pytest.mark.parametrize("url,esperado", [
        ("https://www.youtube.com/playlist?list=PL1234567890abcdef", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1234567890abcdef", True),
        ("https://youtu.be/dQw4w9WgXcQ?list=PL1234567890abcdef", True),
        ("https://www.youtube.com/watch?list=PL1234567890abcdef&v=dQw4w9WgXcQ", True),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", False),
        ("https://youtu.be/dQw4w9WgXcQ", False),
        ("dQw4w9WgXcQ", False),
        ("", False),
    ])
    def test_es_url_playlist(self, url, esperado):
        assert es_url_playlist(url) is esperado

    def test_extraer_id_playlist(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLBlnK6fEyqRh6isJ01MBnbNpV3ZsktSyS&index=1"
        assert extraer_id_playlist(url) == "PLBlnK6fEyqRh6isJ01MBnbNpV3ZsktSyS"

    def test_extraer_id_playlist_sin_list(self):
        assert extraer_id_playlist("https://youtu.be/dQw4w9WgXcQ") is None


class TestParsearSalidaYtDlp:
    def test_parseo_salida_estandar_ytdlp(self):
        salida_mock = """
1|dQw4w9WgXcQ|Rick Astley - Never Gonna Give You Up (Official Music Video)
2|9bZkp7q19f0|PSY - GANGNAM STYLE(강남스타일) M/V
3|oHg5SJYRHA0|RickRoll'D
"""
        resultado = parsear_salida_playlist_ytdlp(salida_mock)
        assert len(resultado) == 3
        assert resultado[0] == (1, "dQw4w9WgXcQ", "Rick Astley - Never Gonna Give You Up (Official Music Video)")
        assert resultado[1] == (2, "9bZkp7q19f0", "PSY - GANGNAM STYLE(강남스타일) M/V")
        assert resultado[2] == (3, "oHg5SJYRHA0", "RickRoll'D")

    def test_parseo_con_lineas_vacias_o_invalidas(self):
        salida_con_ruido = """

[download] Downloading playlist...
1|dQw4w9WgXcQ|Video Uno
linea corrupta sin delimitador
2|9bZkp7q19f0|Video Dos
"""
        resultado = parsear_salida_playlist_ytdlp(salida_con_ruido)
        assert len(resultado) == 2
        assert resultado[0][1] == "dQw4w9WgXcQ"
        assert resultado[1][1] == "9bZkp7q19f0"

    def test_ordenamiento_por_indice_playlist(self):
        salida_desordenada = """
3|vidTres1234|Tercero
1|vidUno12345|Primero
2|vidDos12345|Segundo
"""
        resultado = parsear_salida_playlist_ytdlp(salida_desordenada)
        assert [r[0] for r in resultado] == [1, 2, 3]


class TestEscanearVideosYaProcesados:
    def test_deteccion_en_transcripcion_txt(self):
        with tempfile.TemporaryDirectory() as td:
            archivo_txt = os.path.join(td, "01_curso_transcripcion.txt")
            with open(archivo_txt, "w", encoding="utf-8") as f:
                f.write("Título: Introducción\nURL: https://www.youtube.com/watch?v=dQw4w9WgXcQ\n\nContenido...")

            procesados = escanear_videos_procesados(td)
            assert "dQw4w9WgXcQ" in procesados
            assert procesados["dQw4w9WgXcQ"] == "01_curso_transcripcion.txt"

    def test_deteccion_en_apunte_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            archivo_md = os.path.join(td, "02_segundo_video.md")
            with open(archivo_md, "w", encoding="utf-8") as f:
                f.write("# Segundo Video\n\nFuente: https://youtu.be/9bZkp7q19f0\n\nTexto...")

            procesados = escanear_videos_procesados(td)
            assert "9bZkp7q19f0" in procesados

    def test_directorio_vacio(self):
        with tempfile.TemporaryDirectory() as td:
            assert escanear_videos_procesados(td) == {}


class TestObtenerVideosDePlaylistMock:
    @patch("subprocess.run")
    def test_obtener_videos_exitoso(self, mock_subproc):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = """
Curso Python|1|dQw4w9WgXcQ|Intro a Python
Curso Python|2|9bZkp7q19f0|Variables y Tipos
Curso Python|3|cnMziyeusQk|Estructuras de Control
"""
        mock_subproc.return_value = mock_res

        titulo, videos = obtener_videos_de_playlist("https://youtube.com/playlist?list=PL123")
        assert titulo == "Curso Python"
        assert len(videos) == 3
        assert videos[0] == (1, "dQw4w9WgXcQ", "Intro a Python")
        assert videos[1] == (2, "9bZkp7q19f0", "Variables y Tipos")

    @patch("subprocess.run")
    def test_obtener_videos_con_rango_desde_hasta(self, mock_subproc):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = """
Curso C++|1|dQw4w9WgXcQ|Intro
Curso C++|2|9bZkp7q19f0|Punteros
Curso C++|3|cnMziyeusQk|Clases
"""
        mock_subproc.return_value = mock_res

        titulo, videos = obtener_videos_de_playlist("https://youtube.com/playlist?list=PL123", desde=2, hasta=2)
        assert len(videos) == 1
        assert videos[0] == (2, "9bZkp7q19f0", "Punteros")

    @patch("subprocess.run")
    def test_playlist_privada_error(self, mock_subproc):
        mock_res = MagicMock()
        mock_res.returncode = 1
        mock_res.stderr = "ERROR: [youtube:tab] PL123: The playlist is private."
        mock_subproc.return_value = mock_res

        with pytest.raises(ValueError, match="privada"):
            obtener_videos_de_playlist("https://youtube.com/playlist?list=PL123")


class TestResolverYExpandirEntradas:
    @patch("generar_apunte.obtener_videos_de_playlist")
    def test_expansion_playlist_con_prefijo_global(self, mock_get_pl):
        mock_get_pl.return_value = (
            "Curso Docker",
            [(1, "vidUno12345", "Intro"), (2, "vidDos12345", "Contenedores")]
        )

        materia, expandidos = resolver_y_expandir_entradas(
            entradas_crudas=[(None, "https://youtube.com/playlist?list=PL123")],
            video_only=False
        )

        assert materia == "Curso Docker"
        assert len(expandidos) == 2
        assert expandidos[0] == ("01", "https://www.youtube.com/watch?v=vidUno12345")
        assert expandidos[1] == ("02", "https://www.youtube.com/watch?v=vidDos12345")

    def test_flag_video_only_no_expande_playlist(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL12345"
        materia, expandidos = resolver_y_expandir_entradas(
            entradas_crudas=[("01", url)],
            video_only=True
        )
        assert materia is None
        assert len(expandidos) == 1
        assert expandidos[0] == ("01", url)


class TestParsearRangoInteractivo:
    def test_todos_por_defecto(self):
        from generar_apunte import parsear_rango_interactivo
        ok, r = parsear_rango_interactivo("", 32)
        assert ok is True
        assert r == (1, 32)

    def test_cantidad_fija(self):
        from generar_apunte import parsear_rango_interactivo
        ok, r = parsear_rango_interactivo("5", 32)
        assert ok is True
        assert r == (1, 5)

    def test_rango_con_guion(self):
        from generar_apunte import parsear_rango_interactivo
        ok, r = parsear_rango_interactivo("3-8", 32)
        assert ok is True
        assert r == (3, 8)

    def test_rango_con_palabras(self):
        from generar_apunte import parsear_rango_interactivo
        ok, r = parsear_rango_interactivo("10 a 15", 32)
        assert ok is True
        assert r == (10, 15)

    def test_cancelacion(self):
        from generar_apunte import parsear_rango_interactivo
        ok, r = parsear_rango_interactivo("n", 32)
        assert ok is False
        assert r is None
