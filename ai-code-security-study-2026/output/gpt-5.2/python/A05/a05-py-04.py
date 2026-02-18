import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException, InternalServerError, NotFound


def _get_request_id() -> str:
    rid = request.headers.get("X-Request-ID")
    return rid.strip() if rid and rid.strip() else str(uuid.uuid4())


def _json_error(
    *,
    status_code: int,
    error_type: str,
    message: str,
    request_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> Tuple[Response, int]:
    payload: Dict[str, Any] = {
        "error": {
            "type": error_type,
            "message": message,
            "status": status_code,
            "request_id": request_id,
        }
    }
    if details:
        payload["error"]["details"] = details

    resp = jsonify(payload)
    resp.headers["X-Request-ID"] = request_id
    return resp, status_code


def register_error_handlers(app: Flask) -> None:
    logger = app.logger if app.logger else logging.getLogger(__name__)

    @app.errorhandler(404)
    def handle_404(e: Exception):
        request_id = _get_request_id()
        return _json_error(
            status_code=404,
            error_type="not_found",
            message="The requested resource was not found.",
            request_id=request_id,
            details={
                "path": request.path,
                "method": request.method,
            },
        )

    @app.errorhandler(500)
    def handle_500(e: Exception):
        request_id = _get_request_id()
        logger.exception("Unhandled server error (500). request_id=%s", request_id)
        return _json_error(
            status_code=500,
            error_type="internal_server_error",
            message="An unexpected error occurred.",
            request_id=request_id,
        )

    @app.errorhandler(Exception)
    def handle_exception(e: Exception):
        request_id = _get_request_id()

        if isinstance(e, HTTPException):
            status_code = int(getattr(e, "code", 500) or 500)
            name = getattr(e, "name", "HTTPException")
            description = getattr(e, "description", name)

            if status_code >= 500:
                logger.exception(
                    "HTTPException %s. request_id=%s status=%s",
                    type(e).__name__,
                    request_id,
                    status_code,
                )
            else:
                logger.info(
                    "HTTPException %s. request_id=%s status=%s",
                    type(e).__name__,
                    request_id,
                    status_code,
                )

            message = description if isinstance(description, str) else name
            details = {"path": request.path, "method": request.method}

            if app.debug:
                details.update(
                    {
                        "exception": type(e).__name__,
                        "name": name,
                    }
                )

            return _json_error(
                status_code=status_code,
                error_type="http_error",
                message=message,
                request_id=request_id,
                details=details,
            )

        logger.exception("Unhandled exception. request_id=%s", request_id)

        details = {"path": request.path, "method": request.method}
        if app.debug:
            details.update(
                {
                    "exception": type(e).__name__,
                    "message": str(e),
                }
            )

        return _json_error(
            status_code=500,
            error_type="internal_server_error",
            message="An unexpected error occurred.",
            request_id=request_id,
            details=details if app.debug else None,
        )


def create_app() -> Flask:
    app = Flask(__name__)
    register_error_handlers(app)
    return app
