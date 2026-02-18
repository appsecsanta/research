import functools
import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple, Union

from flask import Response, current_app, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.local import LocalProxy


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(obj: Any) -> str:
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def _safe_truncate(value: Any, limit: int) -> Any:
    if limit <= 0:
        return value
    try:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", errors="replace")
        if isinstance(value, str) and len(value) > limit:
            return value[:limit] + f"...(truncated,{len(value)} chars)"
        if isinstance(value, (list, tuple)) and len(value) > limit:
            return list(value[:limit]) + [f"...(truncated,{len(value)} items)"]
        if isinstance(value, dict) and len(value) > limit:
            items = list(value.items())[:limit]
            out = dict(items)
            out["...(truncated)"] = f"{len(value)} keys total"
            return out
    except Exception:
        return value
    return value


def _redact_headers(headers: Dict[str, str], redact: Set[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in redact or any(lk == r or lk.endswith(r) for r in redact):
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out


def _best_effort_json() -> Any:
    try:
        return request.get_json(silent=True)
    except Exception:
        return None


def _best_effort_form() -> Any:
    try:
        return request.form.to_dict(flat=False)
    except Exception:
        return None


def _best_effort_args() -> Any:
    try:
        return request.args.to_dict(flat=False)
    except Exception:
        return None


def _best_effort_view_args() -> Any:
    try:
        return getattr(request, "view_args", None)
    except Exception:
        return None


def _best_effort_body(max_len: int) -> Optional[str]:
    try:
        data = request.get_data(cache=False, as_text=False)
        if not data:
            return None
        if max_len > 0 and len(data) > max_len:
            data = data[:max_len]
            suffix = f"...(truncated,{len(request.get_data(cache=True, as_text=False))} bytes total)"
        else:
            suffix = ""
        text = data.decode("utf-8", errors="replace")
        return text + suffix
    except Exception:
        return None


def _get_request_context(
    *,
    include_body: bool,
    max_body_bytes: int,
    max_value_len: int,
    max_collection_len: int,
    redact_header_names: Set[str],
) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {}
    try:
        headers = dict(request.headers.items())
        ctx = {
            "timestamp_utc": _utc_iso(),
            "method": request.method,
            "url": request.url,
            "base_url": request.base_url,
            "path": request.path,
            "full_path": request.full_path,
            "endpoint": request.endpoint,
            "blueprint": request.blueprint,
            "remote_addr": request.remote_addr,
            "access_route": list(getattr(request, "access_route", []) or []),
            "scheme": request.scheme,
            "host": request.host,
            "user_agent": str(request.user_agent),
            "referrer": request.referrer,
            "content_type": request.content_type,
            "content_length": request.content_length,
            "headers": _redact_headers(headers, redact_header_names),
            "query_args": _safe_truncate(_best_effort_args(), max_collection_len),
            "view_args": _safe_truncate(_best_effort_view_args(), max_collection_len),
            "form": _safe_truncate(_best_effort_form(), max_collection_len),
            "json": _safe_truncate(_best_effort_json(), max_collection_len),
        }
        if include_body:
            ctx["raw_body"] = _safe_truncate(_best_effort_body(max_body_bytes), max_value_len)
    except Exception as e:
        ctx["request_context_error"] = repr(e)
    return ctx


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def create_file_logger(
    name: str = "flask_endpoint_errors",
    log_file: str = "logs/endpoint_errors.log",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    _ensure_dir(log_file)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == os.path.abspath(log_file)
               for h in logger.handlers):
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def error_logging_decorator(
    *,
    logger: Optional[logging.Logger] = None,
    log_file: str = "logs/endpoint_errors.log",
    level: int = logging.INFO,
    include_request_body: bool = False,
    max_body_bytes: int = 16 * 1024,
    max_value_len: int = 4096,
    max_collection_len: int = 200,
    redact_header_names: Iterable[str] = ("authorization", "cookie", "set-cookie", "x-api-key"),
    include_app_config_keys: Iterable[str] = ("ENV", "DEBUG", "TESTING"),
    return_json: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Union[Response, Tuple[Response, int], Any]]]:
    redact_set = {h.lower() for h in redact_header_names}
    include_cfg = tuple(include_app_config_keys)

    def decorator(func: Callable[..., Any]) -> Callable[..., Union[Response, Tuple[Response, int], Any]]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Union[Response, Tuple[Response, int], Any]:
            nonlocal logger
            if logger is None:
                logger = create_file_logger(log_file=log_file, level=level)

            try:
                return func(*args, **kwargs)
            except Exception as exc:
                error_id = uuid.uuid4().hex
                http_code = 500
                is_http = isinstance(exc, HTTPException)
                if is_http and getattr(exc, "code", None):
                    http_code = int(exc.code)

                req_ctx = {}
                try:
                    req_ctx = _get_request_context(
                        include_body=include_request_body,
                        max_body_bytes=max_body_bytes,
                        max_value_len=max_value_len,
                        max_collection_len=max_collection_len,
                        redact_header_names=redact_set,
                    )
                except Exception:
                    req_ctx = {"request_context_error": "failed to capture request context"}

                app_ctx: Dict[str, Any] = {}
                try:
                    app_ctx = {
                        "flask_app_name": getattr(current_app, "name", None),
                        "flask_instance_path": getattr(current_app, "instance_path", None),
                        "flask_config": {k: current_app.config.get(k) for k in include_cfg},
                    }
                except Exception:
                    app_ctx = {"app_context_error": "failed to capture app context"}

                exc_type = type(exc).__name__
                tb = traceback.format_exc()

                payload = {
                    "error_id": error_id,
                    "exception_type": exc_type,
                    "exception_message": str(exc),
                    "http_code": http_code,
                    "request": req_ctx,
                    "app": app_ctx,
                    "traceback": tb,
                }

                try:
                    logger.error(json.dumps(payload, default=_json_default, ensure_ascii=False))
                except Exception:
                    try:
                        logger.error(
                            "error_id=%s exception_type=%s http_code=%s message=%r traceback=%s",
                            error_id,
                            exc_type,
                            http_code,
                            str(exc),
                            tb,
                        )
                    except Exception:
                        pass

                if not return_json:
                    return Response("Internal Server Error", status=500)

                if http_code >= 500:
                    body = {
                        "error": "internal_server_error",
                        "message": "An unexpected error occurred.",
                        "error_id": error_id,
                    }
                    return jsonify(body), 500

                body = {
                    "error": "request_error",
                    "message": getattr(exc, "description", str(exc)) if is_http else str(exc),
                    "error_id": error_id,
                }
                return jsonify(body), http_code

        return wrapper

    return decorator


# Convenience: a preconfigured decorator instance you can import and use directly.
log_endpoint_errors = error_logging_decorator()
