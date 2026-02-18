# AI-Generated Code Security Study 2026

> **6 LLMs** · 89 prompts · 534 code samples · 6 SAST tools · 1,173 findings triaged

How secure is code written by the leading AI models? We prompted each model with real-world coding tasks mapped to the OWASP Top 10, then scanned every output with multiple open-source SAST tools and manually validated the results.

[Published Article](https://appsecsanta.com/research/ai-code-security-study-2026) · [Back to Catalog](../)

---

## Models Tested

| Model | Provider |
|-------|----------|
| GPT-5.2 | OpenAI |
| Claude Opus 4.6 | Anthropic |
| Gemini 2.5 Pro | Google |
| DeepSeek V3 | DeepSeek |
| Llama 4 Maverick | Meta |
| Grok 4 | xAI |

## SAST Tools Used

| Tool | License |
|------|---------|
| [Bandit](https://github.com/PyCQA/bandit) | Apache-2.0 |
| [CodeQL](https://github.com/github/codeql) | Free for open-source |
| [ESLint + eslint-plugin-security](https://github.com/eslint-community/eslint-plugin-security) | MIT / Apache-2.0 |
| [njsscan](https://github.com/ajinabraham/njsscan) | LGPL-3.0 |
| [OpenGrep](https://github.com/opengrep/opengrep) | LGPL-2.1 |
| [Bearer CLI](https://github.com/Bearer/bearer) | Elastic License 2.0 |

## Key Findings

- **24.5% average vulnerability rate** — roughly 1 in 4 AI-generated code samples contained at least one confirmed vulnerability
- **GPT-5.2 scored best** at 19.1% vulnerability rate; **DeepSeek V3 and Llama 4 Maverick tied worst** at 29.2%
- **SSRF (CWE-918)** was the most common weakness, followed by injection flaws (CWE-502, CWE-943)
- **85% of raw SAST findings were false positives** — manual triage matters
- **78% of confirmed vulnerabilities were flagged by only one tool** — no single scanner catches everything

## Data Pipeline

```
prompts/{python,javascript}/*.json
        │
        ▼
   collect.py  ──►  output/{model}/{language}/{A01-A10}/*.py|*.js
                                    │
                                    ▼
                  scan.py  ──►  scans/{model}/{tool}.json
                                    │
                                    ▼
               validate.py  ──►  data/validation.csv  (manual triage)
                                    │
                                    ▼
              aggregate.py  ──►  data/ai_code_study_2026.json
```

## Directory Structure

```
ai-code-security-study-2026/
├── prompts/                   Coding prompts (10 OWASP categories × 2 languages)
│   ├── python/                Python/Flask prompts (10 JSON files)
│   └── javascript/            JavaScript/Express prompts (10 JSON files)
├── output/                    AI-generated code samples (534 total)
│   ├── gpt-5.2/
│   ├── claude-opus-4.6/
│   ├── gemini-2.5-pro/
│   ├── deepseek-v3/
│   ├── llama-4-maverick/
│   └── grok-4/
│       └── {python,javascript}/{A01-A10}/*.{py,js,response.md}
├── scans/                     SAST scan results (JSON per tool per model)
│   └── {model}/{bandit,bearer,codeql,eslint,njsscan,opengrep}.json
├── data/
│   ├── validation.csv         1,173 findings with manual TP/FP classification
│   └── ai_code_study_2026.json  Final aggregated dataset
└── scripts/
    ├── config.json            Model configuration (IDs, providers)
    ├── collect.py             Sends prompts to LLMs via OpenRouter API
    ├── scan.py                Runs all 6 SAST tools against collected code
    ├── validate.py            Generates validation template from scan results
    └── aggregate.py           Merges validated findings into final JSON
```

## Data Files

| File | Description |
|------|-------------|
| `data/ai_code_study_2026.json` | Final aggregated dataset — per-model vulnerability rates, OWASP/CWE breakdowns, tool agreement stats |
| `data/validation.csv` | All 1,173 SAST findings with manual TP/FP classification and reviewer notes |
| `prompts/**/*.json` | 20 prompt files (10 OWASP categories × 2 languages) with task descriptions |
| `output/**/*` | 534 code samples plus full LLM responses |
| `scans/**/*.json` | Raw SAST tool output for each model (36 JSON files) |

## Reproduce

```bash
# 1. Install SAST tools
pip3 install bandit opengrep njsscan
npm install -g eslint eslint-plugin-security

# 2. Collect code from LLMs (requires OpenRouter API key)
export OPENROUTER_API_KEY=sk-or-...
python3 scripts/collect.py

# 3. Run SAST scans across all models
python3 scripts/scan.py

# 4. Generate validation template
python3 scripts/validate.py

# 5. (Manual) Review each finding in data/validation.csv — mark as TP or FP

# 6. Aggregate into final dataset
python3 scripts/aggregate.py
```

**Output:** `data/ai_code_study_2026.json`

## Known Limitations

- All models were tested at temperature 0 for reproducibility. Higher temperatures may produce different vulnerability rates.
- Prompts simulate common web development tasks but don't cover every possible coding scenario.
- SAST tools have inherent blind spots — the true vulnerability rate may differ from what static analysis catches.
- Bearer results are included in raw scans but excluded from the final dataset due to excessive noise on generated snippets.
- This is a point-in-time snapshot from February 2026. Model behavior changes with updates.

## License

MIT
