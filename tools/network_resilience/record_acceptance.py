# -*- coding: utf-8 -*-
"""Windows-only operator recorder for live Network Resilience acceptance.

This tool is independent of the network_resilience Heartbeat capability. It does not
run Arena, click, type, change adapters, or send a prompt. The operator performs the
live test scenario described in acceptance_scenario.md, then records measured results.
A readiness marker is written only if every required result passes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = 1
REQUIRED_TESTS = (
    "drop_before_ui",
    "waited_full_cycle",
    "zero_ui_actions_offline",
    "safe_resume",
    "single_prompt_send",
    "no_false_no_progress",
    "unrecoverable_failed_cleanly",
    "local_cancel_under_2s",
)


def state_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return base / "Windows-Agent"


def report_dir() -> Path:
    # Match the app's configured Google Drive logs path, including its safe Desktop\\logs fallback.
    repo = str(Path(__file__).resolve().parents[2])
    if repo not in sys.path:
        sys.path.insert(0, repo)
    import app
    root, _drive_used = app.resolve_report_dir()
    return Path(root) / "network_resilience_tests"


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(prompt + " [Y/N]: ").strip().casefold()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please enter Y or N.")


def ask_float(prompt: str, minimum: float = 0.0) -> float:
    while True:
        try:
            value = float(input(prompt).strip())
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"Enter a number greater than or equal to {minimum}.")


def ask_int(prompt: str, minimum: int = 0) -> int:
    while True:
        try:
            value = int(input(prompt).strip())
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"Enter an integer greater than or equal to {minimum}.")


def read_build(repo: Path) -> tuple[str, str]:
    version = (repo / "version.txt").read_text(encoding="utf-8").strip()
    stamp_file = state_dir() / "build_stamp.json"
    commit = ""
    try:
        stamp = json.loads(stamp_file.read_text(encoding="utf-8"))
        commit = str(stamp.get("version") or "")
    except Exception:
        pass
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
        commit = "unknown"
    return version, commit


def write_json_atomic(path: Path, payload: dict) -> bytes:
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)
    return raw


def rollback() -> int:
    root = state_dir()
    marker = root / "network_ready.json"
    try:
        marker.unlink(missing_ok=True)
    except OSError as exc:
        print(f"Could not remove readiness marker: {exc}")
        return 1
    try:
        reports = report_dir()
        if reports.exists():
            import shutil
            shutil.rmtree(reports)
    except Exception as exc:
        print(f"Marker removed, but report cleanup failed: {exc}")
        return 1
    print("Network Resilience readiness revoked. Heartbeat will report network_resilience=false.")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("--rollback", "--revoke"):
        return rollback()
    if sys.platform != "win32":
        print("This acceptance recorder must be run on the real Windows Agent.")
        return 2

    marker_path = state_dir() / "network_ready.json"
    try:
        state_dir().mkdir(parents=True, exist_ok=True)
        # Starting a fresh acceptance attempt revokes any prior readiness first.
        marker_path.unlink(missing_ok=True)
    except OSError as exc:
        print(f"Cannot revoke the previous readiness marker: {exc}")
        return 2

    repo = Path(__file__).resolve().parents[2]
    try:
        app_version, build_commit = read_build(repo)
    except Exception as exc:
        print(f"Cannot read current build identity: {exc}")
        return 2

    print("=" * 68)
    print("LIVE WINDOWS NETWORK RESILIENCE ACCEPTANCE - OPERATOR RECORDER")
    print(f"Build: {app_version} / {build_commit}")
    print("This tool does not trigger UI actions or send prompts.")
    print("Perform the documented test on a dedicated, harmless Arena test prompt first.")
    print("Enter measured observations only. Any failure prevents marker creation.")
    print("=" * 68)
    if not ask_yes_no("Did you run the complete live acceptance scenario on this Windows Agent build?"):
        print("No readiness marker written.")
        return 1

    checks: dict[str, bool] = {}
    checks["drop_before_ui"] = ask_yes_no("Was the Internet cut before the test job began any Arena UI interaction?")
    offline_s = ask_float("Measured continuous outage duration in seconds (must be >=60): ")
    checks["waited_full_cycle"] = offline_s >= 60.0
    action_count = ask_int("Count of job-generated click/key/Enter actions during the outage (must be 0): ")
    checks["zero_ui_actions_offline"] = action_count == 0
    checks["safe_resume"] = ask_yes_no("After reconnect, did the job continue from a safe checkpoint without blind Enter/click?")
    send_count = ask_int("Observed count of submitted test prompts for this run (must be exactly 1): ")
    checks["single_prompt_send"] = send_count == 1
    checks["no_false_no_progress"] = ask_yes_no("Did the command remain alive through the outage without a false no-progress stop?")
    final_status = input("Final status from the unrecoverable-operation test (type failed): ").strip().casefold()
    checks["unrecoverable_failed_cleanly"] = final_status == "failed"
    cancel_s = ask_float("Measured local-cancel-to-process-tree-stop time in seconds (must be <=2): ")
    checks["local_cancel_under_2s"] = cancel_s <= 2.0

    passed = all(checks.get(key) is True for key in REQUIRED_TESTS)
    observations = {
        "offlineSeconds": offline_s,
        "uiActionsDuringOutage": action_count,
        "promptSendCount": send_count,
        "unrecoverableFinalStatus": final_status,
        "localCancelSeconds": cancel_s,
        "attestation": "operator-entered measurements from a live Windows test; this recorder does not independently observe UI or network traffic",
    }
    report_id = uuid.uuid4().hex
    try:
        reports = report_dir()
        reports.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        print(f"Cannot access the configured Windows-Agent-DB\\logs report folder: {exc}")
        marker_path.unlink(missing_ok=True)
        return 2

    evidence_dir = reports / f"network_acceptance_{report_id}_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_files = {}
    total_evidence_bytes = 0
    print("\nProvide one Windows screenshot/log artifact for each criterion.")
    print("Use evidence saved under Windows-Agent-DB\\ScreenShots or logs when possible.")
    for key in REQUIRED_TESTS:
        while True:
            source = Path(input(f"Evidence file for {key} (full path): ").strip().strip('"')).expanduser()
            try:
                if source.is_symlink() or not source.is_file():
                    raise ValueError("not a regular file")
                size = source.stat().st_size
                if size <= 0 or size > 12 * 1024 * 1024 or total_evidence_bytes + size > 80 * 1024 * 1024:
                    raise ValueError("file must be 1 byte–12 MiB; total evidence limit is 80 MiB")
                suffix = source.suffix.lower()[:10]
                if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
                    suffix = ".bin"
                dest = evidence_dir / f"{key}{suffix}"
                shutil.copyfile(source, dest)
                digest = hashlib.sha256(dest.read_bytes()).hexdigest()
                evidence_files[key] = {
                    "file": f"{evidence_dir.name}/{dest.name}",
                    "sha256": digest,
                    "sizeBytes": size,
                }
                total_evidence_bytes += size
                break
            except (OSError, ValueError) as exc:
                print(f"Invalid evidence file: {exc}")

    report_name = f"network_acceptance_{report_id}.json"
    report_path = reports / report_name
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "reportId": report_id,
        "status": "passed" if passed else "failed",
        "platform": "win32",
        "appVersion": app_version,
        "buildCommit": build_commit,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "tests": checks,
        "observations": observations,
        "evidence": evidence_files,
    }
    report_bytes = write_json_atomic(report_path, report)

    marker_path = state_dir() / "network_ready.json"
    if not passed or build_commit == "unknown":
        marker_path.unlink(missing_ok=True)
        print("Acceptance failed or build commit is unknown. No network_ready.json was created.")
        print(f"Report saved for review: {report_path}")
        return 1

    marker = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "passed",
        "platform": "win32",
        "appVersion": app_version,
        "buildCommit": build_commit,
        "createdAt": report["createdAt"],
        "reportId": report_id,
        "tests": checks,
        "reportName": report_name,
        "reportSha256": hashlib.sha256(report_bytes).hexdigest(),
    }
    write_json_atomic(marker_path, marker)
    print("All required results were recorded as passing.")
    print(f"Marker created: {marker_path}")
    print("The next Heartbeat will still require a live authenticated Manager /connection-test preflight.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
