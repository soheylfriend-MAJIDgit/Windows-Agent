import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from drive_control_transport import DriveControlService, FILE_IDS


class FakeDrive:
    def __init__(self, command: dict, payload: bytes, control: str = "play"):
        self.command = command
        self.payload = payload
        self.control = control
        self.updates = {}
        self.reads = []
        self.fail_next_update = None

    def read_file(self, file_id, max_bytes):
        self.reads.append(file_id)
        if file_id == FILE_IDS["control"]:
            return self.control.encode(), {"version": "1", "md5Checksum": "c"}
        if file_id == FILE_IDS["command"]:
            return json.dumps(self.command).encode(), {"version": "3", "md5Checksum": "cmd"}
        if file_id == FILE_IDS["payload"]:
            return self.payload, {"version": "3", "md5Checksum": "payload"}
        if file_id == FILE_IDS["status"]:
            return b'{"commandId":"diag-bootstrap-001","controllerState":"waiting"}', {"version": "146", "md5Checksum": "status"}
        raise AssertionError(f"unexpected file read {file_id}")

    def update_file(self, file_id, data, mime):
        if self.fail_next_update == file_id:
            self.fail_next_update = None
            raise RuntimeError("simulated network failure")
        self.updates[file_id] = (data, mime)


def make_command(payload: bytes, command_id="direct-dialog-interaction-test", revision=3):
    now = datetime.now(timezone.utc)
    return {
        "protocolVersion": 1,
        "revision": revision,
        "commandId": command_id,
        "state": "ready",
        "action": "run_python",
        "issuedAt": now.isoformat().replace("+00:00", "Z"),
        "expiresAt": (now + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
        "payloadFile": "PAYLOAD.py",
        "payloadSha256": hashlib.sha256(payload).hexdigest(),
        "timeoutSeconds": 60,
    }


class DriveControlTests(unittest.TestCase):
    def test_pause_is_fail_closed_and_does_not_fetch_or_run_payload(self):
        payload = b"print('should not run')"
        drive = FakeDrive(make_command(payload), payload, control="pause")
        calls = []
        with tempfile.TemporaryDirectory() as td:
            service = DriveControlService(None, Path(td), drive=drive,
                runner=lambda *args: calls.append(args) or {"exitCode": 0})
            self.assertEqual(service.poll_once(), "pause")
        self.assertEqual(calls, [])
        self.assertNotIn(FILE_IDS["payload"], drive.reads)
        status = json.loads(drive.updates[FILE_IDS["status"]][0])
        self.assertEqual(status["controllerState"], "paused")

    def test_manual_local_mode_blocks_drive_payload_even_when_online_play(self):
        payload = b"print('requires local auto mode')"
        drive = FakeDrive(make_command(payload), payload, control="play")
        app_api = type("Api", (), {"settings": {"auto": False}, "log": lambda self, msg: None})()
        calls = []
        with tempfile.TemporaryDirectory() as td:
            service = DriveControlService(app_api, Path(td), drive=drive,
                runner=lambda *args: calls.append(args) or {"exitCode": 0})
            self.assertEqual(service.poll_once(), "waiting_confirmation")
        self.assertEqual(calls, [])
        status = json.loads(drive.updates[FILE_IDS["status"]][0])
        self.assertEqual(status["controllerState"], "waiting_confirmation")

    def test_valid_online_command_runs_once_and_updates_fixed_output_ids(self):
        payload = b"print('dialog payload')"
        command = make_command(payload)
        drive = FakeDrive(command, payload)
        calls = []
        def fake_runner(*args):
            calls.append(args)
            return {"exitCode": 0, "answers": {"answers": ["Yes"]}, "stdout": "done", "stderr": "", "startedAt": "t0", "finishedAt": "t1", "durationSeconds": 0.1}
        app_api = type("Api", (), {"settings": {"auto": True}, "log": lambda self, msg: None})()
        with tempfile.TemporaryDirectory() as td:
            service = DriveControlService(app_api, Path(td), drive=drive, runner=fake_runner)
            self.assertEqual(service.poll_once(), "completed")
            self.assertEqual(service.poll_once(), "already_processed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], payload)
        self.assertTrue({FILE_IDS["status"], FILE_IDS["result"], FILE_IDS["stdout"], FILE_IDS["stderr"]}.issubset(drive.updates))
        result = json.loads(drive.updates[FILE_IDS["result"]][0])
        self.assertEqual(result["commandId"], command["commandId"])
        self.assertEqual(result["revision"], 3)
        self.assertEqual(result["answers"]["answers"], ["Yes"])

    def test_expired_command_is_rejected_without_running(self):
        payload = b"print('expired must not run')"
        command = make_command(payload)
        now = datetime.now(timezone.utc)
        command["issuedAt"] = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        command["expiresAt"] = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        drive = FakeDrive(command, payload)
        calls = []
        app_api = type("Api", (), {"settings": {"auto": True}, "log": lambda self, msg: None})()
        with tempfile.TemporaryDirectory() as td:
            service = DriveControlService(app_api, Path(td), drive=drive,
                runner=lambda *args: calls.append(args) or {"exitCode": 0})
            self.assertEqual(service.poll_once(), "rejected")
        self.assertEqual(calls, [])
        status = json.loads(drive.updates[FILE_IDS["status"]][0])
        self.assertEqual(status["controllerState"], "rejected")

    def test_outbox_retries_upload_without_replaying_payload(self):
        payload = b"print('one execution only')"
        drive = FakeDrive(make_command(payload), payload)
        drive.fail_next_update = FILE_IDS["result"]
        calls = []
        app_api = type("Api", (), {"settings": {"auto": True}, "log": lambda self, msg: None})()
        with tempfile.TemporaryDirectory() as td:
            service = DriveControlService(app_api, Path(td), drive=drive,
                runner=lambda *args: calls.append(args) or {"exitCode": 0, "stdout": "ok", "stderr": ""})
            with self.assertRaises(RuntimeError):
                service.poll_once()
            self.assertTrue((Path(td) / "drive_control_outbox.bin").is_file())
            self.assertEqual(service.poll_once(), "already_processed")
            self.assertFalse((Path(td) / "drive_control_outbox.bin").exists())
        self.assertEqual(len(calls), 1)
        self.assertIn(FILE_IDS["result"], drive.updates)

    def test_bad_hash_is_rejected_without_running_or_replay(self):
        payload = b"print('safe')"
        command = make_command(payload)
        command["payloadSha256"] = "0" * 64
        drive = FakeDrive(command, payload)
        calls = []
        with tempfile.TemporaryDirectory() as td:
            service = DriveControlService(None, Path(td), drive=drive,
                runner=lambda *args: calls.append(args) or {"exitCode": 0})
            self.assertEqual(service.poll_once(), "rejected")
            self.assertEqual(service.poll_once(), "already_processed")
        self.assertEqual(calls, [])
        status = json.loads(drive.updates[FILE_IDS["status"]][0])
        self.assertEqual(status["controllerState"], "rejected")


if __name__ == "__main__":
    unittest.main()
