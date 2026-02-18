#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import tomllib  # py>=3.11
except Exception:  # pragma: no cover
    tomllib = None

LOG = logging.getLogger("deps_installer")


@dataclasses.dataclass(frozen=True)
class Dependency:
    name: str
    url: str
    sha256: str | None = None
    filename: str | None = None


@dataclasses.dataclass(frozen=True)
class Config:
    dependencies: tuple[Dependency, ...]
    pip_extra_args: tuple[str, ...] = ()


class ConfigError(Exception):
    pass


class DownloadError(Exception):
    pass


def _setup_logging(verbose: bool) -> None:
    handler = logging.StreamHandler(stream=sys.stdout)
    fmt = "%(asctime)s %(levelname)s %(message)s"
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt="%Y-%m-%dT%H:%M:%S"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.DEBUG if verbose else logging.INFO)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ConfigError(f"Config file not found: {path}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read config file: {path}: {e}") from e


def _parse_config(path: Path) -> Config:
    suffix = path.suffix.lower()
    raw_text = _read_text(path)

    data: Any
    if suffix == ".json":
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config {path}: {e}") from e
    elif suffix == ".toml":
        if tomllib is None:
            raise ConfigError("TOML config requires Python 3.11+ (tomllib not available).")
        try:
            data = tomllib.loads(raw_text)
        except Exception as e:
            raise ConfigError(f"Invalid TOML in config {path}: {e}") from e
    elif suffix in (".yml", ".yaml"):
        try:
            import yaml  # type: ignore
        except Exception as e:
            raise ConfigError("YAML config requires PyYAML to be installed.") from e
        try:
            data = yaml.safe_load(raw_text)
        except Exception as e:
            raise ConfigError(f"Invalid YAML in config {path}: {e}") from e
    else:
        raise ConfigError(f"Unsupported config file type: {path.suffix} (use .json/.toml/.yml)")

    if data is None:
        raise ConfigError("Config is empty.")

    deps_node: Any
    pip_node: Any = None

    if isinstance(data, Mapping):
        deps_node = data.get("dependencies")
        pip_node = data.get("pip")
    elif isinstance(data, list):
        deps_node = data
    else:
        raise ConfigError("Config must be a dict with 'dependencies' or a list of dependencies.")

    if not isinstance(deps_node, list) or not deps_node:
        raise ConfigError("'dependencies' must be a non-empty list.")

    deps: list[Dependency] = []
    for i, item in enumerate(deps_node):
        if not isinstance(item, Mapping):
            raise ConfigError(f"Dependency entry #{i} must be an object/dict.")
        url = str(item.get("url") or "").strip()
        if not url:
            raise ConfigError(f"Dependency entry #{i} missing required field: url")
        name = str(item.get("name") or "").strip() or _infer_name_from_url(url) or f"dep_{i}"
        sha256 = item.get("sha256")
        if sha256 is not None:
            sha256 = str(sha256).strip().lower()
        filename = item.get("filename")
        if filename is not None:
            filename = str(filename).strip()
        deps.append(Dependency(name=name, url=url, sha256=sha256, filename=filename))

    pip_extra_args: tuple[str, ...] = ()
    if pip_node is not None:
        if not isinstance(pip_node, Mapping):
            raise ConfigError("'pip' must be an object/dict if provided.")
        extra_args = pip_node.get("extra_args", [])
        if extra_args is None:
            extra_args = []
        if not isinstance(extra_args, list) or any(not isinstance(x, str) for x in extra_args):
            raise ConfigError("'pip.extra_args' must be a list of strings.")
        pip_extra_args = tuple(extra_args)

    return Config(dependencies=tuple(deps), pip_extra_args=pip_extra_args)


