# Raqib accuracy run · 289 s · threshold 60

Scanned inside the locked-down sandbox VM (no API key, deterministic rules only, no Claude).

## Headline (OpenPhish phishing vs. Tranco sites that are not on Raqib's allowlist)

| | Predicted scam | Predicted legit |
|---|---|---|
| **Phishing** | 3 (TP) | 37 (FN) |
| **Legit** | 0 (FP) | 40 (TN) |

| Metric | Value |
|---|---|
| Precision | 100% (3/3, 95% CI 44%–100%) |
| Recall (detection rate) | 8% (3/40, 95% CI 3%–20%) |
| F1 | 14% |
| Accuracy | 54% (43/80, 95% CI 43%–64%) |
| False-positive rate | 0% (0/40, 95% CI 0%–9%) |
| Official UAE sites wrongly flagged (allowlist guard) | 0% (0/20, 95% CI 0%–16%) |
| Median time per URL | 10.9 s |

## Threshold sweep (same scans, no re-run)

| Score ≥ | Precision | Recall | False-positive rate |
|---|---|---|---|
| 40 | 50% | 8% | 8% |
| 50 | 60% | 8% | 5% |
| 60 | 100% | 8% | 0% |
| 70 | 100% | 8% | 0% |
| 80 | – | 0% | 0% |

## Where it misses

| Slice | Recall |
|---|---|
| Phishing page still online when scanned | 8% (3/37, 95% CI 3%–21%) |
| Phishing link already dead | 0% (0/3, 95% CI 0%–56%) |
| Mentions a UAE brand or uses .ae | 100% (1/1, 95% CI 21%–100%) |
| Global brands (Microsoft, banks abroad, ...) | 5% (2/39, 95% CI 1%–17%) |

Legit sites that actually loaded: 31 of 40; false-positive rate among them: 0% (0/31, 95% CI 0%–11%).

## Every mistake (for review)

