"""Prompt builders for Redcode mutation."""

from __future__ import annotations

from typing import Sequence

from pdrq.core.types import Program


SYSTEM_INSTRUCTION = """You generate Core War Redcode-94 warriors.
Return only complete Redcode-94 source text.
Do not return JSON, Markdown fences, or explanatory prose.
The source must be a complete Redcode-94 program, at most 100 instructions."""


def mutation_prompt(
    parents: Sequence[Program],
    opponents: Sequence[Program],
    generation: int,
    condition: str,
    feedback: str = "",
) -> str:
    parent_text = "\n\n".join(_program_block("PARENT", program) for program in parents)
    opponent_text = "\n\n".join(_program_block("OPPONENT", program) for program in opponents)
    return f"""Condition: {condition}
Generation: {generation}

Task: create one Redcode-94 warrior that is a meaningful tactical mutation or
recombination of the parent program(s), designed to improve against the listed
opponents while remaining valid under pMARS ICWS-94 settings.

Constraints:
- Use only Redcode-94 syntax accepted by pMARS.
- Keep the warrior at or below 100 instructions.
- Include ;redcode-94, ;assert 1, ;name, and ;author comments.
- Include at least 3 executable or DAT/SPL/MOV/etc. instruction lines plus an end directive.
- Do not return a comments-only header.
- Avoid undefined macro-heavy tricks unless visible in the parents.
- If recent feedback says pMARS timed out or rejected a pattern, choose a different control-flow pattern.
- Return only the complete Redcode source text.

Recent feedback:
{feedback or "No prior feedback."}

{parent_text}

{opponent_text}
"""


def _program_block(label: str, program: Program) -> str:
    return f"{label} {program.program_id}\n```redcode\n{program.source.strip()}\n```"
