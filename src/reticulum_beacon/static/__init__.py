"""Static assets module for serving local frontend dependencies.

Provides fallback paths for HTMX and Tailwind CSS when CDN is unavailable.
The assets can be downloaded with::

    python -m reticulum_beacon.static.download

"""

import os

# Assets live inside the package's own static/ directory so the location is
# valid for editable installs, wheels, and Docker images alike.
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Expected local asset paths
HTMX_PATH = os.path.join(STATIC_DIR, "htmx.min.js")
HTMX_SSE_PATH = os.path.join(STATIC_DIR, "htmx-sse.js")
TAILWIND_PATH = os.path.join(STATIC_DIR, "tailwind.min.css")


def has_local_assets() -> bool:
    """Check whether local copies of frontend assets are available."""
    return os.path.isfile(HTMX_PATH)


def get_local_urls() -> dict[str, str]:
    """Return dict of local asset URLs relative to the /static/ mount.

    Returns:
        Mapping of asset names to URL paths, or empty dict if assets
        are not downloaded.
    """
    if not has_local_assets():
        return {}

    urls: dict[str, str] = {}
    if os.path.isfile(HTMX_PATH):
        urls["htmx"] = "/static/htmx.min.js"
    if os.path.isfile(HTMX_SSE_PATH):
        urls["htmx_sse"] = "/static/htmx-sse.js"
    if os.path.isfile(TAILWIND_PATH):
        urls["tailwind"] = "/static/tailwind.min.css"
    return urls
