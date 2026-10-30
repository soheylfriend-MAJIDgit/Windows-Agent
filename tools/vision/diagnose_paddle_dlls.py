# -*- coding: utf-8 -*-
"""Best-effort static import-table checker for Windows Paddle native DLL failures.

No external package is used. It lists imported DLL names that are not found in the
Paddle/NumPy/SciPy/venv/Windows search folders. This is diagnostic only, not a loader.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import struct
import sys

API_SET_PREFIXES = ("api-ms-win-", "ext-ms-win-")


def _rva_to_offset(rva: int, sections: list[tuple[int, int, int, int]], size_headers: int) -> int | None:
    if rva < size_headers:
        return rva
    for va, virtual_size, raw_size, raw_ptr in sections:
        span = max(virtual_size, raw_size)
        if va <= rva < va + span:
            delta = rva - va
            if delta >= raw_size:
                return None
            return raw_ptr + delta
    return None


def imports(path: Path) -> list[str]:
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        return []
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        return []
    coff = pe + 4
    nsections = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    directory = opt + (112 if magic == 0x20B else 96 if magic == 0x10B else 0)
    if not directory:
        return []
    size_headers = struct.unpack_from("<I", data, opt + 60)[0]
    import_rva = struct.unpack_from("<I", data, directory + 8)[0]
    if not import_rva:
        return []
    sec_off = opt + opt_size
    sections = []
    for idx in range(nsections):
        off = sec_off + idx * 40
        virtual_size, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, off + 8)
        sections.append((va, virtual_size, raw_size, raw_ptr))
    desc = _rva_to_offset(import_rva, sections, size_headers)
    if desc is None:
        return []
    found = []
    for idx in range(4096):
        off = desc + idx * 20
        if off + 20 > len(data):
            break
        original, stamp, chain, name_rva, thunk = struct.unpack_from("<IIIII", data, off)
        if not any((original, stamp, chain, name_rva, thunk)):
            break
        name_off = _rva_to_offset(name_rva, sections, size_headers)
        if name_off is None or name_off >= len(data):
            continue
        end = data.find(b"\0", name_off, min(len(data), name_off + 512))
        if end > name_off:
            found.append(data[name_off:end].decode("ascii", "replace"))
    return found


def main() -> int:
    if os.name != "nt":
        print(json.dumps({"ok": False, "error": "Windows-only diagnostic."}))
        return 1
    site = Path(sys.prefix) / "Lib" / "site-packages"
    roots = [
        site / "paddle" / "base", site / "paddle" / "libs", site / "paddle",
        site / "numpy.libs", site / "numpy" / ".libs", site / "scipy.libs", site / "scipy" / ".libs",
        Path(sys.prefix), Path(sys.base_prefix),
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32",
    ]
    roots.extend(Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p)
    roots = [p for p in roots if p.is_dir()]
    start = site / "paddle" / "base" / "libpaddle.pyd"
    queue = [start] if start.exists() else []
    seen: set[Path] = set()
    missing: list[dict] = []
    scanned = 0
    while queue and scanned < 1000:
        binary = queue.pop(0).resolve()
        if binary in seen:
            continue
        seen.add(binary)
        scanned += 1
        try:
            names = imports(binary)
        except Exception:
            continue
        for name in names:
            low = name.casefold()
            if low.startswith(API_SET_PREFIXES):
                continue
            located = next((root / name for root in [binary.parent, *roots] if (root / name).is_file()), None)
            if located is None:
                missing.append({"importer": str(binary), "dll": name})
            elif located.suffix.casefold() == ".dll":
                queue.append(located)
    report = {
        "ok": bool(start.exists()) and not missing,
        "binary": str(start),
        "searchDirectories": [str(p) for p in roots],
        "scannedBinaries": scanned,
        "missingDlls": missing[:100],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
