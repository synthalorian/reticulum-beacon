#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# publish-test-pypi.sh — Build wheel, verify, and publish to Test PyPI
# ──────────────────────────────────────────────────────────────────────────────
# Usage:
#   ./scripts/publish-test-pypi.sh              # publish to TestPyPI
#   ./scripts/publish-test-pypi.sh --real       # publish to real PyPI
#   ./scripts/publish-test-pypi.sh --check      # build + check only
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# ── Parse flags ──────────────────────────────────────────────────────────────
MODE="test"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --real)   MODE="real"   ; shift ;;
    --check)  MODE="check"  ; shift ;;
    --help|-h)
      echo "Usage: $(basename "$0") [--real|--check]"
      echo ""
      echo "  (no flag)  Build + publish to Test PyPI"
      echo "  --real     Build + publish to real PyPI"
      echo "  --check    Build + run twine check only (no publish)"
      exit 0
      ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ── Pre-flight checks ────────────────────────────────────────────────────────
command -v python >/dev/null 2>&1 || { echo "❌ python not found"; exit 1; }
command -v pip     >/dev/null 2>&1 || { echo "❌ pip not found";    exit 1; }

echo "🔍 Running pre-publish checks..."

# 1. Lint
echo "   • ruff check …"
ruff check src/ tests/ --quiet || { echo "❌ ruff check failed"; exit 1; }

# 2. Format check
echo "   • ruff format check …"
ruff format src/ tests/ --check --quiet || { echo "❌ ruff format check failed"; exit 1; }

# 3. Type check
echo "   • mypy …"
mypy src/reticulum_beacon/ || { echo "❌ mypy failed"; exit 1; }

# 4. Tests
echo "   • pytest …"
python -m pytest tests/ -v --tb=short -q || { echo "❌ tests failed"; exit 1; }

# 5. Ensure build and twine are installed
if ! python -m build --help >/dev/null 2>&1; then
  pip install build --quiet
fi
if ! command -v twine >/dev/null 2>&1; then
  pip install twine --quiet
fi

# ── Clean & Build ────────────────────────────────────────────────────────────
echo ""
echo "📦 Cleaning dist/ …"
rm -rf dist/

echo "📦 Building wheel …"
python -m build --wheel --quiet || { echo "❌ build failed"; exit 1; }

WHEEL=$(ls dist/*.whl 2>/dev/null | head -1)
echo "   ✅ Built: $WHEEL"

# ── Verify ───────────────────────────────────────────────────────────────────
echo ""
echo "🔏 Running twine check …"
twine check dist/* || { echo "❌ twine check failed"; exit 1; }
echo "   ✅ twine check passed"

# ── Publish? ─────────────────────────────────────────────────────────────────
if [ "$MODE" = "check" ]; then
  echo ""
  echo "✅ Build + check complete. No publish requested."
  echo "   Wheel: $WHEEL"
  exit 0
fi

REPOSITORY="testpypi"
PYPI_URL="https://test.pypi.org/legacy/"
DEST="Test PyPI"

if [ "$MODE" = "real" ]; then
  REPOSITORY="pypi"
  PYPI_URL="https://upload.pypi.org/legacy/"
  DEST="PyPI"
fi

echo ""
echo "🚀 Publishing to $DEST …"
echo "   Repository: $REPOSITORY"
echo "   URL:        $PYPI_URL"
echo ""

twine upload \
  --repository "$REPOSITORY" \
  --repository-url "$PYPI_URL" \
  dist/*

echo ""
echo "✅ Published successfully to $DEST!"
echo "   $WHEEL"
echo ""
echo "   Install from Test PyPI:"
echo "     pip install --index-url https://test.pypi.org/simple/ reticulum-beacon"
echo ""
echo "   Install from PyPI:"
echo "     pip install reticulum-beacon"
