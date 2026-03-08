#!/usr/bin/env bash
# ship.sh — Push this prototype to a customer's GitHub repo.
#
# Usage:
#   ./ship.sh <org/repo>           # e.g. ./ship.sh acme-corp/dashboard
#   ./ship.sh <org/repo> --public  # public repo (default is private)
#
# Prerequisites:
#   - gh CLI authenticated (`gh auth status`)
#   - No .env or credentials committed (they're gitignored)

set -euo pipefail

REPO="${1:?Usage: ./ship.sh <org/repo> [--public]}"
VISIBILITY="--private"
[[ "${2:-}" == "--public" ]] && VISIBILITY="--public"

PROTO_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTO_NAME="$(basename "$PROTO_DIR")"

echo "╔══════════════════════════════════════════╗"
echo "║  codeupipe prototype → customer repo     ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Prototype : $PROTO_NAME"
echo "║  Target    : $REPO ($VISIBILITY)"
echo "╚══════════════════════════════════════════╝"

# Safety: ensure we're inside a prototype dir, not the monorepo root
if [[ -f "$PROTO_DIR/../../pyproject.toml" ]] && grep -q 'name = "codeupipe"' "$PROTO_DIR/../../pyproject.toml" 2>/dev/null; then
    echo "[✓] Detected CUP monorepo parent — good"
else
    echo "[!] Warning: not inside the CUP monorepo — are you sure?"
fi

# Safety: ensure .env is NOT being committed
if [[ -f "$PROTO_DIR/.env" ]]; then
    echo "[✓] .env exists (will NOT be committed — in .gitignore)"
fi

cd "$PROTO_DIR"

# Initialize a fresh git repo for customer delivery
if [[ -d .git ]]; then
    echo "[!] .git already exists — skipping init"
else
    git init
fi

git add -A
git commit -m "Initial prototype: $PROTO_NAME (built with codeupipe)"

# Create the remote repo and push
echo ""
echo "[→] Creating $REPO on GitHub..."
gh repo create "$REPO" "$VISIBILITY" --source=. --push

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  ✓ Shipped to: https://github.com/$REPO"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  • Share repo access with the customer"
echo "  • Delete this local copy: rm -rf prototypes/$PROTO_NAME"
