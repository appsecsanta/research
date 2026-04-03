# MCP Server Security Audit 2026

> **33 servers** · 433 tools · 2 scanners · 27 YARA detections · ~80% false positive rate

What does YARA-based pattern matching actually catch when pointed at real MCP (Model Context Protocol) servers? I scanned 33 locally-runnable MCP servers with two open-source scanners and manually reviewed every detection.

[Published Article](https://appsecsanta.com/research/mcp-server-security-audit-2026) · [Back to Catalog](../)

---

## Scanners Used

| Scanner | Version | Approach | License |
|---------|---------|----------|---------|
| [Cisco mcp-scanner](https://github.com/cisco-ai-defense/mcp-scanner) | v4.3.0 | YARA-based pattern matching on tool descriptions and schemas | Apache-2.0 |
| [mcp-scan](https://github.com/invariantlabs-ai/mcp-scan) (Invariant Labs) | v2.0.1 | Config-level issue detection (mutations, shadowing, typosquatting) | Apache-2.0 |

## Key Findings

- **27 YARA detections** across 10 of 33 connected servers — but after review, only **3-5 represent genuine security concerns**
- **~80% false positive rate** — YARA flags standard MCP tool instructions ("You MUST call this function first") as prompt injection
- **8 of 27** detections were "prompt injection" — all triggered by standard MCP tool dependency instructions, not actual injection
- **browser-devtools-mcp** had 9 detections, all for designed functionality (screenshots, JS execution, navigation)
- **Genuine concerns:** desktop-commander credential harvesting, henkey/postgres arbitrary SQL execution, cyanheads/git injection-capable tools
- **mcp-scan** found 116 config-level findings: 96 server mutations, 11 tool-name shadows, 3 exfiltration risks

## Server Categories

| Category | Servers | Detections |
|----------|---------|------------|
| Web-browsing | 5 | 10 |
| Database | 3 | 3 |
| Filesystem | 3 | 1 |
| Code execution | 2 | 2 |
| DevTools | 3 | 0 |
| API integration | 4 | 0 |
| AI/ML | 2 | 0 |
| Data processing | 2 | 0 |
| System | 2 | 1 |
| Other | 7 | 10 |

## Data Pipeline

```
inventory/registry-dump.json        Full MCP registry snapshot
        │
        ▼
  select_top100.py  ──►  inventory/selected-100.json   (filtered server list)
        │
        ▼
     scan.py  ──►  scans/{server}/                     (mcp-scan + cisco results)
        │
        ▼
   scan_v2.py  ──►  scans_v2/{server}/                 (re-scan with updated config)
        │
        ▼
  validate.py  ──►  data/validation.csv                (manual TP/FP classification)
        │
        ▼
  aggregate.py  ──►  data/scan_v2_results.json         (final aggregated dataset)
```

## Directory Structure

```
mcp-server-security-audit-2026/
├── inventory/                      Server selection
│   ├── registry-dump.json          Full MCP registry snapshot (npm, GitHub, official)
│   ├── selected-100.json           Filtered candidate list with metadata
│   └── categories.json             Category definitions
├── scans/                          First-pass scan results (100 servers attempted)
│   └── {server}/
│       ├── cisco_scanner.json      Cisco mcp-scanner YARA results
│       ├── cisco_stderr.log        Scanner runtime logs
│       └── mcp_scan.json           mcp-scan config-level findings
├── scans_v2/                       Second-pass scans (refined config, 96 servers)
│   └── {server}/
│       ├── cisco_scanner.json
│       ├── cisco_stderr.log
│       └── mcp_scan.json
├── data/
│   ├── validation.csv              All findings with manual TP/FP classification
│   ├── runtime_validation.csv      Runtime scan validation results
│   ├── runtime_scan_results.json   Runtime scan aggregated output
│   └── scan_v2_results.json        Final aggregated dataset (33 connected servers)
└── scripts/
    ├── config.json                 Registry URLs, scanner config, categories
    ├── enumerate.py                Scrapes MCP registries (npm, GitHub, official)
    ├── select_top100.py            Filters and ranks servers for scanning
    ├── scan.py                     Runs both scanners against selected servers
    ├── scan_v2.py                  Re-scan with updated scanner versions
    ├── runtime_scan.py             Runtime scanning with live MCP connections
    ├── validate.py                 Generates validation template from scan results
    └── aggregate.py                Merges validated findings into final JSON
```

## Data Files

| File | Description |
|------|-------------|
| `data/scan_v2_results.json` | Final aggregated dataset — 33 connected servers, 433 tools, 27 YARA detections with categories and severity |
| `data/validation.csv` | All findings with manual TP/FP classification and reviewer notes |
| `data/runtime_validation.csv` | Runtime scan validation with connection status per server |
| `data/runtime_scan_results.json` | Full runtime scan output including tool inventories |
| `inventory/selected-100.json` | 100 candidate servers with npm metadata, GitHub stars, categories |
| `inventory/registry-dump.json` | Raw registry snapshot from npm, GitHub, and official MCP registry |
| `scans_v2/{server}/*.json` | Per-server scan results from both scanners (second pass) |

## Reproduce

```bash
# 1. Install scanners
pip3 install mcp-scan
pip3 install mcp-scanner

# 2. Enumerate MCP servers from registries
python3 scripts/enumerate.py

# 3. Select top servers for scanning
python3 scripts/select_top100.py

# 4. Run both scanners against selected servers
python3 scripts/scan_v2.py

# 5. Generate validation template
python3 scripts/validate.py

# 6. (Manual) Review each finding in data/validation.csv — mark as TP or FP

# 7. Aggregate into final dataset
python3 scripts/aggregate.py
```

**Output:** `data/scan_v2_results.json`

## Known Limitations

- **33 connected servers** out of 100 attempted — only servers that run locally without external API keys were included.
- **YARA is pattern matching, not semantic analysis.** It catches "You MUST call this tool" whether it's a standard instruction or adversarial injection.
- **~80% false positive rate** — MCP tool descriptions inherently contain imperative language that overlaps with threat-pattern vocabulary.
- **Small sample size.** Hasan et al. (2025) scanned 1,899 servers with deeper analysis and found 5.5% tool poisoning.
- **mcp-scan server mutations may be benign** — config reloads and non-deterministic descriptions produce the same signal as malicious behavior.
- **Snapshot in time.** Data collected in April 2026 using mcp-scan v2.0.1 and Cisco mcp-scanner v4.3.0.

## License

MIT
