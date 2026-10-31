# -*- coding: utf-8 -*-
"""Read the current checkout's Git HEAD without requiring git.exe and write a LocalAppData stamp."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zlib
from datetime import datetime, timezone, timedelta

TEHRAN = timezone(timedelta(hours=3, minutes=30))


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    day = 365 * gy2 + (gy2 + 3)//4 - (gy2 + 99)//100 + (gy2 + 399)//400
    day += g_d_m[gm2] + gd2
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        day += 1
    day -= 79
    n = day // 12053
    day %= 12053
    jy = 979 + 33*n + 4*(day//1461)
    day %= 1461
    if day >= 366:
        jy += (day - 1)//365
        day = (day - 1)%365
    if day < 186:
        jm, jd = 1 + day//31, 1 + day%31
    else:
        jm, jd = 7 + (day-186)//30, 1 + (day-186)%30
    return jy, jm, jd


def _git_dir(repo: Path) -> Path:
    marker = repo / ".git"
    if marker.is_dir():
        return marker.resolve()
    if marker.is_file():
        value = marker.read_text(encoding="utf-8").strip()
        if value.lower().startswith("gitdir:"):
            path = Path(value.split(":", 1)[1].strip())
            return (repo / path).resolve() if not path.is_absolute() else path.resolve()
    raise FileNotFoundError(".git metadata not found")


def _head_hash(gitdir: Path) -> str:
    head = (gitdir / "HEAD").read_text(encoding="ascii").strip()
    if not head.startswith("ref: "):
        return head
    ref = head[5:].strip()
    loose = gitdir / ref
    if loose.exists():
        return loose.read_text(encoding="ascii").strip()
    packed = gitdir / "packed-refs"
    if packed.exists():
        for line in packed.read_text(encoding="ascii", errors="ignore").splitlines():
            if line and not line.startswith(("#", "^")):
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref:
                    return parts[0]
    raise FileNotFoundError(f"Git ref not found: {ref}")


def _run_git(git_exe: str, repo: Path) -> tuple[str, int, str]:
    out = subprocess.run(
        [git_exe, "-C", str(repo), "log", "-1", "--format=%H%x1f%ct%x1f%s"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, check=True,
    ).stdout.strip()
    oid, epoch, subject = out.split("\x1f", 2)
    return oid, int(epoch), subject


def _find_git_exe() -> list[str]:
    found: list[str] = []
    path_git = shutil.which("git")
    if path_git:
        found.append(path_git)
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    for pattern in (
        str(Path(os.environ.get("ProgramFiles", r"C:\\Program Files")) / "Git" / "cmd" / "git.exe"),
        str(Path(os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")) / "Git" / "cmd" / "git.exe"),
        str(local / "GitHubDesktop" / "app-*" / "resources" / "app" / "git" / "cmd" / "git.exe"),
        str(local / "GitHubDesktop" / "app-*" / "resources" / "app" / "git" / "bin" / "git.exe"),
    ):
        import glob
        found.extend(glob.glob(pattern))
    # Older GitHub Desktop installations and portable Git locations.
    for base in (Path(os.environ.get("ProgramFiles", r"C:\\Program Files")), local):
        if base.exists():
            for candidate in base.glob("GitHubDesktop/app-*/resources/app/git/cmd/git.exe"):
                found.append(str(candidate))
    return list(dict.fromkeys(found))


def _reflog_metadata(gitdir: Path, oid: str) -> tuple[int, str]:
    candidates = [gitdir / "logs" / "HEAD"]
    try:
        head = (gitdir / "HEAD").read_text(encoding="ascii").strip()
        if head.startswith("ref: "):
            candidates.append(gitdir / "logs" / head[5:].strip())
    except OSError:
        pass
    for reflog in candidates:
        if not reflog.exists():
            continue
        lines = reflog.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            fields = line.split("\t", 1)
            meta = fields[0].split()
            if len(meta) < 4 or meta[1] != oid:
                continue
            try:
                epoch = int(meta[-2])
            except ValueError:
                continue
            subject = fields[1] if len(fields) > 1 else "Git HEAD"
            return epoch, subject[:70]
    raise FileNotFoundError("Current commit timestamp is not present in Git reflog")


def _commit_metadata(gitdir: Path, oid: str) -> tuple[int, str]:
    obj = gitdir / "objects" / oid[:2] / oid[2:]
    raw = zlib.decompress(obj.read_bytes())
    header, body = raw.split(b"\0", 1)
    if not header.startswith(b"commit "):
        raise ValueError("HEAD does not reference a commit object")
    text = body.decode("utf-8", "replace")
    author = next(line for line in text.splitlines() if line.startswith("author "))
    match = re.search(r"\s(\d{9,})\s[+-]\d{4}$", author)
    if not match:
        raise ValueError("Commit timestamp not found")
    message = text.split("\n\n", 1)[1].splitlines()[0].strip()
    return int(match.group(1)), message


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    state = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "Windows-Agent"
    stamp = state / "build_stamp.json"
    try:
        metadata = None
        for git_exe in _find_git_exe():
            try:
                metadata = _run_git(git_exe, repo)
                break
            except Exception:
                continue
        if metadata is None:
            gitdir = _git_dir(repo)
            oid = _head_hash(gitdir)
            try:
                epoch, subject = _commit_metadata(gitdir, oid)
            except Exception:
                epoch, subject = _reflog_metadata(gitdir, oid)
        else:
            oid, epoch, subject = metadata
        moment = datetime.fromtimestamp(epoch, TEHRAN)
        jy, jm, jd = gregorian_to_jalali(moment.year, moment.month, moment.day)
        state.mkdir(parents=True, exist_ok=True)
        tmp = stamp.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "version": oid[:7],
            "date": f"{jy:04d}/{jm:02d}/{jd:02d}",
            "time": moment.strftime("%H:%M"),
            "subject": subject[:70],
        }, ensure_ascii=False), encoding="utf-8")
        tmp.replace(stamp)
        # ASCII-only console output works in Windows cmd regardless of OEM code page.
        print(f"Build {oid[:7]} | latest commit {jy:04d}/{jm:02d}/{jd:02d} {moment:%H:%M} Tehran")
        return 0
    except Exception as exc:
        # Never leave a previous launch's commit stamp masquerading as this build.
        try:
            stamp.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"WARNING: Could not read Git commit metadata; embedded fallback will be used ({exc})")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
