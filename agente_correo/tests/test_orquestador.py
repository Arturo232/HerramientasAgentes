from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from agente_correo.orquestador import (
    ErrorEnrutamiento,
    ErrorPolitica,
    PuenteSelector,
    redactar,
    resumir_resultado,
)

CATALOGO = {
    "sistema": {"script": "scripts/sistema/mantenimiento_pc.py"},
    "redes": {"script": "scripts/redes/diagnosticar_red.py"},
    "datos": {"script": "scripts/datos/generar_excel.py"},
    "libro": {"script": "scripts/datos/construir_libro_pdf.py"},
}


def _datos(nombre: str, script: str, argumentos: list[str]):
    return {
        "exito": True,
        "herramienta": nombre,
        "script": script,
        "argumentos": argumentos,
    }


def test_valida_y_ejecuta_politica_sistema(cfg):
    puente = PuenteSelector(cfg)
    enrutamiento = puente.validar_enrutamiento(
        _datos("sistema", "scripts/sistema/mantenimiento_pc.py", ["--info"]),
        CATALOGO,
    )
    assert enrutamiento.herramienta == "sistema"
    assert enrutamiento.argumentos == ("--info",)


def test_rechaza_herramienta_fuera_de_lista_blanca(cfg):
    puente = PuenteSelector(cfg)
    with pytest.raises(ErrorPolitica):
        puente.validar_enrutamiento(
            _datos("libro", "scripts/datos/construir_libro_pdf.py", []),
            CATALOGO,
        )


def test_rechaza_limpieza_por_correo(cfg):
    puente = PuenteSelector(cfg)
    with pytest.raises(ErrorPolitica):
        puente.validar_enrutamiento(
            _datos("sistema", "scripts/sistema/mantenimiento_pc.py", ["--limpiar"]),
            CATALOGO,
        )


def test_redes_fuerza_solo_diagnostico(cfg):
    puente = PuenteSelector(cfg)
    enrutamiento = puente.validar_enrutamiento(
        _datos("redes", "scripts/redes/diagnosticar_red.py", []),
        CATALOGO,
    )
    assert "--sin-reconexion" in enrutamiento.argumentos
    assert "solo diagnóstico" in enrutamiento.nota


def test_datos_fuerza_salida_en_out(cfg):
    puente = PuenteSelector(cfg)
    enrutamiento = puente.validar_enrutamiento(
        _datos("datos", "scripts/datos/generar_excel.py", ["--test"]),
        CATALOGO,
    )
    assert enrutamiento.argumentos[0] == "--test"
    assert "--salida" in enrutamiento.argumentos
    salida = Path(enrutamiento.argumentos[enrutamiento.argumentos.index("--salida") + 1])
    assert salida.parent == cfg.dir_salida
    assert salida.suffix == ".xlsx"


def test_rechaza_script_con_travesia(cfg):
    catalogo = {"sistema": {"script": "../evil.py"}}
    puente = PuenteSelector(cfg)
    with pytest.raises(ErrorEnrutamiento):
        puente.validar_enrutamiento(
            _datos("sistema", "../evil.py", ["--info"]),
            catalogo,
        )


def test_libro_exige_pdf_dentro_de_entrada(cfg):
    cfg_libro = dataclasses.replace(
        cfg, herramientas_permitidas=("sistema", "redes", "datos", "libro")
    )
    puente = PuenteSelector(cfg_libro)
    with pytest.raises(ErrorPolitica):
        puente.validar_enrutamiento(
            _datos(
                "libro",
                "scripts/datos/construir_libro_pdf.py",
                ["--pdf", "/etc/passwd"],
            ),
            CATALOGO,
        )

    pdf = cfg_libro.dir_entrada / "libro.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    enrutamiento = puente.validar_enrutamiento(
        _datos(
            "libro",
            "scripts/datos/construir_libro_pdf.py",
            ["--pdf", "libro.pdf"],
        ),
        CATALOGO,
    )
    assert "--salida" in enrutamiento.argumentos
    assert str(enrutamiento.salida_forzada).endswith(".pdf")


def test_config_real_es_coherente(cfg):
    PuenteSelector(cfg).validar_config()


def test_resumen_no_vuelca_ruido(cfg):
    texto = resumir_resultado(
        {"mensaje": "todo bien", "ram_porcentaje": 42, "script": "x.py"},
        "",
    )
    assert "todo bien" in texto
    assert "ram_porcentaje: 42" in texto
    assert "x.py" not in texto


def test_redacta_tokens():
    texto = redactar(
        "access_token=SUPERSECRETO ya29.ABCDEF 1//XYZ AIzaABCDEFGHIJKLMNOPQRST"
    )
    assert "SUPERSECRETO" not in texto
    assert "ABCDEF" not in texto
    assert "AIza" not in texto
