from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tool import READABILITY_TOOL, Tool


@dataclass
class Agent:
    """
    Tiny demo agent that can call tools.

    This is intentionally simple (no external libraries). It demonstrates:
    - manual tool selection (rule-based)
    - function-calling style selection (tool name + arguments)
    """

    name: str
    tools: List[Tool]

    def _get_tool_by_name(self, tool_name: str) -> Tool:
        for t in self.tools:
            if t.name == tool_name:
                return t
        raise KeyError(f"Tool not found: {tool_name}")

    def run_manual(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Manual tool selection: choose a tool with simple rules.
        """
        task_l = task.lower()
        if any(k in task_l for k in ["readability", "grade level", "flesch", "accessible", "plain language"]):
            tool = self._get_tool_by_name("readability_calculator")
            return tool.execute(**payload)
        return {
            "ok": False,
            "error": {"code": "no_tool_selected", "message": "Agent did not select any tool for this task.", "details": {"task": task}},
            "metrics": None,
            "counts": None,
        }

    def run_function_calling(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Function-calling style: the agent receives a tool call object and executes it.

        Expected format:
        {
          "tool_name": "readability_calculator",
          "arguments": {"text": "...", "include_counts": true}
        }
        """
        tool_name = tool_call.get("tool_name")
        arguments = tool_call.get("arguments", {})

        if not isinstance(tool_name, str) or tool_name.strip() == "":
            return {
                "ok": False,
                "error": {"code": "invalid_tool_call", "message": "`tool_name` must be a non-empty string.", "details": {"tool_call": tool_call}},
                "metrics": None,
                "counts": None,
            }

        if not isinstance(arguments, dict):
            return {
                "ok": False,
                "error": {"code": "invalid_tool_call", "message": "`arguments` must be an object/dict.", "details": {"arguments_type": type(arguments).__name__}},
                "metrics": None,
                "counts": None,
            }

        try:
            tool = self._get_tool_by_name(tool_name)
        except KeyError as e:
            return {
                "ok": False,
                "error": {"code": "unknown_tool", "message": str(e), "details": {"available_tools": [t.name for t in self.tools]}},
                "metrics": None,
                "counts": None,
            }

        return tool.execute(**arguments)


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def main() -> None:
    agent = Agent(name="DocumentQualityAgent", tools=[READABILITY_TOOL])

    business_text = (
        "This policy explains how we collect and use your data. "
        "We only collect what we need to provide the service. "
        "You can request deletion of your account at any time by emailing support."
    )

    print("=== Tool schema (inputs/outputs) ===")
    print(_pretty(READABILITY_TOOL.schema))
    print()

    print("=== Demo A: Manual tool selection (success) ===")
    result_ok = agent.run_manual(
        task="Check readability and grade level for this business notice.",
        payload={"text": business_text, "include_counts": True},
    )
    print(_pretty(result_ok))
    print()

    print("=== Demo B: Manual tool selection (error handling) ===")
    result_bad = agent.run_manual(
        task="Check readability for this text.",
        payload={"text": "   "},  # bad input: whitespace-only
    )
    print(_pretty(result_bad))
    print()

    print("=== Demo C: Function-calling style (success) ===")
    tool_call_ok = {
        "tool_name": "readability_calculator",
        "arguments": {"text": business_text, "include_counts": False},
    }
    print(_pretty(agent.run_function_calling(tool_call_ok)))
    print()

    print("=== Demo D: Function-calling style (unknown tool) ===")
    tool_call_unknown = {"tool_name": "not_a_real_tool", "arguments": {"text": business_text}}
    print(_pretty(agent.run_function_calling(tool_call_unknown)))


if __name__ == "__main__":
    main()

