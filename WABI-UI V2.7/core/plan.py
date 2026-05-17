"""
plan.py — Typed plan schema + validation layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# KEY_ALIASES lives in prompter.py — single source of truth for the alias table
from ..llm.prompter import KEY_ALIASES


# ---------------------------------------------------------------------------
# Alias expansion (was in checker.py — moved here, owns the transform)
# ---------------------------------------------------------------------------

def _expand_aliases(obj: Any) -> Any:
    """
    Recursively replace short LLM output keys with canonical builder keys.
    Walks the entire tree so nested items[], gauges[], sections[] are all
    normalised before reaching builder.py.
    """
    if isinstance(obj, dict):
        return {KEY_ALIASES.get(k, k): _expand_aliases(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_aliases(x) for x in obj]
    return obj


# ---------------------------------------------------------------------------
# Plan — the schema contract
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    """
    Represents a fully validated, alias-expanded UI plan ready for builder.py.

    Attributes
    ----------
    mode     : intent string — 'recognition', 'recommendation', 'fallback', etc.
    summary  : short header text shown in the card header (<=120 chars)
    sections : list of section dicts, each guaranteed to have a non-empty 'type' key.
               Section dicts keep their dict form so builder.py renderers are unchanged.
    """
    mode:     str
    summary:  str
    sections: List[Dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(
        cls,
        raw: Dict[str, Any],
        intent_default: str = "fallback",
    ) -> "Plan":
        """
        Build a Plan from a raw LLM-output dict.

        Steps:
          1. Expand short key aliases (e.g. 'ttl' → 'title')
          2. Coerce top-level fields to expected types
          3. Filter sections: keep only dicts with a non-empty 'type' string
          4. Truncate summary to 120 chars
        """
        if not isinstance(raw, dict):
            raw = {}

        expanded = _expand_aliases(raw)

        mode    = str(expanded.get("mode") or intent_default).strip() or intent_default
        summary = str(expanded.get("summary") or "")[:120]

        raw_sections = expanded.get("sections")
        if not isinstance(raw_sections, list):
            raw_sections = []

        sections: List[Dict[str, Any]] = [
            s for s in raw_sections
            if isinstance(s, dict)
            and isinstance(s.get("type"), str)
            and s["type"].strip()
        ]

        return cls(mode=mode, summary=summary, sections=sections)

    # ------------------------------------------------------------------
    # Serialisation (backward compat with anything expecting a plain dict)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode":     self.mode,
            "summary":  self.summary,
            "sections": self.sections,
        }

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.sections)

    def __bool__(self) -> bool:
        return bool(self.sections)

    def __repr__(self) -> str:
        return (
            f"Plan(mode={self.mode!r}, summary={self.summary[:40]!r}..., "
            f"sections=[{len(self.sections)} items])"
        )
