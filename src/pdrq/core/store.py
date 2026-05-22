"""Append-only artifact store for pilot runs."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from .types import CandidateProposal, Program
from ..corewar.redcode import source_hash


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    return value


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root
        for name in ("programs", "prompts", "completions"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def write_config(self, config: Mapping[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._write_json(self.root / "config.json", dict(config))

    def save_program(self, program: Program) -> Path:
        digest = source_hash(program.source)
        path = self.root / "programs" / f"{program.program_id}_{digest[:12]}.red"
        path.write_text(program.source, encoding="utf-8")
        return path

    def save_proposal(self, candidate_id: str, proposal: CandidateProposal) -> None:
        (self.root / "prompts" / f"{candidate_id}.txt").write_text(proposal.prompt, encoding="utf-8")
        self._write_json(self.root / "completions" / f"{candidate_id}.json", proposal)

    def append_event(self, name: str, payload: Mapping[str, Any]) -> None:
        record = {"event": name, **dict(payload)}
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=_json_default, sort_keys=True) + "\n")

    def append_match(self, payload: Mapping[str, Any]) -> None:
        with (self.root / "matches.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(payload), default=_json_default, sort_keys=True) + "\n")

    def write_summary(self, summary: Mapping[str, Any]) -> None:
        self._write_json(self.root / "summary.json", dict(summary))

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, default=_json_default, indent=2, sort_keys=True) + "\n", encoding="utf-8")
