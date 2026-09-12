"""Pruebas basicas del modulo de documentos (PDF)."""

import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "modulos", "documentos", "scripts"))

import buscar_pdf  # noqa: E402
import leer_pdf  # noqa: E402
import resumir_pdf  # noqa: E402


def _crear_pdf(ruta):
    import pymupdf
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((72, 90), "Proyecto SPT", fontsize=18, fontname="helv")
    p.insert_text((72, 130), "La herramienta calcula flujos de potencia en Python.",
                  fontsize=11, fontname="helv")
    p.insert_text((72, 152), "Se probo con mas de 250 pruebas unitarias.",
                  fontsize=11, fontname="helv")
    doc.save(ruta)
    doc.close()


class TestDocumentos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pdf = os.path.join(self.tmp, "doc.pdf")
        _crear_pdf(self.pdf)

    def test_leer_genera_markdown_y_json(self):
        res = leer_pdf.leer(self.pdf, self.tmp, ocr="no")
        self.assertTrue(os.path.exists(res["markdown"]))
        self.assertTrue(os.path.exists(res["json"]))
        with open(res["markdown"], encoding="utf-8") as f:
            self.assertIn("flujos de potencia", f.read())

    def test_cache(self):
        leer_pdf.leer(self.pdf, self.tmp, ocr="no")
        res2 = leer_pdf.leer(self.pdf, self.tmp, ocr="no")
        self.assertTrue(res2.get("cache"))

    def test_buscar(self):
        resultados = buscar_pdf.buscar(self.pdf, "flujos de potencia", 2, self.tmp)
        self.assertTrue(resultados)
        self.assertIn("potencia", resultados[0]["texto"].lower())

    def test_resumen(self):
        res = resumir_pdf.resumir(self.pdf, 3, self.tmp)
        self.assertTrue(res["resumen"])


if __name__ == "__main__":
    unittest.main()
