"""
Readability Calculator Tool
===========================

Purpose
-------
Compute readability metrics for a given text input, to help ensure business
documents are accessible to a wide audience.

Metrics (implemented)
---------------------
- Flesch Reading Ease (FRE)
- Flesch-Kincaid Grade Level (FKGL)

Formulas
--------
Let:
  - W = number of words
  - S = number of sentences
  - Y = number of syllables

FRE  = 206.835 - 1.015*(W/S) - 84.6*(Y/W)
FKGL = 0.39*(W/S) + 11.8*(Y/W) - 15.59

Notes
-----
Syllable counting is heuristic-based (no external dictionaries). Results are
appropriate for relative comparisons, QA checks, and guardrails, but should not
be treated as perfectly precise for all edge cases (e.g., acronyms, names).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import re


class ToolInputError(ValueError):
    """Raised when tool inputs fail validation."""

    def __init__(self, message: str, *, code: str = "invalid_input", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


# ---- Parameter schemas (JSON-Schema-like dicts) ----

READABILITY_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "readability_calculator",
    "description": (
        "Compute readability metrics (Flesch Reading Ease and Flesch-Kincaid Grade Level) "
        "for a text string to help ensure business documents are accessible."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {
                "type": "string",
                "description": "The input text to analyze.",
                "minLength": 1,
            },
            "include_counts": {
                "type": "boolean",
                "description": "Whether to include counts (words/sentences/syllables/chars) in the output.",
                "default": True,
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum allowed characters in `text` for this tool call.",
                "default": 200_000,
                "minimum": 1,
            },
        },
        "required": ["text"],
    },
    "returns": {
        "type": "object",
        "description": "JSON-serializable result object.",
        "properties": {
            "ok": {"type": "boolean"},
            "error": {
                "type": ["object", "null"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "details": {"type": "object"},
                },
                "required": ["code", "message", "details"],
            },
            "metrics": {
                "type": ["object", "null"],
                "properties": {
                    "flesch_reading_ease": {"type": "number"},
                    "flesch_kincaid_grade_level": {"type": "number"},
                    "reading_ease_interpretation": {"type": "string"},
                    "grade_level_interpretation": {"type": "string"},
                },
                "required": [
                    "flesch_reading_ease",
                    "flesch_kincaid_grade_level",
                    "reading_ease_interpretation",
                    "grade_level_interpretation",
                ],
            },
            "counts": {
                "type": ["object", "null"],
                "properties": {
                    "characters": {"type": "integer"},
                    "words": {"type": "integer"},
                    "sentences": {"type": "integer"},
                    "syllables": {"type": "integer"},
                },
                "required": ["characters", "words", "sentences", "syllables"],
            },
        },
        "required": ["ok", "error", "metrics", "counts"],
    },
}


_VOWEL_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_SENTENCE_END_RE = re.compile(r"[.!?]+")


def _count_syllables_in_word(word: str) -> int:
    """
    Heuristic syllable counter for a single word.

    Strategy:
    - Count contiguous vowel groups as syllables
    - Subtract 1 for many trailing silent "e" cases
    - Add 1 for some consonant + "le" endings
    - Ensure minimum of 1 syllable for non-empty words
    """
    w = word.lower()
    if not w:
        return 0

    # Remove non-letters (defensive; word regex should already guarantee letters/apostrophes).
    w = re.sub(r"[^a-z']", "", w)
    if not w:
        return 0

    vowel_groups = _VOWEL_RE.findall(w)
    syllables = len(vowel_groups)

    # Silent 'e' at the end (but not words ending with 'le' preceded by a consonant).
    if w.endswith("e"):
        if not (w.endswith("le") and len(w) > 2 and w[-3].isalpha() and w[-3] not in "aeiouy"):
            syllables -= 1

    # Add syllable for consonant + 'le' endings (e.g., "table", "candle").
    if w.endswith("le") and len(w) > 2 and w[-3] not in "aeiouy":
        syllables += 1

    # Some very short words can underflow to 0.
    return max(1, syllables)


def _split_sentences(text: str) -> int:
    # Count sentence-ending punctuation clusters; fallback to 1 if there are words but no punctuation.
    ends = _SENTENCE_END_RE.findall(text)
    return len(ends)


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _count_syllables(text: str) -> int:
    return sum(_count_syllables_in_word(w) for w in _WORD_RE.findall(text))


def _reading_ease_label(score: float) -> str:
    # Common interpretation bands for FRE (approximate).
    if score >= 90:
        return "Very easy (about 5th grade)"
    if score >= 80:
        return "Easy (about 6th grade)"
    if score >= 70:
        return "Fairly easy (about 7th grade)"
    if score >= 60:
        return "Standard (about 8th-9th grade)"
    if score >= 50:
        return "Fairly difficult (about 10th–12th grade)"
    if score >= 30:
        return "Difficult (college)"
    return "Very confusing (college graduate)"


def _grade_level_label(grade: float) -> str:
    if grade < 0:
        return "Below grade 1"
    if grade < 1:
        return "Grade 1"
    if grade < 12:
        return f"Grade {int(round(grade))}"
    if grade < 16:
        return "College"
    return "College graduate"


def readability_calculator(*, text: str, include_counts: bool = True, max_chars: int = 200_000) -> Dict[str, Any]:
    """
    Compute readability metrics (Flesch Reading Ease and Flesch-Kincaid Grade Level).

    Parameters
    ----------
    text:
        The input text to analyze. Must be a non-empty string (validated at runtime).
    include_counts:
        If True, include computed counts in the output (characters/words/sentences/syllables).
    max_chars:
        Maximum allowed length of `text` in characters (guards against accidental huge inputs).

    Returns
    -------
    dict
        JSON-serializable dict with:
        - ok: bool
        - error: null or {code, message, details}
        - metrics: null or {flesch_reading_ease, flesch_kincaid_grade_level, ...}
        - counts: null or {characters, words, sentences, syllables} (if include_counts=True)

    Error Handling
    --------------
    This function returns structured errors (ok=False) instead of raising, making it
    convenient for agent/tool execution environments.
    """
    try:
        if not isinstance(max_chars, int) or max_chars <= 0:
            raise ToolInputError("`max_chars` must be a positive integer.", code="invalid_parameter", details={"max_chars": max_chars})

        if not isinstance(text, str):
            raise ToolInputError("`text` must be a string.", code="type_error", details={"received_type": type(text).__name__})

        if len(text) > max_chars:
            raise ToolInputError(
                "Input text exceeds `max_chars` limit.",
                code="too_large",
                details={"text_length": len(text), "max_chars": max_chars},
            )

        if text.strip() == "":
            raise ToolInputError("`text` cannot be empty or whitespace.", code="empty_text")

        characters = len(text)
        words = _count_words(text)
        if words == 0:
            raise ToolInputError("No words found in `text`.", code="no_words")

        sentences = _split_sentences(text)
        if sentences == 0:
            # If there are words but no sentence punctuation, treat as one sentence.
            sentences = 1

        syllables = _count_syllables(text)
        if syllables <= 0:
            raise ToolInputError("Failed to count syllables.", code="internal_count_error")

        words_per_sentence = words / sentences
        syllables_per_word = syllables / words

        flesch_reading_ease = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
        flesch_kincaid_grade_level = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59

        metrics = {
            "flesch_reading_ease": round(flesch_reading_ease, 2),
            "flesch_kincaid_grade_level": round(flesch_kincaid_grade_level, 2),
            "reading_ease_interpretation": _reading_ease_label(flesch_reading_ease),
            "grade_level_interpretation": _grade_level_label(flesch_kincaid_grade_level),
        }

        counts = None
        if include_counts:
            counts = {
                "characters": characters,
                "words": words,
                "sentences": sentences,
                "syllables": syllables,
            }

        return {"ok": True, "error": None, "metrics": metrics, "counts": counts}

    except ToolInputError as e:
        return {"ok": False, "error": {"code": e.code, "message": str(e), "details": e.details}, "metrics": None, "counts": None}
    except Exception as e:  # Defensive: keep tool failure structured for agent environments.
        return {
            "ok": False,
            "error": {"code": "unexpected_error", "message": f"Unexpected error: {e}", "details": {"exception_type": type(e).__name__}},
            "metrics": None,
            "counts": None,
        }


# ---- Optional wrapper class (matches assignment suggestion) ----

@dataclass(frozen=True)
class Tool:
    """
    Minimal tool wrapper for agent integration.

    Attributes
    ----------
    name:
        Stable tool identifier used by agents.
    description:
        Brief description of what the tool does.
    fn:
        Callable implementing the tool. Should accept **kwargs and return JSON-serializable dict.
    schema:
        Parameter/return schema to support function-calling style tool selection.
    """

    name: str
    description: str
    fn: Any
    schema: Dict[str, Any]

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        return self.fn(**kwargs)


READABILITY_TOOL = Tool(
    name=READABILITY_TOOL_SCHEMA["name"],
    description=READABILITY_TOOL_SCHEMA["description"],
    fn=readability_calculator,
    schema=READABILITY_TOOL_SCHEMA,
)

