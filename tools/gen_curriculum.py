"""Number the curriculum and regenerate the generated parts of DESIGN.md.

    python3 tools/gen_curriculum.py            # rewrite DESIGN.md in place
    python3 tools/gen_curriculum.py --check    # exit 1 if DESIGN.md is stale (CI)
    python3 tools/gen_curriculum.py --dirs     # print implemented level directories
"""

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIERS = {1: "◆ easy", 2: "◆◆ medium", 3: "◆◆◆ hard", 4: "◆◆◆◆ very hard"}


def numbered():
    arcs = tomllib.loads((ROOT / "tools" / "curriculum.toml").read_text())["arc"]
    total = sum(len(a["levels"]) for a in arcs)
    n = total - 1
    for arc in arcs:
        for lv in arc["levels"]:
            lv["number"] = n
            n -= 1
    return arcs, total


def render(arcs, total) -> tuple[str, str]:
    out = []
    for arc in arcs:
        first, last = arc["levels"][0]["number"], arc["levels"][-1]["number"]
        bugs = sum(1 for lv in arc["levels"] if "bug" in lv)
        out.append(f"### Arc {arc['id']} — {arc['name']} (Levels {first}–{last})\n")
        out.append(f"Runner: {arc['runner']}. {len(arc['levels'])} levels, {bugs} of them bug levels.\n")
        out.append("| Level | Title | Concepts | Gate |\n|---|---|---|---|")
        for lv in arc["levels"]:
            title = lv["title"]
            if "bug" in lv:
                title = f"**Bug:** {title} {TIERS[lv['bug']].split()[0]}"
            if lv.get("boss"):
                title = f"{title} ★"
            out.append(f"| {lv['number']} | {title} | {lv['concepts']} | {lv['gate']} |")
        out.append("")
    curriculum = "\n".join(out)

    rows = ["| Level | Arc | Bug | Tier | What it teaches |", "|---|---|---|---|---|"]
    for arc in arcs:
        for lv in arc["levels"]:
            if "bug" in lv:
                rows.append(f"| {lv['number']} | {arc['id']} | {lv['title']} | {TIERS[lv['bug']]} | {lv['concepts']} |")
    return curriculum, "\n".join(rows) + "\n"


def replace_block(text: str, name: str, body: str) -> str:
    start, end = f"<!-- BEGIN GENERATED {name} -->", f"<!-- END GENERATED {name} -->"
    a, b = text.index(start) + len(start), text.index(end)
    return text[:a] + "\n" + body + text[b:]


def main() -> int:
    arcs, total = numbered()
    if "--dirs" in sys.argv:
        for arc in arcs:
            for lv in arc["levels"]:
                if "dir" in lv:
                    print(f"{lv['number']:03d}_{lv['dir']}")
        return 0
    curriculum, bugs = render(arcs, total)
    design = ROOT / "DESIGN.md"
    text = design.read_text()
    new = replace_block(text, "CURRICULUM", curriculum)
    new = replace_block(new, "BUG TRACK", bugs)
    if "--check" in sys.argv:
        if new != text:
            print("DESIGN.md is out of date: run python3 tools/gen_curriculum.py")
            return 1
        return 0
    design.write_text(new)
    print(f"{total} levels ({total - 1} → 0), "
          f"{sum(1 for a in arcs for lv in a['levels'] if 'bug' in lv)} bug levels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
