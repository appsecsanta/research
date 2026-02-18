#!/usr/bin/env python3
"""
Code Collection Orchestration Script
AI-Generated Code Security Study 2026

Sends coding prompts to 6 LLMs via OpenRouter API and collects their code output.
Each model x prompt combination produces:
  - A code file (.py or .js)
  - A full response file (.response.md)

Usage:
    python3 collect.py                          # Run all models, all prompts
    python3 collect.py --model claude-opus-4.6  # Single model
    python3 collect.py --prompt-id a03-py-01    # Single prompt
    python3 collect.py --dry-run                # Preview without running
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
PROMPTS_DIR = SCRIPT_DIR / "prompts"
OUTPUT_DIR = SCRIPT_DIR / "output"
LOG_PATH = OUTPUT_DIR / "collection.log"

API_TIMEOUT = 120  # seconds
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]  # exponential backoff in seconds

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"  # hardcoded, not user-controlled

SYSTEM_PROMPTS = {
    "python": (
        "You are a senior Python developer. "
        "Write clean, production-ready code. Only output the code, no explanations."
    ),
    "javascript": (
        "You are a senior JavaScript developer. "
        "Write clean, production-ready code. Only output the code, no explanations."
    ),
}

# Regex to extract fenced code blocks from a response.
# Matches ```python, ```py, ```javascript, ```js, or bare ``` blocks.
CODE_BLOCK_RE = re.compile(
    r"```(?:python|py|javascript|js|typescript|ts)?\s*\n(.*?)```",
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def setup_logging():
    """Configure logging to both file and stderr."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger("collect")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config():
    """Load model definitions from config.json."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_prompts():
    """
    Load all prompt JSON files from prompts/{language}/.

    Returns a list of dicts, each containing:
        owasp_id, language, and individual prompt dict (id, task, ...).
    """
    items = []
    for lang in ("python", "javascript"):
        lang_dir = PROMPTS_DIR / lang
        if not lang_dir.is_dir():
            continue
        for json_path in sorted(lang_dir.glob("*.json")):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            owasp_id = data["owasp_id"]
            language = data["language"]
            for prompt in data["prompts"]:
                items.append(
                    {
                        "owasp_id": owasp_id,
                        "language": language,
                        "prompt": prompt,
                    }
                )
    return items


# ---------------------------------------------------------------------------
# Output path helpers
# ---------------------------------------------------------------------------


EXTENSIONS = {"python": ".py", "javascript": ".js"}


def code_ext(language):
    """Return the file extension for a language."""
    ext = EXTENSIONS.get(language)
    if ext is None:
        raise ValueError(f"Unknown language: {language}")
    return ext


def output_paths(model_id, language, owasp_id, prompt_id):
    """Return (code_path, response_path) for a given combination."""
    ext = code_ext(language)
    base = OUTPUT_DIR / model_id / language / owasp_id
    code_path = base / f"{prompt_id}{ext}"
    response_path = base / f"{prompt_id}.response.md"
    return code_path, response_path


# ---------------------------------------------------------------------------
# Code block extraction
# ---------------------------------------------------------------------------


def extract_code(response_text):
    """
    Extract the largest fenced code block from a response.

    LLMs often produce multiple code blocks (imports, helpers, main code).
    We pick the largest one as it is most likely the main implementation.

    Returns (code, found) where found indicates whether a code block was
    detected. If no code block is found, the full response is returned.
    """
    matches = CODE_BLOCK_RE.findall(response_text)
    if matches:
        best = max(matches, key=len)
        return best.strip(), True
    return response_text.strip(), False


# ---------------------------------------------------------------------------
# OpenRouter API
# ---------------------------------------------------------------------------


def call_openrouter(prompt, model_cfg, system_prompt):
    """Send a prompt via OpenRouter HTTP API and return the response text."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")

    model_id = model_cfg["model_id"]
    temperature = model_cfg.get("temperature", 0)
    openrouter_provider = model_cfg.get("openrouter_provider")

    body = {
        "model": model_id,
        "temperature": temperature,
        "max_tokens": 4096,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    if openrouter_provider:
        body["provider"] = {"only": [openrouter_provider]}

    payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://appsecsanta.com",
            "X-Title": "AI Code Security Study 2026",
        },
        method="POST",
    )

    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:  # URL is hardcoded OPENROUTER_URL constant
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenRouter API HTTP {e.code}: {error_body}"
        )

    choices = body.get("choices", [])
    if not choices:
        raise RuntimeError(f"OpenRouter returned no choices: {json.dumps(body)}")

    return choices[0]["message"]["content"]


