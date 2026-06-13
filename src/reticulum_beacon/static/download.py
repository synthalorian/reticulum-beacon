"""Download frontend assets for offline/local serving.

Usage::

    python -m reticulum_beacon.static.download

Downloads HTMX (with SSE extension) and Tailwind CSS to the
``static/`` directory so they can be served locally instead of
from CDN.

"""

import os
import sys
import urllib.request

from . import HTMX_PATH, HTMX_SSE_PATH, STATIC_DIR, TAILWIND_PATH

# ── URLs ─────────────────────────────────────────────────────────────────

HTMX_URL = "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js"
HTMX_SSE_URL = "https://unpkg.com/htmx.org@2.0.4/dist/ext/sse.js"
TAILWIND_URL = "https://cdn.jsdelivr.net/npm/@tailwindcss/ui@latest/dist/tailwind-ui.min.css"

# ── Download helpers ──────────────────────────────────────────────────────


def _download(url: str, dest: str) -> None:
    """Download a single file from *url* to *dest*."""
    print(f"  ↓ {url.rsplit('/', maxsplit=1)[-1]} → {os.path.relpath(dest, STATIC_DIR)}")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as response, open(dest, "wb") as f:
        f.write(response.read())


def download_assets() -> None:
    """Download all frontend assets to the static directory."""
    os.makedirs(STATIC_DIR, exist_ok=True)

    print(f"Downloading frontend assets to {STATIC_DIR}")
    _download(HTMX_URL, HTMX_PATH)
    _download(HTMX_SSE_URL, HTMX_SSE_PATH)
    _download(TAILWIND_URL, TAILWIND_PATH)

    print("\n✅ Done. Assets are ready for local serving.")
    print("   Update base.html to set STATIC_MODE='local' to use them.")


if __name__ == "__main__":
    download_assets()
    sys.exit(0)
