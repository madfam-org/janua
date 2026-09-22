"""janua MCP server (pilot slice: transactional email).

P1 pilot per internal-devops/roadmaps/2026-09-22-ecosystem-strategic-priorities.md.
See app/mcp/README.md for the generator mapping, the auth model, and how to extend.
"""

from .generator import ToolOverride, ToolSpec, generate_tools

__all__ = ["ToolOverride", "ToolSpec", "generate_tools"]
