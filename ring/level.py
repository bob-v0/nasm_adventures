"""Level definitions: level.toml + brief.md + starter.asm (+ optional prelude.asm,
include/, gen.py, reference.asm)."""

from __future__ import annotations

import importlib.util
import os
import random
import struct
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MASK64 = (1 << 64) - 1


def levels_root() -> Path:
    env = os.environ.get("RING_LEVELS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "levels"


def to_int(v) -> int:
    """Test values may be ints or strings like "0xFFFF_FFFF_FFFF_FFFF" (TOML ints are i64)."""
    if isinstance(v, str):
        v = int(v.replace("_", ""), 0)
    return v & MASK64


def encode_mem(spec: dict) -> bytes:
    """A memory value: one of hex / str / u8 / u16 / u32 / u64 (lists or scalars)."""
    if "hex" in spec:
        return bytes.fromhex(spec["hex"].replace(" ", ""))
    if "str" in spec:
        return spec["str"].encode()
    for key, fmt in (("u8", "B"), ("u16", "H"), ("u32", "I"), ("u64", "Q")):
        if key in spec:
            vals = spec[key] if isinstance(spec[key], list) else [spec[key]]
            mask = (1 << struct.calcsize(fmt) * 8) - 1
            return b"".join(struct.pack("<" + fmt, to_int(v) & mask) for v in vals)
    raise ValueError(f"memory spec needs hex/str/u8/u16/u32/u64: {spec}")


@dataclass
class TestCase:
    __test__ = False  # not a pytest test class
    name: str
    hidden: bool = False
    regs: dict[str, int] = field(default_factory=dict)
    mem: list[dict] = field(default_factory=list)
    stdin: bytes = b""
    expect: dict = field(default_factory=dict)
    files: dict = field(default_factory=dict)     # path -> contents, in the virtual filesystem
    argv: list | None = None
    env: dict = field(default_factory=dict)
    inject: dict = field(default_factory=dict)    # faults for the kernel (see kernel.Injection)
    userland: bool = False                        # install the game's /bin utilities

    @classmethod
    def from_dict(cls, d: dict, hidden: bool | None = None) -> "TestCase":
        stdin = d.get("stdin", b"")
        if "stdin_hex" in d:
            stdin = bytes.fromhex(d["stdin_hex"])
        if isinstance(stdin, str):
            stdin = stdin.encode()
        return cls(name=d["name"], hidden=d.get("hidden", False) if hidden is None else hidden,
                   regs={k: v if isinstance(v, str) and v.startswith("@") else to_int(v)
                         for k, v in d.get("regs", {}).items()},  # "@label" = its address
                   mem=list(d.get("mem", [])), stdin=stdin, expect=dict(d.get("expect", {})),
                   files=dict(d.get("files", {})), argv=d.get("argv"), env=dict(d.get("env", {})),
                   inject=dict(d.get("inject", {})), userland=d.get("userland", False))


@dataclass
class Context:
    """Per-player values a level generator may use (e.g. the level 174 vault seed)."""
    seed: int = 0


@dataclass
class Level:
    path: Path
    number: int
    slug: str
    title: str
    arc: str
    mode: str
    concepts: list[str]
    introduces: list[str]
    constraints: dict
    stretch: dict
    hints: list[str]
    tests: list[TestCase]
    random_count: int
    data: dict

    @property
    def brief(self) -> str:
        return (self.path / "brief.md").read_text()

    @property
    def starter(self) -> Path:
        return self.path / "starter.asm"

    @property
    def reference(self) -> Path:
        return self.path / "reference.asm"

    @property
    def prelude(self) -> Path | None:
        p = self.path / "prelude.asm"
        return p if p.exists() else None

    @property
    def include_dir(self) -> Path | None:
        p = self.path / "include"
        return p if p.is_dir() else None

    @property
    def poison(self) -> bool:
        """Do tests start with garbage in the registers? Always for function levels:
        that's what a real caller leaves behind."""
        return self.constraints.get("poison", self.mode == "function")

    def build_options(self) -> dict:
        """Keyword arguments for build.build()."""
        helpers = self.path / "helpers.asm"
        return {"include_dirs": [self.include_dir] if self.include_dir else [],
                "prelude": self.prelude, "helpers": [helpers] if helpers.exists() else [],
                "entry": self.data.get("entry"), "c_sources": sorted(self.path.glob("*.c"))}

    def _gen_module(self):
        p = self.path / "gen.py"
        if not p.exists():
            return None
        spec = importlib.util.spec_from_file_location(f"ring_gen_{self.number}", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def all_tests(self, ctx: Context, include_hidden: bool = True) -> list[TestCase]:
        tests = [t for t in self.tests if include_hidden or not t.hidden]
        mod = self._gen_module()
        if mod is not None:
            if hasattr(mod, "fixed_tests"):
                for d in mod.fixed_tests(ctx):
                    t = TestCase.from_dict(d)
                    if include_hidden or not t.hidden:
                        tests.append(t)
            if include_hidden and self.random_count and hasattr(mod, "generate"):
                rng = random.Random(ctx.seed ^ (self.number * 0x9E3779B9))
                tests += [TestCase.from_dict(d, hidden=True)
                          for d in mod.generate(rng, self.random_count, ctx)]
        return tests

    def prepare(self, workdir: Path, ctx: Context) -> None:
        """Per-level hook for files the player needs (e.g. level 174's vault binary)."""
        mod = self._gen_module()
        if mod is not None and hasattr(mod, "prepare"):
            mod.prepare(self, workdir, ctx)


def load_level(path: Path) -> Level:
    data = tomllib.loads((path / "level.toml").read_text())
    return Level(
        path=path, number=data["level"], slug=data["slug"], title=data["title"], arc=data["arc"],
        mode=data.get("mode", "fragment"), concepts=data.get("concepts", []),
        introduces=data.get("introduces", []), constraints=data.get("constraints", {}),
        stretch=data.get("stretch", {}), hints=data.get("hints", []),
        tests=[TestCase.from_dict(t) for t in data.get("tests", [])],
        random_count=data.get("random", {}).get("count", 0), data=data,
    )


def all_levels() -> dict[int, Level]:
    root = levels_root()
    levels = {}
    for d in sorted(root.iterdir()) if root.exists() else []:
        if (d / "level.toml").exists():
            lv = load_level(d)
            levels[lv.number] = lv
    return levels