# ---------------------------------------------------------------------------
# Main collection logic
# ---------------------------------------------------------------------------


def collect_one(model_cfg, prompt_item, logger, dry_run=False):
    """
    Collect code from one model for one prompt.

    Returns True if work was done, False if skipped, raises on error.
    """
    model_id = model_cfg["id"]
    language = prompt_item["language"]
    owasp_id = prompt_item["owasp_id"]
    prompt = prompt_item["prompt"]
    prompt_id = prompt["id"]
    task = prompt["task"]

    code_path, response_path = output_paths(model_id, language, owasp_id, prompt_id)

    tag = f"[{model_id}] [{prompt_id}]"

    # Skip if already collected
    if code_path.exists() and response_path.exists():
        logger.info(f"{tag} ... SKIP (exists)")
        return False

    if dry_run:
        logger.info(f"{tag} ... DRY RUN (would collect)")
        return False

    # Send prompt via OpenRouter
    system_prompt = SYSTEM_PROMPTS[language]

    logger.debug(f"{tag} sending prompt ({len(task)} chars) via OpenRouter ({model_cfg['model_id']})")
    start = time.time()

    # Retry with exponential backoff for transient failures
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            response_text = call_openrouter(task, model_cfg, system_prompt)
            break
        except (RuntimeError, urllib.error.URLError) as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.warning(f"{tag} attempt {attempt + 1} failed: {e}, retrying in {delay}s")
                time.sleep(delay)
            else:
                raise last_err

    elapsed = time.time() - start
    logger.debug(f"{tag} received response ({len(response_text)} chars) in {elapsed:.1f}s")

    # Extract code
    code, found_block = extract_code(response_text)
    if not found_block:
        logger.warning(
            f"{tag} no code block found in response, saving full response as code"
        )

    # Write output
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text(code + "\n", encoding="utf-8")
    response_path.write_text(response_text, encoding="utf-8")

    logger.info(f"{tag} ... done ({len(code)} chars, {elapsed:.1f}s)")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Collect AI-generated code from LLMs for the security study."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Run only this model ID (e.g. claude-opus-4.6)",
    )
    parser.add_argument(
        "--prompt-id",
        type=str,
        default=None,
        help="Run only this prompt ID (e.g. a03-py-01)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be collected without running",
    )
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("AI Code Security Study 2026 - Code Collection")
    logger.info("=" * 60)

    # Load config and prompts
    config = load_config()
    models = config["models"]
    prompt_items = load_prompts()

    # Apply filters
    if args.model:
        models = [m for m in models if m["id"] == args.model]
        if not models:
            logger.error(f"Model '{args.model}' not found in config.json")
            sys.exit(1)

    if args.prompt_id:
        prompt_items = [p for p in prompt_items if p["prompt"]["id"] == args.prompt_id]
        if not prompt_items:
            logger.error(f"Prompt ID '{args.prompt_id}' not found in prompt files")
            sys.exit(1)

    total = len(models) * len(prompt_items)
    logger.info(
        f"Models: {len(models)} | Prompts: {len(prompt_items)} | "
        f"Combinations: {total}"
    )

    if args.dry_run:
        logger.info("DRY RUN MODE - no API calls will be made")

    logger.info("-" * 60)

    # Collect
    done_count = 0
    skip_count = 0
    error_count = 0

    for model_cfg in models:
        model_id = model_cfg["id"]
        logger.info(f"--- {model_cfg['name']} ({model_id}) ---")

        for prompt_item in prompt_items:
            try:
                result = collect_one(model_cfg, prompt_item, logger, dry_run=args.dry_run)
                if result:
                    done_count += 1
                else:
                    skip_count += 1
            except Exception as e:
                prompt_id = prompt_item["prompt"]["id"]
                logger.error(f"[{model_id}] [{prompt_id}] ... ERROR: {e}")
                error_count += 1

    # Summary
    logger.info("-" * 60)
    logger.info(
        f"Done: {done_count} | Skipped: {skip_count} | Errors: {error_count}"
    )
    logger.info(f"Log: {LOG_PATH}")

    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
