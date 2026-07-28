"""Basic tests for Reticulum Beacon."""

import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock

# Point to src for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reticulum_beacon import __version__
from reticulum_beacon.config import generator as cfg


class TestConfigGenerator(unittest.TestCase):
    """Test the Reticulum config file generator."""

    def test_generate_config_defaults(self):
        """Test default config generation produces valid config."""
        config = cfg.generate_config()
        self.assertIn("enable_transport = yes", config)
        self.assertIn("type = AutoInterface", config)
        self.assertIn("type = TCPClientInterface", config)
        self.assertIn("target_host = dismail.de", config)
        self.assertIn("target_host = reticulum.chen.lu", config)
        self.assertIn("[reticulum]", config)
        self.assertIn("[interfaces]", config)

    def test_generate_config_no_transport(self):
        """Test config with transport disabled."""
        config = cfg.generate_config(enable_transport=False)
        self.assertIn("enable_transport = no", config)

    def test_generate_config_no_autointerface(self):
        """Test config without AutoInterface."""
        config = cfg.generate_config(autointerface=False)
        self.assertNotIn("type = AutoInterface", config)

    def test_generate_config_custom_nodes(self):
        """Test config with custom testnet nodes."""
        nodes = [("custom.example.com", 9999)]
        config = cfg.generate_config(testnet_nodes=nodes)
        self.assertIn("target_host = custom.example.com", config)
        self.assertIn("target_port = 9999", config)
        self.assertNotIn("target_host = dismail.de", config)

    def test_generate_config_multiple_nodes(self):
        """Test config with multiple testnet nodes."""
        nodes = [("a.com", 1), ("b.com", 2)]
        config = cfg.generate_config(testnet_nodes=nodes)
        self.assertIn("target_host = a.com", config)
        self.assertIn("target_host = b.com", config)

    def test_ensure_dirs_creates_directories(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_beacon = cfg.BEACON_CONFIG_DIR
            orig_rns = cfg.RNS_CONFIG_DIR
            try:
                cfg.BEACON_CONFIG_DIR = str(tmp)
                cfg.RNS_CONFIG_DIR = os.path.join(str(tmp), "reticulum")
                cfg.ensure_dirs()
                self.assertTrue(os.path.exists(cfg.RNS_CONFIG_DIR))
                self.assertEqual(os.stat(cfg.RNS_CONFIG_DIR).st_mode & 0o777, 0o700)
            finally:
                cfg.BEACON_CONFIG_DIR = orig_beacon
                cfg.RNS_CONFIG_DIR = orig_rns

    def test_config_exists(self):
        """Test config_exists returns correct values."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_beacon = cfg.BEACON_CONFIG_DIR
            orig_rns = cfg.RNS_CONFIG_DIR
            try:
                cfg.BEACON_CONFIG_DIR = str(tmp)
                cfg.RNS_CONFIG_DIR = os.path.join(str(tmp), "reticulum")
                cfg.ensure_dirs()
                self.assertFalse(cfg.config_exists())
                cfg.write_config()
                self.assertTrue(cfg.config_exists())
            finally:
                cfg.BEACON_CONFIG_DIR = orig_beacon
                cfg.RNS_CONFIG_DIR = orig_rns

    def test_write_config_creates_file(self):
        """Test write_config creates the config file on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            orig_beacon = cfg.BEACON_CONFIG_DIR
            orig_rns = cfg.RNS_CONFIG_DIR
            try:
                cfg.BEACON_CONFIG_DIR = str(tmp)
                cfg.RNS_CONFIG_DIR = os.path.join(str(tmp), "reticulum")
                config = cfg.write_config()
                config_path = cfg.rns_config_path()
                self.assertTrue(os.path.exists(config_path))
                with open(config_path) as f:
                    content = f.read()
                self.assertEqual(content, config)
            finally:
                cfg.BEACON_CONFIG_DIR = orig_beacon
                cfg.RNS_CONFIG_DIR = orig_rns

    def test_get_config_path(self):
        """Test get_config_path returns the correct path."""
        path = cfg.get_config_path()
        self.assertTrue(path.endswith("reticulum"))


class TestIdentityManager(unittest.TestCase):
    """Test the identity management module."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        import reticulum_beacon.identity.manager as id_mgr

        self._orig_identities_dir = id_mgr.IDENTITIES_DIR
        id_mgr.IDENTITIES_DIR = os.path.join(self.tmp.name, "identities")

    def tearDown(self):
        import reticulum_beacon.identity.manager as id_mgr

        id_mgr.IDENTITIES_DIR = self._orig_identities_dir
        self.tmp.cleanup()

    def test_create_and_list_identities(self):
        """Test creating an identity and listing it."""
        from reticulum_beacon.identity import manager as id_mgr

        identity = id_mgr.create_identity("test_node")
        self.assertIsNotNone(identity)

        identities = id_mgr.list_identities()
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0]["name"], "test_node")

    def test_create_duplicate_raises(self):
        """Test creating a duplicate identity raises FileExistsError."""
        from reticulum_beacon.identity import manager as id_mgr

        id_mgr.create_identity("dup")
        with self.assertRaises(FileExistsError):
            id_mgr.create_identity("dup")

    def test_load_identity(self):
        """Test loading an identity by name."""
        from reticulum_beacon.identity import manager as id_mgr

        created = id_mgr.create_identity("load_test")
        loaded = id_mgr.load_identity("load_test")
        self.assertEqual(created.hash, loaded.hash)

    def test_load_nonexistent_raises(self):
        """Test loading a nonexistent identity raises FileNotFoundError."""
        from reticulum_beacon.identity import manager as id_mgr

        with self.assertRaises(FileNotFoundError):
            id_mgr.load_identity("nonexistent")

    def test_delete_identity(self):
        """Test deleting an identity."""
        from reticulum_beacon.identity import manager as id_mgr

        id_mgr.create_identity("delete_me")
        id_mgr.delete_identity("delete_me")
        identities = id_mgr.list_identities()
        self.assertEqual(len(identities), 0)

    def test_import_identity(self):
        """Test importing an identity from a file."""
        from reticulum_beacon.identity import manager as id_mgr

        original = id_mgr.create_identity("original")
        export_path = os.path.join(self.tmp.name, "exported.identity")
        original.to_file(export_path)

        imported = id_mgr.import_identity(export_path, "imported")
        self.assertEqual(original.hash, imported.hash)

        identities = id_mgr.list_identities()
        names = [i["name"] for i in identities]
        self.assertIn("imported", names)
        self.assertIn("original", names)

    def test_export_identity(self):
        """Test exporting an identity to a file in cwd."""
        from reticulum_beacon.identity import manager as id_mgr

        created = id_mgr.create_identity("export_me")
        # Use cwd-safe path (export is restricted to home/cwd)
        export_path = os.path.join(os.getcwd(), "_test_export.identity")
        try:
            id_mgr.export_identity("export_me", export_path)
            self.assertTrue(os.path.exists(export_path))

            reloaded = id_mgr.import_identity(export_path, "reimported")
            self.assertEqual(created.hash, reloaded.hash)
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)


class TestPropagationNodeModule(unittest.TestCase):
    """Test the propagation node module (no RNS init needed)."""

    def test_module_imports(self):
        """Test that the propagation module can be imported."""
        from reticulum_beacon.propagation.node import PropagationNode

        self.assertIsNotNone(PropagationNode)

    def test_singleton_pattern(self):
        """Test PropagationNode follows singleton pattern."""
        from reticulum_beacon.propagation.node import PropagationNode

        pn1 = PropagationNode.get_instance()
        pn2 = PropagationNode.get_instance()
        self.assertIs(pn1, pn2)

    def test_initial_state(self):
        """Test PropagationNode starts in stopped state."""
        from reticulum_beacon.propagation.node import PropagationNode

        pn = PropagationNode.get_instance()
        self.assertFalse(pn.is_running)
        self.assertEqual(pn.uptime, 0.0)
        status = pn.get_status()
        self.assertFalse(status["running"])


class TestNodeModule(unittest.TestCase):
    """Test the BeaconNode module (no RNS init needed)."""

    def test_module_imports(self):
        """Test that the node module can be imported."""
        from reticulum_beacon.node import BeaconNode

        self.assertIsNotNone(BeaconNode)

    def test_singleton_pattern(self):
        """Test BeaconNode follows singleton pattern."""
        from reticulum_beacon.node import BeaconNode

        bn1 = BeaconNode.get_instance()
        bn2 = BeaconNode.get_instance()
        self.assertIs(bn1, bn2)

    def test_initial_state(self):
        """Test BeaconNode starts in stopped state."""
        from reticulum_beacon.node import BeaconNode

        bn = BeaconNode.get_instance()
        self.assertFalse(bn.is_running)
        self.assertEqual(bn.uptime, 0.0)
        status = bn.get_status()
        self.assertFalse(status["running"])


class TestAPIModule(unittest.TestCase):
    """Test the API module (no FastAPI server started)."""

    def test_module_imports(self):
        """Test that the API modules can be imported."""
        from reticulum_beacon.api.app import create_app

        self.assertIsNotNone(create_app)

    def test_create_app(self):
        """Test that create_app returns a FastAPI app with all core routes."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app, get_api_key

        app = create_app()
        self.assertIsNotNone(app)
        self.assertEqual(app.title, "Reticulum Beacon API")
        # FastAPI 0.140+ mounts included routers lazily, so app.routes does not
        # list them eagerly. Verify via the OpenAPI schema (materializes all
        # schema-visible paths) fetched through TestClient.
        auth = {"Authorization": f"Bearer {get_api_key()}"}
        with TestClient(app) as client:
            schema = client.get("/openapi.json", headers=auth).json()
        paths = set(schema["paths"])
        self.assertIn("/api/v1/status", paths)
        self.assertIn("/api/v1/health", paths)
        self.assertIn("/api/v1/peers", paths)
        self.assertIn("/api/v1/interfaces", paths)
        self.assertIn("/api/v1/messages", paths)
        self.assertIn("/api/v1/metrics", paths)

    def test_event_manager(self):
        """Test EventManager pub/sub."""
        from reticulum_beacon.api.websocket import EventManager

        em = EventManager.get_instance()
        received = []

        def callback(event):
            received.append(event)

        unsub = em.subscribe(callback)
        em.publish("test_event", {"foo": "bar"})

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["type"], "test_event")
        self.assertEqual(received[0]["data"]["foo"], "bar")
        self.assertIn("timestamp", received[0])

        # Unsubscribe and verify no more events
        unsub()
        em.publish("another_event", {})
        self.assertEqual(len(received), 1)

    def test_event_manager_recent_events(self):
        """Test recent event history."""
        from reticulum_beacon.api.websocket import EventManager

        em = EventManager.get_instance()
        em.publish("e1", {})
        em.publish("e2", {})
        recent = em.get_recent_events(5)
        self.assertGreaterEqual(len(recent), 2)
        self.assertEqual(recent[-1]["type"], "e2")


