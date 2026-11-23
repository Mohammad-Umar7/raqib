# Raqib (رقيب)

**Proactive scam hunting for police.** Raqib finds scam websites in Google Search, Google Maps and newly issued certificates before citizens click them, investigates each one in an isolated browser, links sites into campaigns, and hands officers the evidence and the takedown requests.

> Built for the Abu Dhabi Police × 42 Abu Dhabi "ScamShield AI" hackathon challenge: *detecting fraudulent links and websites used in cybercrime and financial fraud, including in search results and Maps.*

## What it does

1. **Hunt** – four discovery sources feed one triage funnel: search results and sponsored ads, Google Maps listings, new TLS certificates, and citizen reports. Triage is cheap (no browser): domain look-alikes of 26 protected UAE brands, scam-theme words, risky Maps categories, certificate age.
2. **Investigate** – only the suspicious ones are opened in an isolated, throwaway Chromium (mobile profile, UAE locale). A Claude browser agent follows the victim's path. The dashboard shows the browser, the agent's narration and the network log live.
3. **Explain** – deterministic detectors turn the recorded evidence into an explainable score: impersonation, payment/credential harvesting, data-theft channels (Telegram bot, Discord webhook), fraud patterns (guaranteed returns, upfront fees, crypto wallets, pressure tactics) and infrastructure age. Every signal has a weight and a reason, in English and Arabic.
4. **Link** – every site gets a fingerprint (kit file hashes, bot IDs, wallets, phone/WhatsApp numbers, favicon, layout). Links carry a strength: *strong* (shared operator tooling or contact details), *medium*, *weak* (look-alike only). Two operators copying the same brand are not merged.
5. **Act** – case file, PDF report (English + Arabic) with SHA-256 chain of custody, takedown drafts (registrar, host, Safe Browsing, Maps), blocklist CSV and a public warning.

The case view is **generative UI**: Claude chooses which of 13 block types to show, in what order and with what wording (structured JSON): verdict, key figures, the victim's journey step by step, why the score, how the score adds up (waterfall), campaign links, shareable indicators, infrastructure, targets, evidence and actions. The dashboard renders them from a block registry, shows the chosen layout as a strip, suggests follow-up questions, and the "Ask Raqib" box answers with blocks of its own. Figures always come from the deterministic pipeline, so the model cannot invent numbers.

The dashboard is built for a live demo: a hunt radar with a sweeping scan, a funnel that fills as candidates stream in, an isolated-browser view with an animated agent cursor, flagged fields and floating score chips, a gauge that climbs with every signal, and a campaign graph that grows outward from the investigated site.

## Quick start (Windows PowerShell)

```powershell
# backend
cd backend
uv venv .venv --python 3.11
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python.exe tools\build_seed.py      # regenerates the demo cases and feeds

# dashboard
cd ..\frontend
npm install
npm run build

# run (serves the API and the built dashboard)
cd ..\backend
.venv\Scripts\python.exe -m uvicorn raqib.main:app --port 8600
```

Open <http://127.0.0.1:8600>. During development run `npm run dev` in `frontend/` (port 5173, proxies `/api`).

### Modes

| Mode | What runs | Needs |
|---|---|---|
| **Replay** (default) | Recorded evidence of 18 fictional demo sites is "browsed" step by step. Detectors, scoring, fingerprints, linking and reports run for real on it. | nothing |
| **Live** | An isolated Chromium driven by Claude's browser-use tool, on any URL. | `ANTHROPIC_API_KEY`, `RAQIB_MODE=live`, Chrome/Chromium |
| **Triage only** | Unknown URL with live mode off: domain check only. | nothing |

Claude without a key: summaries, layout and Q&A fall back to an offline writer, and the UI says which one wrote each case.

Add the key in **Settings** (stored in a git-ignored `.env`) or copy `.env.example` to `.env`.

### Run live mode in a hardened container

```powershell
docker compose -f docker/docker-compose.yml up --build
```

Loopback-only port, no host mounts, all capabilities dropped, read-only filesystem, memory and CPU caps.

## Safety by design

- The browser agent can **never** type into card, CVV, OTP, password, ID or login fields (enforced in `raqib/live.py`, not in the prompt), and Raqib never submits data to a scam site.
- Only `http`/`https`; private, loopback and link-local addresses blocked; downloads, uploads, JavaScript execution and extra tabs disabled; fresh context per run.
- Page text is untrusted: the verdict comes from recorded evidence, never from what the agent concludes. Claude receives page-derived data only inside a JSON case file with instructions to ignore any commands in it.
- Hosting country is shown as an *infrastructure indicator* only, never as the operator's location.
- Raqib sends nothing by itself: takedowns and warnings are drafts for an officer.

## Layout

```
backend/raqib/   detectors.py scoring · campaign.py linking · hunters.py triage · live.py browser agent
                 claude_service.py + ui_spec.py generative UI · report.py PDF/takedowns · investigations.py orchestration
backend/tools/   build_seed.py (fictional demo data)       backend/tests/  pytest suite
frontend/src/    views/ (Command, Investigation, Campaigns, Brands) · components/ (Browser, Graph, Blocks, Maps)
docker/          hardened runtime
```

## Tests

```powershell
cd backend ; .venv\Scripts\python.exe -m pytest
```

Covers the detectors on every recorded case, campaign linking (including "copied layout is not the same operator"), triage, URL policy, and the live executor against a local page with a scripted stand-in for Claude, proving the typing guardrail.

## Honest limits

- The demo data is fictional: invented `.test` domains, documentation IP ranges, made-up numbers. The feeds are recorded datasets; production would use SERP/Maps APIs and a CT-log stream.
- The live browser agent has been exercised against a local page with a scripted model. It has **not** yet been run against the real Claude API or real scam sites from this repo.
- The protected-brand registry lists official domains from public knowledge; verify them with each organisation before operational use.
- A look-alike detector and a risk score support officers; they do not replace review.
