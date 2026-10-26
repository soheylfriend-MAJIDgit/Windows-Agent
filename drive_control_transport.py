# -*- coding: utf-8 -*-
"""Direct Google Drive control transport for the Windows interactive controller.

Google Drive Desktop is deliberately not used as a command source. OAuth is provisioned
manually by tools/drive_control/authorize.py and the authorized-user token is DPAPI-sealed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Any

DRIVE_API = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_CONTROL_FOLDER_ID = "1jOlamQWCNbr38-KgvOmA94CdWQwNg1OC"
POLL_SECONDS = 3.0
MAX_COMMAND_BYTES = 32 * 1024
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_CAPTURE_BYTES = 128 * 1024

# Fixed IDs are intentional: online command data cannot redirect the controller to another file.
FILE_IDS = {
    "command": "1ypV2HwqTSwXQhTRIYuEAuB080JIu-KaE",
    "payload": "1RFVLgm0p7RJuNhZJ48j8pwPR6WIMeiUs",
    "control": "1B9w519L3nCkAnwjnt1t98TE_ZZOQBvzg",
    "status": "1fXrUnxuZPdAcO3dtmR4bndSKYjl8SxZM",
    "result": "1wyyEFvFjHaAB-YgD8z2R9IxDJbNYtq_u",
    "stdout": "1_OTvRJTJsNAJ3fixxZLAYWa1Ph19XVye",
    "stderr": "1VLf0mElbvE-TuVSPG8Od2JbnubQLwdcX",
}
_TERMINAL = {"completed", "failed", "expired", "rejected", "stopped", "paused", "control_unreachable", "interrupted"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text() -> str:
    return _utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing timestamp")
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must contain a timezone")
    return parsed.astimezone(timezone.utc)


def _safe_message(text: str, limit: int = 1000) -> str:
    text = str(text or "")
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+", r"\1[redacted]", text)
    text = re.sub(r"(?i)\bya29\.[A-Za-z0-9._~-]+|\b1//[A-Za-z0-9_-]+", "[redacted-token]", text)
    text = re.sub(r"(?i)(access_token|refresh_token|client_secret|client_id)\s*[=:]\s*[^\s,;]+", r"\1=[redacted]", text)
    return text[-limit:]


class DriveAPI:
    """Small REST client: only the fixed Drive API origin and configured file IDs are used."""

    def __init__(self, token_file: Path):
        if sys.platform != "win32":
            raise RuntimeError("Direct Drive control is Windows-only.")
        self.token_file = token_file
        self._credentials = None
        self._session = None

    def _load_credentials(self):
        if self._credentials is not None:
            return self._credentials
        import manager_client
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        if not self.token_file.is_file():
            raise RuntimeError("Drive OAuth is not authorized; run tools/drive_control/authorize.bat first.")
        try:
            data = json.loads(manager_client.dpapi_decrypt(self.token_file.read_bytes()).decode("utf-8"))
            creds = Credentials.from_authorized_user_info(data)
        except Exception as exc:
            raise RuntimeError("Encrypted Drive OAuth data could not be opened; re-authorize locally.") from exc
        if not creds.valid:
            if not creds.refresh_token:
                raise RuntimeError("Drive OAuth refresh token is missing; re-authorize locally.")
            creds.refresh(Request())
            sealed = manager_client.dpapi_encrypt(creds.to_json().encode("utf-8"))
            tmp = self.token_file.with_suffix(".tmp")
            tmp.write_bytes(sealed)
            tmp.replace(self.token_file)
        self._credentials = creds
        return creds

    def _request(self, method: str, url: str, *, params: dict | None = None, body: bytes | None = None, mime: str | None = None) -> bytes:
        import requests
        creds = self._load_credentials()
        if not creds.valid:
            self._credentials = None
            creds = self._load_credentials()
        headers = {"Authorization": f"Bearer {creds.token}"}
        if mime:
            headers["Content-Type"] = mime
        try:
            response = requests.request(method, url, params=params, data=body, headers=headers, timeout=(3.05, 8.0))
        except requests.RequestException as exc:
            raise RuntimeError(f"Google Drive connection failed: {type(exc).__name__}") from exc
        if response.status_code in (401, 403):
            self._credentials = None
            raise RuntimeError(f"Google Drive authorization rejected (HTTP {response.status_code}); no command was run.")
        if not response.ok:
            raise RuntimeError(f"Google Drive API returned HTTP {response.status_code}.")
        return response.content

    def metadata(self, file_id: str) -> dict:
        if file_id not in FILE_IDS.values():
            raise ValueError("unapproved Drive file ID")
        raw = self._request("GET", f"{DRIVE_API}/{file_id}", params={"fields": "id,name,mimeType,modifiedTime,version,md5Checksum,size,parents,trashed", "supportsAllDrives": "true"})
        data = json.loads(raw.decode("utf-8"))
        if data.get("id") != file_id:
            raise RuntimeError("Drive returned a different file ID.")
        if data.get("trashed") or DRIVE_CONTROL_FOLDER_ID not in (data.get("parents") or []):
            raise RuntimeError("Configured Drive control file is trashed or outside the approved control folder.")
        return data

    def read_file(self, file_id: str, max_bytes: int) -> tuple[bytes, dict]:
        first = self.metadata(file_id)
        try:
            announced_size = int(first.get("size", "0"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Drive file size metadata is invalid.") from exc
        if announced_size > max_bytes:
            raise RuntimeError("Drive file exceeds the configured size limit.")
        raw = self._request("GET", f"{DRIVE_API}/{file_id}", params={"alt": "media", "supportsAllDrives": "true"})
        if len(raw) > max_bytes:
            raise RuntimeError("Drive file exceeds the configured size limit.")
        second = self.metadata(file_id)
        if str(first.get("version")) != str(second.get("version")) or first.get("md5Checksum") != second.get("md5Checksum"):
            raise RuntimeError("Drive file changed during download; retry on the next poll.")
        return raw, second

    def update_file(self, file_id: str, data: bytes, mime: str) -> None:
        if file_id not in (FILE_IDS["status"], FILE_IDS["result"], FILE_IDS["stdout"], FILE_IDS["stderr"]):
            raise ValueError("unapproved Drive output file ID")
        self.metadata(file_id)
        self._request("PATCH", f"{DRIVE_UPLOAD_API}/{file_id}", params={"uploadType": "media", "supportsAllDrives": "true"}, body=data, mime=mime)


class DriveControlService:
    def __init__(self, api, state_dir: Path, drive: Any | None = None, runner=None):
        self.app_api = api
        self.state_dir = Path(state_dir)
        self.token_file = self.state_dir / "drive_control_oauth.bin"
        self.state_file = self.state_dir / "drive_control_state.json"
        self.drive = drive or DriveAPI(self.token_file)
        self.runner = runner or self._run_payload
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_status: tuple[str, str, str] | None = None
        self._active_proc: subprocess.Popen | None = None
        self._instance_lock_file = None

    def _acquire_process_lock(self) -> bool:
        if sys.platform != "win32":
            return True
        self.state_dir.mkdir(parents=True, exist_ok=True)
        handle = open(self.state_dir / "drive_control.lock", "a+b")
        try:
            import msvcrt
            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            handle.close()
            return False
        self._instance_lock_file = handle
        return True

    def _release_process_lock(self) -> None:
        handle = self._instance_lock_file
        self._instance_lock_file = None
        if handle is None:
            return
        try:
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass

    def start(self) -> bool:
        if not self.token_file.is_file():
            return False
        with self._lock:
            if self._thread and self._thread.is_alive():
                return True
            if not self._acquire_process_lock():
                self._log("Another Windows Agent process owns the direct Drive controller lock.")
                return False
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="drive-control-direct", daemon=True)
            self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        proc = self._active_proc
        if proc and proc.poll() is None:
            self._terminate_tree(proc)

    def _log(self, message: str) -> None:
        if self.app_api is not None:
            try:
                self.app_api.log("Drive Control: " + _safe_message(message, 500))
            except Exception:
                pass

    def _load_state(self) -> dict:
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("processed"), list):
                return data
        except Exception:
            pass
        return {"processed": [], "inFlight": None}

    def _save_state(self, state: dict) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(self.state_file)

    def _publish_status(self, state: str, command_id: str | None, message: str, revision: int | None = None, force: bool = False) -> None:
        key = (state, command_id or "", str(revision or ""))
        if not force and key == self._last_status:
            return
        body = {
            "protocolVersion": 1,
            "controllerState": state,
            "commandId": command_id,
            "updatedAt": _utc_text(),
            "message": _safe_message(message, 1000),
        }
        if revision is not None:
            body["revision"] = revision
        raw = (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.drive.update_file(FILE_IDS["status"], raw, "application/json; charset=utf-8")
        self._last_status = key

    def _read_control(self) -> str:
        raw, _ = self.drive.read_file(FILE_IDS["control"], 256)
        control = raw.decode("utf-8-sig").strip().lower()
        if control not in {"play", "pause", "stop"}:
            raise RuntimeError("CONTROL.txt must contain exactly play, pause or stop.")
        return control

    def _read_command(self) -> tuple[dict, str]:
        raw, metadata = self.drive.read_file(FILE_IDS["command"], MAX_COMMAND_BYTES)
        try:
            command = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeError, ValueError) as exc:
            raise RuntimeError("COMMAND.json is not valid UTF-8 JSON.") from exc
        if not isinstance(command, dict):
            raise RuntimeError("COMMAND.json must contain an object.")
        return command, str(metadata.get("version") or "")

    def _validate_command(self, command: dict) -> tuple[str, int, int, bytes]:
        if command.get("protocolVersion") != 1 or command.get("state") != "ready" or command.get("action") != "run_python":
            raise ValueError("unsupported protocol, state, or action")
        command_id = command.get("commandId")
        revision = command.get("revision")
        if not isinstance(command_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", command_id):
            raise ValueError("invalid commandId")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ValueError("invalid revision")
        if command.get("payloadFile") != "PAYLOAD.py":
            raise ValueError("payloadFile must be the fixed PAYLOAD.py")
        expected_hash = str(command.get("payloadSha256") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError("invalid payload SHA-256")
        issued, expires = _parse_utc(command.get("issuedAt")), _parse_utc(command.get("expiresAt"))
        now = _utc_now()
        if issued.timestamp() > now.timestamp() + 300 or expires <= now or expires <= issued:
            raise ValueError("command is not currently valid")
        timeout_seconds = command.get("timeoutSeconds", 900)
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 5 <= timeout_seconds <= 3600:
            raise ValueError("timeoutSeconds is out of range")
        payload, _ = self.drive.read_file(FILE_IDS["payload"], MAX_PAYLOAD_BYTES)
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            raise ValueError("PAYLOAD.py SHA-256 does not match COMMAND.json")
        # Re-read the command after payload download to reject a changing envelope.
        check, _ = self._read_command()
        if check != command:
            raise RuntimeError("COMMAND.json changed while the payload was downloaded.")
        return command_id, revision, int(timeout_seconds), payload

    def _write_outbox(self, bundle: dict) -> None:
        import manager_client
        raw = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        sealed = manager_client.dpapi_encrypt(raw)
        target = self.state_dir / "drive_control_outbox.bin"
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(sealed)
        tmp.replace(target)

    def _flush_outbox(self) -> bool:
        target = self.state_dir / "drive_control_outbox.bin"
        if not target.is_file():
            return False
        import base64
        import manager_client
        bundle = json.loads(manager_client.dpapi_decrypt(target.read_bytes()).decode("utf-8"))
        self.drive.update_file(FILE_IDS["result"], base64.b64decode(bundle["resultB64"]), "application/json; charset=utf-8")
        self.drive.update_file(FILE_IDS["stdout"], base64.b64decode(bundle["stdoutB64"]), "text/plain; charset=utf-8")
        self.drive.update_file(FILE_IDS["stderr"], base64.b64decode(bundle["stderrB64"]), "text/plain; charset=utf-8")
        status = bundle["status"]
        state = self._load_state()
        key = f"{status['commandId']}:{status['revision']}"
        processed = [str(item) for item in state.get("processed", [])]
        if key not in processed:
            processed.append(key)
        state["processed"] = processed
        inflight = state.get("inFlight")
        if isinstance(inflight, dict) and inflight.get("key") == key:
            state["inFlight"] = None
        self._save_state(state)
        self._publish_status(status["state"], status["commandId"], status["message"], status.get("revision"), force=True)
        target.unlink(missing_ok=True)
        return True

    def poll_once(self) -> str:
        self._flush_outbox()
        control = self._read_control()
        if control != "play":
            self._publish_status("paused" if control == "pause" else "stopped", None, f"CONTROL.txt is {control}; no payload will start.")
            return control

        command, drive_version = self._read_command()
        raw_command_id = command.get("commandId")
        command_id = raw_command_id if isinstance(raw_command_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", raw_command_id) else ""
        raw_revision = command.get("revision")
        revision = raw_revision if type(raw_revision) is int and raw_revision >= 1 else None
        if command.get("state") != "ready":
            self._publish_status("waiting", command_id or None, "No ready command on Drive.", revision)
            return "waiting"
        if not command_id or revision is None:
            self._publish_status("rejected", None, "COMMAND.json has an invalid commandId or revision.", force=True)
            return "rejected"
        if self.app_api is not None and not bool((getattr(self.app_api, "settings", None) or {}).get("auto", False)):
            self._publish_status("waiting_confirmation", command_id or None, "Enable automatic mode locally before the Drive command can run.", revision)
            return "waiting_confirmation"

        state = self._load_state()
        key = f"{command_id}:{revision}"
        processed = [str(item) for item in state.get("processed", [])]
        prior_revisions = []
        for item in processed:
            prior_id, sep, prior_rev = item.rpartition(":")
            if sep and prior_id == command_id and prior_rev.isdigit():
                prior_revisions.append(int(prior_rev))
        if prior_revisions and revision <= max(prior_revisions) and key not in processed:
            state["processed"] = (processed + [key])
            self._save_state(state)
            self._publish_status("rejected", command_id, "Revision must strictly increase for an existing commandId.", revision, force=True)
            return "rejected"
        inflight = state.get("inFlight")
        if key in processed or (isinstance(inflight, dict) and inflight.get("key") == key):
            if isinstance(inflight, dict) and inflight.get("key") == key:
                self._publish_status("interrupted", command_id, "Controller restarted while this command was in flight; replay is blocked.", revision, force=True)
                state["processed"] = (processed + [key])
                state["inFlight"] = None
                self._save_state(state)
                return "interrupted"
            return "already_processed"

        # The receipt check and second CONTROL read close the local-mirror race before launch.
        online_status, _ = self.drive.read_file(FILE_IDS["status"], MAX_COMMAND_BYTES)
        try:
            prior_status = json.loads(online_status.decode("utf-8-sig"))
        except Exception:
            prior_status = {}
        if prior_status.get("commandId") == command_id and prior_status.get("revision") == revision:
            prior_state = prior_status.get("controllerState")
            if prior_state in _TERMINAL:
                state["processed"] = (processed + [key])
                self._save_state(state)
                return "already_terminal"
            if prior_state == "running":
                state["processed"] = (processed + [key])
                self._save_state(state)
                self._publish_status("interrupted", command_id, "Online status says this command was already running; replay is blocked.", revision, force=True)
                return "interrupted"

        try:
            command_id, revision, timeout_seconds, payload = self._validate_command(command)
        except ValueError as exc:
            state["processed"] = (processed + [key])
            self._save_state(state)
            self._publish_status("rejected", command_id, f"Command rejected: {_safe_message(str(exc), 300)}", revision, force=True)
            return "rejected"
        if self._read_control() != "play":
            self._publish_status("paused", command_id, "CONTROL.txt changed before launch; payload was not started.", revision, force=True)
            return "paused"

        state["inFlight"] = {"key": key, "commandId": command_id, "revision": revision, "driveVersion": drive_version, "startedAt": _utc_text()}
        self._save_state(state)
        self._publish_status("running", command_id, "Online command and SHA-256 verified; starting interactive payload.", revision, force=True)
        result = self.runner(payload, command_id, revision, timeout_seconds)

        finished_state = result.get("controllerState")
        if finished_state not in {"paused", "stopped", "control_unreachable"}:
            finished_state = "completed" if result.get("exitCode") == 0 else "failed"
        result_doc = {
            "protocolVersion": 1,
            "commandId": command_id,
            "revision": revision,
            "controllerState": finished_state,
            "startedAt": result.get("startedAt"),
            "finishedAt": result.get("finishedAt") or _utc_text(),
            "durationSeconds": result.get("durationSeconds"),
            "exitCode": result.get("exitCode"),
            "answers": result.get("answers"),
            "message": _safe_message(result.get("message") or ("Payload completed." if finished_state == "completed" else "Payload failed."), 1000),
        }
        import base64
        result_bytes = (json.dumps(result_doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        stdout_bytes = _safe_message(result.get("stdout", ""), MAX_CAPTURE_BYTES).encode("utf-8", errors="replace")
        stderr_bytes = _safe_message(result.get("stderr", ""), MAX_CAPTURE_BYTES).encode("utf-8", errors="replace")
        self._write_outbox({
            "resultB64": base64.b64encode(result_bytes).decode("ascii"),
            "stdoutB64": base64.b64encode(stdout_bytes).decode("ascii"),
            "stderrB64": base64.b64encode(stderr_bytes).decode("ascii"),
            "status": {"state": finished_state, "commandId": command_id, "revision": revision, "message": result_doc["message"]},
        })
        state = self._load_state()
        state["processed"] = [str(item) for item in state.get("processed", [])] + [key]
        state["inFlight"] = None
        self._save_state(state)
        self._flush_outbox()
        return finished_state

    def _run_payload(self, payload: bytes, command_id: str, revision: int, timeout_seconds: int) -> dict:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        started = _utc_text()
        began = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="drive_control_", dir=str(self.state_dir)) as tmp:
            work = Path(tmp)
            script = work / "PAYLOAD.py"
            script.write_bytes(payload)
            import manager_client
            env = {
                key: value for key, value in os.environ.items()
                if key.upper() not in manager_client.FORBIDDEN_ENV_KEYS
                and not key.upper().startswith(("WAM_AGENT_", "WINDOWS_AGENT_MANAGER_", "GOOGLE_", "OAUTH_"))
                and not any(marker in key.upper() for marker in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"))
            }
            env["DRIVE_CONTROL_FOLDER"] = str(work)
            env["DRIVE_CONTROL_COMMAND_ID"] = command_id
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
            kwargs = {"cwd": str(work), "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True, "encoding": "utf-8", "errors": "replace", "env": env}
            if flags:
                kwargs["creationflags"] = flags
            else:
                kwargs["start_new_session"] = True
            proc = subprocess.Popen([sys.executable, "-u", str(script)], **kwargs)
            self._active_proc = proc
            out_parts: list[str] = []
            err_parts: list[str] = []
            readers = [
                threading.Thread(target=self._drain, args=(proc.stdout, out_parts), daemon=True),
                threading.Thread(target=self._drain, args=(proc.stderr, err_parts), daemon=True),
            ]
            for reader in readers:
                reader.start()
            exit_code = None
            deadline = time.monotonic() + timeout_seconds
            next_control = time.monotonic() + POLL_SECONDS
            message = "Payload exited."
            controller_state = None
            while exit_code is None:
                try:
                    exit_code = proc.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    if self._stop.is_set():
                        self._terminate_tree(proc)
                        message = "Controller stopped the payload during shutdown."
                        controller_state = "stopped"
                        exit_code = proc.poll()
                    elif time.monotonic() >= deadline:
                        self._terminate_tree(proc)
                        message = "Payload timed out; process tree was terminated."
                        exit_code = proc.poll()
                    elif time.monotonic() >= next_control:
                        next_control = time.monotonic() + POLL_SECONDS
                        try:
                            control = self._read_control()
                        except Exception as exc:
                            self._terminate_tree(proc)
                            message = f"Online CONTROL check failed; payload stopped fail-closed ({type(exc).__name__})."
                            controller_state = "control_unreachable"
                            exit_code = proc.poll()
                        else:
                            if control != "play":
                                self._terminate_tree(proc)
                                message = f"Online CONTROL changed to {control}; payload stopped."
                                controller_state = "paused" if control == "pause" else "stopped"
                                exit_code = proc.poll()
                if exit_code is None and proc.poll() is not None:
                    exit_code = proc.returncode
            for reader in readers:
                reader.join(timeout=0.5)
            self._active_proc = None
            stdout = "".join(out_parts)[-MAX_CAPTURE_BYTES:]
            stderr = "".join(err_parts)[-MAX_CAPTURE_BYTES:]
            answers = self._extract_result(stdout, work / "INTERACTION_RESULT.json")
            return {
                "startedAt": started,
                "finishedAt": _utc_text(),
                "durationSeconds": round(time.monotonic() - began, 3),
                "exitCode": exit_code,
                "controllerState": controller_state,
                "answers": answers,
                "stdout": stdout,
                "stderr": stderr,
                "message": message,
            }

    @staticmethod
    def _drain(stream, output: list[str]) -> None:
        if stream is None:
            return
        for line in iter(stream.readline, ""):
            if sum(map(len, output)) < MAX_CAPTURE_BYTES * 2:
                output.append(line)
        try:
            stream.close()
        except Exception:
            pass

    @staticmethod
    def _extract_result(stdout: str, result_file: Path) -> Any:
        if result_file.is_file():
            try:
                raw = result_file.read_bytes()
                if len(raw) <= MAX_CAPTURE_BYTES:
                    return json.loads(raw.decode("utf-8"))
            except Exception:
                pass
        for line in reversed(stdout.splitlines()):
            if line.startswith("DIRECT_DIALOG_RESULT="):
                try:
                    return json.loads(line.split("=", 1)[1])
                except Exception:
                    break
        return None

    @staticmethod
    def _terminate_tree(proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=1.5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            try:
                import signal
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            proc.wait(timeout=0.25)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _loop(self) -> None:
        try:
            self._loop_body()
        finally:
            self._release_process_lock()

    def _loop_body(self) -> None:
        try:
            self._publish_status("waiting", None, "Direct online Drive polling is active; no local Drive mirror is used.", force=True)
        except Exception as exc:
            self._log(f"Could not publish startup status ({type(exc).__name__}).")
        delay = POLL_SECONDS
        while not self._stop.is_set():
            try:
                result = self.poll_once()
                delay = POLL_SECONDS
                if result not in ("waiting", "paused", "stopped", "already_processed", "already_terminal"):
                    self._log(f"command cycle: {result}")
                if result == "stopped":
                    self._stop.set()
                    break
            except Exception as exc:
                # Fail closed: a failed auth or Drive request can never launch a payload.
                self._log(f"poll failed; no payload launched ({type(exc).__name__}).")
                delay = min(60.0, max(POLL_SECONDS, delay * 2.0))
            self._stop.wait(delay)


_services: dict[int, DriveControlService] = {}
_services_lock = threading.Lock()


def start(api=None, state_dir: Path | None = None) -> bool:
    """Start only if a DPAPI-protected OAuth token was provisioned explicitly by the owner."""
    if sys.platform != "win32":
        return False
    if state_dir is None:
        import manager_client
        state_dir = manager_client.STATE_DIR
    key = id(api)
    with _services_lock:
        service = _services.get(key)
        if service is None:
            service = DriveControlService(api, Path(state_dir))
            _services[key] = service
    return service.start()


def stop(api=None) -> None:
    key = id(api)
    with _services_lock:
        service = _services.get(key)
    if service:
        service.stop()
