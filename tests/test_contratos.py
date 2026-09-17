"""Pruebas del contrato comun y del catalogo (nucleo + capacidades.json)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from nucleo import config  # noqa: E402
from nucleo.contrato import exito, fallo  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402


class TestContrato(unittest.TestCase):
    def test_exito_tiene_forma(self):
        d = exito(datos={"a": 1}, meta={"m": 2}).a_dict()
        self.assertEqual(set(d), {"ok", "datos", "meta", "artefactos", "error"})
        self.assertTrue(d["ok"])
        self.assertIsNone(d["error"])

    def test_fallo_tiene_codigo(self):
        d = fallo(("pdf", "noExiste"), "no existe").a_dict()
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["codigo"], "agente:pdf:noExiste")

    def test_agente_error_id(self):
        e = AgenteError("web", "sesionExpirada", "expiro")
        self.assertEqual(e.id, "agente:web:sesionExpirada")
        self.assertFalse(e.a_resultado().ok)


class TestCatalogo(unittest.TestCase):
    def test_catalogo_valido(self):
        cmds = config.comandos()
        self.assertTrue(cmds)
        ids = [c["id"] for c in cmds]
        self.assertEqual(len(ids), len(set(ids)), "ids duplicados en capacidades.json")

    def test_scripts_existen(self):
        faltan = [
            c["id"]
            for c in config.comandos()
            if not os.path.exists(os.path.join(RAIZ, c["script"]))
        ]
        self.assertEqual(faltan, [], "scripts faltantes: %s" % faltan)


class TestCliContrato(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, os.path.join(RAIZ, "agente.py"), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )

    def test_lista_json(self):
        proc = self._run("lista", "--json")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("comandos", json.loads(proc.stdout))

    def test_registro_contrato(self):
        proc = self._run("registro", "listar", "plataformas", "--json")
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertTrue(data["ok"])
        self.assertIn("datos", data)


class TestFlujo(unittest.TestCase):
    def test_flujo_detecta_paso_fallido(self):
        from interfaces import flujo

        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "flujo.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump({"flujo": [{"comando": "no-existe"}]}, f)
            res = flujo.ejecutar(ruta)
        self.assertFalse(res.ok)
        self.assertEqual(res.error["codigo"], "agente:flujo:pasoFallido")


if __name__ == "__main__":
    unittest.main()