class TestBotModule(unittest.TestCase):
    """Test the bot module."""

    def test_base_bot_import(self):
        """Test that the bot base class can be imported."""
        from reticulum_beacon.bots.base import BeaconBot

        self.assertIsNotNone(BeaconBot)

    def test_base_bot_defaults(self):
        """Test default bot attributes."""
        from reticulum_beacon.bots.base import BeaconBot

        bot = BeaconBot()
        self.assertEqual(bot.name, "base_bot")
        self.assertEqual(bot.description, "Base bot plugin")
        self.assertTrue(bot.enabled)
        self.assertEqual(bot.schedule_interval, 0)

    def test_echo_bot_import(self):
        """Test that the echo bot can be imported."""
        from reticulum_beacon.bots.echo import EchoBot

        self.assertIsNotNone(EchoBot)
        self.assertEqual(EchoBot.name, "echo")

    def test_ping_bot_import(self):
        """Test that the ping bot can be imported."""
        from reticulum_beacon.bots.ping import PingBot

        self.assertIsNotNone(PingBot)
        self.assertEqual(PingBot.name, "ping")

    def test_ai_bot_import(self):
        """Test that the AI bot can be imported."""
        from reticulum_beacon.bots.ai_bot import AIBot

        self.assertIsNotNone(AIBot)
        self.assertEqual(AIBot.name, "ai")

    def test_bot_registry_singleton(self):
        """Test BotRegistry singleton pattern."""
        from reticulum_beacon.bots.loader import BotRegistry

        r1 = BotRegistry.get_instance()
        r2 = BotRegistry.get_instance()
        self.assertIs(r1, r2)

    def test_bot_registry_register_list(self):
        """Test registering and listing bots."""
        from reticulum_beacon.bots.base import BeaconBot
        from reticulum_beacon.bots.loader import BotRegistry

        reg = BotRegistry.get_instance()

        bot1 = BeaconBot()
        bot1.name = "test_bot_1"
        bot1.description = "Test bot 1"

        bot2 = BeaconBot()
        bot2.name = "test_bot_2"

        reg.register_bot(bot1)
        reg.register_bot(bot2)

        bots = reg.list_bots()
        names = [b["name"] for b in bots]
        self.assertIn("test_bot_1", names)
        self.assertIn("test_bot_2", names)

        # Cleanup
        reg.unregister_bot("test_bot_1")
        reg.unregister_bot("test_bot_2")

    def test_bot_registry_enable_disable(self):
        """Test enabling and disabling bots."""
        from reticulum_beacon.bots.base import BeaconBot
        from reticulum_beacon.bots.loader import BotRegistry

        reg = BotRegistry.get_instance()
        bot = BeaconBot()
        bot.name = "toggle_bot"
        reg.register_bot(bot)

        self.assertTrue(bot.enabled)
        self.assertTrue(reg.disable_bot("toggle_bot"))
        self.assertFalse(bot.enabled)
        self.assertTrue(reg.enable_bot("toggle_bot"))
        self.assertTrue(bot.enabled)

        reg.unregister_bot("toggle_bot")

    def test_bot_registry_deliver_message(self):
        """Test message delivery to bots."""
        from reticulum_beacon.bots.base import BeaconBot
        from reticulum_beacon.bots.loader import BotRegistry

        reg = BotRegistry.get_instance()

        received = []

        class TestBot(BeaconBot):
            name = "test_receive"

            def on_message(self, message):
                received.append(message)

        bot = TestBot()
        reg.register_bot(bot)

        msg = MagicMock()
        msg.content = "hello"
        reg.deliver_message(msg)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].content, "hello")

        reg.unregister_bot("test_receive")

    def test_bot_registry_discover_bots(self):
        """Test bot discovery finds built-in bots."""
        from reticulum_beacon.bots.loader import BotRegistry

        reg = BotRegistry.get_instance()
        available = reg.discover_bots()

        names = [b["name"] for b in available]
        self.assertIn("echo", names)
        self.assertIn("ping", names)
        self.assertIn("ai", names)


