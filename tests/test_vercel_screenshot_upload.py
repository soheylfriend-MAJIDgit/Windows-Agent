from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import manager_client


class VercelScreenshotUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old = {
            "queue": manager_client.SCREENSHOT_QUEUE_DIR,
            "manifests": manager_client.SCREENSHOT_MANIFEST_DIR,
            "blocked": manager_client._screenshot_auth_blocked_key,
            "api": manager_client._api_ref,
            "auth_until": manager_client._auth_blocked_until,
            "invalid_fp": manager_client._auth_blocked_agent_key_fingerprint,
            "invalid_until": manager_client._auth_blocked_agent_key_until,
            "blocked_ops": manager_client._auth_blocked_operations,
        }
        manager_client.SCREENSHOT_QUEUE_DIR = self.root / "screenshot_uploads"
        manager_client.SCREENSHOT_MANIFEST_DIR = manager_client.SCREENSHOT_QUEUE_DIR / "queue"
        manager_client._screenshot_auth_blocked_key = ""
        manager_client._api_ref = None
        manager_client._auth_blocked_until = 0
        manager_client._auth_blocked_agent_key_fingerprint = ""
        manager_client._auth_blocked_agent_key_until = 0
        manager_client._auth_blocked_operations = {}

    def tearDown(self) -> None:
        manager_client.SCREENSHOT_QUEUE_DIR = self.old["queue"]
        manager_client.SCREENSHOT_MANIFEST_DIR = self.old["manifests"]
        manager_client._screenshot_auth_blocked_key = self.old["blocked"]
        manager_client._api_ref = self.old["api"]
        manager_client._auth_blocked_until = self.old["auth_until"]
        manager_client._auth_blocked_agent_key_fingerprint = self.old["invalid_fp"]
        manager_client._auth_blocked_agent_key_until = self.old["invalid_until"]
        manager_client._auth_blocked_operations = self.old["blocked_ops"]
        self.temp.cleanup()

    def make_job(self, body: bytes = b"fake-png-bytes") -> tuple[dict, Path]:
        folder = manager_client.SCREENSHOT_QUEUE_DIR / "cmd_test"
        folder.mkdir(parents=True, exist_ok=True)
        image = folder / "shot.png"
        image.write_bytes(body)
        queued = manager_client._enqueue_screenshot(
            image, "cmd_test", "exec_test", "agent_test", "prompt_submitted",
            "shot.png", "2026-10-31T10:00:00.000Z", 120, 80,
        )
        manifest_path = next(iter(manager_client._screenshot_manifest_files()))
        return json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path

    def test_legacy_url_maps_to_vercel_and_rejects_secret_bearing_urls(self) -> None:
        self.assertEqual(manager_client.normalize_base_url(
            "https://windows-agent-management-cloudflare.soheylfriend.workers.dev/api/agent"),
            "https://windows-agent-management.vercel.app/api/agent")
        self.assertEqual(manager_client.normalize_base_url(
            "https://user:pass@example.test/api/agent?key=secret"), manager_client.DEFAULT_BASE_URL)
        self.assertEqual(manager_client.DEFAULT_BASE_URL, "https://windows-agent-management.vercel.app/api/agent")

    def test_http_401_prevents_fast_retry_with_same_key(self) -> None:
        with patch.object(manager_client, "_request_once", return_value=(False, 401, {"error": "invalid"}, False)) as request:
            self.assertEqual(manager_client._http_json("GET", "https://windows-agent-management.vercel.app/api/agent/connection-test",
                                                        "invalid-agent-key")[1], 401)
            blocked = manager_client._http_json("GET", "https://windows-agent-management.vercel.app/api/agent/connection-test",
                                                "invalid-agent-key")
        self.assertEqual(blocked[1], 401)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(blocked[2]["error"]["code"], "auth_retry_blocked")

    def test_legacy_secret_is_resealed_once_to_official_endpoint_without_key_change(self) -> None:
        secret_file = self.root / "manager_secret.bin"
        old_payload = {"base_url": "https://windows-agent-management-cloudflare.soheylfriend.workers.dev/api/agent",
                       "agent_key": "wam_agent_secret_value", "agent_id": "stable-agent"}
        encrypted = b"sealed:" + json.dumps(old_payload).encode("utf-8")
        secret_file.write_bytes(encrypted)
        manager_client._runtime_info.pop("migration_notice", None)
        def seal(raw: bytes) -> bytes: return b"sealed:" + raw
        def unseal(raw: bytes) -> bytes: return raw.removeprefix(b"sealed:")
        with patch.object(manager_client, "SECRET_FILE", secret_file), \
             patch.object(manager_client, "STATE_DIR", self.root), \
             patch.object(manager_client, "dpapi_encrypt", side_effect=seal), \
             patch.object(manager_client, "dpapi_decrypt", side_effect=unseal):
            cfg = manager_client.load_secret()
            migrated_raw = unseal(secret_file.read_bytes())
        self.assertEqual(cfg["base_url"], manager_client.DEFAULT_BASE_URL)
        self.assertEqual(cfg["agent_key"], old_payload["agent_key"])
        self.assertEqual(json.loads(migrated_raw)["base_url"], manager_client.DEFAULT_BASE_URL)
        self.assertEqual(manager_client._runtime_info.get("migration_notice"),
                         "آدرس قدیمی Cloudflare با حفظ کلید رمز‌شده به Vercel منتقل شد.")

    def test_heartbeat_reports_vercel_capabilities_and_drive_false(self) -> None:
        payload = manager_client._build_heartbeat_payload(None, "agent_test")
        self.assertEqual(payload["state"]["manager_base"], "vercel")
        self.assertFalse(payload["state"]["drive"])
        self.assertTrue(payload["capabilities"]["vercel_blob_screenshot_upload"])
        self.assertFalse(payload["capabilities"]["google_drive_artifacts"])
        self.assertTrue(payload["capabilities"]["database_automations"])

    def test_multipart_request_contains_auth_and_file_without_json_encoding(self) -> None:
        class Response:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def read(self, _size=-1): return b'{"ok":true}'
        class Opener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return Response()
        opener = Opener()
        file_path = self.root / "capture.png"
        file_path.write_bytes(b"PNG-CONTENT")
        with patch.object(manager_client.urllib.request, "build_opener", return_value=opener), \
             patch.object(manager_client, "_system_proxy", return_value=None):
            code, response = manager_client._http_multipart_file(
                "https://windows-agent-management.vercel.app/api/agent/screenshots",
                "test-agent-secret", {"commandId": "cmd_test", "stage": "prompt_submitted"}, file_path)
        self.assertEqual(code, 201)
        self.assertTrue(response["ok"])
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer test-agent-secret")
        self.assertIn(b'name="commandId"', opener.request.data)
        self.assertIn(b'name="file"; filename="capture.png"', opener.request.data)
        self.assertIn(b"PNG-CONTENT", opener.request.data)
        self.assertIn("multipart/form-data; boundary=", opener.request.get_header("Content-type"))

    def test_success_requires_http_201_and_persists_idempotent_result(self) -> None:
        job, manifest = self.make_job()
        cfg = {"base_url": "https://manager.example/api/agent", "agent_key": "valid-agent-key", "agent_id": "agent_test"}
        success = (201, {"ok": True, "screenshot": {"id": "shot_123", "contentUrl": "/api/screenshots/shot_123/content"}})
        with patch.object(manager_client, "load_secret", return_value=cfg), \
             patch.object(manager_client, "_screenshot_upload_once", return_value=success), \
             patch.object(manager_client, "_http_json", return_value=(True, 200, {"ok": True})):
            manager_client._process_screenshot_job(manifest)
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "succeeded")
        self.assertEqual(saved["screenshotId"], "shot_123")
        self.assertEqual(saved["contentUrl"], "/api/screenshots/shot_123/content")
        self.assertFalse(Path(job["file"]).exists())

        duplicate = self.root / "duplicate.png"
        duplicate.write_bytes(b"fake-png-bytes")
        result = manager_client._enqueue_screenshot(duplicate, "cmd_test", "exec_test", "agent_test",
                                                     "prompt_submitted", "shot.png", "2026-10-31T10:00:00Z", 120, 80)
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["screenshotId"], "shot_123")

    def test_non_201_success_body_is_not_accepted(self) -> None:
        _job, manifest = self.make_job()
        cfg = {"base_url": "https://manager.example/api/agent", "agent_key": "valid-agent-key"}
        with patch.object(manager_client, "load_secret", return_value=cfg), \
             patch.object(manager_client, "_screenshot_upload_once", return_value=(200, {"ok": True, "screenshot": {"id": "shot_bad", "contentUrl": "/api/screenshots/shot_bad/content"}})), \
             patch.object(manager_client, "_http_json", return_value=(True, 200, {"ok": True})):
            manager_client._process_screenshot_job(manifest)
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "failed_permanent")
        self.assertNotIn("screenshotId", saved)

    def test_transient_failure_uses_five_second_backoff(self) -> None:
        _job, manifest = self.make_job()
        cfg = {"base_url": "https://manager.example/api/agent", "agent_key": "valid-agent-key"}
        with patch.object(manager_client, "load_secret", return_value=cfg), \
             patch.object(manager_client, "_screenshot_upload_once", return_value=(503, {"error": {"code": "temporary"}})), \
             patch.object(manager_client, "_http_json", return_value=(True, 200, {"ok": True})), \
             patch.object(manager_client.time, "time", return_value=1_000.0):
            manager_client._process_screenshot_job(manifest)
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "retry")
        self.assertEqual(saved["attempts"], 1)
        self.assertEqual(saved["nextAttemptAt"], 1_005.0)

    def test_restart_recovers_in_flight_upload_manifest_without_replaying_command(self) -> None:
        _job, manifest = self.make_job()
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        saved.update(status="uploading", attempts=1, nextAttemptAt=9999999999)
        manager_client._atomic_json(manifest, saved)
        manager_client._recover_uploading_screenshot_jobs()
        recovered = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(recovered["status"], "queued")
        self.assertEqual(recovered["attempts"], 1)
        self.assertEqual(recovered["commandId"], "cmd_test")
        self.assertTrue(Path(recovered["file"]).is_file())

    def test_401_blocks_same_key_without_retry(self) -> None:
        _job, manifest = self.make_job()
        cfg = {"base_url": "https://manager.example/api/agent", "agent_key": "invalid-agent-key"}
        with patch.object(manager_client, "load_secret", return_value=cfg), \
             patch.object(manager_client, "_screenshot_upload_once", return_value=(401, {"error": {"code": "invalid_key"}})) as upload, \
             patch.object(manager_client, "_http_json", return_value=(True, 200, {"ok": True})):
            manager_client._process_screenshot_job(manifest)
            manager_client._process_screenshot_job(manifest)
        self.assertEqual(upload.call_count, 1)
        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["status"], "auth_blocked")

    def test_413_reduces_once_and_retries_only_the_reduced_image(self) -> None:
        _job, manifest = self.make_job(b"small-original-image")
        cfg = {"base_url": "https://manager.example/api/agent", "agent_key": "valid-agent-key"}
        reduced = self.root / "reduced.jpg"
        reduced.write_bytes(b"small-jpeg")
        def normalize(_path, target_bytes):
            self.assertLess(target_bytes, manager_client.SCREENSHOT_SAFE_MAX_BYTES)
            return reduced, 60, 40
        replies = [(413, {"error": {"code": "too_large"}}),
                   (201, {"ok": True, "screenshot": {"id": "shot_small", "contentUrl": "/api/screenshots/shot_small/content"}})]
        with patch.object(manager_client, "load_secret", return_value=cfg), \
             patch.object(manager_client, "_normalize_screenshot", side_effect=normalize), \
             patch.object(manager_client, "_screenshot_upload_once", side_effect=replies) as upload, \
             patch.object(manager_client, "_http_json", return_value=(True, 200, {"ok": True})):
            manager_client._process_screenshot_job(manifest)
        self.assertEqual(upload.call_count, 2)
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertTrue(saved["resizeRetried"])
        self.assertEqual(saved["status"], "succeeded")
        self.assertEqual(saved["screenshotId"], "shot_small")


if __name__ == "__main__":
    unittest.main()
