"""Logging estructurado para el ETL.

Imprime a stdout (apto para Railway/contenedores) en JSON o texto plano.
"""
import json
import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Serializa cada registro como una línea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Permite agregar campos extra via logger.info("msg", extra={"key": "v"})
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", fmt: str = "json") -> logging.Logger:
    """Configura el logger raíz una sola vez.

    Args:
        level: Nivel mínimo a emitir (DEBUG, INFO, WARNING, ERROR).
        fmt: ``"json"`` para JSON estructurado, otro valor para texto plano.

    Returns:
        El logger raíz configurado.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Evita handlers duplicados si se llama varias veces (notebooks, tests).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
        )
    root.addHandler(handler)
    return root
