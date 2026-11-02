#!/usr/bin/env bash
# Publish the opencode portfolio.
#
#   measure -> verify -> commit -> push -> confirm
#
# The site is served by GitHub Pages from the repository named below, with
# CNAME = the custom domain. Both live in the repository, so a push cannot
# detach the domain the way a force-push once did.
#
# Usage: deploy/opencode-publish.sh [--dry-run]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

OWNER="oskamart"
REPO="portfolio-opencode"
BRANCH="main"
DOMAIN="osys.one"

say() { printf '\033[36m▸\033[0m %s\n' "$*"; }
ok()  { printf '\033[32m✓\033[0m %s\n' "$*"; }
die() { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

token() {
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then printf '%s' "$GITHUB_TOKEN"; return; fi
  local f="$HOME/.config/gh/hosts.yml"
  [[ -f "$f" ]] || return 1
  python3 - "$f" <<'PY'
import re, sys
s = open(sys.argv[1]).read()
m = re.findall(r"oauth_token:\s*(\S+)", s)
print(m[-1] if m else "")
PY
}

TOKEN="$(token || true)"
[[ -n "$TOKEN" ]] || die "no GitHub token found (set GITHUB_TOKEN or log in with gh)"

# ── 1. measure ─────────────────────────────────────────────────────────────
say "measuring every tree (build/opencode-manifest.py)"
python3 "$ROOT/build/opencode-manifest.py" --out assets/manifest.json

# ── 2. verify ──────────────────────────────────────────────────────────────
say "verifying the site (build/opencode-verify.py)"
if [[ $DRY -eq 0 ]]; then
  PORT=$(( ( RANDOM % 2000 ) + 9000 ))
  python3 "$ROOT/serve.py" --port "$PORT" --no-browser >/tmp/opencode/opencode-logs/verify.log 2>&1 &
  SRV=$!
  trap 'kill $SRV 2>/dev/null || true' EXIT
  for _ in $(seq 1 30); do
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/" && break
    sleep 0.2
  done
  python3 "$ROOT/build/opencode-verify.py" --url "http://127.0.0.1:$PORT/"
  kill $SRV 2>/dev/null || true
  trap - EXIT
else
  python3 "$ROOT/build/opencode-verify.py" --no-serve-check
fi
ok "site verified"

# ── 3. commit ──────────────────────────────────────────────────────────────
cd "$ROOT"
git add -A
if git diff --cached --quiet; then
  say "nothing to commit"
else
  git -c user.name="opencode agent" -c user.email="opencode@opencode.ai" \
      commit -q -m "Portfolio (opencode): refresh the measured manifest

Co-Authored-By: opencode <opencode@opencode.ai>"
  ok "committed"
fi

# The CNAME binds the domain to this Pages site. It is part of the source,
# so every push keeps it — but a stray delete would detach the domain
# silently, so it is restored and checked before pushing.
if [[ ! -f CNAME ]] || [[ "$(cat CNAME)" != "$DOMAIN" ]]; then
  say "restoring CNAME ($DOMAIN)"
  printf '%s\n' "$DOMAIN" > CNAME
  git add CNAME
  git -c user.name="opencode agent" -c user.email="opencode@opencode.ai" \
      commit -q -m "Portfolio (opencode): restore CNAME

Co-Authored-By: opencode <opencode@opencode.ai>"
fi

# ── 4. push ────────────────────────────────────────────────────────────────
if [[ $DRY -eq 1 ]]; then
  say "dry run: would push to $OWNER/$REPO"
  exit 0
fi

say "pushing to $OWNER/$REPO ($BRANCH)"
# Never force. The branch may carry another agent's commits; a force-push
# would discard them.
git push "https://$OWNER:$TOKEN@github.com/$OWNER/$REPO.git" "$BRANCH"
ok "pushed"

# ── 5. confirm ─────────────────────────────────────────────────────────────
say "confirming the live site"
for host in "https://$OWNER.github.io/$REPO/" "https://$DOMAIN/"; do
  code=$(curl -s -o /dev/null -m 20 -w '%{http_code}' -L "$host" || echo 000)
  if [[ "$code" == "200" ]]; then
    ok "$host → $code"
  else
    say "$host → $code (may still be building, or waiting on the DNS change)"
  fi
done