def _infer_name_from_url(url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(url)
        fname = Path(urllib.parse.unquote(parsed.path)).name
        if not fname:
            return None
        # Basic heuristic: strip common archive extensions
        for ext in (".whl", ".tar.gz", ".zip", ".tgz", ".tar"):
            if fname.endswith(ext):
                return fname[: -len(ext)]
        return fname
    except Exception:
        return None


def _safe_filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    fname = Path(urllib.parse.unquote(parsed.path)).name
    if not fname:
        fname = "download"
    # Avoid path traversal and illegal names
    fname = fname.replace("/", "_").replace("\\", "_")
    return fname


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _download_with_retries(
    url: str,
    dest_path: Path,
    *,
    timeout: float,
    retries: int,
    backoff_seconds: float,
    headers: Mapping[str, str] | None = None,
) -> None:
    last_err: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            _download(url, dest_path, timeout=timeout, headers=headers)
            return
        except Exception as e:
            last_err = e
            if attempt >= retries + 1:
                break
            sleep_s = backoff_seconds * (2 ** (attempt - 1))
            LOG.warning("Download failed (attempt %d/%d): %s; retrying in %.1fs", attempt, retries + 1, e, sleep_s)
            time.sleep(sleep_s)
    raise DownloadError(f"Failed to download {url}: {last_err}") from last_err


def _download(url: str, dest_path: Path, *, timeout: float, headers: Mapping[str, str] | None = None) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers=dict(headers or {}))
    req.add_header("User-Agent", "internal-ci-deps-installer/1.0")

    tmp_fd = None
    tmp_path: Path | None = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if hasattr(resp, "status") and resp.status >= 400:
                raise DownloadError(f"HTTP {resp.status} for {url}")

            tmp_fd, tmp_name = tempfile.mkstemp(prefix=dest_path.name + ".", suffix=".tmp", dir=str(dest_path.parent))
            tmp_path = Path(tmp_name)

            with os.fdopen(tmp_fd, "wb") as out:
                tmp_fd = None
                shutil.copyfileobj(resp, out, length=1024 * 1024)

        tmp_path.replace(dest_path)
    except urllib.error.HTTPError as e:
        raise DownloadError(f"HTTP error for {url}: {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise DownloadError(f"URL error for {url}: {e.reason}") from e
    except TimeoutError as e:
        raise DownloadError(f"Timeout downloading {url}") from e
    except OSError as e:
        raise DownloadError(f"I/O error downloading {url}: {e}") from e
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except Exception:
                pass
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def _verify_sha256(path: Path, expected_hex: str) -> None:
    expected = expected_hex.strip().lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise DownloadError(f"Invalid expected sha256 value: {expected_hex!r}")
    actual = _sha256_file(path)
    if actual != expected:
        raise DownloadError(f"SHA256 mismatch for {path.name}: expected {expected}, got {actual}")


def _pip_install(
    artifacts: Sequence[Path],
    *,
    install_dir: Path,
    download_dir: Path,
    pip_extra_args: Sequence[str],
) -> None:
    install_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-input",
        "--no-color",
        "--no-index",
        "--find-links",
        str(download_dir),
        "--target",
        str(install_dir),
        "--upgrade",
        "--disable-pip-version-check",
        "--no-warn-script-location",
    ]
    cmd.extend(pip_extra_args)
    cmd.extend(str(p) for p in artifacts)

    LOG.info("Installing %d artifact(s) into %s", len(artifacts), install_dir)
    LOG.debug("Running: %s", " ".join(cmd))

    proc = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"pip install failed with exit code {proc.returncode}")


