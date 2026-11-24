# Raqib (رقيب) — find scam sites before citizens click them

**SCAMSHIELD AI Hackathon · 42 Abu Dhabi × Abu Dhabi Police**
Challenge: *detecting fraudulent links and websites used in cybercrime and financial fraud, including in search engine results and Maps.*

**Team:** `[TEAM NAME]` — `[MEMBER 1]`, `[MEMBER 2]`, `[MEMBER 3]`, `[MEMBER 4]`

---

## 1. The problem

Most financial-fraud links that reach UAE residents impersonate an organisation people trust: RTA and Salik fines, Emirates Post parcel fees, bank "account restricted" messages, UAE PASS, TAMM. They arrive by SMS, sponsored search ads and fake Google Maps listings with "helpline" numbers. Today they are handled one report at a time, after victims have already paid. One operator usually runs many look-alike sites with the same tooling, so blocking a single URL barely slows them down.

## 2. The solution

Raqib is an investigation platform for police analysts that works **before** the reports arrive:

| Step | What Raqib does |
|---|---|
| **Hunt** | Watches the places scams appear: newly registered domains (live daily feed), Google Search results and sponsored ads, Google Maps listings, and citizen / hotline reports. |
| **Triage** | Cheap checks without opening the site: look-alikes of 36 protected UAE brands (homoglyphs, brand + lure words, brand hidden in a sub-domain), domain age, abused TLDs, Maps listing oddities. |
| **Investigate** | Opens the dangerous ones in an isolated, throwaway browser (mobile, UAE locale): follows every redirect, expands URL shorteners, compares what phones and computers are shown (cloaking), captures a screenshot, the rendered page, forms, scripts and network log. Nothing is typed, submitted or downloaded. |
| **Explain** | 28 deterministic detectors turn the evidence into a risk score (0-100) where every point has a reason, in English and Arabic. Optional Claude Sonnet 5.5 vision check on the screenshot. |
| **Link** | Fingerprints each site (scam-kit file hashes, Telegram-bot / Discord-webhook IDs, crypto wallets, phone / WhatsApp numbers, favicon, analytics IDs, redirectors, registration batch, screenshot similarity) and links it to known campaigns with a graded strength. Looking alike is not proof of the same operator. |
| **Act** | Evidence with SHA-256 chain of custody, PDF case report (English + Arabic), takedown drafts for the registrar, host, Google Safe Browsing and Google Maps, blocklist CSV, JSON case bundle, public warning text. |

### How this maps to the judging criteria

| Criterion | Weight | In Raqib |
|---|---|---|
| Detection accuracy | 30% | Real scanner for any URL; redirect, shortener and cloaking handling; false-positive guard (official brand registry, vetted `.gov.ae` / `.ac.ae` / `.bank` zones, trusted-site list, domain age, "names a brand but collects nothing" rule); **batch evaluator and CLI** that report precision / recall / F1 / confusion matrix on any labelled list (the hidden test set). |
| Early detection & coverage | 25% | Live newly-registered-domain hunt (~70,000 domains a day), Search + sponsored ads + Maps listings (SerpAPI connector, recorded demo feed without a key), citizen reports; triage funnel shown live on a radar. |
| Explainability & actionability | 20% | Every signal has a weight and a plain-language reason; "how the score adds up" waterfall; screenshots, RDAP/WHOIS, hosting, redirect chain and timestamps with SHA-256 hashes; PDF / CSV / JSON exports and takedown drafts. |
| UAE relevance & innovation | 15% | 36 protected UAE brands (banks, RTA, Salik, TAMM, UAE PASS, ICP, MOI, police, couriers, telcos), Arabic lure detection, fully bilingual UI and reports; generative case files composed by Claude Sonnet 5.5; Claude vision brand check; campaign network linking; visual page similarity. |
| Feasibility & presentation | 10% | Working app, CLI and tests; hardened container; pluggable data sources; pilot route below; honest limitations. |

