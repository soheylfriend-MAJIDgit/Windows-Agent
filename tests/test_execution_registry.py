from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import manager_client


class ExecutionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry_file = self.root / "execution_registry.json"
        self.saved = {
            "STATE_DIR": manager_client.STATE_DIR,
            "EXECUTION_REGISTRY_FILE": manager_client.EXECUTION_REGISTRY_FILE,
            "loaded": manager_client._execution_registry_loaded,
            "records": manager_client._execution_records,
            "handles": manager_client._process_handles,
            "events": manager_client._command_cancel_events,
        }
        manager_client.STATE_DIR = self.root
        manager_client.EXECUTION_REGISTRY_FILE = self.registry_file
        manager_client._execution_registry_loaded = True
        manager_client._execution_records = {}
        manager_client._process_handles = {}
        manager_client._command_cancel_events = {}

    def tearDown(self) -> None:
        manager_client.STATE_DIR = self.saved["STATE_DIR"]
        manager_client.EXECUTION_REGISTRY_FILE = self.saved["EXECUTION_REGISTRY_FILE"]
        manager_client._execution_registry_loaded = self.saved["loaded"]
        manager_client._execution_records = self.saved["records"]
        manager_client._process_handles = self.saved["handles"]
        manager_client._command_cancel_events = self.saved["events"]
        self.temp.cleanup()

    def test_registry_persists_status_and_process_identity(self) -> None:
        manager_client.register_execution(
            "cmd-test", "نمونه", "فرمان مدیریتی", status="running", stage="process_started",
            pid=1234, parent_pid=99, process_start_marker=42.5,
            owned_processes=[{"pid": 1234, "parent_pid": 99, "start_marker": 42.5}],
        )
        manager_client.update_execution("cmd-test", child_pids=[2345], remaining_pids=[])

        saved = json.loads(self.registry_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["cmd-test"]["pid"], 1234)
        self.assertEqual(saved["cmd-test"]["child_pids"], [2345])
        self.assertEqual(saved["cmd-test"]["status"], "running")

        manager_client._execution_registry_loaded = False
        manager_client._execution_records = {}
        row = manager_client.get_execution_registry()[0]
        self.assertEqual(row["execution_id"], "cmd-test")
        self.assertEqual(row["process_start_marker"], 42.5)

    def test_stop_request_sets_bound_cancel_event_and_records_stopping(self) -> None:
        manager_client.register_execution("cmd-stop", "نمونه", "فرمان مدیریتی", status="running")
        cancel = threading.Event()
        manager_client.bind_execution_cancel_event("cmd-stop", cancel)

        result = manager_client.request_execution_stop("cmd-stop", "توقف آزمایشی")

        self.assertTrue(result["ok"])
        self.assertTrue(cancel.is_set())
        row = next(r for r in manager_client.get_execution_registry() if r["execution_id"] == "cmd-stop")
        self.assertEqual(row["status"], "stopping")
        self.assertTrue(row["cancel_requested_at"])

    def test_unknown_or_terminal_execution_cannot_be_stopped(self) -> None:
        manager_client.register_execution("cmd-done", "نمونه", "فرمان مدیریتی", status="succeeded")
        self.assertFalse(manager_client.request_execution_stop("cmd-missing")["ok"])
        self.assertFalse(manager_client.request_execution_stop("cmd-done")["ok"])

    def test_live_process_without_verified_marker_is_never_reported_stopped(self) -> None:
        class RunningProcess:
            pid = 54321
            def poll(self): return None

        manager_client.register_execution("cmd-marker", "نمونه", "فرمان مدیریتی", status="running")
        with patch.object(manager_client, "_get_process_start_marker", return_value=None):
            result = manager_client._terminate_process_tree(RunningProcess(), None, 0.1, "cmd-marker", [])
        self.assertFalse(result["ok"])
        self.assertEqual(result["remaining"], [54321])
        row = next(r for r in manager_client.get_execution_registry() if r["execution_id"] == "cmd-marker")
        self.assertEqual(row["status"], "termination_failed")


if __name__ == "__main__":
    unittest.main()
