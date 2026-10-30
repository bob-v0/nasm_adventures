"""Built-in reference for instructions, NASM directives and concepts (`ring docs`)."""

from __future__ import annotations

import tomllib
from functools import cache
from pathlib import Path


@cache
def _db() -> dict[str, dict]:
    raw = tomllib.loads((Path(__file__).parent / "docs" / "reference.toml").read_text())
    entries = {}
    for name, e in raw.items():
        entries[name.lower()] = e
        for alias in e.get("aliases", []):
            entries.setdefault(alias.lower(), e | {"_alias_of": name})
    return entries


def index() -> str:
    db = _db()
    groups: dict[str, list[str]] = {}
    for name, e in db.items():
        if "_alias_of" not in e:
            groups.setdefault(e["kind"], []).append(name)
    out = ["Reference topics (`ring docs <topic>`):"]
    for kind in sorted(groups):
        out.append(f"\n  {kind}:")
        out.append("    " + "  ".join(sorted(groups[kind])))
    return "\n".join(out)


def lookup(term: str) -> str:
    e = _db().get(term.lower().strip())
    if e is None:
        close = [n for n in _db() if term.lower() in n]
        return f"No entry for {term!r}." + (f" Did you mean: {', '.join(close)}?" if close else "")
    out = [f"{e.get('_alias_of', term).upper()}  ({e['kind']}, introduced in ring {e['ring']})", ""]
    if "syntax" in e:
        out += ["  " + line for line in e["syntax"].strip().splitlines()] + [""]
    out.append(e["summary"].strip())
    if "flags" in e:
        out += ["", f"Flags: {e['flags']}"]
    if "notes" in e:
        out += ["", e["notes"].strip()]
    if "sdm" in e:
        out += ["", f"Intel SDM: {e['sdm']}"]
    return "\n".join(out)