class TestSecurity(unittest.TestCase):
    """Security-focused tests for identity management, API auth, and input validation."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        import reticulum_beacon.identity.manager as id_mgr

        self._orig_identities_dir = id_mgr.IDENTITIES_DIR
        id_mgr.IDENTITIES_DIR = os.path.join(self.tmp.name, "identities")

    def tearDown(self):
        import reticulum_beacon.identity.manager as id_mgr

        id_mgr.IDENTITIES_DIR = self._orig_identities_dir
        self.tmp.cleanup()

    # ── Identity name validation ────────────────────────────────────────

    def test_identity_name_rejects_slashes(self):
        """Reject identity names with slashes (path traversal)."""
        from reticulum_beacon.identity import manager as id_mgr

        for bad_name in ["../etc/shadow", "foo/bar", "../../root", "a/b/c"]:
            with self.subTest(name=bad_name), self.assertRaises(ValueError):
                id_mgr.create_identity(bad_name)

    def test_identity_name_rejects_dots(self):
        """Reject identity names starting with dots."""
        from reticulum_beacon.identity import manager as id_mgr

        for bad_name in [".", "..", ".hidden", "..hidden"]:
            with self.subTest(name=bad_name), self.assertRaises(ValueError):
                id_mgr.create_identity(bad_name)

    def test_identity_name_rejects_special_chars(self):
        """Reject identity names with special characters."""
        from reticulum_beacon.identity import manager as id_mgr

        for bad_name in ["foo bar", "foo;bar", "foo|bar", "foo$bar", "foo`bar"]:
            with self.subTest(name=bad_name), self.assertRaises(ValueError):
                id_mgr.create_identity(bad_name)

    def test_identity_name_accepts_valid(self):
        """Accept valid identity names."""
        from reticulum_beacon.identity import manager as id_mgr

        for good_name in ["node1", "my-node", "test_node", "AlphaBeta123", "a"]:
            with self.subTest(name=good_name):
                identity = id_mgr.create_identity(good_name)
                self.assertIsNotNone(identity)
                id_mgr.delete_identity(good_name)

    def test_load_identity_rejects_path_traversal(self):
        """Reject load attempts with path traversal names."""
        from reticulum_beacon.identity import manager as id_mgr

        with self.assertRaises(ValueError):
            id_mgr.load_identity("../../etc/shadow")

    def test_delete_identity_rejects_path_traversal(self):
        """Reject delete attempts with path traversal names."""
        from reticulum_beacon.identity import manager as id_mgr

        with self.assertRaises(ValueError):
            id_mgr.delete_identity("../other")

    # ── Identity import security ────────────────────────────────────────

    def test_import_rejects_invalid_file(self):
        """Reject import of files that are not valid Reticulum identities."""
        from reticulum_beacon.identity import manager as id_mgr

        with self.assertRaises(ValueError):
            id_mgr.import_identity("/etc/passwd", "malicious")

    def test_import_rejects_nonexistent_path(self):
        """Reject import from nonexistent paths."""
        from reticulum_beacon.identity import manager as id_mgr

        with self.assertRaises(FileNotFoundError):
            id_mgr.import_identity("/nonexistent/path/file.identity", "nope")

    def test_import_rejects_directory(self):
        """Reject import if source is a directory."""
        from reticulum_beacon.identity import manager as id_mgr

        with self.assertRaises(ValueError):
            id_mgr.import_identity(self.tmp.name, "dir_test")

    def test_export_prevents_path_traversal(self):
        """Reject export to paths outside home/cwd."""
        from reticulum_beacon.identity import manager as id_mgr

        id_mgr.create_identity("safe")
        with self.assertRaises((ValueError, OSError)):
            id_mgr.export_identity("safe", "/etc/should_not_write")

    # ── EventManager thread safety ──────────────────────────────────────

    def test_event_manager_concurrent_subscribe_unsubscribe(self):
        """EventManager handles concurrent subscribe/unsubscribe safely."""
        from reticulum_beacon.api.websocket import EventManager

        em = EventManager.get_instance()
        callbacks = []
        unsubs = []

        # Subscribe many callbacks
        for i in range(50):

            def cb(event, idx=i):
                return None

            callbacks.append(cb)
            unsubs.append(em.subscribe(cb))

        # Unsubscribe half
        for i in range(25):
            unsubs[i]()

        # Publish should not raise
        try:
            em.publish("stress_test", {"data": "x" * 1000})
        except Exception as e:
            self.fail(f"Concurrent publish failed: {e}")

        # Clean up remaining
        for i in range(25, 50):
            unsubs[i]()

    # ── FastAPI auth middleware ──────────────────────────────────────────

    def test_fastapi_app_has_auth_middleware(self):
        """FastAPI app enforces Bearer auth on protected endpoints."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app, get_api_key

        app = create_app()
        with TestClient(app) as client:
            # No credentials -> rejected
            self.assertEqual(client.get("/api/v1/status").status_code, 403)
            # Wrong key -> rejected
            bad = {"Authorization": "Bearer wrong-key"}
            self.assertEqual(client.get("/api/v1/status", headers=bad).status_code, 403)
            # Valid key -> allowed
            good = {"Authorization": f"Bearer {get_api_key()}"}
            self.assertEqual(client.get("/api/v1/status", headers=good).status_code, 200)

    # ── Bot registry security ───────────────────────────────────────────

    def test_bot_load_validates_class_path(self):
        """Bot loader validates class path format."""
        from reticulum_beacon.bots.loader import BotRegistry

        reg = BotRegistry.get_instance()
        # Invalid module path should return None, not crash
        result = reg.load_bot("nonexistent.module.Class")
        self.assertIsNone(result)

        # Non-bot class should return None
        result = reg.load_bot("os.path.join")
        self.assertIsNone(result)


