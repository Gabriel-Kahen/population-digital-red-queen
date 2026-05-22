"""Shared types for the real Core War pilot harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Program:
    program_id: str
    source: str
    language: str = "redcode-94"
    generation: int = 0
    parent_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateProposal:
    source: str
    strategy_summary: str
    raw_response: str
    model: str
    prompt: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchResult:
    red_id: str
    blue_id: str
    offset: int
    red_score: int
    blue_score: int
    margin: float
    command: tuple[str, ...]
    stdout: str
    stderr: str


@dataclass(frozen=True)
class BudgetState:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
