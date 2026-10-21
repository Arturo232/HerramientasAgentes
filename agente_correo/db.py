"""Persistencia SQLite: idempotencia, estado de pausa y contadores."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def ahora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BaseDatos:
    """Base SQLite de un solo proceso (el listener)."""

    def __init__(self, ruta: str | Path):
        self.ruta = str(ruta)
        if self.ruta != ":memory:":
            Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.ruta, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._crear_esquema()

    def _crear_esquema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS mensajes (
                    message_id   TEXT PRIMARY KEY,
                    gmail_id     TEXT NOT NULL,
                    thread_id    TEXT,
                    remitente    TEXT,
                    asunto       TEXT,
                    estado       TEXT NOT NULL,
                    herramienta  TEXT,
                    codigo_salida INTEGER,
                    ejecutado    INTEGER NOT NULL DEFAULT 0,
                    detalle      TEXT,
                    recibido_en  TEXT NOT NULL,
                    procesado_en TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mensajes_procesado
                    ON mensajes(procesado_en);
                CREATE TABLE IF NOT EXISTS estado (
                    clave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    detalle TEXT
                );
                """
            )

    def cerrar(self) -> None:
        self._conn.close()

    def __enter__(self) -> "BaseDatos":
        return self

    def __exit__(self, *_exc) -> None:
        self.cerrar()

    # -- idempotencia -----------------------------------------------------
    def reservar(
        self,
        message_id: str,
        gmail_id: str,
        thread_id: str = "",
        remitente: str = "",
        asunto: str = "",
    ) -> bool:
        """Reserva el mensaje. ``False`` si ya estaba registrado."""
        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT OR IGNORE INTO mensajes
                    (message_id, gmail_id, thread_id, remitente, asunto,
                     estado, recibido_en)
                VALUES (?, ?, ?, ?, ?, 'reservado', ?)
                """,
                (
                    message_id,
                    gmail_id,
                    thread_id,
                    remitente,
                    asunto[:200],
                    ahora_utc(),
                ),
            )
        return cursor.rowcount == 1

    def finalizar(
        self,
        message_id: str,
        estado: str,
        *,
        herramienta: str | None = None,
        codigo_salida: int | None = None,
        ejecutado: bool = False,
        detalle: str | None = None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                UPDATE mensajes
                   SET estado = ?, herramienta = ?, codigo_salida = ?,
                       ejecutado = ?, detalle = ?, procesado_en = ?
                 WHERE message_id = ?
                """,
                (
                    estado,
                    herramienta,
                    codigo_salida,
                    1 if ejecutado else 0,
                    (detalle or "")[:2000],
                    ahora_utc(),
                    message_id,
                ),
            )

    def obtener(self, message_id: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM mensajes WHERE message_id = ?", (message_id,)
        ).fetchone()

    def contar_ejecutadas_ultima_hora(self, ahora: datetime | None = None) -> int:
        ahora = ahora or datetime.now(timezone.utc)
        desde = (ahora - timedelta(hours=1)).isoformat(timespec="seconds")
        fila = self._conn.execute(
            """
            SELECT COUNT(*) AS total FROM mensajes
             WHERE ejecutado = 1 AND procesado_en IS NOT NULL
               AND procesado_en >= ?
            """,
            (desde,),
        ).fetchone()
        return int(fila["total"] if fila else 0)

    def reservas_colgadas(self, minutos: int = 30) -> list[sqlite3.Row]:
        limite = (
            datetime.now(timezone.utc) - timedelta(minutes=minutos)
        ).isoformat(timespec="seconds")
        return list(
            self._conn.execute(
                """
                SELECT * FROM mensajes
                 WHERE estado = 'reservado' AND recibido_en < ?
                """,
                (limite,),
            ).fetchall()
        )

    # -- pausa ------------------------------------------------------------
    def pausar(self, motivo: str = "") -> None:
        self._estado("pausado", "1")
        self._estado("pausado_motivo", motivo[:200])
        self._estado("pausado_en", ahora_utc())
        self.registrar_evento("pausa", motivo)

    def reanudar(self) -> None:
        self._estado("pausado", "0")
        self._estado("pausado_motivo", "")
        self._estado("pausado_en", "")
        self.registrar_evento("reanudar", "")

    def esta_pausado(self) -> tuple[bool, str]:
        pausado = self._leer_estado("pausado", "0") == "1"
        motivo = self._leer_estado("pausado_motivo", "")
        return pausado, motivo

    # -- estado/eventos ---------------------------------------------------
    def _estado(self, clave: str, valor: str) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO estado (clave, valor) VALUES (?, ?)
                ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
                """,
                (clave, valor),
            )

    def _leer_estado(self, clave: str, defecto: str = "") -> str:
        fila = self._conn.execute(
            "SELECT valor FROM estado WHERE clave = ?", (clave,)
        ).fetchone()
        return str(fila["valor"]) if fila else defecto

    def registrar_evento(self, tipo: str, detalle: str = "") -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO eventos (ts, tipo, detalle) VALUES (?, ?, ?)",
                (ahora_utc(), tipo, (detalle or "")[:1000]),
            )

    def eventos(self, limite: int = 50) -> list[sqlite3.Row]:
        return list(
            self._conn.execute(
                "SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
        )
