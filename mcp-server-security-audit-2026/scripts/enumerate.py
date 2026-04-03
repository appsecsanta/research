#!/usr/bin/env python3
"""
MCP Server Enumeration Script
MCP Server Security Audit 2026

Discovers MCP servers from multiple registries and produces a unified
inventory for downstream selection and scanning.

Sources:
    1. Official MCP Registry (registry.modelcontextprotocol.io)
    2. npm registry (@modelcontextprotocol scope + keyword search)
    3. GitHub topic search (mcp-server)

Usage:
    python3 enumerate.py                          # All sources
    python3 enumerate.py --source official        # One source only
    python3 enumerate.py --output inventory.json  # Custom output
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_DIR = SCRIPT_DIR.parent
DEFAULT_OUTPUT = STUDY_DIR / "inventory" / "registry-dump.json"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS_JSON = {"Accept": "application/json", "User-Agent": "AppSecSanta-MCP-Audit/1.0"}


def fetch_json(url, headers=None, retries=3, delay=1.0):
    hdrs = dict(HEADERS_JSON)
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                print(f"  WARN: Failed to fetch {url}: {e}", file=sys.stderr)
                return None


def enumerate_official_registry():
    print("=== Official MCP Registry ===")
    servers = []
    offset = 0
    page_size = 100
    base = "https://registry.modelcontextprotocol.io/v0.1/servers"

    while True:
        url = f"{base}?limit={page_size}&offset={offset}"
        data = fetch_json(url)
        if not data:
            break

        batch = data.get("servers", data) if isinstance(data, dict) else data
        if not batch or not isinstance(batch, list):
            break

        for srv in batch:
            servers.append({
                "id": srv.get("id", srv.get("name", "")),
                "name": srv.get("name", srv.get("displayName", "")),
                "description": srv.get("description", "")[:200],
                "source": "official-registry",
                "url": srv.get("url", srv.get("homepage", "")),
                "github_url": srv.get("repository", srv.get("sourceUrl", "")),
                "npm_package": srv.get("package", {}).get("name", "") if isinstance(srv.get("package"), dict) else "",
                "install_command": "",
                "stars": 0,
                "weekly_downloads": 0,
            })

        print(f"  Fetched {len(batch)} servers (total: {len(servers)})")
        if len(batch) < page_size:
            break
        offset += page_size
        time.sleep(0.5)

    print(f"  Total from official registry: {len(servers)}")
    return servers


def enumerate_npm():
    print("=== npm Registry ===")
    servers = []
    search_terms = ["mcp-server", "@modelcontextprotocol"]

    for term in search_terms:
        offset = 0
        page_size = 250
        while offset < 1000:
            url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote(term)}&size={page_size}&from={offset}"
            data = fetch_json(url)
            if not data:
                break

            objects = data.get("objects", [])
            if not objects:
                break

            for obj in objects:
                pkg = obj.get("package", {})
                name = pkg.get("name", "")
                if not name:
                    continue

                servers.append({
                    "id": name,
                    "name": name,
                    "description": pkg.get("description", "")[:200],
                    "source": "npm",
                    "url": pkg.get("links", {}).get("homepage", ""),
                    "github_url": pkg.get("links", {}).get("repository", ""),
                    "npm_package": name,
                    "install_command": f"npx {name}",
                    "stars": 0,
                    "weekly_downloads": obj.get("score", {}).get("detail", {}).get("popularity", 0),
                })

            print(f"  [{term}] Fetched {len(objects)} packages (offset: {offset})")
            if len(objects) < page_size:
                break
            offset += page_size
            time.sleep(0.5)

    print(f"  Total from npm: {len(servers)}")
    return servers


def enumerate_github():
    print("=== GitHub Topic Search ===")
    servers = []
    headers = dict(HEADERS_JSON)
    headers["Accept"] = "application/vnd.github.v3+json"
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    queries = ["topic:mcp-server", "mcp server in:name,description language:TypeScript", "mcp server in:name,description language:Python"]

    for query in queries:
        page = 1
        while page <= 5:
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page=100&page={page}"
            data = fetch_json(url, headers=headers)
            if not data:
                break

            items = data.get("items", [])
            if not items:
                break

            for repo in items:
                full_name = repo.get("full_name", "")
                servers.append({
                    "id": full_name,
                    "name": repo.get("name", ""),
                    "description": (repo.get("description") or "")[:200],
                    "source": "github",
                    "url": repo.get("homepage", "") or "",
                    "github_url": repo.get("html_url", ""),
                    "npm_package": "",
                    "install_command": "",
                    "stars": repo.get("stargazers_count", 0),
                    "weekly_downloads": 0,
                })

            print(f"  [{query[:30]}...] Page {page}: {len(items)} repos")
            if len(items) < 100:
                break
            page += 1
            time.sleep(1.0)

    print(f"  Total from GitHub: {len(servers)}")
    return servers


def deduplicate(servers):
    seen = {}
    for srv in servers:
        key = srv["name"].lower().strip().replace("@", "").replace("/", "-")
        if key not in seen:
            seen[key] = srv
        else:
            existing = seen[key]
            if srv["stars"] > existing["stars"]:
                existing["stars"] = srv["stars"]
            if srv["github_url"] and not existing["github_url"]:
                existing["github_url"] = srv["github_url"]
            if srv["npm_package"] and not existing["npm_package"]:
                existing["npm_package"] = srv["npm_package"]
            if srv["weekly_downloads"] > existing["weekly_downloads"]:
                existing["weekly_downloads"] = srv["weekly_downloads"]
            if not existing["description"] and srv["description"]:
                existing["description"] = srv["description"]

    deduped = sorted(seen.values(), key=lambda s: s["stars"], reverse=True)
    return deduped


def main():
    parser = argparse.ArgumentParser(description="Enumerate MCP servers from registries.")
    parser.add_argument("--source", choices=["official", "npm", "github", "all"], default="all")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    print("MCP Server Enumeration")
    print("=" * 50)

    all_servers = []

    if args.source in ("all", "official"):
        all_servers.extend(enumerate_official_registry())
    if args.source in ("all", "npm"):
        all_servers.extend(enumerate_npm())
    if args.source in ("all", "github"):
        all_servers.extend(enumerate_github())

    print(f"\nTotal raw: {len(all_servers)}")

    deduped = deduplicate(all_servers)
    print(f"After dedup: {len(deduped)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    print(f"Output: {args.output}")

    source_counts = {}
    for s in deduped:
        src = s["source"]
        source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in sorted(source_counts.items()):
        print(f"  {src}: {count}")


if __name__ == "__main__":
    main()
