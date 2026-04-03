#!/usr/bin/env python3
"""
Top 100 MCP Server Selection
MCP Server Security Audit 2026

Selects 100 servers from the registry dump based on:
- Popularity (stars, downloads)
- Category diversity
- Transport type diversity
- Official vs community balance
- Known CVE servers (control group)
"""

import json
import re
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent.parent
INPUT = STUDY_DIR / "inventory" / "registry-dump.json"
OUTPUT = STUDY_DIR / "inventory" / "selected-100.json"
CATEGORIES_OUTPUT = STUDY_DIR / "inventory" / "categories.json"

CATEGORY_KEYWORDS = {
    "filesystem": ["filesystem", "file-system", "fs-", "file-server", "file manager", "directory"],
    "database": ["postgres", "mysql", "sqlite", "mongo", "redis", "supabase", "firebase", "prisma", "database", "db-", "-db"],
    "api-integration": ["github", "gitlab", "slack", "notion", "google-drive", "google-maps", "twitter", "discord", "jira", "linear", "stripe", "twilio", "sendgrid", "shopify", "salesforce", "hubspot", "airtable", "trello", "asana", "zapier"],
    "code-execution": ["everything", "eval", "execute", "sandbox", "jupyter", "notebook", "repl", "code-runner"],
    "web-browsing": ["puppeteer", "playwright", "browser", "chrome", "selenium", "scraping", "fetch", "crawl", "web-search"],
    "devtools": ["git-", "docker", "kubernetes", "k8s", "terraform", "aws-", "azure-", "gcp-", "cloudflare", "vercel", "netlify", "github-actions", "ci-cd"],
    "data-processing": ["pandas", "csv", "excel", "json", "xml", "yaml", "data-", "etl", "transform"],
    "ai-ml": ["openai", "anthropic", "huggingface", "ollama", "llm", "embedding", "vector", "rag", "langchain"],
    "system": ["shell", "ssh", "terminal", "command", "process", "os-", "system-"],
}

MUST_INCLUDE = [
    "@modelcontextprotocol/server-filesystem",
    "@modelcontextprotocol/server-everything",
    "@modelcontextprotocol/server-github",
    "@modelcontextprotocol/server-gitlab",
    "@modelcontextprotocol/server-postgres",
    "@modelcontextprotocol/server-slack",
    "@modelcontextprotocol/server-memory",
    "@modelcontextprotocol/server-sequential-thinking",
    "@anthropic/claude-code-mcp",
    "playwright-mcp",
    "github-mcp-server",
    "mcp-remote",
    "context7",
]


def categorize(server):
    name = (server.get("name", "") + " " + server.get("description", "")).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return cat
    return "other"


def main():
    with open(INPUT) as f:
        servers = json.load(f)

    for s in servers:
        s["category"] = categorize(s)

    cat_counts = {}
    for s in servers:
        cat = s["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    print("Category distribution (all servers):")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    with open(CATEGORIES_OUTPUT, "w") as f:
        json.dump(cat_counts, f, indent=2)

    selected = []
    selected_names = set()

    for must in MUST_INCLUDE:
        for s in servers:
            if s["name"] == must or must in s.get("npm_package", "") or must in s.get("github_url", ""):
                if s["name"] not in selected_names:
                    s["selection_reason"] = "must-include"
                    selected.append(s)
                    selected_names.add(s["name"])
                break

    print(f"\nMust-include servers added: {len(selected)}")

    scannable = [s for s in servers if s["name"] not in selected_names and (s.get("npm_package") or s.get("install_command"))]
    not_scannable = [s for s in servers if s["name"] not in selected_names and not s.get("npm_package") and not s.get("install_command")]

    by_stars = sorted(scannable, key=lambda x: x.get("stars", 0), reverse=True)
    by_stars_fallback = sorted(not_scannable, key=lambda x: x.get("stars", 0), reverse=True)

    target_per_cat = 10
    cat_selected = {cat: 0 for cat in CATEGORY_KEYWORDS}
    cat_selected["other"] = 0

    for s in selected:
        cat_selected[s["category"]] = cat_selected.get(s["category"], 0) + 1

    for s in by_stars:
        if len(selected) >= 100:
            break
        cat = s["category"]
        if cat_selected.get(cat, 0) < target_per_cat:
            s["selection_reason"] = f"top-in-{cat}"
            selected.append(s)
            selected_names.add(s["name"])
            cat_selected[cat] = cat_selected.get(cat, 0) + 1

    remaining = 100 - len(selected)
    if remaining > 0:
        for s in by_stars:
            if len(selected) >= 100:
                break
            if s["name"] not in selected_names:
                s["selection_reason"] = "top-scannable-by-stars"
                selected.append(s)
                selected_names.add(s["name"])

    remaining = 100 - len(selected)
    if remaining > 0:
        for s in by_stars_fallback:
            if len(selected) >= 100:
                break
            if s["name"] not in selected_names:
                s["selection_reason"] = "top-by-stars-noscan"
                selected.append(s)
                selected_names.add(s["name"])

    print(f"Total selected: {len(selected)}")
    print("\nSelected by category:")
    sel_cats = {}
    for s in selected:
        cat = s["category"]
        sel_cats[cat] = sel_cats.get(cat, 0) + 1
    for cat, count in sorted(sel_cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    selected_clean = []
    for s in selected:
        selected_clean.append({
            "id": s.get("id", s["name"]),
            "name": s["name"],
            "description": s.get("description", "")[:200],
            "category": s["category"],
            "source": s["source"],
            "url": s.get("url", ""),
            "github_url": s.get("github_url", ""),
            "npm_package": s.get("npm_package", ""),
            "install_command": s.get("install_command", ""),
            "stars": s.get("stars", 0),
            "weekly_downloads": s.get("weekly_downloads", 0),
            "selection_reason": s.get("selection_reason", ""),
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(selected_clean, f, indent=2, ensure_ascii=False)

    print(f"\nOutput: {OUTPUT}")


if __name__ == "__main__":
    main()