## 3. Technical choices, tools, APIs and data

**Backend** — Python 3.11, FastAPI, Uvicorn. Playwright drives headless Chrome for the sandbox browser. httpx follows redirects and fetches pages (system trust store via `truststore`). ReportLab + arabic-reshaper + python-bidi build the bilingual PDF. Pillow computes screenshot difference-hashes.

**Frontend** — React 19 + TypeScript + Vite, framer-motion for animation, d3-force for the campaign graph, d3-geo + topojson (world-atlas) for the infrastructure map, lucide icons, Inter / IBM Plex Sans Arabic fonts.

**AI** — Anthropic Claude **Sonnet 5.5** (`claude-sonnet-5-5`, configurable with `RAQIB_MODEL`; one model only, no automatic fallback to another model):
* writes the case summary and **chooses the case-file layout** (structured JSON output: which of 14 block types to show, in what order, with what wording) and suggests follow-up questions;
* answers analyst questions with blocks of its own;
* looks at screenshots to spot brand impersonation (vision, structured output);
* optionally drives the live browser agent (`browser_toolset_20260801`) to follow the victim's path, with guardrails enforced in code.
Numbers and verdicts always come from the deterministic pipeline, so the model cannot invent figures. Without a key an offline writer produces the same shapes and the UI says which wrote each case.

**External services / data**

