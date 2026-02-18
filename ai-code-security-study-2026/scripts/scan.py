#!/usr/bin/env python3
"""
SAST Scanning Orchestration Script
AI-Generated Code Security Study 2026

Runs 6 open-source SAST tools against AI-generated code and normalizes
the results into a common JSON format for downstream analysis.

Tools:
    1. Bandit        - Python static analysis
    2. OpenGrep      - Multi-language pattern matching (semgrep CLI)
    3. ESLint        - JavaScript linting with security plugin
    4. njsscan       - Node.js security scanner
    5. Bearer        - Multi-language security scanner
    6. CodeQL        - GitHub's semantic code analysis

Usage:
    python3 scan.py                    # Run all tools on all models
    python3 scan.py --tool bandit      # Run only Bandit
    python3 scan.py --model gpt-5.2    # Scan only one model
    python3 scan.py --dry-run          # Preview without running
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
OUTPUT_DIR = SCRIPT_DIR / "output"
SCANS_DIR = SCRIPT_DIR / "scans"
RULES_DIR = SCRIPT_DIR / "rules" / "opengrep"
LOG_PATH = SCANS_DIR / "scan.log"

# Tool binary paths — resolve via PATH, allow env var override
TOOL_PATHS = {
    "bandit": os.environ.get("BANDIT_PATH", shutil.which("bandit") or "bandit"),
    "semgrep": os.environ.get("SEMGREP_PATH", shutil.which("semgrep") or "semgrep"),
    "eslint": os.environ.get("ESLINT_PATH", shutil.which("eslint") or "eslint"),
    "njsscan": os.environ.get("NJSSCAN_PATH", shutil.which("njsscan") or "njsscan"),
    "bearer": os.environ.get("BEARER_PATH", shutil.which("bearer") or "bearer"),
    "codeql": os.environ.get("CODEQL_PATH", shutil.which("codeql") or "codeql"),
}

# Timeouts in seconds
TIMEOUT_DEFAULT = 120
TIMEOUT_CODEQL = 300

# Severity mapping helpers
ESLINT_SEVERITY_MAP = {1: "LOW", 2: "MEDIUM"}
SARIF_LEVEL_MAP = {"error": "HIGH", "warning": "MEDIUM", "note": "LOW", "none": "LOW"}
BEARER_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "warning": "LOW",
}

# All supported tools in execution order
ALL_TOOLS = ["bandit", "opengrep", "eslint", "njsscan", "bearer", "codeql"]

# File extensions to language mapping
EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
}

# Global npm modules path (for ESLint plugin resolution)
# Resolve dynamically; fall back to common locations
def _find_npm_global_path():
    try:
        result = subprocess.run(
            ["npm", "root", "-g"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return os.environ.get("NPM_GLOBAL_PATH", "/opt/homebrew/lib/node_modules")

GLOBAL_NPM_PATH = _find_npm_global_path()

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def setup_logging():
    """Configure logging to both file and stderr."""
    SCANS_DIR.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger("scan")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def discover_models():
    """
    Discover model directories from the output/ folder.

    Returns a list of model IDs (directory names) that exist in output/.
    """
    if not OUTPUT_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in OUTPUT_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def tool_available(tool_name):
    """Check whether a tool binary is available on PATH."""
    binary = TOOL_PATHS.get(tool_name, tool_name)
    return shutil.which(binary) is not None


def extract_owasp_from_path(filepath, model_output_dir):
    """
    Extract OWASP category from file path.

    Expected structure: output/{model_id}/{language}/{owasp_id}/{file}
    The filepath may be absolute or already relative (e.g. SARIF URIs).
    Returns the owasp_id component (e.g. "A03") or "unknown".
    """
    p = Path(filepath)

    # Try to make it relative to the model output dir
    try:
        rel = p.relative_to(model_output_dir)
    except ValueError:
        # Already relative or under a different root — use as-is
        rel = p

    parts = rel.parts
    # parts[0] = language, parts[1] = owasp_id, parts[2] = filename
    if len(parts) >= 3:
        candidate = parts[1].upper()
        if re.match(r"^A\d{2}$", candidate):
            return candidate
    return "unknown"


def extract_language_from_path(filepath, model_output_dir):
    """
    Extract language from file path structure or extension.

    First tries the directory structure: output/{model_id}/{language}/...
    The filepath may be absolute or already relative (e.g. SARIF URIs).
    Falls back to file extension.
    """
    p = Path(filepath)
    try:
        rel = p.relative_to(model_output_dir)
    except ValueError:
        rel = p

    parts = rel.parts
    if len(parts) >= 1 and parts[0] in ("python", "javascript"):
        return parts[0]

    ext = Path(filepath).suffix.lower()
    return EXT_TO_LANG.get(ext, "unknown")


def make_relative(filepath, model_output_dir):
    """Make a filepath relative to the model output directory."""
    try:
        return str(Path(filepath).relative_to(model_output_dir))
    except ValueError:
        return str(filepath)


def resolve_sarif_uri(uri, source_root):
    """Resolve a SARIF artifact URI to a path relative to source_root."""
    # Strip file:/// prefix if present
    if uri.startswith("file:///"):
        uri = uri[7:]
    # SARIF URIs may already be relative to sourceRoot
    full = Path(source_root) / uri
    return make_relative(str(full), source_root)


def extract_cwe_number(cwe_input):
    """
    Extract CWE ID string from various formats.

    Handles:
        - int: 89 -> "CWE-89"
        - dict: {"id": 89, ...} -> "CWE-89"
        - str: "CWE-89: SQL Injection..." -> "CWE-89"
        - list: ["CWE-89: ..."] -> "CWE-89"
    """
    if cwe_input is None:
        return ""

    if isinstance(cwe_input, list):
        # Take the first CWE from a list
        if not cwe_input:
            return ""
        return extract_cwe_number(cwe_input[0])

    if isinstance(cwe_input, dict):
        cwe_id = cwe_input.get("id")
        if cwe_id is not None:
            return f"CWE-{cwe_id}"
        return ""

    if isinstance(cwe_input, int):
        return f"CWE-{cwe_input}"

    # String: extract CWE-NNN pattern
    text = str(cwe_input)
    m = re.search(r"CWE-(\d+)", text)
    if m:
        return f"CWE-{m.group(1)}"

    # Bare number string
    if text.isdigit():
        return f"CWE-{text}"

    return ""


def save_results(tool_name, model_id, findings, output_path):
    """Save normalized findings to JSON."""
    result = {
        "tool": tool_name,
        "model": model_id,
        "scan_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "findings": findings,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool runners
# ---------------------------------------------------------------------------


def run_bandit(model_id, model_output_dir, logger):
    """Run Bandit on Python files and return normalized findings."""
    binary = TOOL_PATHS["bandit"]

    cmd = [
        binary,
        "-r", str(model_output_dir),
        "-f", "json",
        "--severity-level", "all",
    ]

    logger.debug(f"[{model_id}] [bandit] cmd: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_DEFAULT,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"[{model_id}] [bandit] timed out after {TIMEOUT_DEFAULT}s")
        return []
    except FileNotFoundError:
        logger.error(f"[{model_id}] [bandit] binary not found: {binary}")
        return []

    # Bandit exits 1 when findings are detected, that's normal
    if result.returncode not in (0, 1):
        logger.error(
            f"[{model_id}] [bandit] exited {result.returncode}: "
            f"{result.stderr.strip()[:500]}"
        )
        return []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f"[{model_id}] [bandit] failed to parse JSON: {e}")
        return []

    findings = []
    for r in data.get("results", []):
        findings.append({
            "file": make_relative(r.get("filename", ""), model_output_dir),
            "line": r.get("line_number", 0),
            "rule_id": r.get("test_id", ""),
            "severity": r.get("issue_severity", "MEDIUM").upper(),
            "confidence": r.get("issue_confidence", "MEDIUM").upper(),
            "cwe": extract_cwe_number(r.get("issue_cwe")),
            "owasp": extract_owasp_from_path(
                r.get("filename", ""), model_output_dir
            ),
            "message": r.get("issue_text", ""),
            "language": "python",
        })

    return findings


def run_opengrep(model_id, model_output_dir, logger):
    """Run OpenGrep (semgrep) with community rules and return normalized findings."""
    binary = TOOL_PATHS["semgrep"]

    cmd = [
        binary, "scan",
        "--config", "auto",
        str(model_output_dir),
        "--json",
        "--no-git-ignore",
    ]

    logger.debug(f"[{model_id}] [opengrep] cmd: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_DEFAULT,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"[{model_id}] [opengrep] timed out after {TIMEOUT_DEFAULT}s")
        return []
    except FileNotFoundError:
        logger.error(f"[{model_id}] [opengrep] binary not found: {binary}")
        return []

    # Semgrep may exit non-zero for various reasons; try to parse stdout anyway
    stdout = result.stdout
    if not stdout.strip():
        if result.returncode != 0:
            logger.warning(
                f"[{model_id}] [opengrep] exited {result.returncode} with no output. "
                f"stderr: {result.stderr.strip()[:300]}"
            )
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"[{model_id}] [opengrep] failed to parse JSON: {e}")
        return []

    findings = []
    for r in data.get("results", []):
        filepath = r.get("path", "")
        extra = r.get("extra", {})
        metadata = extra.get("metadata", {})

        # Severity: semgrep uses ERROR/WARNING/INFO
        raw_sev = extra.get("severity", "WARNING").upper()
        severity_map = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
        severity = severity_map.get(raw_sev, "MEDIUM")

        # CWE from metadata.cwe (list of strings like "CWE-89: ...")
        cwe = extract_cwe_number(metadata.get("cwe"))

        # Confidence from metadata if available
        confidence = metadata.get("confidence", "MEDIUM")
        if isinstance(confidence, str):
            confidence = confidence.upper()

        findings.append({
            "file": make_relative(filepath, model_output_dir),
            "line": r.get("start", {}).get("line", 0),
            "rule_id": r.get("check_id", ""),
            "severity": severity,
            "confidence": confidence if confidence in ("HIGH", "MEDIUM", "LOW") else "MEDIUM",
            "cwe": cwe,
            "owasp": extract_owasp_from_path(filepath, model_output_dir),
            "message": extra.get("message", ""),
            "language": extract_language_from_path(filepath, model_output_dir),
        })

    return findings


def run_eslint(model_id, model_output_dir, logger):
    """Run ESLint with security plugin on JS files and return normalized findings."""
    binary = TOOL_PATHS["eslint"]

    # Find all .js files
    js_files = list(model_output_dir.rglob("*.js"))
    if not js_files:
        logger.debug(f"[{model_id}] [eslint] no .js files found, skipping")
        return []

    # Create a temporary ESLint flat config that uses the global security plugin
    # ESLint v9 requires flat config (eslint.config.mjs)
    config_content = (
        'import { createRequire } from "node:module";\n'
        "const require = createRequire(import.meta.url);\n"
        f'const security = require("{GLOBAL_NPM_PATH}/eslint-plugin-security");\n'
        "export default [security.configs.recommended];\n"
    )

    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp(prefix="eslint_scan_")
        config_path = Path(tmpdir) / "eslint.config.mjs"
        config_path.write_text(config_content, encoding="utf-8")

        # ESLint v9 picks up the config from the config file location.
        # We pass --config pointing to our temp config and the JS files.
        cmd = [
            binary,
            "--config", str(config_path),
            "-f", "json",
        ] + [str(f) for f in js_files]

        logger.debug(f"[{model_id}] [eslint] cmd: {binary} --config ... -f json [{len(js_files)} files]")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_DEFAULT,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"[{model_id}] [eslint] timed out after {TIMEOUT_DEFAULT}s")
        return []
    except FileNotFoundError:
        logger.error(f"[{model_id}] [eslint] binary not found: {binary}")
        return []
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ESLint exits 1 when there are lint warnings/errors, 2 on fatal errors
    stdout = result.stdout
    if not stdout.strip():
        if result.returncode == 2:
            logger.error(
                f"[{model_id}] [eslint] fatal error (exit 2): "
                f"{result.stderr.strip()[:500]}"
            )
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"[{model_id}] [eslint] failed to parse JSON: {e}")
        return []

    findings = []
    for file_result in data:
        filepath = file_result.get("filePath", "")
        for msg in file_result.get("messages", []):
            # Skip parsing errors (no ruleId)
            rule_id = msg.get("ruleId")
            if not rule_id:
                continue

            raw_sev = msg.get("severity", 1)
            severity = ESLINT_SEVERITY_MAP.get(raw_sev, "LOW")

            findings.append({
                "file": make_relative(filepath, model_output_dir),
                "line": msg.get("line", 0),
                "rule_id": rule_id,
                "severity": severity,
                "confidence": "HIGH",
                "cwe": "",
                "owasp": extract_owasp_from_path(filepath, model_output_dir),
                "message": msg.get("message", ""),
                "language": "javascript",
            })

    return findings


def run_njsscan(model_id, model_output_dir, logger):
    """Run njsscan on JS files and return normalized findings."""
    binary = TOOL_PATHS["njsscan"]

    # Check if there are any JS files
    js_files = list(model_output_dir.rglob("*.js"))
    if not js_files:
        logger.debug(f"[{model_id}] [njsscan] no .js files found, skipping")
        return []

    cmd = [binary, "--json", str(model_output_dir)]

    logger.debug(f"[{model_id}] [njsscan] cmd: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_DEFAULT,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"[{model_id}] [njsscan] timed out after {TIMEOUT_DEFAULT}s")
        return []
    except FileNotFoundError:
        logger.error(f"[{model_id}] [njsscan] binary not found: {binary}")
        return []

    # njsscan may exit non-zero; try to parse stdout
    stdout = result.stdout
    if not stdout.strip():
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"[{model_id}] [njsscan] failed to parse JSON: {e}")
        return []

    findings = []

    # njsscan JSON structure: top-level keys are categories like "nodejs", "templates"
    # Each category contains rule IDs as keys, each with "metadata" and "files"
    for category_key, category_data in data.items():
        if category_key in ("errors", "njsscan_version"):
            continue
        if not isinstance(category_data, dict):
            continue

        for rule_id, rule_data in category_data.items():
            if not isinstance(rule_data, dict):
                continue

            metadata = rule_data.get("metadata", {})
            raw_sev = metadata.get("severity", "WARNING").upper()
            severity_map = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
            severity = severity_map.get(raw_sev, "MEDIUM")
            cwe = extract_cwe_number(metadata.get("cwe"))
            description = metadata.get("description", "")

            for file_info in rule_data.get("files", []):
                filepath = file_info.get("file_path", "")
                # match_lines is typically [start_line, end_line]
                match_lines = file_info.get("match_lines", [])
                line = match_lines[0] if match_lines and isinstance(match_lines[0], int) else 0

                findings.append({
                    "file": make_relative(filepath, model_output_dir),
                    "line": line,
                    "rule_id": rule_id,
                    "severity": severity,
                    "confidence": "MEDIUM",
                    "cwe": cwe,
                    "owasp": extract_owasp_from_path(filepath, model_output_dir),
                    "message": description,
                    "language": "javascript",
                })

    return findings


def run_bearer(model_id, model_output_dir, logger):
    """Run Bearer CLI and return normalized findings."""
    binary = TOOL_PATHS["bearer"]

    cmd = [
        binary, "scan",
        str(model_output_dir),
        "--format", "json",
        "--quiet",
    ]

    logger.debug(f"[{model_id}] [bearer] cmd: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_DEFAULT,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"[{model_id}] [bearer] timed out after {TIMEOUT_DEFAULT}s")
        return []
    except FileNotFoundError:
        logger.error(f"[{model_id}] [bearer] binary not found: {binary}")
        return []

    stdout = result.stdout
    if not stdout.strip():
        return []

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"[{model_id}] [bearer] failed to parse JSON: {e}")
        return []

    findings = []

    # Bearer output formats:
    # 1. Severity-grouped dict: {"high": [...], "medium": [...], "low": [...]}
    # 2. Wrapper dict: {"findings": [...], "warnings": [...]}
    # 3. Flat list: [...]
    if isinstance(data, dict):
        # Handle Bearer v1.x wrapper format: {"findings": [...], "warnings": [...]}
        if "findings" in data or "warnings" in data:
            flat_items = data.get("findings", []) + data.get("warnings", [])
            data = flat_items  # fall through to list handling below

    if isinstance(data, dict):
        for severity_key, severity_findings in data.items():
            if not isinstance(severity_findings, list):
                continue

            mapped_sev = BEARER_SEVERITY_MAP.get(severity_key.lower(), "MEDIUM")

            for finding in severity_findings:
                filepath = finding.get("full_filename", finding.get("filename", ""))
                cwe_ids = finding.get("cwe_ids", [])
                cwe = ""
                if cwe_ids:
                    # CWE IDs in bearer are bare numbers as strings
                    first_cwe = cwe_ids[0]
                    cwe = f"CWE-{first_cwe}" if not str(first_cwe).startswith("CWE") else str(first_cwe)

                findings.append({
                    "file": make_relative(filepath, model_output_dir),
                    "line": finding.get("line_number", 0),
                    "rule_id": finding.get("id", finding.get("rule_id", "")),
                    "severity": mapped_sev,
                    "confidence": "HIGH",
                    "cwe": cwe,
                    "owasp": extract_owasp_from_path(filepath, model_output_dir),
                    "message": finding.get("title", finding.get("description", "")),
                    "language": extract_language_from_path(filepath, model_output_dir),
                })
    elif isinstance(data, list):
        # Alternate format: flat array of findings
        for finding in data:
            filepath = finding.get("full_filename", finding.get("filename", ""))
            raw_sev = finding.get("severity", "medium").lower()
            mapped_sev = BEARER_SEVERITY_MAP.get(raw_sev, "MEDIUM")

            cwe_ids = finding.get("cwe_ids", [])
            cwe = ""
            if cwe_ids:
                first_cwe = cwe_ids[0]
                cwe = f"CWE-{first_cwe}" if not str(first_cwe).startswith("CWE") else str(first_cwe)

            findings.append({
                "file": make_relative(filepath, model_output_dir),
                "line": finding.get("line_number", 0),
                "rule_id": finding.get("id", finding.get("rule_id", "")),
                "severity": mapped_sev,
                "confidence": "HIGH",
                "cwe": cwe,
                "owasp": extract_owasp_from_path(filepath, model_output_dir),
                "message": finding.get("title", finding.get("description", "")),
                "language": extract_language_from_path(filepath, model_output_dir),
            })

    return findings


def run_codeql(model_id, model_output_dir, logger):
    """
    Run CodeQL analysis and return normalized findings.

    CodeQL requires:
    1. Creating a database per language (python, javascript)
    2. Running analysis on each database
    3. Parsing SARIF output
    """
    binary = TOOL_PATHS["codeql"]

    # Determine which languages have files
    languages = []
    if list(model_output_dir.rglob("*.py")):
        languages.append("python")
    if list(model_output_dir.rglob("*.js")):
        languages.append("javascript")

    if not languages:
        logger.debug(f"[{model_id}] [codeql] no analyzable files found, skipping")
        return []

    all_findings = []
    tmpdir = tempfile.mkdtemp(prefix="codeql_scan_")

    try:
        for lang in languages:
            db_path = Path(tmpdir) / f"db-{lang}"
            sarif_path = Path(tmpdir) / f"results-{lang}.sarif"

            # Step 1: Create database
            create_cmd = [
                binary, "database", "create",
                str(db_path),
                f"--language={lang}",
                f"--source-root={model_output_dir}",
                "--overwrite",
            ]

            logger.debug(
                f"[{model_id}] [codeql] creating {lang} database..."
            )

            try:
                create_result = subprocess.run(
                    create_cmd,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_CODEQL,
                )
            except subprocess.TimeoutExpired:
                logger.error(
                    f"[{model_id}] [codeql] database creation timed out "
                    f"for {lang} after {TIMEOUT_CODEQL}s"
                )
                continue

            if create_result.returncode != 0:
                logger.error(
                    f"[{model_id}] [codeql] database creation failed for {lang} "
                    f"(exit {create_result.returncode}): "
                    f"{create_result.stderr.strip()[:500]}"
                )
                continue

            # Step 2: Analyze database
            analyze_cmd = [
                binary, "database", "analyze",
                str(db_path),
                "--format=sarif-latest",
                f"--output={sarif_path}",
            ]

            logger.debug(
                f"[{model_id}] [codeql] analyzing {lang} database..."
            )

            try:
                analyze_result = subprocess.run(
                    analyze_cmd,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_CODEQL,
                )
            except subprocess.TimeoutExpired:
                logger.error(
                    f"[{model_id}] [codeql] analysis timed out "
                    f"for {lang} after {TIMEOUT_CODEQL}s"
                )
                continue

            if analyze_result.returncode != 0:
                logger.error(
                    f"[{model_id}] [codeql] analysis failed for {lang} "
                    f"(exit {analyze_result.returncode}): "
                    f"{analyze_result.stderr.strip()[:500]}"
                )
                continue

            if not sarif_path.exists():
                logger.warning(
                    f"[{model_id}] [codeql] no SARIF output for {lang}"
                )
                continue

            # Step 3: Parse SARIF
            try:
                with open(sarif_path, "r", encoding="utf-8") as f:
                    sarif = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(
                    f"[{model_id}] [codeql] failed to parse SARIF for {lang}: {e}"
                )
                continue

            # Build a rule_id -> CWE mapping from the tool driver rules
            cwe_map = {}
            for run in sarif.get("runs", []):
                driver = run.get("tool", {}).get("driver", {})
                for rule in driver.get("rules", []):
                    rule_id = rule.get("id", "")
                    tags = rule.get("properties", {}).get("tags", [])
                    for tag in tags:
                        cwe_match = re.search(r"cwe/cwe-(\d+)", tag, re.IGNORECASE)
                        if cwe_match:
                            cwe_map[rule_id] = f"CWE-{cwe_match.group(1)}"
                            break

                # Parse results
                for result in run.get("results", []):
                    rule_id = result.get("ruleId", "")
                    message = result.get("message", {}).get("text", "")
                    level = result.get("level", "warning")
                    severity = SARIF_LEVEL_MAP.get(level, "MEDIUM")

                    # Location — SARIF URIs need special resolution
                    locations = result.get("locations", [])
                    filepath = ""
                    line = 0
                    if locations:
                        phys = locations[0].get("physicalLocation", {})
                        artifact = phys.get("artifactLocation", {})
                        raw_uri = artifact.get("uri", "")
                        filepath = resolve_sarif_uri(raw_uri, model_output_dir)
                        region = phys.get("region", {})
                        line = region.get("startLine", 0)

                    # CWE from our pre-built map
                    cwe = cwe_map.get(rule_id, "")

                    # Also check result-level tags/properties for CWE
                    if not cwe:
                        result_tags = result.get("properties", {}).get("tags", [])
                        for tag in result_tags:
                            cwe_match = re.search(r"cwe/cwe-(\d+)", tag, re.IGNORECASE)
                            if cwe_match:
                                cwe = f"CWE-{cwe_match.group(1)}"
                                break

                    all_findings.append({
                        "file": filepath,
                        "line": line,
                        "rule_id": rule_id,
                        "severity": severity,
                        "confidence": "HIGH",
                        "cwe": cwe,
                        "owasp": extract_owasp_from_path(filepath, model_output_dir),
                        "message": message,
                        "language": lang,
                    })

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return all_findings


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

TOOL_RUNNERS = {
    "bandit": run_bandit,
    "opengrep": run_opengrep,
    "eslint": run_eslint,
    "njsscan": run_njsscan,
    "bearer": run_bearer,
    "codeql": run_codeql,
}

# Map tool names to the binary we need to check for availability
TOOL_BINARY_CHECK = {
    "bandit": "bandit",
    "opengrep": "semgrep",
    "eslint": "eslint",
    "njsscan": "njsscan",
    "bearer": "bearer",
    "codeql": "codeql",
}

# Output filenames for each tool
TOOL_OUTPUT_NAMES = {
    "bandit": "bandit.json",
    "opengrep": "opengrep.json",
    "eslint": "eslint.json",
    "njsscan": "njsscan.json",
    "bearer": "bearer.json",
    "codeql": "codeql.json",
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Run SAST tools on AI-generated code and normalize results."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Scan only this model ID (e.g. gpt-5.2)",
    )
    parser.add_argument(
        "--tool",
        type=str,
        default=None,
        choices=ALL_TOOLS,
        help="Run only this tool",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be scanned without running tools",
    )
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("AI Code Security Study 2026 - SAST Scanning")
    logger.info("=" * 60)

    # Discover models
    model_ids = discover_models()
    if not model_ids:
        logger.error(f"No model directories found in {OUTPUT_DIR}")
        logger.error("Run collect.py first to generate code samples.")
        sys.exit(1)

    # Filter by --model
    if args.model:
        if args.model not in model_ids:
            logger.error(
                f"Model '{args.model}' not found in output/. "
                f"Available: {', '.join(model_ids)}"
            )
            sys.exit(1)
        model_ids = [args.model]

    # Determine tools to run
    tools = ALL_TOOLS
    if args.tool:
        tools = [args.tool]

    # Check tool availability
    available_tools = []
    for tool in tools:
        check_binary = TOOL_BINARY_CHECK[tool]
        if tool_available(check_binary):
            available_tools.append(tool)
        else:
            logger.warning(f"[SKIP] {tool}: binary '{check_binary}' not found")

    if not available_tools:
        logger.error("No tools available. Install at least one SAST tool.")
        sys.exit(1)

    logger.info(f"Models:  {len(model_ids)} ({', '.join(model_ids)})")
    logger.info(f"Tools:   {len(available_tools)} ({', '.join(available_tools)})")
    logger.info(f"Output:  {SCANS_DIR}")

    if args.dry_run:
        logger.info("")
        logger.info("DRY RUN - no tools will be executed")
        logger.info("-" * 60)
        for model_id in model_ids:
            model_dir = OUTPUT_DIR / model_id
            py_count = len(list(model_dir.rglob("*.py")))
            js_count = len(list(model_dir.rglob("*.js")))
            logger.info(
                f"  {model_id}: {py_count} .py files, {js_count} .js files"
            )
            for tool in available_tools:
                out_path = SCANS_DIR / model_id / TOOL_OUTPUT_NAMES[tool]
                status = "EXISTS" if out_path.exists() else "would scan"
                logger.info(f"    {tool}: {status} -> {out_path}")
        logger.info("-" * 60)
        logger.info("Dry run complete. Remove --dry-run to execute.")
        return

    logger.info("-" * 60)

    # Run scans
    total_findings = 0
    total_scans = 0
    error_count = 0

    for model_id in model_ids:
        model_dir = OUTPUT_DIR / model_id
        logger.info(f"--- {model_id} ---")

        for tool in available_tools:
            output_path = SCANS_DIR / model_id / TOOL_OUTPUT_NAMES[tool]

            logger.info(f"[{model_id}] [{tool}] scanning...")
            start_time = time.time()

            try:
                runner = TOOL_RUNNERS[tool]
                findings = runner(model_id, model_dir, logger)
                elapsed = time.time() - start_time

                save_results(tool, model_id, findings, output_path)
                total_findings += len(findings)
                total_scans += 1

                logger.info(
                    f"[{model_id}] [{tool}] done "
                    f"({len(findings)} findings, {elapsed:.1f}s)"
                )

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    f"[{model_id}] [{tool}] ERROR: {e} ({elapsed:.1f}s)"
                )
                error_count += 1

    # Summary
    logger.info("-" * 60)
    logger.info(
        f"Scans: {total_scans} | Findings: {total_findings} | Errors: {error_count}"
    )
    logger.info(f"Results: {SCANS_DIR}")
    logger.info(f"Log: {LOG_PATH}")

    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
