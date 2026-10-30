"""Briefs name game actions with placeholders, rendered for the interface in use:
`{{test}}` becomes "**Test**" in the browser and "`ring test`" in a terminal."""

from __future__ import annotations

import re

_ACTIONS = {
    #            browser                         terminal
    "test":     ("**Test**",                      "`ring test`"),
    "submit":   ("**Submit**",                    "`ring submit`"),
    "listing":  ("the **Listing** tab",           "`ring listing`"),
    "debug":    ("the **Debugger**",              "`ring debug`"),
    "hints":    ("the **Hints** tab",             "`ring hint`"),
    "terminal": ("the **Terminal** tab",          "your terminal, in this level's folder"),
    "start":    ("opening the level",             "`ring start`"),
}


def render(text: str, ui: str) -> str:
    """ui: "web" or "cli". `{{docs mov}}` becomes a pointer to the reference."""
    def sub(m: re.Match) -> str:
        name, arg = m.group(1), (m.group(2) or "").strip()
        if name == "docs":
            return f"the **Reference** tab (look up `{arg}`)" if ui == "web" else f"`ring docs {arg}`"
        if name not in _ACTIONS:
            return m.group(0)
        return _ACTIONS[name][0 if ui == "web" else 1]

    return re.sub(r"\{\{(\w+)(?:\s+([^}]*))?\}\}", sub, text)
