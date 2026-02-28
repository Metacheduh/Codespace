"""
Deterministic Agent Manager
============================
Rule-based orchestration for victim-compensation monitoring.

All scheduling, alerting, and job-routing decisions are driven by
config.yaml rules, DAG dependencies, and explicit state-machine
transitions.  No LLM is used in any authoritative decision path.
"""

__version__ = "0.1.0"