| Kind | URL (defanged) | Score | Page | Top reasons | Screenshot |
|---|---|---|---|---|---|
| FN (fraud) | `hxxps://www[.]frontdeskportal[.]icu/` | 37 | browser | Domain was registered only 1 days before this investigation; Uses a top-level domain heavily abused for scams (.icu) | shots/005.png |
| FN (fraud) | `hxxp://lingesh077[.]github[.]io/wepage` | 28 | browser | Presents itself as Netflix but is not an official Netflix domain; Hosted on a free site-builder / hosting platform (github.io) that scammers often abuse | shots/021.png |
| FN (fraud) | `hxxps://about-blank-b9l[.]pages[.]dev/robots.txt/2606%3A4700%3A310c%3A%3Aac42%3A2f59/appeals/subm` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/001.png |
| FN (fraud) | `hxxp://qavzaro-mpt-felmuni-h7d2pe83[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/002.png |
| FN (fraud) | `hxxp://sp28ct11-zulvoro-biz-kelmari[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/003.png |
| FN (fraud) | `hxxps://h0itk-nk3-xam7-i1xuh-01-10-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/004.png |
| FN (fraud) | `hxxps://8s7q0g-qw999agreg-5m2k9p1z8x-qwxk[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/006.png |
| FN (fraud) | `hxxp://2u19d-hhl-bmem-2gl0a-30-09-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/007.png |
| FN (fraud) | `hxxps://meccamacextnsuin[.]gitbook[.]io/us` | 15 | browser | Presents itself as MetaMask but is not an official MetaMask domain | shots/008.png |
| FN (fraud) | `hxxp://www[.]user7076013[.]weebly[.]com/` | 15 | browser | Hosted on a free site-builder / hosting platform (weebly.com) that scammers often abuse | shots/010.png |
| FN (fraud) | `hxxps://ephemeral-squirrel-f84ee4[.]netlify[.]app/` | 15 | browser | Hosted on a free site-builder / hosting platform (netlify.app) that scammers often abuse | shots/011.png |
| FN (fraud) | `hxxp://zt7lu-68z-6ceb-1149i-30-09-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/014.png |
| FN (fraud) | `hxxps://769x7-l41-xrra-38ld5-01-10-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/015.png |
| FN (fraud) | `hxxp://zoomconnect-cr5[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/016.png |
| FN (fraud) | `hxxp://ybmgc-1kl-8atg-jvyy1-23-10-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/017.png |
| FN (fraud) | `hxxp://cjy6s-x3t-r6ix-9mof3-17-10-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/018.png |
| FN (fraud) | `hxxps://m0cbt-uhx-o0au-c62vj-17-10-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/020.png |
| FN (fraud) | `hxxp://sp28ct11-zorkelo-biz-nuvmari[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/022.png |
| FN (fraud) | `hxxp://eoojm-4et-gpqd-iucfc-29-09-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/023.png |
| FN (fraud) | `hxxp://sp28ct11-zorkuni-biz-vemrilo[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/024.png |
| FN (fraud) | `hxxp://ptvd9-f5v-857a-15vyc-29-09-2026-aa-4t1[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/025.png |
| FN (fraud) | `hxxps://s7liw-lzn-xs1u-r68d1-29-09-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/026.png |
| FN (fraud) | `hxxps://tlddh-nd8-f6xx-rx3ak-29-09-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/027.png |
| FN (fraud) | `hxxps://filesxonmnasonorderpdfdocumentsprdlrxszmn[.]pages[.]dev/second.htm` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/028.png |
| FN (fraud) | `hxxp://7bz5f-g8m-64td-qbcbx-19-10-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/029.png |
| FN (fraud) | `hxxp://q0but-xed-lgmv-zi0ay-30-09-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/032.png |
| FN (fraud) | `hxxp://h6ckc-42y-croo-4smka-23-10-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/033.png |
| FN (fraud) | `hxxps://sp28ct11-melruni-biz-zorkavo[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/034.png |
| FN (fraud) | `hxxps://hledk-cr0-yihy-sq5fd-17-10-2026-aa[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/036.png |
| FN (fraud) | `hxxp://sp11ct-kolvar-biz8-drasik-hemlor[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/037.png |
| FN (fraud) | `hxxps://raqfelo-mpt-zumqani-k7x5pe92[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/038.png |
| FN (fraud) | `hxxps://raqvuri-mpt-felqeni-r6d5me84[.]pages[.]dev/` | 15 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/039.png |
| FN (fraud) | `hxxps://u[.]to/XbPiIg` | 12 | none | The link uses a URL shortener (u.to) that hides the real destination |  |
| FN (fraud) | `hxxps://8ovys-p8s-7vc7-rw9nt-23-10-2026-aa[.]pages[.]dev/qaz-wsx-edc-rfv` | 0 | browser | Hosted on a free site-builder / hosting platform (pages.dev) that scammers often abuse | shots/009.png |
| FN (fraud) | `hxxp://cryby[.]xchhx[.]biz[.]id/` | 0 | none | – |  |
| FN (fraud) | `hxxps://belepes-telekom-hu[.]vh22325[.]vh[.]net[.]pl/` | 0 | browser | – | shots/030.png |
| FN (fraud) | `hxxp://member084[.]agencyconnectnetwork[.]com/` | 0 | none | – |  |

## Reading these numbers

- **No false alarms:** 0 of 40 ordinary websites (none of them on Raqib's allowlist) and 0 of 20 official UAE sites were flagged.
- **Low recall on this feed:** 37 of 40 OpenPhish pages were missed. Almost all target global brands and sit on free hosting (`pages.dev`, `github.io`, `weebly`, `netlify`) with random names and little visible content to a first-time visitor (cloaked or script-loaded kits). Raqib's rules are built around UAE brands and visible forms, which is why they score 15–37 here.
- The run had no Claude (keyless sandbox). The screenshot brand check, which can now name any brand, was not part of these numbers.
- Sample size is small (80 + 20), so the 95% intervals are wide.
