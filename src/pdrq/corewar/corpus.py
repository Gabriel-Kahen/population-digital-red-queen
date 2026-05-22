"""Load Redcode corpora from directories."""

from __future__ import annotations

from pathlib import Path

from pdrq.core.types import Program

from .redcode import normalize_source, source_hash


def load_programs(path: Path, generation: int = 0, role: str | None = None) -> list[Program]:
    programs: list[Program] = []
    for file_path in sorted(file for file in path.iterdir() if is_redcode_file(file)):
        source = normalize_source(file_path.read_text(encoding="utf-8", errors="replace"))
        digest = source_hash(source)
        programs.append(
            Program(
                program_id=file_path.stem,
                source=source,
                generation=generation,
                metadata={"path": str(file_path), "sha256": digest, "role": role or file_path.stem},
            )
        )
    return programs


def is_redcode_file(file_path: Path) -> bool:
    return file_path.is_file() and file_path.suffix.lower() == ".red" and not file_path.name.startswith("._")
