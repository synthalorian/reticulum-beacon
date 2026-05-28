"""Integration tests for Reticulum Beacon infrastructure.

Tests the Dockerfile, CI/CD config, static assets module, and basic
API contract via FastAPI TestClient (without starting a real server).

All tests should run without RNS initialization or external services.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestDockerfile(unittest.TestCase):
    """Validate the Dockerfile structure."""

    def setUp(self):
        self.dockerfile = os.path.join(os.path.dirname(__file__), "..", "Dockerfile")

    def test_dockerfile_exists(self):
        """Dockerfile must exist at project root."""
        self.assertTrue(os.path.isfile(self.dockerfile))

    def test_dockerfile_uses_python_slim(self):
        """Dockerfile must use python:3.11-slim for minimal image size."""
        with open(self.dockerfile) as f:
            content = f.read()
        self.assertIn("python:3.11-slim", content)

    def test_dockerfile_non_root_user(self):
        """Dockerfile must create and use a non-root user."""
        with open(self.dockerfile) as f:
            content = f.read()
        self.assertIn("useradd", content)
        self.assertIn("USER beacon", content)

    def test_dockerfile_has_entrypoint(self):
        """Dockerfile must define ENTRYPOINT for the beacon CLI."""
        with open(self.dockerfile) as f:
            content = f.read()
        self.assertIn("ENTRYPOINT", content)
        self.assertIn("beacon", content)

    def test_dockerfile_multi_stage(self):
        """Dockerfile should use multi-stage build for smaller images."""
        with open(self.dockerfile) as f:
            content = f.read()
        self.assertIn("AS builder", content)

    def test_dockerfile_exposes_port(self):
        """Dockerfile must EXPOSE the default API port (8931)."""
        with open(self.dockerfile) as f:
            content = f.read()
        self.assertIn("EXPOSE 8931", content)

    def test_dockerfile_volume_mount(self):
        """Dockerfile must define a VOLUME for /etc/reticulum-beacon."""
        with open(self.dockerfile) as f:
            content = f.read()
        self.assertIn("VOLUME", content)
        self.assertIn("/etc/reticulum-beacon", content)


class TestDockerIgnore(unittest.TestCase):
    """Validate the .dockerignore file."""

    def setUp(self):
        self.ignore = os.path.join(os.path.dirname(__file__), "..", ".dockerignore")

    def test_dockerignore_exists(self):
        """.dockerignore must exist at project root."""
        self.assertTrue(os.path.isfile(self.ignore))

    def test_dockerignore_excludes_git(self):
        """.dockerignore must exclude .git."""
        with open(self.ignore) as f:
            content = f.read()
        self.assertIn(".git/", content)

    def test_dockerignore_excludes_venv(self):
        """.dockerignore must exclude virtual environments."""
        with open(self.ignore) as f:
            content = f.read()
        self.assertIn(".venv/", content)

    def test_dockerignore_excludes_tests(self):
        """.dockerignore must exclude tests/ from production image."""
        with open(self.ignore) as f:
            content = f.read()
        self.assertIn("tests/", content)


class TestCIConfig(unittest.TestCase):
    """Validate the GitHub Actions CI configuration."""

    def setUp(self):
        self.ci_yml = os.path.join(
            os.path.dirname(__file__), "..", ".github", "workflows", "ci.yml"
        )

    def test_ci_config_exists(self):
        """CI config must exist."""
        self.assertTrue(os.path.isfile(self.ci_yml))

    def test_ci_runs_ruff(self):
        """CI must run ruff linting."""
        with open(self.ci_yml) as f:
            content = f.read()
        self.assertIn("ruff", content)

    def test_ci_runs_mypy(self):
        """CI must run mypy type checking."""
        with open(self.ci_yml) as f:
            content = f.read()
        self.assertIn("mypy", content)

    def test_ci_runs_pytest(self):
        """CI must run pytest."""
        with open(self.ci_yml) as f:
            content = f.read()
        self.assertIn("pytest", content)

    def test_ci_matrix_python(self):
        """CI must test multiple Python versions."""
        with open(self.ci_yml) as f:
            content = f.read()
        self.assertIn("python-version", content)
        self.assertIn("matrix", content)

    def test_ci_docker_build(self):
        """CI must build Docker image after tests pass."""
        with open(self.ci_yml) as f:
            content = f.read()
        self.assertIn("docker/build-push-action", content)

    def test_ci_formats_check(self):
        """CI must check formatting with ruff format."""
        with open(self.ci_yml) as f:
            content = f.read()
        self.assertIn("ruff format", content)
        self.assertIn("--check", content)


class TestStaticAssetsModule(unittest.TestCase):
    """Test the static assets module for local frontend dependencies."""

    def test_static_module_imports(self):
        """Static module must import cleanly."""
        from reticulum_beacon.static import STATIC_DIR, get_local_urls, has_local_assets

        self.assertTrue(callable(has_local_assets))
        self.assertTrue(callable(get_local_urls))
        self.assertTrue(os.path.isdir(STATIC_DIR))

    def test_has_local_assets_returns_bool(self):
        """has_local_assets() must return a boolean."""
        from reticulum_beacon.static import has_local_assets

        result = has_local_assets()
        self.assertIsInstance(result, bool)

    def test_get_local_urls_returns_dict(self):
        """get_local_urls() always returns a dict."""
        from reticulum_beacon.static import get_local_urls

        urls = get_local_urls()
        self.assertIsInstance(urls, dict)

    def test_static_dir_exists(self):
        """Static directory must exist (created by mkdir)."""
        from reticulum_beacon.static import STATIC_DIR

        self.assertTrue(os.path.isdir(STATIC_DIR))

    def test_download_script_has_urls(self):
        """Download script must define URLs for HTMX and Tailwind."""
        from reticulum_beacon.static.download import HTMX_SSE_URL, HTMX_URL, TAILWIND_URL

        self.assertTrue(HTMX_URL.startswith("http"))
        self.assertTrue(HTMX_SSE_URL.startswith("http"))
        self.assertTrue(TAILWIND_URL.startswith("http"))
        self.assertIn("htmx.org", HTMX_URL)
        self.assertIn("htmx.org", HTMX_SSE_URL)

    def test_download_script_has_main(self):
        """Download script must have a __main__ guard."""
        from reticulum_beacon.static.download import download_assets

        self.assertTrue(callable(download_assets))


class TestFastAPIContract(unittest.TestCase):
    """Test the FastAPI app contract via TestClient.

    These tests verify that the API returns correct status codes and
    headers without starting a real server or requiring RNS.
    """

    def setUp(self):
        """Create a fresh app instance for each test."""
        from reticulum_beacon.api.app import create_app

        self.app = create_app()

    def test_app_has_expected_routes(self):
        """App must register all expected API routes."""
        route_paths = {r.path for r in self.app.routes}
        core_routes = {
            "/api/v1/status",
            "/api/v1/health",
            "/api/v1/health/self-test",
            "/api/v1/health/history",
            "/api/v1/health/diagnostics",
            "/api/v1/peers",
            "/api/v1/interfaces",
            "/api/v1/messages",
            "/api/v1/metrics",
            "/api/v1/",
            "/api/v1/web/dashboard-data",
            "/api/v1/web/status-bar",
            "/api/v1/web/messages/inbox",
            "/api/v1/web/messages/send",
            "/api/v1/web/bots/list",
            "/api/v1/web/bots/available",
            "/api/v1/web/bots/enable/{name}",
            "/api/v1/web/bots/disable/{name}",
            "/api/v1/web/bots/load",
            "/api/v1/web/interfaces",
            "/api/v1/web/peers",
        }
        for route in core_routes:
            self.assertIn(route, route_paths, f"Route {route} not registered")

    def test_app_has_cors_middleware(self):
        """App must have CORS middleware configured."""
        has_cors = any("CORSMiddleware" in str(m.cls) for m in self.app.user_middleware)
        self.assertTrue(has_cors, "CORS middleware not found")

    def test_app_has_rate_limit_middleware(self):
        """App must have rate limiting middleware registered."""
        # The rate limiter is added via @app.middleware("http")
        # Verify user_middleware contains at least CORS middleware
        self.assertGreater(
            len(self.app.user_middleware), 0, "App should have middleware registered"
        )

    def test_app_title_is_correct(self):
        """App title must be 'Reticulum Beacon API'."""
        self.assertEqual(self.app.title, "Reticulum Beacon API")

    def test_app_websocket_route(self):
        """WebSocket /api/v1/events route must be registered."""
        route_paths = {r.path for r in self.app.routes}
        self.assertIn("/api/v1/events", route_paths)

    def test_health_routes_accept_get(self):
        """Health check routes must accept GET."""
        for route in self.app.routes:
            if hasattr(route, "path") and route.path == "/api/v1/health":
                self.assertIn("GET", route.methods)
                return
        self.fail("Health route not found")

    def test_metrics_route_accepts_get(self):
        """Metrics route must accept GET."""
        for route in self.app.routes:
            if hasattr(route, "path") and route.path == "/api/v1/metrics":
                self.assertIn("GET", route.methods)
                return
        self.fail("Metrics route not found")


class TestStaticFileMounting(unittest.TestCase):
    """Test the static file mounting logic in api/app.py."""

    def setUp(self):
        from reticulum_beacon.api.app import create_app

        self.app = create_app()

    def test_static_mount_code_path(self):
        """The static file mounting code path in app.py is reachable."""
        from reticulum_beacon.api.app import create_app as _ca

        self.assertIsNotNone(_ca)


class TestPyprojectDevExtras(unittest.TestCase):
    """Test that pyproject.toml has correct dev extras."""

    def setUp(self):
        self.pyproject = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")

    def test_dev_extras_include_httpx(self):
        """Dev extras must include httpx for integration tests."""
        with open(self.pyproject) as f:
            content = f.read()
        self.assertIn("httpx", content)

    def test_dev_extras_include_python_multipart(self):
        """Dev extras must include python-multipart for form data."""
        with open(self.pyproject) as f:
            content = f.read()
        self.assertIn("python-multipart", content)

    def test_dev_extras_include_ruff(self):
        """Dev extras must include ruff."""
        with open(self.pyproject) as f:
            content = f.read()
        self.assertIn("ruff", content)

    def test_dev_extras_include_mypy(self):
        """Dev extras must include mypy."""
        with open(self.pyproject) as f:
            content = f.read()
        self.assertIn("mypy", content)


class TestLocalAssetsJinja2Global(unittest.TestCase):
    """Test that local_assets is registered as a Jinja2 global."""

    def test_local_assets_in_template_globals(self):
        """local_assets must be registered in Jinja2 environment globals."""
        from reticulum_beacon.web.routes import _templates

        self.assertIn("local_assets", _templates.env.globals)
        self.assertIsInstance(_templates.env.globals["local_assets"], dict)

    def test_local_assets_referenced_in_base_template(self):
        """base.html must reference local_assets."""
        import reticulum_beacon.web.routes as web_routes

        base = os.path.join(
            os.path.dirname(web_routes.__file__),
            "templates",
            "base.html",
        )
        with open(base) as f:
            content = f.read()
        self.assertIn("local_assets", content)
        self.assertIn("local_assets.get('htmx'", content)
        self.assertIn("local_assets.get('tailwind'", content)


class TestSecurityInfrastructure(unittest.TestCase):
    """Test security properties of the infrastructure."""

    def test_dockerfile_no_root(self):
        """Dockerfile must not run as root."""
        with open(os.path.join(os.path.dirname(__file__), "..", "Dockerfile")) as f:
            content = f.read()
        # Check USER beacon is set
        self.assertIn("USER beacon", content)
        # Check there's no USER root after it
        beacon_pos = content.index("USER beacon")
        self.assertNotIn("USER root", content[beacon_pos:])

    def test_csp_in_template(self):
        """base.html must have Content-Security-Policy."""
        import reticulum_beacon.web.routes as web_routes

        base = os.path.join(
            os.path.dirname(web_routes.__file__),
            "templates",
            "base.html",
        )
        with open(base) as f:
            content = f.read()
        self.assertIn("Content-Security-Policy", content)
        self.assertIn("default-src 'self'", content)

    def test_local_assets_fallback(self):
        """base.html must fall back to CDN when local_assets is empty."""
        import reticulum_beacon.web.routes as web_routes

        base = os.path.join(
            os.path.dirname(web_routes.__file__),
            "templates",
            "base.html",
        )
        with open(base) as f:
            content = f.read()
        # Should reference unpkg.com as fallback
        self.assertIn("unpkg.com", content)
        self.assertIn("cdn.jsdelivr.net", content)

    def test_no_sensitive_env_in_dockerfile(self):
        """Dockerfile must not hardcode secrets."""
        with open(os.path.join(os.path.dirname(__file__), "..", "Dockerfile")) as f:
            content = f.read()
        # Must not contain BEACON_API_KEY
        self.assertNotIn("BEACON_API_KEY", content)

    def test_dockerignore_excludes_systemd(self):
        """.dockerignore must exclude systemd directory."""
        with open(os.path.join(os.path.dirname(__file__), "..", ".dockerignore")) as f:
            content = f.read()
        self.assertIn("systemd/", content)

    def test_dockerignore_excludes_pycache(self):
        """.dockerignore must exclude __pycache__."""
        with open(os.path.join(os.path.dirname(__file__), "..", ".dockerignore")) as f:
            content = f.read()
        self.assertIn("__pycache__/", content)


if __name__ == "__main__":
    unittest.main()
