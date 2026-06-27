"""Tool Mesh — tool registration, orchestration, dependency tracking, and agent governance.

Components:
  - ToolRegistry:     register + execute tools with input validation
  - ToolGraph:        track inter-tool dependencies for impact analysis
  - AgentToolLayer:   agent-facing interface with governance (forbidden ops,
                      ActionRegistry bridge, QA post-validation)
"""
