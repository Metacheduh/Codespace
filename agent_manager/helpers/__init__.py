"""
Optional LLM helper modules (advisory only).

These helpers may use an LLM for summarization or tagging but
MUST NEVER:
  - confirm deposits
  - trigger alerts
  - modify authoritative database facts
  - drive scheduling or routing decisions

All outputs are treated as advisory text/tags only.
"""