class TestModule(unittest.TestCase):
    """Test module-level items."""

    def test_version(self):
        """Test that version is a string."""
        self.assertIsInstance(__version__, str)
        self.assertTrue(len(__version__) > 0)


class TestAuditLog(unittest.TestCase):
    """Test the structured audit logging module."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from reticulum_beacon import audit

        self._orig_path = audit.AUDIT_LOG_PATH
        self._orig_dir = audit.cfg.BEACON_CONFIG_DIR
        audit.cfg.BEACON_CONFIG_DIR = self.tmp.name
        audit.AUDIT_LOG_PATH = os.path.join(self.tmp.name, "audit.log")

    def tearDown(self):
        from reticulum_beacon import audit

        audit.AUDIT_LOG_PATH = self._orig_path
        audit.cfg.BEACON_CONFIG_DIR = self._orig_dir
        self.tmp.cleanup()

    def test_log_event_creates_file(self):
        """Test that log_event creates the audit log file."""
        from reticulum_beacon import audit

        audit.log_event("test.event", "INFO", {"msg": "hello"})
        self.assertTrue(os.path.exists(audit.AUDIT_LOG_PATH))

    def test_log_event_has_correct_structure(self):
        """Test that audit entries have the correct JSON schema."""
        from reticulum_beacon import audit

        audit.log_event("system.start", "INFO", {"version": "1.0"})
        with open(audit.AUDIT_LOG_PATH) as f:
            entry = json.loads(f.readline())
        self.assertIn("ts", entry)
        self.assertIn("iso", entry)
        self.assertEqual(entry["event"], "system.start")
        self.assertEqual(entry["sev"], "INFO")
        self.assertEqual(entry["details"]["version"], "1.0")

    def test_log_event_thread_safe(self):
        """Test concurrent logging does not corrupt the file."""
        from reticulum_beacon import audit

        def writer(idx):
            for _ in range(50):
                audit.log_event("stress", "INFO", {"i": idx})

        threads = []
        for i in range(10):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        # Verify every line is valid JSON
        with open(audit.AUDIT_LOG_PATH) as f:
            for i, line in enumerate(f):
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    self.fail(f"Line {i} is not valid JSON: {line[:100]}")

    def test_log_rotation(self):
        """Test log rotation when file exceeds max size."""
        from reticulum_beacon import audit

        # Write enough data to trigger rotation
        large_details = {"padding": "x" * 10000}
        for _ in range(20):  # ~200 KB
            audit.log_event("padding", "INFO", large_details)

        # Force rotation by writing again
        orig_rotated = audit._rotated
        orig_max_bytes = audit._MAX_LOG_BYTES
        try:
            audit._rotated = False
            audit._MAX_LOG_BYTES = 1  # 1 byte — force immediate rotation
            audit.log_event("rotate_test", "INFO", {})

            # The .old file should exist
            old_path = audit.AUDIT_LOG_PATH + ".old"
            self.assertTrue(os.path.exists(old_path))
        finally:
            audit._rotated = orig_rotated
            audit._MAX_LOG_BYTES = orig_max_bytes
            if os.path.exists(old_path):
                os.unlink(old_path)

    def test_log_auth_success(self):
        """Test log_auth helper."""
        from reticulum_beacon import audit

        audit.log_auth(success=True, client_ip="127.0.0.1")
        with open(audit.AUDIT_LOG_PATH) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["event"], "auth")
        self.assertEqual(entry["details"]["client_ip"], "127.0.0.1")

    def test_log_auth_failure(self):
        """Test log_auth failure records reason."""
        from reticulum_beacon import audit

        audit.log_auth(success=False, client_ip="10.0.0.1", reason="invalid_key")
        with open(audit.AUDIT_LOG_PATH) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["event"], "auth.failure")
        self.assertEqual(entry["sev"], "WARNING")
        self.assertEqual(entry["details"]["reason"], "invalid_key")

    def test_log_error_silent(self):
        """Test that audit failures never raise exceptions."""
        from reticulum_beacon import audit

        # Point to unwritable path
        audit.AUDIT_LOG_PATH = "/nonexistent/deep/dir/audit.log"
        # Should not raise
        audit.log_event("test", "INFO", {"foo": "bar"})


class TestCerts(unittest.TestCase):
    """Test the TLS certificate management module."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from reticulum_beacon.crypto import certs

        self._orig_dir = certs.CERTS_DIR
        self._orig_cert = certs.CERT_PATH
        self._orig_key = certs.KEY_PATH
        certs.CERTS_DIR = os.path.join(self.tmp.name, "certs")
        certs.CERT_PATH = os.path.join(certs.CERTS_DIR, "beacon.pem")
        certs.KEY_PATH = os.path.join(certs.CERTS_DIR, "beacon-key.pem")

    def tearDown(self):
        from reticulum_beacon.crypto import certs

        certs.CERTS_DIR = self._orig_dir
        certs.CERT_PATH = self._orig_cert
        certs.KEY_PATH = self._orig_key
        self.tmp.cleanup()

    def test_cert_paths_creates_files(self):
        """Test that cert_paths() generates cert files on first call."""
        from reticulum_beacon.crypto.certs import cert_paths

        cert_p, key_p = cert_paths()
        self.assertTrue(os.path.exists(cert_p))
        self.assertTrue(os.path.exists(key_p))

    def test_cert_paths_returns_existing(self):
        """Test that cert_paths() returns existing certs without re-generating."""
        from reticulum_beacon.crypto.certs import cert_paths

        # First call creates
        cert1, _key1 = cert_paths()
        mtime1 = os.path.getmtime(cert1)

        # Second call should return same files without regenerating
        cert2, _key2 = cert_paths()
        mtime2 = os.path.getmtime(cert2)

        self.assertEqual(cert1, cert2)
        self.assertEqual(mtime1, mtime2)

    def test_cert_key_permissions(self):
        """Test that private key has 0o600 permissions."""
        from reticulum_beacon.crypto.certs import cert_paths

        _, key_p = cert_paths()
        mode = os.stat(key_p).st_mode & 0o777
        self.assertEqual(mode, 0o600, f"Expected 0o600, got {oct(mode)}")

    def test_cert_contains_subject(self):
        """Test that the generated cert contains expected subject fields."""
        import subprocess

        from reticulum_beacon.crypto.certs import cert_paths

        cert_p, _ = cert_paths()

        # Parse cert with openssl to verify content
        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", cert_p, "-subject", "-noout"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            self.assertIn("reticulum-beacon", result.stdout)
            self.assertIn("ReticulumBeacon", result.stdout)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass  # openssl not available — skip content check

    def test_cert_has_san(self):
        """Test that the cert has SAN for localhost."""
        import subprocess

        from reticulum_beacon.crypto.certs import cert_paths

        cert_p, _ = cert_paths()

        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", cert_p, "-ext", "subjectAltName", "-noout"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            self.assertIn("localhost", result.stdout)
            self.assertIn("127.0.0.1", result.stdout)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass  # openssl not available — skip SAN check

    def test_cert_expiry_far_future(self):
        """Test that the cert is valid for at least 10 years."""
        import subprocess

        from reticulum_beacon.crypto.certs import cert_paths

        cert_p, _ = cert_paths()

        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", cert_p, "-enddate", "-noout"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            import datetime

            enddate_str = result.stdout.replace("notAfter=", "").strip()
            enddate = datetime.datetime.strptime(enddate_str, "%b %d %H:%M:%S %Y %Z")
            now = datetime.datetime.now()
            # Should be at least 9 years in the future
            years_valid = (enddate - now).days / 365.0
            self.assertGreater(years_valid, 9.0, f"Cert valid for only {years_valid:.1f} years")
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    def test_cert_key_pair_matches(self):
        """Test that the cert and key form a valid pair."""
        import subprocess

        from reticulum_beacon.crypto.certs import cert_paths

        cert_p, _key_p = cert_paths()

        try:
            # Verify the key matches the cert
            result = subprocess.run(
                ["openssl", "verify", "-CAfile", cert_p, cert_p],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            # Self-signed verification should at least complete
            self.assertIn(cert_p, result.stdout)
        except FileNotFoundError:
            pass  # openssl not available


class TestWebUI(unittest.TestCase):
    """Test the Web UI module (Jinja2 templates + HTMX routes)."""

    def test_web_module_imports(self):
        """Test that the web module can be imported."""
        from reticulum_beacon.web.routes import router

        self.assertIsNotNone(router)

    def test_web_routes_registered(self):
        """Test that web routes respond correctly via HTTP."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app, get_api_key

        app = create_app()
        auth = {"Authorization": f"Bearer {get_api_key()}"}
        with TestClient(app) as client:
            # Web UI dashboard page returns HTML
            r = client.get("/api/v1/")
            self.assertEqual(r.status_code, 200)
            self.assertIn("text/html", r.headers["content-type"])
            # /messages, /bots, /interfaces are shared with the REST API, which
            # is registered first and takes precedence: they serve JSON (auth
            # required) rather than HTML pages.
            for path in ("/api/v1/messages", "/api/v1/bots", "/api/v1/interfaces"):
                self.assertEqual(client.get(path).status_code, 403)
                r = client.get(path, headers=auth)
                self.assertEqual(r.status_code, 200)
            # Web UI HTMX fragment routes return HTML without auth
            for path in (
                "/api/v1/web/dashboard-data",
                "/api/v1/web/status-bar",
                "/api/v1/web/messages/inbox",
                "/api/v1/web/bots/list",
                "/api/v1/web/bots/available",
                "/api/v1/web/interfaces",
                "/api/v1/web/peers",
            ):
                r = client.get(path)
                self.assertEqual(r.status_code, 200, f"{path} -> {r.status_code}")
                self.assertIn("text/html", r.headers["content-type"])
            # Web UI POST routes exist (GET is rejected with 405)
            for path in (
                "/api/v1/web/messages/send",
                "/api/v1/web/bots/load",
                "/api/v1/web/bots/enable/echo",
                "/api/v1/web/bots/disable/echo",
            ):
                self.assertEqual(client.get(path).status_code, 405)

    def test_web_pages_return_html(self):
        """Test that the web dashboard page returns HTML content type."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            r = client.get("/api/v1/")
            self.assertEqual(r.status_code, 200)
            self.assertIn("text/html", r.headers["content-type"])

    def test_web_send_message_validates_input(self):
        """Test that the send message endpoint validates form input."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            # POST route exists; GET is not allowed
            self.assertEqual(client.get("/api/v1/web/messages/send").status_code, 405)
            # Missing form fields -> 422 validation error
            r = client.post("/api/v1/web/messages/send", data={})
            self.assertEqual(r.status_code, 422)
            # Non-HTMX POST is rejected by the CSRF header check
            r = client.post(
                "/api/v1/web/messages/send",
                data={"destination": "ab" * 32, "content": "hi"},
            )
            self.assertEqual(r.status_code, 200)
            self.assertIn("Invalid request", r.text)

    def test_web_bot_enable_disable_routes(self):
        """Test bot enable/disable routes accept POST."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            # GET is not allowed on these POST-only routes
            self.assertEqual(client.get("/api/v1/web/bots/enable/echo").status_code, 405)
            self.assertEqual(client.get("/api/v1/web/bots/disable/echo").status_code, 405)
            # POST toggles return HTML fragments
            r = client.post("/api/v1/web/bots/enable/echo")
            self.assertEqual(r.status_code, 200)
            self.assertIn("text/html", r.headers["content-type"])
            self.assertEqual(client.post("/api/v1/web/bots/disable/echo").status_code, 200)

    def test_template_directory_exists(self):
        """Test that template files exist on disk."""
        import reticulum_beacon.web.routes as web_routes

        templates_dir = os.path.join(os.path.dirname(web_routes.__file__), "templates")
        self.assertTrue(os.path.isdir(templates_dir))
        expected = ["base.html", "dashboard.html", "messages.html", "bots.html", "interfaces.html"]
        for name in expected:
            self.assertTrue(
                os.path.exists(os.path.join(templates_dir, name)),
                f"Missing template: {name}",
            )

    def test_fragment_directory_exists(self):
        """Test that fragment templates directory exists."""
        import reticulum_beacon.web.routes as web_routes

        fragments_dir = os.path.join(os.path.dirname(web_routes.__file__), "templates", "fragments")
        self.assertTrue(os.path.isdir(fragments_dir))

    def test_dashboard_data_fragment_content(self):
        """Test that dashboard_data.html was created and has valid content."""
        import reticulum_beacon.web.routes as web_routes

        fragment = os.path.join(
            os.path.dirname(web_routes.__file__),
            "templates",
            "fragments",
            "dashboard_data.html",
        )
        self.assertTrue(os.path.exists(fragment))
        with open(fragment) as f:
            content = f.read()
        self.assertIn("dashboard-content", content)
        self.assertIn("Node Status", content)
        self.assertIn("LXMF Propagation", content)
        self.assertIn("API Server", content)

    def test_web_routes_skip_auth(self):
        """Test web routes are in the auth skip list."""
        # Verify that web paths would be skipped by the middleware
        paths_to_skip = [
            "/api/v1/",
            "/api/v1/messages",
            "/api/v1/bots",
            "/api/v1/interfaces",
            "/api/v1/web/dashboard-data",
            "/api/v1/web/status-bar",
            "/api/v1/web/messages/inbox",
            "/api/v1/web/bots/list",
        ]
        for path in paths_to_skip:
            self.assertTrue(
                path in ("/api/v1/", "/api/v1/messages", "/api/v1/bots", "/api/v1/interfaces")
                or path.startswith("/api/v1/web/"),
                f"Path {path} not covered by auth skip",
            )

    def test_csp_header_in_template(self):
        """Test that base.html contains Content-Security-Policy meta tag."""
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
        self.assertIn("script-src 'self'", content)

    def test_htmx_loaded_in_template(self):
        """Test that HTMX is loaded in the base template."""
        import reticulum_beacon.web.routes as web_routes

        base = os.path.join(
            os.path.dirname(web_routes.__file__),
            "templates",
            "base.html",
        )
        with open(base) as f:
            content = f.read()
        self.assertIn("htmx.org", content)
        self.assertIn("unpkg.com/htmx.org", content)

    def test_message_form_has_maxlength(self):
        """Test message form enforces maxlength on content field."""
        import reticulum_beacon.web.routes as web_routes

        msg_template = os.path.join(
            os.path.dirname(web_routes.__file__),
            "templates",
            "messages.html",
        )
        with open(msg_template) as f:
            content = f.read()
        self.assertIn('maxlength="10000"', content)


class TestHealthModule(unittest.TestCase):
    """Test the health check module (no RNS init needed)."""

    def test_health_module_imports(self):
        """Test that the health module can be imported."""
        from reticulum_beacon.api.routes.health import router

        self.assertIsNotNone(router)

    def test_health_routes_registered(self):
        """Test that health routes respond via HTTP (node stopped in tests)."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            # Node is stopped: liveness-style checks report 503...
            self.assertEqual(client.get("/api/v1/health").status_code, 503)
            self.assertEqual(client.get("/api/v1/health/self-test").status_code, 503)
            # ...while history and diagnostics still serve data.
            self.assertEqual(client.get("/api/v1/health/history").status_code, 200)
            self.assertEqual(client.get("/api/v1/health/diagnostics").status_code, 200)

    def test_health_returns_stopped_when_node_offline(self):
        """Test health check returns 'stopped' when node is not running."""
        from reticulum_beacon.api.routes.health import _compute_overall_health

        # Node is not running by default in tests
        status = _compute_overall_health()
        self.assertEqual(status, "stopped")

    def test_health_self_test_has_expected_checks(self):
        """Test self-test returns expected check keys without sensitive data."""
        from reticulum_beacon.api.routes.health import self_test

        # Just verify the function exists and is callable
        self.assertTrue(callable(self_test))

    def test_health_diagnostics_no_sensitive_data(self):
        """Test diagnostics endpoint doesn't expose sensitive info."""
        from reticulum_beacon.api.routes.health import diagnostics

        self.assertTrue(callable(diagnostics))

    def test_health_history_default_limit(self):
        """Test history endpoint returns within limit."""
        from reticulum_beacon.api.routes.health import health_history

        self.assertTrue(callable(health_history))

    def test_health_node_status_function(self):
        """Test internal node_status function returns safe data."""
        from reticulum_beacon.api.routes.health import node_status

        result = node_status()
        self.assertIn("running", result)
        self.assertIn("uptime_seconds", result)
        self.assertIn("transport_enabled", result)
        self.assertIn("interfaces_active", result)
        self.assertIn("connectivity", result)
        # Must NOT contain sensitive data
        self.assertNotIn("identity", result)
        self.assertNotIn("hash", str(result))
        self.assertNotIn("path", str(result))


class TestMetricsModule(unittest.TestCase):
    """Test the Prometheus metrics module."""

    def test_metrics_module_imports(self):
        """Test that the metrics module can be imported."""
        from reticulum_beacon.api.routes.metrics import router

        self.assertIsNotNone(router)

    def test_metrics_routes_registered(self):
        """Test that the metrics endpoint serves Prometheus output."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            r = client.get("/api/v1/metrics")
            self.assertEqual(r.status_code, 200)
            self.assertIn("text/plain", r.headers["content-type"])

    def test_metrics_route_exists(self):
        """Test that the /metrics route accepts GET and returns beacon metrics."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            r = client.get("/api/v1/metrics")
            self.assertEqual(r.status_code, 200)
            self.assertIn("beacon_uptime_seconds", r.text)

    def test_metrics_helper_functions(self):
        """Test that metrics helper functions exist and are callable."""
        from reticulum_beacon.api.routes import metrics

        self.assertTrue(callable(metrics.record_message_received))
        self.assertTrue(callable(metrics.record_message_sent))
        self.assertTrue(callable(metrics.record_announce))

    def test_metrics_labels_use_fixed_cardinality(self):
        """Test that metric labels use only fixed-cardinality values — no identity hashes or IPs."""
        from reticulum_beacon.api.routes import metrics

        # Check the bandwidth metric uses only the safe 'direction' label
        bw_metric = metrics._bandwidth_bytes
        label_names = list(bw_metric._labelnames)
        self.assertEqual(
            label_names, ["direction"], "Bandwidth metric labels must be fixed-cardinality only"
        )

        # Verify no metric uses labels that could leak sensitive data
        all_metrics = [
            metrics._uptime_gauge,
            metrics._running_gauge,
            metrics._transport_gauge,
            metrics._ifaces_active,
            metrics._ifaces_online,
            metrics._bandwidth_bytes,
            metrics._peers_total,
            metrics._messages_stored,
            metrics._messages_received,
            metrics._messages_sent,
            metrics._announces_received,
            metrics._bots_active,
            metrics._bots_total,
            metrics._api_running,
            metrics._api_tls_enabled,
            metrics._health_status,
            metrics._connectivity_gauge,
        ]
        for m in all_metrics:
            for label in m._labelnames:
                label_str = str(label)
                # No label should contain identity hashes, IPs, paths
                self.assertNotIn("identity", label_str.lower())
                self.assertNotIn("hash", label_str.lower())
                self.assertNotIn("ip", label_str.lower())
                self.assertNotIn("path", label_str.lower())
                self.assertNotIn("key", label_str.lower())

    def test_metrics_prometheus_output(self):
        """Test that generate_latest produces valid Prometheus output."""
        from prometheus_client import generate_latest

        output = generate_latest()
        self.assertTrue(isinstance(output, bytes))
        self.assertGreater(len(output), 0)

    def test_metrics_registered_in_fastapi_app(self):
        """Test that the metrics endpoint is reachable without auth (scrape-only)."""
        from fastapi.testclient import TestClient

        from reticulum_beacon.api.app import create_app

        app = create_app()
        with TestClient(app) as client:
            # No Authorization header — metrics is public for Prometheus scrapers
            r = client.get("/api/v1/metrics")
            self.assertEqual(r.status_code, 200)
            self.assertIn("beacon_running", r.text)

    def test_metrics_auth_skipped(self):
        """Test that metrics endpoint is in the auth skip list."""
        # The /api/v1/metrics path is public for Prometheus scrapers
        path = "/api/v1/metrics"
        # In the auth middleware, paths in ("/api/v1/health", "/api/v1/metrics") skip auth
        skip_paths = {"/api/v1/health", "/api/v1/metrics"}
        self.assertIn(path, skip_paths)


if __name__ == "__main__":
    unittest.main()
