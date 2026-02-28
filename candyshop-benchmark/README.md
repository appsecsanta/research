# CandyShop Benchmark

Open-source security tool benchmark that compares 11 scanning tools against 6 intentionally vulnerable applications. All tools are open-source with permissive licenses suitable for benchmarking.

**Full results:** [appsecsanta.com/research/candyshop-devsecops](https://appsecsanta.com/research/candyshop-devsecops)

## Quick Start

```bash
# 1. Clone and enter
git clone https://github.com/appsecsanta/research.git
cd research/candyshop-benchmark

# 2. Clone target source code (for SAST/SCA)
mkdir -p sources && cd sources
git clone --depth 1 https://github.com/juice-shop/juice-shop.git
git clone --depth 1 https://github.com/NeuraLegion/brokencrystals.git
git clone --depth 1 https://github.com/HCL-TECH-SOFTWARE/AltoroJ.git altoro-mutual
git clone --depth 1 https://github.com/Contrast-Security-OSS/vulnpy.git
git clone --depth 1 https://github.com/digininja/DVWA.git dvwa
git clone --depth 1 https://github.com/WebGoat/WebGoat.git webgoat
cd ..

# 3. Start vulnerable apps
docker compose up -d

# 4. Run all scans (~30-60 min)
bash scripts/run-all.sh

# 5. Normalize + triage + F-measure
python3 scripts/normalize-results.py results/$(date +%Y-%m-%d) > results/normalized-all.csv
python3 scripts/triage-consensus.py results/normalized-all.csv ground-truth/ triage/
python3 scripts/calculate-fmeasure.py triage/ ground-truth/ metrics/
```

## Target Applications

| App | Language | Port | Description |
|-----|----------|------|-------------|
| [Juice Shop](https://github.com/juice-shop/juice-shop) | Node.js | 3000 | OWASP flagship, 100+ challenges |
| [Broken Crystals](https://github.com/NeuraLegion/brokencrystals) | Node.js/TS | 3001 | 22+ vulnerability types |
| [Altoro Mutual](https://github.com/HCL-TECH-SOFTWARE/AltoroJ) | Java/J2EE | 8080 | Enterprise banking app |
| [vulnpy](https://github.com/Contrast-Security-OSS/vulnpy) | Python/Flask | 5050 | 13 vulnerability categories |
| [DVWA](https://github.com/digininja/DVWA) | PHP | 8081 | Classic web vulnerabilities |
| [WebGoat](https://github.com/WebGoat/WebGoat) | Java/Spring | 8082 | OWASP teaching platform |

## Scanning Tools

| Category | Tools |
|----------|-------|
| **SAST** | Bearer, NodeJsScan, Bandit |
| **DAST** | OWASP ZAP, Nuclei |
| **SCA** | npm audit, pip-audit, OWASP Dependency-Check |
| **Container** | Trivy, Grype |
| **IaC** | Checkov |

All tools are open-source with licenses that permit benchmarking (Apache 2.0, MIT, ELv2, or similar).

## Results (2026-02-28)

- **7,819** total findings across all tools and targets
- **503** confirmed true positives via multi-tool consensus
- **152** ground-truth entries across 6 targets

### F-Measure Scorecard

| Tool | Avg F1 | Precision | Recall | TP | CWEs Found |
|------|--------|-----------|--------|-----|-----------|
| Trivy | 0.683 | 1.000 | 0.554 | 217 | 25 |
| Bearer | 0.626 | 1.000 | 0.490 | 175 | 17 |
| Bandit | 0.454 | 1.000 | 0.294 | 5 | 4 |
| Dep-Check | 0.400 | 1.000 | 0.263 | 27 | 10 |
| npm audit | 0.383 | 1.000 | 0.237 | 18 | 10 |
| ZAP | 0.235 | 1.000 | 0.150 | 18 | 6 |

## Directory Structure

```
candyshop-benchmark/
├── docker-compose.yml          # 6 vulnerable apps + databases
├── targets/                    # Custom Dockerfiles (Altoro Mutual, vulnpy)
├── scripts/
│   ├── run-all.sh              # Orchestrator
│   ├── scan-container.sh       # Trivy + Grype
│   ├── scan-sast.sh            # Bearer + NodeJsScan + Bandit
│   ├── scan-sca.sh             # npm audit + pip-audit + Dep-Check
│   ├── scan-dast.sh            # ZAP + Nuclei
│   ├── scan-iac.sh             # Checkov
│   ├── normalize-results.py    # Unified CSV from 11 tool formats
│   ├── triage-consensus.py     # Multi-tool consensus engine
│   └── calculate-fmeasure.py   # Precision/Recall/F1 calculator
├── ground-truth/               # Known vulnerabilities per target (CSV)
├── results/                    # Raw scan output (JSON)
├── triage/                     # Classified findings (TP/FP/pending)
├── metrics/                    # F-measure, CWE coverage, scorecard
└── methodology-commits.txt     # Source repo commit hashes scanned
```

## Methodology

1. **Target setup**: Docker Compose runs all 6 apps with healthchecks
2. **Scanning**: Each tool scans applicable targets (SAST needs source, DAST needs running apps)
3. **Normalization**: All tool outputs converted to unified CSV format
4. **Triage**: Multi-tool consensus — findings detected by 2+ tools are auto-confirmed as TP
5. **F-Measure**: Precision = TP/(TP+FP), Recall = TP/(TP+FN), F1 = harmonic mean

Ground truth is built from application documentation + multi-tool consensus + validation.

## License

Data and scripts: [MIT](../LICENSE)

Tool selection excludes products with anti-benchmarking clauses (e.g., Snyk ToS Section 2.2, SonarQube AUP).
