<p align="center">
  <a href="https://appsecsanta.com">
    <img src=".github/logo.png" width="200" alt="AppSec Santa" />
  </a>
</p>

<h1 align="center">AppSec Santa Research</h1>

<p align="center">
  Open datasets, collection scripts, and methodology behind our published research.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License" /></a>
  <a href="https://github.com/appsecsanta/research/stargazers"><img src="https://img.shields.io/github/stars/appsecsanta/research?style=for-the-badge&logo=github" alt="GitHub Stars" /></a>
  <a href="https://appsecsanta.com/research"><img src="https://img.shields.io/badge/Published_at-AppSec_Santa-c41926?style=for-the-badge" alt="AppSec Santa" /></a>
</p>

<p align="center">
  <a href="https://appsecsanta.com">Website</a> ·
  <a href="https://appsecsanta.com/research">All Research</a> ·
  <a href="https://github.com/appsecsanta/security-tools">Security Tools</a> ·
  <a href="#license">License</a>
</p>

---

## About

[AppSec Santa](https://appsecsanta.com) is an independent review and comparison platform covering **129+ application security tools** across 10 categories including SAST, SCA, DAST, IaC Security, and more.

This repository contains everything needed to **verify, reproduce, or build upon** our published research — raw datasets, collection scripts, and aggregation code.

---

## Studies

<br />

### AI-Generated Code Security Study 2026

> **6 LLMs** · 89 prompts · 534 code samples · 6 SAST tools · 1,173 findings triaged

```
GPT-5.2 · Claude Opus 4.6 · Gemini 2.5 Pro · DeepSeek V3 · Llama 4 Maverick · Grok 4
```

[Documentation](./ai-code-security-study-2026) · [Published Article](https://appsecsanta.com/research/ai-code-security-study-2026)

<br />

### State of Open-Source AppSec Tools 2026

> **65 tools** · 5 health dimensions · GitHub + npm + PyPI + Docker Hub data

```
Recency · Activity · Releases · Community · Responsiveness
```

[Documentation](./oss-tools-study-2026) · [Published Article](https://appsecsanta.com/research/state-of-open-source-appsec-tools-2026)

<br />

### Security Headers Adoption 2026

> **10,000 websites** · Mozilla Observatory scoring · A+ to F grading

```
CSP · HSTS · X-Frame-Options · Referrer-Policy · X-Content-Type-Options · Redirection · X-XSS-Protection
```

[Documentation](./security-headers-study-2026) · [Published Article](https://appsecsanta.com/research/security-headers-study-2026)

<br />

---

## How It Works

Each study follows a three-stage pipeline — collect raw data from public sources, aggregate into scored datasets, and publish findings with full reproducibility.

```
                         ┌─────────────────────────────────────────────┐
                         │           Data Collection                   │
                         │                                             │
  Source APIs ──────────►│  GitHub API · npm · PyPI · Docker Hub       │
  LLM APIs ────────────►│  OpenRouter · SAST tool scans               │
  Target sites ────────►│  HTTP HEAD requests · DNS queries            │
                         │                                             │
                         └──────────────────┬──────────────────────────┘
                                            │
                                            ▼
                         ┌─────────────────────────────────────────────┐
                         │           Aggregation & Scoring             │
                         │                                             │
                         │  Merge datasets · Compute health scores     │
                         │  Validate findings · Generate distributions │
                         │                                             │
                         └──────────────────┬──────────────────────────┘
                                            │
                                            ▼
                         ┌─────────────────────────────────────────────┐
                         │           Output                            │
                         │                                             │
                         │  Final JSON dataset · Published article     │
                         │                                             │
                         └─────────────────────────────────────────────┘
```

---

## Requirements

- Python 3.10+
- Node.js 18+

Study-specific dependencies are listed in each study's README.

---

## Related

Looking for the security scanning tools used in our research? Check out [**appsecsanta/security-tools**](https://github.com/appsecsanta/security-tools) — 4 open-source security scanners (HTTP headers, DNS, SSL/TLS, subdomains) you can self-host on Cloudflare Workers.

---

## Contributing

Found an issue with our data or methodology? [Open an issue](https://github.com/appsecsanta/research/issues) and we'll look into it.

## License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  Built by <a href="https://appsecsanta.com">AppSec Santa</a> — curated application security tools comparison.
</p>
