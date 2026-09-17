"""Núcleo compartido de HerramientasAgentes.

Engranajes comunes a todos los módulos: contrato de resultado, errores
tipados, configuración/catálogo y utilidades de CLI.
"""

from .contrato import Artefacto, Resultado, exito, fallo
from .errores import AgenteError

__all__ = ["Artefacto", "Resultado", "exito", "fallo", "AgenteError"]
