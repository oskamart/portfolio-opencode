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

- **The verification engine leads.** UVMStack is the thing that was delivered
  to CERN, so it is first and it is given the most room.
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
python3 serve.py                      # http://127.0.0.1:8080/
python3 deploy/opencode-serve.py      # the production server, port 8095
```

## Verifying it

```bash
python3 build/opencode-manifest.py     # re-measure
python3 build/opencode-verify.py       # links, anchors, assets, metrics
```

## Publishing

`deploy/opencode-publish.sh` measures, verifies, commits, pushes and checks
the live site. It never force-pushes.

The site is served by GitHub Pages from `oskamart/portfolio-opencode` with
`CNAME` = `osys.one`.

**The DNS change at the registrar is still outstanding** — `osys.one` currently
points at an AWS Global Accelerator address that redirects to
`osys.duckdns.org`, whose origin does not answer from the public internet.
To finish, the registrar has to publish:

| Name | Type | Value |
|---|---|---|
| `osys.one` | A | `185.199.108.153` |
| `osys.one` | A | `185.199.109.153` |
| `osys.one` | A | `185.199.110.153` |
| `osys.one` | A | `185.199.111.153` |
| `www.osys.one` | CNAME | `oskamart.github.io` |

The Proton Mail MX and SPF records must not be touched. GitHub issues the
certificate for the domain on its own once DNS resolves.

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
build/opencode-cookies.py       AES-GCM for Chromium cookies, no dependencies
serve.py                        local dev server
deploy/                         production server, publish, DNS notes
```
