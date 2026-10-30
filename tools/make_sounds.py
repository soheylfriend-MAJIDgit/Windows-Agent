# -*- coding: utf-8 -*-
"""ساخت افکت‌های صوتی برنامه (بدون نیاز به فایل صوتی بیرونی).

اجرا:  python tools/make_sounds.py
خروجی: assets/sounds/*.wav
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"


def _write(name: str, samples: list[float], gain: float = 0.55) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for value in samples:
        clipped = max(-1.0, min(1.0, value * gain))
        frames += struct.pack("<h", int(clipped * 32767))
    with wave.open(str(OUT / name), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        fh.writeframes(bytes(frames))
    size = (OUT / name).stat().st_size
    print(f"✔ {name}  ({size // 1024} KB)")


def _env(i: int, total: int, attack: float = 0.01, release: float = 0.5) -> float:
    """پوش ساده: حمله سریع، افت نرم."""
    t = i / max(1, total)
    if t < attack:
        return t / attack
    fade = (t - attack) / max(1e-6, release)
    return max(0.0, 1.0 - fade) ** 1.6


def tone(freq: float, ms: int, *, sweep: float | None = None, harm: float = 0.25) -> list[float]:
    total = int(RATE * ms / 1000)
    out: list[float] = []
    phase = 0.0
    for i in range(total):
        f = freq if sweep is None else freq + (sweep - freq) * (i / total)
        phase += 2 * math.pi * f / RATE
        value = math.sin(phase) + harm * math.sin(2 * phase)
        out.append(value * _env(i, total))
    return out


def click() -> list[float]:
    return tone(1046.0, 45, sweep=784.0, harm=0.15)


def toggle() -> list[float]:
    first = tone(660.0, 45, harm=0.1)
    second = tone(990.0, 55, harm=0.1)
    return first + [0.0] * 12 + second


def open_sound() -> list[float]:
    return tone(320.0, 180, sweep=860.0, harm=0.3)


def run_sound() -> list[float]:
    base = tone(440.0, 160, sweep=660.0, harm=0.35)
    tail = tone(880.0, 90, harm=0.2)
    return base + tail


def success() -> list[float]:
    a = tone(659.25, 110, harm=0.2)
    b = tone(987.77, 190, harm=0.2)
    return a + b


def error() -> list[float]:
    total = int(RATE * 0.34)
    out: list[float] = []
    phase = 0.0
    for i in range(total):
        f = 230 - 70 * (i / total)
        phase += 2 * math.pi * f / RATE
        value = math.sin(phase) + 0.4 * math.sin(3 * phase)
        out.append(value * _env(i, total, release=0.8))
    return out


def shutter() -> list[float]:
    """صدای شاتر دوربین: دو کلیک تیز با نویز کوتاه."""
    click_a = tone(2200.0, 18, harm=0.0)
    noise = []
    rnd = random.Random(7)
    for i in range(int(RATE * 0.05)):
        noise.append(rnd.uniform(-1, 1) * _env(i, int(RATE * 0.05), release=1.0) * 0.5)
    click_b = tone(1500.0, 22, harm=0.0)
    return click_a + noise + [0.0] * 40 + click_b


def tick() -> list[float]:
    return tone(1600.0, 28, harm=0.05)


def notify() -> list[float]:
    a = tone(784.0, 80, harm=0.15)
    b = tone(1046.5, 80, harm=0.15)
    c = tone(1318.5, 130, harm=0.15)
    return a + b + c


def main() -> None:
    _write("click.wav", click())
    _write("toggle.wav", toggle())
    _write("open.wav", open_sound())
    _write("run.wav", run_sound())
    _write("success.wav", success())
    _write("error.wav", error())
    _write("shutter.wav", shutter())
    _write("tick.wav", tick())
    _write("notify.wav", notify())
    print(f"\nهمه فایل‌ها در {OUT}")


if __name__ == "__main__":
    main()
