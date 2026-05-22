#!/usr/bin/env python3
"""Fetch external Core War benchmark warriors used by the paper."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "corewar" / "benchmarks"
DOWNLOADS = BENCH / "_downloads"


@dataclass(frozen=True)
class Suite:
    name: str
    url: str
    archive: str
    kind: str
    note: str


SUITES = [
    Suite(
        name="wilkies",
        url="http://www.koth.org/wilkies/bench.zip",
        archive="wilkies_bench.zip",
        kind="zip",
        note="JKW's Beginner's Benchmark, 12 warriors.",
    ),
    Suite(
        name="wilmoo",
        url="http://www.koth.org/wilmoo/wilmoo.zip",
        archive="wilmoo.zip",
        kind="zip",
        note="WilMoo benchmark, 12 warriors.",
    ),
    Suite(
        name="koenigstuhl_94nop_top50",
        url="https://asdflkj.net/COREWAR/94/TOP50/94top50.tar.gz",
        archive="94top50.tar.gz",
        kind="tar.gz",
        note="Koenigstuhl 94nop Top-50 archive.",
    ),
    Suite(
        name="koenigstuhl_94nop_full",
        url="https://asdflkj.net/COREWAR/94/94.tar.gz",
        archive="94.tar.gz",
        kind="tar.gz",
        note="Full Koenigstuhl 94nop archive, used only for deterministic random-known sampling.",
    ),
    Suite(
        name="cgm1_round1",
        url="https://corewar.co.uk/cgm1/Benchmark_CGM1R1.zip",
        archive="Benchmark_CGM1R1.zip",
        kind="zip",
        note="Corewar Global Masters 1 round 1 benchmark, 20 warriors.",
    ),
]


def main() -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "suites": [],
    }
    for suite in SUITES:
        archive = DOWNLOADS / suite.archive
        download(suite.url, archive)
        out = BENCH / suite.name
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        files = extract_redcode(archive, suite.kind, out)
        manifest["suites"].append(
            {
                "name": suite.name,
                "url": suite.url,
                "archive": str(archive.relative_to(ROOT)),
                "sha256": sha256_file(archive),
                "redcode_files": len(files),
                "note": suite.note,
            }
        )
    (BENCH / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    write_readme(manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


def download(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    with urllib.request.urlopen(url, timeout=60) as response:
        path.write_bytes(response.read())


def extract_redcode(archive: Path, kind: str, out: Path) -> list[Path]:
    extracted: list[Path] = []
    if kind == "zip":
        with zipfile.ZipFile(archive) as zf:
            members = [name for name in zf.namelist() if is_redcode_member(name)]
            for member in members:
                target = out / sanitize(Path(member).name)
                target.write_bytes(zf.read(member))
                extracted.append(target)
    elif kind == "tar.gz":
        with tarfile.open(archive, "r:gz") as tf:
            members = [member for member in tf.getmembers() if member.isfile() and is_redcode_member(member.name)]
            for member in members:
                handle = tf.extractfile(member)
                if handle is None:
                    continue
                target = out / sanitize(Path(member.name).name)
                target.write_bytes(handle.read())
                extracted.append(target)
    else:
        raise ValueError(f"unsupported archive type: {kind}")
    return sorted(extracted)


def is_redcode_member(name: str) -> bool:
    path = Path(name)
    return path.suffix.lower() == ".red" and not path.name.startswith("._")


def sanitize(name: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "._-+" else "_" for ch in name)
    return clean or "warrior.red"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_readme(manifest: dict[str, object]) -> None:
    lines = [
        "# External Core War Benchmarks",
        "",
        "These benchmark warriors are mirrored for reproducible evaluation. They are",
        "third-party Core War programs and are included here for research attribution,",
        "not relicensed by this project.",
        "",
        "Run `python3 scripts/fetch_corewar_benchmarks.py` to refresh the local copy.",
        "",
    ]
    for suite in manifest["suites"]:  # type: ignore[index]
        lines.extend(
            [
                f"## {suite['name']}",
                "",
                f"- Source: {suite['url']}",
                f"- Files: {suite['redcode_files']}",
                f"- Archive SHA-256: `{suite['sha256']}`",
                f"- Note: {suite['note']}",
                "",
            ]
        )
    (BENCH / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
