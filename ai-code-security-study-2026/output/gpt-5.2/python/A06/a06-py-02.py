#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests


LOG = logging.getLogger("model_downloader")


def _safe_filename(name: str) -> str:
    name = name.strip().replace("\\", "_").replace("/", "_")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "model"


def _infer_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    base = os.path.basename(path)
    return _safe_filename(base) if base else "model"


def _infer_filename_from_headers(headers: dict[str, str]) -> Optional[str]:
    cd = headers.get("content-disposition") or headers.get("Content-Disposition")
    if not cd:
        return None
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.IGNORECASE)
    if not m:
        return None
    return _safe_filename(m.group(1))


def _detect_format_from_suffix(path: Path) -> Optional[str]:
    suf = path.suffix.lower()
    if suf == ".pkl":
        return "pkl"
    if suf == ".h5":
        return "h5"
    return None


def download_model(
    url: str,
    output_dir: Path,
    filename: Optional[str] = None,
    timeout: float = 60.0,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()

        inferred = _infer_filename_from_headers(r.headers) or _infer_filename_from_url(url)
        out_name = _safe_filename(filename) if filename else inferred

        out_path = output_dir / out_name

        # If no extension, try to infer from content-type
        if out_path.suffix == "":
            ct = (r.headers.get("content-type") or "").lower()
            if "hdf5" in ct or "h5" in ct:
                out_path = out_path.with_suffix(".h5")
            elif "pickle" in ct or "pkl" in ct:
                out_path = out_path.with_suffix(".pkl")

        tmp_fd, tmp_name = tempfile.mkstemp(prefix=out_path.name + ".", suffix=".tmp", dir=str(output_dir))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                f.flush()
                os.fsync(f.fileno())

            tmp_path.replace(out_path)
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    return out_path


def load_model(model_path: Path) -> Any:
    fmt = _detect_format_from_suffix(model_path)
    if fmt is None:
        raise ValueError(f"Unsupported model format (expected .pkl or .h5): {model_path}")

    if fmt == "pkl":
        try:
            import joblib  # type: ignore
            return joblib.load(model_path)
        except Exception:
            with model_path.open("rb") as f:
                return pickle.load(f)

    # fmt == "h5"
    try:
        import tensorflow as tf  # type: ignore
    except Exception as e:
        raise RuntimeError("TensorFlow is required to load .h5 models. Install: pip install tensorflow") from e

    return tf.keras.models.load_model(str(model_path))


def _to_2d_array(data: Any) -> Any:
    try:
        import numpy as np  # type: ignore
    except Exception as e:
        raise RuntimeError("NumPy is required for inference. Install: pip install numpy") from e

    arr = np.asarray(data)
    if arr.ndim == 0:
        arr = arr.reshape(1, 1)
    elif arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr


def run_inference(model: Any, input_json: str, prefer_proba: bool = False) -> Any:
    payload = json.loads(input_json)
    x = _to_2d_array(payload)

    if prefer_proba and hasattr(model, "predict_proba"):
        y = model.predict_proba(x)
    elif hasattr(model, "predict"):
        y = model.predict(x)
    else:
        raise TypeError("Loaded object does not support inference (missing predict/predict_proba).")

    try:
        import numpy as np  # type: ignore
        if isinstance(y, np.ndarray):
            return y.tolist()
    except Exception:
        pass

    if hasattr(y, "tolist"):
        return y.tolist()
    return y


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Download a .pkl or .h5 model from a URL, save locally, and load for inference.")
    p.add_argument("url", help="Model URL (.pkl or .h5)")
    p.add_argument("-o", "--output-dir", default="models", help="Directory to save the model (default: models)")
    p.add_argument("-f", "--filename", default=None, help="Override the saved filename")
    p.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds (default: 60)")
    p.add_argument("--predict-json", default=None, help="Run inference using a JSON array (e.g. '[[1,2,3],[4,5,6]]' or '[1,2,3]')")
    p.add_argument("--prefer-proba", action="store_true", help="Prefer predict_proba when available (for .pkl models)")
    p.add_argument("--quiet", action="store_true", help="Reduce logging output")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    output_dir = Path(args.output_dir).expanduser().resolve()

    try:
        model_path = download_model(args.url, output_dir=output_dir, filename=args.filename, timeout=args.timeout)
        LOG.info("Saved model to: %s", model_path)

        model = load_model(model_path)
        LOG.info("Model loaded successfully.")

        if args.predict_json is not None:
            preds = run_inference(model, args.predict_json, prefer_proba=args.prefer_proba)
            sys.stdout.write(json.dumps({"predictions": preds}) + "\n")
        else:
            sys.stdout.write(json.dumps({"model_path": str(model_path), "status": "loaded"}) + "\n")

        return 0
    except requests.HTTPError as e:
        LOG.error("HTTP error: %s", e)
        return 2
    except Exception as e:
        LOG.error("Error: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
