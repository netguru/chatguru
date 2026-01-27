"""
PromptFoo Python Provider Adapter for chatguru Agent.

This adapter enables PromptFoo to evaluate the chatguru Agent without
building Docker containers or starting the full application.
It directly calls the Agent class from src/agent/service.py.

Usage in promptfooconfig.yaml:
    providers:
      - id: 'file://provider.py'
        label: 'chatguru Agent'
        config:
          pythonExecutable: '../.venv/bin/python'
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add the src directory to the path so we can import agent modules
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent
_src_dir = _project_root / "src"
sys.path.insert(0, str(_src_dir))

# Import Agent at module level after path is set up
from agent.service import Agent  # noqa: E402


def call_api(
    prompt: str, options: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """
    Main entry point for PromptFoo to call the chatguru Agent.

    This function is called by PromptFoo for each test case.
    It wraps the async Agent.astream() method in a synchronous call.

    Args:
        prompt: The prompt/message to send to the agent
        options: Provider configuration options from promptfooconfig.yaml
        context: Additional context including vars and other test data

    Returns:
        Dictionary with 'output' key containing the response,
        or 'error' key if something went wrong
    """
    # options is required by PromptFoo interface but not used here
    _ = options

    try:
        # Get conversation history from context vars if provided
        history = context.get("vars", {}).get("history", None)

        # Run the async agent call synchronously
        response = asyncio.run(_run_agent(prompt, history))

    except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
        return {"error": f"Agent error: {e!s}"}

    else:
        return {"output": response}


async def _run_agent(prompt: str, history: list[dict[str, str]] | None = None) -> str:
    """
    Run the chatguru Agent asynchronously and collect the streamed response.

    Args:
        prompt: The user's message to send to the agent
        history: Optional conversation history

    Returns:
        The complete agent response as a string
    """
    # Create a new Agent instance for each call
    agent = Agent()

    # Collect all streamed chunks into a single response using async comprehension
    response_chunks = [chunk async for chunk in agent.astream(prompt, history=history)]

    return "".join(response_chunks)
