from __future__ import annotations

from agente_correo.db import BaseDatos


def test_reserva_es_idempotente(tmp_path):
    db = BaseDatos(tmp_path / "agente.db")
    assert db.reservar("<a@example.com>", "gmail-1", "hilo-1", "a@b.c", "Asunto")
    assert not db.reservar("<a@example.com>", "gmail-1", "hilo-1", "a@b.c", "Asunto")
    fila = db.obtener("<a@example.com>")
    assert fila is not None
    assert fila["estado"] == "reservado"
    db.cerrar()


def test_finalizar_y_contar_ejecutadas(tmp_path):
    db = BaseDatos(tmp_path / "agente.db")
    assert db.reservar("<b@example.com>", "gmail-2")
    db.finalizar(
        "<b@example.com>",
        "ok",
        herramienta="sistema",
        codigo_salida=0,
        ejecutado=True,
    )
    fila = db.obtener("<b@example.com>")
    assert fila["estado"] == "ok"
    assert fila["herramienta"] == "sistema"
    assert fila["ejecutado"] == 1
    assert db.contar_ejecutadas_ultima_hora() == 1
    db.cerrar()


def test_pausa_y_reanudar(tmp_path):
    db = BaseDatos(tmp_path / "agente.db")
    assert db.esta_pausado() == (False, "")
    db.pausar("correo STOP")
    pausado, motivo = db.esta_pausado()
    assert pausado is True
    assert "STOP" in motivo
    db.reanudar()
    assert db.esta_pausado() == (False, "")
    db.cerrar()


def test_eventos(tmp_path):
    db = BaseDatos(tmp_path / "agente.db")
    db.registrar_evento("prueba", "detalle")
    eventos = db.eventos()
    assert eventos[0]["tipo"] == "prueba"
    assert eventos[0]["detalle"] == "detalle"
    db.cerrar()


def test_token_guardado_con_permisos_600(tmp_path):
    from agente_correo.gmail_client import guardar_token

    class CredencialesFalsas:
        def to_json(self):
            return '{"token": "x", "refresh_token": "y"}'

    ruta = tmp_path / "secrets" / "token.json"
    guardar_token(CredencialesFalsas(), ruta, obligatorio=True)
    assert ruta.is_file()
    assert (ruta.stat().st_mode & 0o777) == 0o600
