"""Player workspace and save file."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

START_LEVEL = 184
HINT_HEAT = {1: 1, 2: 2, 3: 4}

# This only deters casual edits; it is a learning game, not DRM.
_MAC_KEY = b"nasm-adventures/save/v1"


def workspace() -> Path:
    return Path(os.environ.get("RING_WORKSPACE", Path.home() / "nasm-adventures"))


def level_dir(number: int) -> Path:
    return workspace() / f"level{number:03d}"


def dev_mode() -> bool:
    return os.environ.get("RING_DEV") == "1"


class SaveError(Exception):
    pass


class Progress:
    def __init__(self, data: dict):
        self.data = data

    @property
    def path(self) -> Path:
        return workspace() / ".ring" / "save.json"

    @classmethod
    def load(cls) -> "Progress":
        p = workspace() / ".ring" / "save.json"
        if not p.exists():
            prog = cls({"version": 1, "current": START_LEVEL, "completed": {}, "hints": {},
                        "heat": 0, "badges": [], "seed": secrets.randbits(63)})
            prog.save()
            return prog
        raw = json.loads(p.read_text())
        mac = raw.pop("mac", "")
        if not hmac.compare_digest(mac, _mac(raw)):
            raise SaveError(f"{p} has been modified outside the game. Restore it, or delete "
                            "it to start over.")
        return cls(raw)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        out = dict(self.data, mac=_mac(self.data))
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2))
        tmp.replace(self.path)

    @property
    def current(self) -> int:
        return self.data["current"]

    @property
    def seed(self) -> int:
        return self.data["seed"]

    @property
    def heat(self) -> int:
        return self.data["heat"]

    def unlocked(self, number: int) -> bool:
        return dev_mode() or number >= self.current

    def completed(self, number: int) -> bool:
        return str(number) in self.data["completed"]

    def hints_used(self, number: int) -> list[int]:
        return self.data["hints"].get(str(number), [])

    def use_hint(self, number: int, n: int) -> int:
        """Record a hint; returns heat added (0 if already used)."""
        used = self.data["hints"].setdefault(str(number), [])
        if n in used:
            return 0
        used.append(n)
        self.data["heat"] += HINT_HEAT.get(n, 4)
        self.save()
        return HINT_HEAT.get(n, 4)

    def complete(self, number: int, instructions: int, badges: list[str], next_level: int) -> None:
        prev = self.data["completed"].get(str(number))
        best = min(instructions, prev["best_instructions"]) if prev else instructions
        self.data["completed"][str(number)] = {"at": int(time.time()), "best_instructions": best}
        for b in badges:
            if b not in self.data["badges"]:
                self.data["badges"].append(b)
        if number == self.current:
            self.data["current"] = next_level
        self.save()


def _mac(data: dict) -> str:
    return hmac.new(_MAC_KEY, json.dumps(data, sort_keys=True).encode(), hashlib.sha256).hexdigest()