def _normalize_sha(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.strip().lower()
    return s or None


def _download_and_verify_one(
    dep: Dependency,
    *,
    download_dir: Path,
    timeout: float,
    retries: int,
    backoff_seconds: float,
    allow_unverified: bool,
    lock: threading.Lock,
) -> Path:
    filename = dep.filename or _safe_filename_from_url(dep.url)
    dest = download_dir / filename

    expected_sha = _normalize_sha(dep.sha256)
    if expected_sha is None and not allow_unverified:
        raise DownloadError(f"Dependency '{dep.name}' is missing sha256 and --allow-unverified not set.")

    # If file exists and hash matches, skip download
    if dest.exists():
        if expected_sha is None:
            LOG.info("Using existing file (unverified): %s", dest)
            return dest
        try:
            _verify_sha256(dest, expected_sha)
            LOG.info("Using cached verified artifact: %s", dest)
            return dest
        except DownloadError:
            LOG.warning("Cached artifact failed verification; re-downloading: %s", dest)
            try:
                dest.unlink()
            except Exception:
                pass

    LOG.info("Downloading %s from %s", dep.name, dep.url)
    _download_with_retries(
        dep.url,
        dest,
        timeout=timeout,
        retries=retries,
        backoff_seconds=backoff_seconds,
        headers=None,
    )

    if expected_sha is not None:
        LOG.info("Verifying sha256 for %s", dest.name)
        _verify_sha256(dest, expected_sha)
    else:
        with lock:
            LOG.warning("Downloaded without verification (sha256 missing): %s", dep.name)

    return dest


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="deps_installer",
        description="Download, verify, and install internal build dependencies into a local directory.",
    )
    p.add_argument("--config", required=True, type=Path, help="Path to config (.json/.toml/.yml)")
    p.add_argument("--download-dir", required=True, type=Path, help="Directory for downloaded artifacts")
    p.add_argument("--install-dir", required=True, type=Path, help="Local install directory (pip --target)")
    p.add_argument("--jobs", type=int, default=4, help="Parallel download jobs (default: 4)")
    p.add_argument("--timeout", type=float, default=60.0, help="Download timeout in seconds (default: 60)")
    p.add_argument("--retries", type=int, default=3, help="Download retries (default: 3)")
    p.add_argument("--backoff", type=float, default=1.0, help="Retry backoff base seconds (default: 1.0)")
    p.add_argument(
        "--allow-unverified",
        action="store_true",
        help="Allow dependencies without sha256 (NOT recommended).",
    )
    p.add_argument(
        "--pip-arg",
        action="append",
        default=[],
        help="Extra argument to pass to pip install (repeatable).",
    )
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    _setup_logging(args.verbose)

    try:
        cfg = _parse_config(args.config)
        pip_extra_args = tuple(cfg.pip_extra_args) + tuple(args.pip_arg or [])
        download_dir = args.download_dir
        install_dir = args.install_dir

        download_dir.mkdir(parents=True, exist_ok=True)
        install_dir.mkdir(parents=True, exist_ok=True)

        lock = threading.Lock()
        artifacts: list[Path] = []

        LOG.info("Downloading %d dependenc(ies) to %s", len(cfg.dependencies), download_dir)

        with ThreadPoolExecutor(max_workers=max(1, int(args.jobs))) as ex:
            futures = [
                ex.submit(
                    _download_and_verify_one,
                    dep,
                    download_dir=download_dir,
                    timeout=float(args.timeout),
                    retries=int(args.retries),
                    backoff_seconds=float(args.backoff),
                    allow_unverified=bool(args.allow_unverified),
                    lock=lock,
                )
                for dep in cfg.dependencies
            ]
            for fut in as_completed(futures):
                artifacts.append(fut.result())

        # Deterministic install order
        artifacts_sorted = sorted(artifacts, key=lambda p: p.name)
        _pip_install(
            artifacts_sorted,
            install_dir=install_dir,
            download_dir=download_dir,
            pip_extra_args=pip_extra_args,
        )

        LOG.info("Done.")
        return 0

    except ConfigError as e:
        LOG.error("Config error: %s", e)
        return 2
    except DownloadError as e:
        LOG.error("Download/verification error: %s", e)
        return 3
    except subprocess.SubprocessError as e:
        LOG.error("Subprocess error: %s", e)
        return 4
    except Exception as e:
        LOG.exception("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
