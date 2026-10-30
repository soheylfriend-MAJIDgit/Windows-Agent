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
            "active_command_id": manager_client._active_command_id,
            "claim_in_progress": manager_client._claim_in_progress,
            "emergency_inflight": manager_client._emergency_control_inflight,
            "emergency_gate": manager_client._emergency_control_gate.is_set(),
        }
        manager_client.STATE_DIR = self.root
        manager_client.EXECUTION_REGISTRY_FILE = self.registry_file
        manager_client._execution_registry_loaded = True
        manager_client._execution_records = {}
        manager_client._process_handles = {}
        manager_client._command_cancel_events = {}
        manager_client._active_command_id = None
        manager_client._claim_in_progress = False
        manager_client._emergency_control_inflight = set()
        manager_client._emergency_control_gate.clear()

    def tearDown(self) -> None:
        manager_client.STATE_DIR = self.saved["STATE_DIR"]
        manager_client.EXECUTION_REGISTRY_FILE = self.saved["EXECUTION_REGISTRY_FILE"]
        manager_client._execution_registry_loaded = self.saved["loaded"]
        manager_client._execution_records = self.saved["records"]
        manager_client._process_handles = self.saved["handles"]
        manager_client._command_cancel_events = self.saved["events"]
        manager_client._active_command_id = self.saved["active_command_id"]
        manager_client._claim_in_progress = self.saved["claim_in_progress"]
        manager_client._emergency_control_inflight = self.saved["emergency_inflight"]
        manager_client._emergency_control_gate.set() if self.saved["emergency_gate"] else manager_client._emergency_control_gate.clear()
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

    def test_tree_snapshot_keeps_owned_child_after_parent_exits(self) -> None:
        manager_client.register_execution("cmd-child", "نمونه", "دفترچه", status="running", pid=101,
                                          process_start_marker=1.0,
                                          owned_processes=[{"pid": 101, "start_marker": 1.0},
                                                           {"pid": 202, "parent_pid": 101, "start_marker": 2.0}])
        with (patch.object(manager_client, "_marker_matches", side_effect=lambda pid, marker: int(pid) == 202),
              patch.object(manager_client, "_owned_descendants", return_value=[])):
            children = manager_client.snapshot_execution_tree("cmd-child", 101, 1.0)
        self.assertEqual(children, [202])
        row = next(r for r in manager_client.get_execution_registry() if r["execution_id"] == "cmd-child")
        self.assertEqual(row["status"], "monitoring")
        self.assertEqual(row["child_pids"], [202])

    def test_emergency_stop_capability_is_advertised_and_empty_registry_is_verified(self) -> None:
        payload = manager_client._build_heartbeat_payload(None, "test-agent")
        self.assertTrue(payload["capabilities"]["emergency_stop_all"])
        result = manager_client.request_stop_all_executions("آزمون registry خالی", wait=True, timeout_seconds=1)
        self.assertTrue(result["verified"])
        self.assertEqual(result["registryActiveCount"], 0)
        self.assertEqual(result["remainingPids"], [])
        self.assertIn("Registry بررسی شد", result["message"])

    def test_successful_heartbeat_dispatches_emergency_control(self) -> None:
        control = {"id": "ctl_heartbeat", "action": "stop_all_executions",
                   "resultEndpoint": "/api/agent/controls/ctl_heartbeat"}
        with (patch.object(manager_client, "_network_preflight_ok", return_value=False),
              patch.object(manager_client, "_http_json", return_value=(True, 200, {"emergencyControl": control})),
              patch.object(manager_client, "_queue_emergency_control", return_value=True) as queue_control):
            ok, code, _ = manager_client.send_heartbeat_once(None, {
                "base_url": "https://manager.example/api/agent", "agent_key": "test-agent-key", "agent_id": "test-agent"
            })
        self.assertTrue(ok)
        self.assertEqual(code, 200)
        queue_control.assert_called_once_with(None, {
            "base_url": "https://manager.example/api/agent", "agent_key": "test-agent-key", "agent_id": "test-agent"
        }, control)

    def test_emergency_result_endpoint_is_same_origin_and_bound_to_control_id(self) -> None:
        control = {"id": "ctl_test-1", "resultEndpoint": "/api/agent/controls/ctl_test-1"}
        self.assertEqual(manager_client._emergency_result_url("https://manager.example/api/agent", control),
                         "https://manager.example/api/agent/controls/ctl_test-1")
        self.assertIsNone(manager_client._emergency_result_url("https://manager.example/api/agent",
                                                               {**control, "resultEndpoint": "https://evil.example/steal"}))
        self.assertIsNone(manager_client._emergency_result_url("https://manager.example/api/agent",
                                                               {**control, "resultEndpoint": "/api/agent/controls/other"}))

    def test_emergency_result_is_persisted_as_completed_only_after_http_success(self) -> None:
        control = {"id": "ctl_result", "action": "stop_all_executions",
                   "resultEndpoint": "/api/agent/controls/ctl_result"}
        result = {"verified": True, "remainingPids": [], "message": "Registry بررسی شد؛ اجرای فعالی وجود ندارد."}
        manager_client._write_emergency_state({"schema": 1, "controls": {"ctl_result": {
            "control": control, "status": "result_pending", "result": {"status": "succeeded", "result": result}
        }}})
        cfg = {"base_url": "https://manager.example/api/agent", "agent_key": "test-agent-key"}
        with patch.object(manager_client, "_http_json", return_value=(False, 503, {"error": "offline"})):
            self.assertFalse(manager_client._post_emergency_result(None, cfg, "ctl_result"))
        pending = manager_client._read_emergency_state()["controls"]["ctl_result"]
        self.assertEqual(pending["status"], "result_pending")
        with patch.object(manager_client, "_http_json", return_value=(True, 200, {"ok": True})) as post:
            self.assertTrue(manager_client._post_emergency_result(None, cfg, "ctl_result"))
        self.assertEqual(post.call_args.args[0:2], ("POST", "https://manager.example/api/agent/controls/ctl_result"))
        self.assertEqual(manager_client._read_emergency_state()["controls"]["ctl_result"]["status"], "completed")

    def test_emergency_worker_posts_verified_empty_registry_result(self) -> None:
        control = {"id": "ctl_empty", "action": "stop_all_executions", "reason": "توقف آزمایشی",
                   "requestedAt": "2026-10-30T18:00:00Z", "resultEndpoint": "/api/agent/controls/ctl_empty"}
        manager_client._write_emergency_state({"schema": 1, "controls": {"ctl_empty": {
            "control": control, "status": "processing", "attempts": 0
        }}})
        class FakeApi:
            busy = None
            def __init__(self): self.messages = []
            def prepare_emergency_stop_all(self, reason, control_id): self.messages.append("received")
            def set_emergency_control_status(self, message): self.messages.append(message)
            def log(self, message): self.messages.append(message)
        api = FakeApi()
        cfg = {"base_url": "https://manager.example/api/agent", "agent_key": "test-agent-key"}
        verified = {"verified": True, "requested": 0, "stopped": 0, "failed": 0,
                    "registryActiveCount": 0, "activeExecutionIds": [], "remainingPids": [],
                    "message": "Registry بررسی شد؛ اجرای فعالی وجود ندارد."}
        with (patch.object(manager_client, "request_local_cancel") as cancel,
              patch.object(manager_client, "request_stop_all_executions", return_value=verified),
              patch.object(manager_client, "_http_json", return_value=(True, 200, {"ok": True})) as post):
            manager_client._emergency_control_worker(api, cfg, "ctl_empty")
        cancel.assert_called_once_with("توقف آزمایشی")
        self.assertEqual(post.call_args.args[0:2], ("POST", "https://manager.example/api/agent/controls/ctl_empty"))
        self.assertEqual(post.call_args.args[3], {"status": "succeeded", "result": verified})
        self.assertEqual(manager_client._read_emergency_state()["controls"]["ctl_empty"]["status"], "completed")
        self.assertFalse(manager_client._emergency_control_gate.is_set())

    def test_duplicate_emergency_control_id_starts_only_one_worker(self) -> None:
        started = []
        class DummyThread:
            def __init__(self, target=None, args=(), **kwargs): self.target, self.args = target, args
            def start(self): started.append((self.target, self.args))
        control = {"id": "ctl_idempotent", "action": "stop_all_executions", "resultEndpoint": "/api/agent/controls/ctl_idempotent"}
        cfg = {"base_url": "https://manager.example/api/agent", "agent_key": "test-agent-key"}
        with patch.object(manager_client.threading, "Thread", DummyThread):
            self.assertTrue(manager_client._queue_emergency_control(None, cfg, control))
            self.assertFalse(manager_client._queue_emergency_control(None, cfg, control))
        self.assertEqual(len(started), 1)
        saved = json.loads((self.root / "emergency_control_state.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["controls"]["ctl_idempotent"]["status"], "processing")

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
