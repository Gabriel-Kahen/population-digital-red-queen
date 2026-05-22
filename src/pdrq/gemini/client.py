"""Gemini and stub generators with explicit budget accounting."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Sequence

import httpx
from google import genai
from google.genai import errors
from google.genai import types

from pdrq.core.types import BudgetState, CandidateProposal, Program
from pdrq.corewar.redcode import extract_redcode, normalize_source

from .prompts import SYSTEM_INSTRUCTION, mutation_prompt


@dataclass
class BudgetGuard:
    max_calls: int = 20
    max_estimated_cost_usd: float = 1.0
    input_price_per_million: float = 0.30
    output_price_per_million: float = 2.50
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def estimate_call_cost(self, prompt: str, max_output_tokens: int) -> float:
        input_estimate = max(1, len(prompt) // 4)
        return (
            input_estimate * self.input_price_per_million / 1_000_000
            + max_output_tokens * self.output_price_per_million / 1_000_000
        )

    def reserve(self, prompt: str, max_output_tokens: int) -> None:
        projected = self.estimated_cost_usd + self.estimate_call_cost(prompt, max_output_tokens)
        if self.calls + 1 > self.max_calls:
            raise RuntimeError(f"LLM call budget exhausted: {self.calls}/{self.max_calls}")
        if projected > self.max_estimated_cost_usd:
            raise RuntimeError(
                f"estimated LLM budget would exceed ${self.max_estimated_cost_usd:.2f}: ${projected:.4f}"
            )

    def record(self, input_tokens: int, output_tokens: int) -> float:
        cost = (
            input_tokens * self.input_price_per_million / 1_000_000
            + output_tokens * self.output_price_per_million / 1_000_000
        )
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.estimated_cost_usd += cost
        return cost

    def state(self) -> BudgetState:
        return BudgetState(self.calls, self.input_tokens, self.output_tokens, self.estimated_cost_usd)


class StubRedcodeGenerator:
    """No-spend generator for harness testing."""

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.calls = 0

    def propose(
        self,
        parents: Sequence[Program],
        opponents: Sequence[Program],
        generation: int,
        condition: str,
        feedback: str = "",
    ) -> CandidateProposal:
        self.calls += 1
        parent = parents[0]
        step = self.rng.choice([1, 2, 4, 5, 7])
        source = f""";redcode-94
;name Stub Mutant {generation}-{self.calls}
;author PDRQ dry-run
;strategy no-spend smoke-test mutation from {parent.program_id}
        org start
start   add #{step}, ptr
        mov bomb, @ptr
        jmp start
bomb    dat #0, #0
ptr     dat #0, #{self.rng.randrange(40, 200)}
        end start
"""
        prompt = mutation_prompt(parents, opponents, generation, condition, feedback)
        return CandidateProposal(
            source=normalize_source(source),
            strategy_summary="Deterministic stub bomber for dry-run validation.",
            raw_response=source,
            model="stub",
            prompt=prompt,
        )


class GeminiRedcodeGenerator:
    def __init__(
        self,
        project: str,
        location: str,
        model: str,
        budget: BudgetGuard,
        max_output_tokens: int = 700,
        temperature: float = 0.8,
        max_retries: int = 8,
        retry_initial_delay_seconds: float = 3.0,
        api_timeout_ms: int = 120_000,
    ):
        self.project = project
        self.location = location
        self.model = model
        self.budget = budget
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_initial_delay_seconds = retry_initial_delay_seconds
        self.client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=types.HttpOptions(timeout=api_timeout_ms),
        )

    def propose(
        self,
        parents: Sequence[Program],
        opponents: Sequence[Program],
        generation: int,
        condition: str,
        feedback: str = "",
    ) -> CandidateProposal:
        prompt = mutation_prompt(parents, opponents, generation, condition, feedback)
        self.budget.reserve(prompt, self.max_output_tokens)
        response = self._generate_content(prompt)
        raw = response.text or ""
        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or max(1, len(prompt) // 4))
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or max(1, len(raw) // 4))
        cost = self.budget.record(input_tokens, output_tokens)
        source = normalize_source(extract_redcode(raw))
        return CandidateProposal(
            source=source,
            strategy_summary=_strategy_summary(source),
            raw_response=raw,
            model=self.model,
            prompt=prompt,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            metadata={},
        )

    def _generate_content(self, prompt: str):
        for attempt in range(self.max_retries + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=self.temperature,
                        max_output_tokens=self.max_output_tokens,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
            except _RETRYABLE_EXCEPTIONS as exc:
                if attempt >= self.max_retries or not _is_retryable_api_error(exc):
                    raise
                delay = self.retry_initial_delay_seconds * (2**attempt)
                time.sleep(delay)


_RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.TransportError,
    TimeoutError,
    ConnectionError,
    errors.APIError,
)


def _is_retryable_api_error(exc: BaseException) -> bool:
    if isinstance(exc, errors.ClientError):
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        return code in {408, 409, 425, 429, 499}
    return True


def _strategy_summary(source: str) -> str:
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(";strategy"):
            return stripped.lstrip(";").strip()
    return "Plain Redcode model response."
