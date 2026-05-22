"""Small Redcode helpers used before invoking pMARS."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable

OPCODES = (
    "DAT",
    "MOV",
    "ADD",
    "SUB",
    "MUL",
    "DIV",
    "MOD",
    "JMP",
    "JMZ",
    "JMN",
    "DJN",
    "CMP",
    "SEQ",
    "SNE",
    "SLT",
    "SPL",
    "NOP",
    "LDP",
    "STP",
)


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def extract_redcode(text: str) -> str:
    fenced = re.search(r"```(?:redcode|red|asm)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip() + "\n"
    return text.strip() + "\n"


def normalize_source(source: str) -> str:
    lines = [line.rstrip() for line in source.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip() + "\n"


def opcode_counts(source: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for line in _code_lines(source):
        token = _opcode_token(line)
        if token in OPCODES:
            counts[token] += 1
    return counts


def static_features(source: str) -> dict[str, float]:
    code = list(_code_lines(source))
    counts = opcode_counts(source)
    total = max(1, sum(counts.values()))
    features = {
        "line_count": float(len(code)),
        "instruction_count": float(sum(counts.values())),
        "dat_density": counts["DAT"] / total,
        "spl_density": counts["SPL"] / total,
        "jmp_density": counts["JMP"] / total,
    }
    for opcode in OPCODES:
        features[f"opcode_{opcode.lower()}"] = counts[opcode] / total
    return features


def dominant_opcode(source: str) -> str:
    counts = opcode_counts(source)
    if not counts:
        return "unknown"
    return counts.most_common(1)[0][0].lower()


def _code_lines(source: str) -> Iterable[str]:
    for raw in source.splitlines():
        line = raw.split(";", 1)[0].strip()
        if line:
            yield line


def _opcode_token(line: str) -> str:
    parts = re.split(r"\s+", line, maxsplit=2)
    if not parts:
        return ""
    first = parts[0].upper().split(".", 1)[0]
    if first in OPCODES:
        return first
    if len(parts) > 1:
        return parts[1].upper().split(".", 1)[0]
    return first
