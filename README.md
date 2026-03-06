# Readability Calculator Tool

## What the tool does
This project implements a **Readability Calculator** tool that computes:
- **Flesch Reading Ease (FRE)**: higher is easier to read
- **Flesch-Kincaid Grade Level (FKGL)**: approximate U.S. school grade level

**Use case:** quickly check whether business documents (policies, announcements, emails) are understandable for a broad audience.

The tool includes:
- **Input validation + structured error handling**
- **Clear parameter schema** (inputs/outputs) in `READABILITY_TOOL_SCHEMA`
- **Agent integration demo** using:
  - manual tool selection, and
  - function-calling style tool execution

## Files
- `tool.py`: tool implementation + schema + wrapper class
- `demo.py`: integration demo script
- `prompt-log.md`: full AI chat history used to produce this submission

## How to run the demo
From this folder:

```bash
python demo.py
```

You should see:
- the tool schema printed
- a successful readability run
- a failure case (bad input) showing structured error output

## Design decisions and limitations
- **JSON-serializable outputs**: tool returns a dict with `ok`, `error`, `metrics`, `counts` for easy agent consumption.
- **No external libraries**: uses only Python standard library for portability.
- **Heuristic syllable counting**: syllables are estimated using vowel-group rules and common English adjustments. This is good for *comparisons and guardrails*, but not perfect for acronyms, names, and unusual words.
- **Sentence detection**: sentences are estimated from `. ! ?`. If none are found but words exist, the tool assumes **1 sentence**.
- **Safety limits**: `max_chars` prevents accidental huge inputs.

