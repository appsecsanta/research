from __future__ import annotations

import mimetypes
from pathlib import Path

from flask import Flask, abort, request, send_file
from werkzeug.utils import safe_join


def create_app() -> Flask:
    app = Flask(__name__)

    uploads_dir = Path(app.root_path) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/download")
    def download() -> tuple:
        filename = request.args.get("filename", type=str)
        if not filename:
            abort(400, description="Missing 'filename' query parameter.")

        joined = safe_join(str(uploads_dir), filename)
        if not joined:
            abort(400, description="Invalid filename.")

        file_path = Path(joined)
        if not file_path.is_file():
            abort(404)

        mimetype, _ = mimetypes.guess_type(str(file_path))
        return send_file(
            file_path,
            mimetype=mimetype or "application/octet-stream",
            as_attachment=False,
            download_name=file_path.name,
            conditional=True,
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False)
