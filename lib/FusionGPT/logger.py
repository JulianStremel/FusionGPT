"""FusionGPT file-based logger.

Writes rotating log files to  <addin-root>/logs/fusiongpt.log  so that every
LLM interaction and tool-call can be inspected outside of Fusion 360's own
Text Commands window.
"""

import json
import logging
import os
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Resolve the log directory relative to this file.
# File layout:  <addin-root>/lib/FusionGPT/logger.py
#               <addin-root>/logs/fusiongpt.log
# ---------------------------------------------------------------------------
_ADDIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOG_DIR = os.path.join(_ADDIN_ROOT, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "fusiongpt.log")

_logger: logging.Logger = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(_LOG_DIR, exist_ok=True)

    _logger = logging.getLogger("FusionGPT")
    _logger.setLevel(logging.DEBUG)

    if not _logger.handlers:
        handler = RotatingFileHandler(
            _LOG_FILE,
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=2,
            encoding="utf-8",
        )
        handler.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(fmt)
        _logger.addHandler(handler)

    return _logger


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def log_info(message: str) -> None:
    """Log a generic informational message."""
    _get_logger().info(message)


def log_error(message: str, exc_info: bool = False) -> None:
    """Log an error message, optionally with the current exception traceback."""
    _get_logger().error(message, exc_info=exc_info)


def log_llm_request(model: str, messages: list) -> None:
    """Log an outgoing LLM request (model + summarised message list)."""
    summary = [
        {"role": m.get("role"), "content_len": len(str(m.get("content") or ""))}
        for m in messages
    ]
    _get_logger().info(
        "LLM REQUEST  | model=%s | messages=%s", model, json.dumps(summary)
    )


def log_llm_response(response_text: str, tool_calls: list = None) -> None:
    """Log an incoming LLM response (text preview or tool-call names)."""
    if tool_calls:
        names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
        _get_logger().info("LLM RESPONSE | tool_calls=%s", names)
    else:
        preview = (response_text or "")[:300].replace("\n", " ")
        _get_logger().info("LLM RESPONSE | text=%r", preview)


def log_tool_call(tool_name: str, args: dict, result: str) -> None:
    """Log a tool / function call and its result."""
    result_preview = (result or "")[:300].replace("\n", " ")
    _get_logger().info(
        "TOOL CALL    | tool=%s | args=%s | result=%r",
        tool_name,
        json.dumps(args),
        result_preview,
    )
