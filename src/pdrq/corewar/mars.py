"""pMARS command-line wrapper."""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pdrq.core.types import MatchResult, Program
from pdrq.corewar.redcode import opcode_counts


@dataclass(frozen=True)
class MarsConfig:
    binary: Path = Path("vendor/pmars-bin")
    core_size: int = 8000
    max_cycles: int = 80000
    max_processes: int = 8000
    max_length: int = 100
    min_distance: int = 100
    rounds: int = 10
    timeout_seconds: float = 10.0


class MarsError(RuntimeError):
    pass


class MarsRunner:
    def __init__(self, config: MarsConfig):
        self.config = config

    def validate(self, program: Program) -> tuple[bool, str]:
        with tempfile.TemporaryDirectory(prefix="pdrq_validate_") as tmp:
            path = Path(tmp) / f"{program.program_id}.red"
            path.write_text(program.source, encoding="utf-8")
            command = [str(self.config.binary), "-A", "-b", str(path)]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_seconds,
                    env={"LC_ALL": "C", "LANG": "C"},
                )
            except subprocess.TimeoutExpired:
                return False, f"pMARS validation timed out after {self.config.timeout_seconds:.1f}s"
            output = (completed.stdout + "\n" + completed.stderr).strip()
            has_instruction = sum(opcode_counts(program.source).values()) > 0
            has_no_instruction_warning = "No instructions" in output
            return completed.returncode == 0 and has_instruction and not has_no_instruction_warning, output

    def run_pair(self, red: Program, blue: Program, offset: int) -> MatchResult:
        with tempfile.TemporaryDirectory(prefix="pdrq_match_") as tmp:
            red_path = Path(tmp) / f"{red.program_id}.red"
            blue_path = Path(tmp) / f"{blue.program_id}.red"
            red_path.write_text(red.source, encoding="utf-8")
            blue_path.write_text(blue.source, encoding="utf-8")
            command = self._command(offset, red_path, blue_path)
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_seconds,
                    env={"LC_ALL": "C", "LANG": "C"},
                )
            except subprocess.TimeoutExpired as exc:
                raise MarsError(f"pMARS timed out for {red.program_id} vs {blue.program_id}") from exc
        if completed.returncode != 0:
            raise MarsError((completed.stdout + "\n" + completed.stderr).strip())
        red_score, blue_score = parse_koth_scores(completed.stdout)
        denom = max(1, abs(red_score) + abs(blue_score))
        return MatchResult(
            red_id=red.program_id,
            blue_id=blue.program_id,
            offset=offset,
            red_score=red_score,
            blue_score=blue_score,
            margin=(red_score - blue_score) / denom,
            command=tuple(command),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def evaluate(self, red: Program, blue: Program, offsets: Sequence[int]) -> list[MatchResult]:
        return [self.run_pair(red, blue, offset) for offset in offsets]

    def _command(self, offset: int, red_path: Path, blue_path: Path) -> list[str]:
        return [
            str(self.config.binary),
            "-b",
            "-k",
            "-F",
            str(offset),
            "-r",
            str(self.config.rounds),
            "-s",
            str(self.config.core_size),
            "-c",
            str(self.config.max_cycles),
            "-p",
            str(self.config.max_processes),
            "-l",
            str(self.config.max_length),
            "-d",
            str(self.config.min_distance),
            str(red_path),
            str(blue_path),
        ]


def parse_koth_scores(stdout: str) -> tuple[int, int]:
    rows: list[tuple[int, int]] = []
    for line in stdout.splitlines():
        match = re.match(r"^\s*(-?\d+)\s+(-?\d+)\s*$", line)
        if match:
            rows.append((int(match.group(1)), int(match.group(2))))
    if len(rows) < 2:
        raise MarsError(f"could not parse pMARS -k output: {stdout!r}")
    return rows[0][0], rows[1][0]
