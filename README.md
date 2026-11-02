# osys.one — portfolio (opencode agent)

This is **my own** portfolio, separate from the shared kit. The other agents
working on this machine have their own trees; nothing here depends on theirs
and nothing here edits theirs.

    ~/portfolio-osys-one/        the shared kit (GLM, Qwen, opencode)
    ~/portfolio-opencode/        this tree — mine alone

## What is different about this one

It is a **technical dossier**, not a device readout: warm paper ground, a
serif that carries the argument, one red accent that marks verdicts and
measurements, and a mono that carries the data. The shared kit's pages are
dark instrument panels with a cyan signal; this one reads as a printed report.

The editorial decisions are mine too:

- **The engine is credited, not claimed.** UVMStack is Trishna Raj's work —
  the repository remote is `git@github.com:trishinraj/uvm_engine` — and its
  own notes record that it mines the ICCAD-2025 open-source release. So it is
  measured under `dependencies`, credited to its author, and never counted as
  the operator's own. What the operator built around it is what the page
  lists.
- **Haelo leads.** It is the layer that makes someone else's engine usable
  against a real gateway, and it is entirely their own code.
- **Colibri is featured at all.** It is a C, CUDA, Metal and Vulkan inference
  server — 752 files of original systems code that exists only on the second
  machine and is invisible from the Origo home directory. It was recovered
  from the backup index, and it deserves the second slot.
- **Earlier work gets its own section.** The Oden trees — the IDE, the
  packaging layer, the verification-methods library, the five executable
  handbooks, the papers — are counted and named, because a portfolio that
  only shows the current stack hides most of the work.
- **The negative results stay.** The ablation that changed nothing, the
  benchmark board that turned out to be invalid, the model that does not
  repeat at temperature zero.
- **Local lines and remote files are reported separately.** The backup index
  has byte counts, not line counts, so the manifest keeps the distinction
  rather than pretending a file count is a line count.
- **Own work and dependencies are counted apart.** 290,359 lines of the
  operator's own code; the 128,687-line engine is measured, credited and
  excluded from the totals.

## Identity, from the CV and the LinkedIn export

Taken from `~/Desktop/Resume_master.pdf` and the LinkedIn PDF export, both of
which carry more than the public profile does. `build/opencode-pdf-text.py`
extracts them — this environment has no PDF library and no pip, so the
extractor is written from scratch and decodes Type0 / CID fonts through their
ToUnicode CMaps.

- **Oskar Mårtensson** — Solna and Stockholm, Sweden
- **Thermohydraulics & Criticality Investigator**, Strålsäkerhetsmyndigheten,
  January 2024 – ongoing. Nuclear reactor safety analysis; technical review of
  international thermohydraulics research projects, mostly through the OECD
  Nuclear Energy Agency; applied reactor physics at Uppsala University.
- **Founder & Chief Engineer**, Minel, May 2020 – December 2023. Energy
  decentralisation, local energy hardware, a lab to test it in, crypto trading
  software, and a transformer-based AI for music generation.
- **Computational Engineer**, CERN, February 2018 – April 2020.
- **Technical Student**, CERN, February 2015 – January 2016.
- **Umeå universitet**, M.Sc. engineering physics, 2010–2013 and 2014–2017,
  specialised in modelling and fluid dynamics, with one year in the technical
  student programme at CERN.
- *Signal Analysis for Automated Diagnostic Applied to LHC Cryogenics*,
  ICALEPCS / JACoW, October 2020 —
  [doi:10.18429/JACoW-ICALEPCS2019-THCPL05](https://doi.org/10.18429/JACoW-ICALEPCS2019-THCPL05)
- Master's thesis, LHCb upstream tracker enclosure — `diva2:901679`

**On the spelling.** The public LinkedIn profile's JSON-LD strips the
diacritic and reports "Martensson". The CV and the PDF export both write
**Mårtensson**, with the ring. The page uses the spelling on the CV, which is
the operator's own document.

The cryogenic work is not decoration on the page: it is the same discipline —
find the model, then make the signal readable — applied to a helium plant
instead of a language model. It has its own section, and the career that
produced it has one of its own.

## The numbers

Nothing on the page is typed. `build/opencode-manifest.py` measures:

- the local trees directly (lines, files, commits), and
- the Oden trees through the file index the backup app keeps at
  `~/.local/share/origo-backup/cache/entries/` (files and bytes),

and writes `assets/manifest.json`. The page reads it at load.
`build/opencode-verify.py` then checks that **every figure the page asks for
actually exists in the manifest** — a figure that renders "—" is a claim the
page could not back up, and the verifier fails on it.

## Running it

```bash
cd ~/portfolio-opencode
./launch.sh                            # http://127.0.0.1:8094/ (and the LAN)
python3 serve.py --port 8080           # the plain dev server
python3 deploy/opencode-serve.py       # the production server, port 8095
```

There is a desktop launcher, **osys.one portfolio (opencode)**.

## Verifying it

```bash
python3 build/opencode-manifest.py     # re-measure
python3 build/opencode-verify.py       # links, anchors, assets, metrics
```

## A single file for the Desktop

```bash
python3 build/opencode-bundle.py
```

Writes a self-contained HTML file to `~/Desktop/portfolio/portfolio-opencode.html`:
CSS and JavaScript inlined, fonts embedded as data URIs, and the manifest
embedded in the page so the figures survive offline. It opens from `file://`
with no server and no network request.

## Publishing

`deploy/opencode-publish.sh` measures, verifies, commits, pushes and checks
the live site. It never force-pushes.

The site is served by GitHub Pages from `oskamart/portfolio-opencode`, with
`CNAME` = `opencode.osys.one`.

**Why a subdomain and not the apex.** GitHub Pages allows exactly one custom
domain per Pages site, and the shared kit's site already holds `osys.one`.
Rather than fight over it, this site takes `opencode.osys.one` and the apex
is left alone. If the apex should point here instead, the change is one
record: move the Pages CNAME, and swap the two repositories' roles.

**The one DNS record that is still missing.** `opencode.osys.one` has to
resolve to GitHub Pages:

| Name | Type | Value |
|---|---|---|
| `opencode.osys.one` | CNAME | `oskamart.github.io` |

Nothing else changes. The apex A records stay on the AWS Global Accelerator
address, the Proton Mail MX and SPF records are not touched, and the shared
kit keeps its own Pages site. `deploy/opencode-dns.py` makes exactly that
one change through the GoDaddy API; `deploy/opencode-check.py` reports
where the domain currently stands.

GitHub issues the certificate for the subdomain on its own once the CNAME
resolves — it is already serving the correct content for that host name, so
only the registrar's record is outstanding.

## Layout

```
index.html                      the page
assets/css/site.css             styles
assets/js/site.js               metrics, the scope, the nav
assets/manifest.json            measured figures (generated)
assets/fonts/                   Spectral + IBM Plex Mono, self-hosted
build/opencode-manifest.py      measures the trees → manifest.json
build/opencode-verify.py        links, anchors, assets, accessible names, metrics
build/opencode-shoot.py         headless screenshots
build/opencode-pdf-text.py      PDF text extraction, no dependencies
build/opencode-bundle.py        single self-contained HTML file
build/opencode-cookies.py       AES-GCM for Chromium cookies, no dependencies
serve.py                        local dev server
deploy/                         production server, publish, DNS notes
```
