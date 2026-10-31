"""Arc names (the curriculum in tools/curriculum.toml is the source; a test keeps them equal)."""

ARCS = {
    "I": "The Assembler & the Machine",
    "II": "Arithmetic & Flags",
    "III": "Control Flow & Data",
    "IV": "Stack & Procedures",
    "V": "Linux Userland",
    "VI": "Events, Tasks & Actors (one thread)",
    "VII": "Performance & Microarchitecture",
    "VIII": "Threads & the Memory Model",
    "IX": "Floating Point & SIMD",
    "X": "Machine Code",
    "XI": "Real Mode & Boot",
    "XII": "Protected Mode & Interrupts",
    "XIII": "Long Mode",
    "XIV": "Ring 0",
}


def arc_title(arc: str) -> str:
    """"Arc V · Linux Userland"."""
    name = ARCS.get(arc)
    return f"Arc {arc} · {name}" if name else f"Arc {arc}"