| Source | Used for | Key needed |
|---|---|---|
| [WhoisDS newly registered domains](https://www.whoisds.com/newly-registered-domains) (daily list) | live early detection | no |
| [RDAP](https://rdap.org) | registration date, registrar, name servers, IP owner | no |
| [SerpAPI](https://serpapi.com) Google + Google Maps engines | live Search results, sponsored ads, Maps listings | `SERPAPI_KEY` |
| [OpenPhish](https://openphish.com) community feed | optional live phishing sample for evaluation | no |
| Anthropic Messages API | summaries, generative layout, vision, browser agent | `ANTHROPIC_API_KEY` |

**Bundled data** (`backend/raqib/data/`)
* `registry.json` — 36 protected UAE brands with official domains, English/Arabic names and keywords.
* `trusted_domains.txt` — well-known legitimate sites (UAE government, banks, telecom, media, global platforms).
* `cases/` and `feeds/` — the **fictional** demo dataset (generated by `backend/tools/build_seed.py`): recorded evidence of 18 scam / benign sites on reserved `.test` domains, documentation IP ranges and made-up numbers, plus recorded Search / Maps / certificate / report feeds. It lets the full flow be demonstrated safely and offline.

## 4. Build and run

Prerequisites: Python 3.11, Node 20+, Google Chrome (or `playwright install chromium`).

```powershell
# backend
cd backend
python -m venv .venv            # or: uv venv .venv --python 3.11
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python tools\build_seed.py        # (re)generate the demo dataset

# dashboard
cd ..\frontend
npm install
npm run build

# run: API + dashboard on http://127.0.0.1:8600
cd ..\backend
.venv\Scripts\python -m uvicorn raqib.main:app --port 8600
```

macOS / Linux: use `.venv/bin/...` instead of `.venv\Scripts\...`. During development run `npm run dev` in `frontend/` (port 5173, proxies `/api`).

Optional configuration in a `.env` file at the repository root (see `.env.example`), or the key can be pasted in the app's Settings:

```
ANTHROPIC_API_KEY=sk-ant-...     # Claude Sonnet 5.5 features
RAQIB_MODEL=claude-sonnet-5-5
SERPAPI_KEY=...                  # live Google Search / ads / Maps
RAQIB_MODE=live                  # let the Claude browser agent drive unknown URLs
RAQIB_BROWSER_CHANNEL=chrome     # use installed Chrome if Playwright's Chromium is not installed
```

### Scan a URL list (e.g. the hidden test set)

```powershell
cd backend
.venv\Scripts\python -m raqib.cli urls.txt --out results.csv            # one URL per line
.venv\Scripts\python -m raqib.cli test.csv --out results.csv --json results.json   # CSV with url,label → precision / recall / F1
.venv\Scripts\python -m raqib.cli urls.txt --no-browser                 # faster HTTP-only mode
```

A URL is labelled `fraud` when its score is 60 or more (`--threshold` to change). The same evaluation runs in the dashboard under **Evaluate**.

### Run in a hardened container

```powershell
docker compose -f docker/docker-compose.yml up --build
```

Loopback-only port, no host folders mounted, all Linux capabilities dropped, read-only root filesystem, memory / CPU / process caps. Use this when investigating real scam URLs.

### Tests

```powershell
cd backend
.venv\Scripts\python -m pytest
```

18 tests: detectors on every recorded case, false-positive rules (news articles mentioning a brand, old domains, trusted and vetted zones), URL tricks (shortener, IP host, punycode, `@`, brand in sub-domain, free hosting), the HTML fallback, cloaking, campaign linking ("copied layout ≠ same operator"), triage, batch metrics, and the live browser executor against a local page with a scripted stand-in for Claude (proves the agent can never type into card / OTP / password fields).

## 5. Using the dashboard

* **Command** — hunt radar and detection funnel, live newly-registered-domain hunt, active campaigns, UAE map of targeted emirates, world map of hosting infrastructure.
* **Cases** — every investigation, newest first. Paste any URL in the top bar to investigate it: the isolated browser opens it live, the agent crew (browser agent, detectors, campaign linker, case writer) and the activity log show every action, the score climbs as signals are found.
* **Case file** — generative layout chosen per case; ask follow-up questions.
* **Campaign** — graph of linked sites with the reason for every link.
* **Report pack** — PDF, CSV, JSON, takedown drafts, public warning.
* **Evaluate** — batch scan and accuracy metrics.
* **Brands** — the protected-entity registry and a domain checker.

## 6. Route to a police pilot

1. **Pilot (4 weeks)** — run on Abu Dhabi Police infrastructure in the container; ingest citizen SMS reports and the new-domain feed; analysts review every flag; measure precision on real cases.
2. **Expand** — Search / Maps feeds, takedown workflow with registrars, hosts and Google, shared blocklist with TDRA and ISPs, legal-request templates for telecoms, exchanges and messaging platforms.
3. **Scale** — horizontally scaled scan workers behind a queue, national rollout, accuracy reported on every release.

## 7. Honest limitations

* The demo dataset is fictional and recorded for safety. Real URLs are scanned live by the scanner; the bundled evaluation sample mixes recorded demo cases with real UAE sites, so its 100% score demonstrates the pipeline and the false-positive guard, not real-world recall. Run the CLI on a fresh phishing feed for that.
* Live Search / Maps data needs a SerpAPI key; without it the recorded feed is used. The new-domain hunt is live.
* Hosting country is an infrastructure indicator, never the location of the people behind a scam.
* Pages that only show the scam after interaction (a button, a form step) are best covered by the Claude browser agent in live mode, which has been exercised against a local test page with a scripted model but not yet against the real API.
* Raqib is decision support: officers review every flag, and nothing is sent automatically.

## 8. Repository layout

```
backend/raqib/   scanner.py (real URL scanner) · detectors.py (signals + score) · campaign.py (linking) · hunters.py / hunters_live.py (discovery)
                 batch.py + cli.py (evaluation) · investigations.py (orchestration) · live.py (Claude browser agent) · claude_service.py + ui_spec.py (generative UI)
                 report.py (PDF / takedowns) · main.py (API)
backend/tests/   pytest suite          backend/tools/   build_seed.py (fictional demo data)
frontend/src/    views/ (Command, Investigation, Cases, Evaluate, Campaigns, Brands) · components/ (browser, graph, maps, blocks, crew)
docs/deck/       pitch deck and the script that builds it          docker/   hardened runtime
```
