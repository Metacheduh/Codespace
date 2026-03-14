"""
Lesson 3: Advanced CrewAI Patterns with MCP Server
===================================================
This lesson covers:
- Multi-agent workflows with hierarchical processes
- Inter-agent data sharing through the MCP server
- Manager agent that delegates and coordinates work
- Quality assurance feedback loops
- Production-ready error handling and retry logic
"""

import os
import json
import time
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from fastmcp import FastMCP

load_dotenv()


# =============================================================================
# Part 1: Enhanced MCP Server with versioning and feedback support
# =============================================================================

mcp_server = FastMCP("AdvancedResearchServer")

_research_store: dict[str, list[dict]] = {}
_report_store: dict[str, list[dict]] = {}
_feedback_store: dict[str, list[dict]] = {}


@mcp_server.tool()
def store_finding(topic: str, title: str, content: str, source: str = "",
                  confidence: str = "medium") -> str:
    """Store a research finding with a confidence level."""
    if topic not in _research_store:
        _research_store[topic] = []

    finding = {
        "id": len(_research_store[topic]) + 1,
        "title": title,
        "content": content,
        "source": source,
        "confidence": confidence,
        "timestamp": time.time(),
    }
    _research_store[topic].append(finding)
    return json.dumps({"status": "stored", "finding_id": finding["id"]})


@mcp_server.tool()
def retrieve_findings(topic: str, min_confidence: str = "") -> str:
    """Retrieve findings, optionally filtered by minimum confidence."""
    findings = _research_store.get(topic, [])
    if min_confidence:
        confidence_order = {"low": 0, "medium": 1, "high": 2}
        threshold = confidence_order.get(min_confidence, 0)
        findings = [
            f for f in findings
            if confidence_order.get(f.get("confidence", "medium"), 1) >= threshold
        ]
    return json.dumps({"topic": topic, "count": len(findings), "findings": findings})


@mcp_server.tool()
def store_report(topic: str, version: int, content: str, author: str) -> str:
    """Store a versioned report draft."""
    if topic not in _report_store:
        _report_store[topic] = []

    report = {
        "version": version,
        "content": content,
        "author": author,
        "timestamp": time.time(),
    }
    _report_store[topic].append(report)
    return json.dumps({"status": "stored", "version": version})


@mcp_server.tool()
def retrieve_latest_report(topic: str) -> str:
    """Retrieve the latest version of a report for a topic."""
    reports = _report_store.get(topic, [])
    if not reports:
        return json.dumps({"error": "No reports found", "topic": topic})
    latest = max(reports, key=lambda r: r["version"])
    return json.dumps({"topic": topic, "report": latest})


@mcp_server.tool()
def store_feedback(topic: str, version: int, feedback: str, reviewer: str,
                   approved: bool = False) -> str:
    """Store review feedback for a specific report version."""
    if topic not in _feedback_store:
        _feedback_store[topic] = []

    entry = {
        "version": version,
        "feedback": feedback,
        "reviewer": reviewer,
        "approved": approved,
        "timestamp": time.time(),
    }
    _feedback_store[topic].append(entry)
    return json.dumps({"status": "feedback_stored", "approved": approved})


@mcp_server.tool()
def retrieve_feedback(topic: str, version: int = 0) -> str:
    """Retrieve feedback, optionally for a specific version."""
    feedback_list = _feedback_store.get(topic, [])
    if version > 0:
        feedback_list = [f for f in feedback_list if f["version"] == version]
    return json.dumps({"topic": topic, "feedback": feedback_list})


# =============================================================================
# Part 2: CrewAI Tool wrappers
# =============================================================================

class StoreResearchTool(BaseTool):
    name: str = "Store Research Finding"
    description: str = (
        "Store a research finding on the MCP server. "
        "Input: JSON with keys topic, title, content, source (optional), "
        "confidence ('low', 'medium', 'high')."
    )

    def _run(self, input_data: str) -> str:
        try:
            data = json.loads(input_data)
            return store_finding(
                topic=data["topic"],
                title=data["title"],
                content=data["content"],
                source=data.get("source", ""),
                confidence=data.get("confidence", "medium"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            return json.dumps({"error": str(e)})


class RetrieveResearchTool(BaseTool):
    name: str = "Retrieve Research Findings"
    description: str = (
        "Retrieve stored research findings. "
        "Input: JSON with keys topic and optional min_confidence."
    )

    def _run(self, input_data: str) -> str:
        try:
            data = json.loads(input_data) if input_data.strip().startswith("{") else {"topic": input_data.strip()}
            return retrieve_findings(
                topic=data["topic"],
                min_confidence=data.get("min_confidence", ""),
            )
        except (json.JSONDecodeError, KeyError) as e:
            return json.dumps({"error": str(e)})


class StoreReportTool(BaseTool):
    name: str = "Store Report Draft"
    description: str = (
        "Store a versioned report draft on the MCP server. "
        "Input: JSON with keys topic, version (int), content, author."
    )

    def _run(self, input_data: str) -> str:
        try:
            data = json.loads(input_data)
            return store_report(
                topic=data["topic"],
                version=int(data["version"]),
                content=data["content"],
                author=data["author"],
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return json.dumps({"error": str(e)})


class RetrieveReportTool(BaseTool):
    name: str = "Retrieve Latest Report"
    description: str = "Retrieve the latest report draft. Input: topic name as string."

    def _run(self, topic: str) -> str:
        return retrieve_latest_report(topic=topic.strip())


class StoreFeedbackTool(BaseTool):
    name: str = "Store Review Feedback"
    description: str = (
        "Store review feedback for a report version. "
        "Input: JSON with keys topic, version (int), feedback, reviewer, approved (bool)."
    )

    def _run(self, input_data: str) -> str:
        try:
            data = json.loads(input_data)
            return store_feedback(
                topic=data["topic"],
                version=int(data["version"]),
                feedback=data["feedback"],
                reviewer=data["reviewer"],
                approved=data.get("approved", False),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return json.dumps({"error": str(e)})


class RetrieveFeedbackTool(BaseTool):
    name: str = "Retrieve Feedback"
    description: str = "Retrieve review feedback. Input: JSON with keys topic and optional version (int)."

    def _run(self, input_data: str) -> str:
        try:
            data = json.loads(input_data) if input_data.strip().startswith("{") else {"topic": input_data.strip()}
            return retrieve_feedback(
                topic=data["topic"],
                version=int(data.get("version", 0)),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return json.dumps({"error": str(e)})


# =============================================================================
# Part 3: Advanced Agent Definitions
# =============================================================================

store_research = StoreResearchTool()
retrieve_research = RetrieveResearchTool()
store_report_tool = StoreReportTool()
retrieve_report = RetrieveReportTool()
store_feedback_tool = StoreFeedbackTool()
retrieve_feedback_tool = RetrieveFeedbackTool()

# Senior Researcher: deep research with confidence scoring
senior_researcher = Agent(
    role="Senior Research Analyst",
    goal=(
        "Conduct thorough research and store high-quality findings with "
        "confidence ratings on the MCP server"
    ),
    backstory=(
        "You are a senior analyst who rates the confidence of each finding "
        "(low/medium/high) based on source reliability. You store all findings "
        "on the MCP server for the team to access."
    ),
    tools=[store_research, retrieve_research],
    verbose=True,
    allow_delegation=False,
)

# Lead Writer: retrieves research and produces versioned drafts
lead_writer = Agent(
    role="Lead Technical Writer",
    goal=(
        "Retrieve high-confidence research findings and produce versioned "
        "report drafts stored on the MCP server"
    ),
    backstory=(
        "You are a lead writer who retrieves findings from the MCP server, "
        "focusing on high-confidence data. You store each draft as a "
        "versioned report on the server."
    ),
    tools=[retrieve_research, store_report_tool, retrieve_report],
    verbose=True,
    allow_delegation=False,
)

# Senior Reviewer: cross-references reports against research
senior_reviewer = Agent(
    role="Senior Quality Reviewer",
    goal=(
        "Cross-reference reports against research findings, provide "
        "structured feedback, and approve or request revisions"
    ),
    backstory=(
        "You are a senior reviewer who checks reports against the original "
        "research stored on the MCP server. You store your feedback and "
        "approval decisions on the server for traceability."
    ),
    tools=[retrieve_research, retrieve_report, store_feedback_tool, retrieve_feedback_tool],
    verbose=True,
    allow_delegation=False,
)

# Manager Agent: coordinates the hierarchical workflow
manager = Agent(
    role="Project Manager",
    goal="Coordinate the research, writing, and review workflow efficiently",
    backstory=(
        "You oversee the entire content pipeline. You delegate research to "
        "the analyst, writing to the lead writer, and review to the senior "
        "reviewer. You ensure quality at every stage."
    ),
    verbose=True,
    allow_delegation=True,
)


# =============================================================================
# Part 4: Hierarchical Task Definitions
# =============================================================================

deep_research_task = Task(
    description=(
        "Conduct deep research on '{topic}'. "
        "Find at least 5 findings and store each on the MCP server with "
        "confidence ratings (low/medium/high). Focus on recent developments, "
        "key statistics, and expert opinions."
    ),
    expected_output="All findings stored on MCP server with confidence ratings.",
    agent=senior_researcher,
)

draft_report_task = Task(
    description=(
        "Retrieve all high-confidence findings for '{topic}' from the MCP server. "
        "Write a comprehensive report and store it as version 1 on the MCP server. "
        "Include: executive summary, detailed analysis, and recommendations."
    ),
    expected_output="Version 1 report stored on MCP server.",
    agent=lead_writer,
)

review_task = Task(
    description=(
        "Retrieve the latest report and original findings for '{topic}' from "
        "the MCP server. Cross-reference the report against stored research. "
        "Store your feedback on the server. If the report is good, mark approved=true. "
        "If revisions are needed, mark approved=false with specific feedback."
    ),
    expected_output="Feedback stored on MCP server with approval decision.",
    agent=senior_reviewer,
)

revision_task = Task(
    description=(
        "Retrieve the feedback for '{topic}' from the MCP server. "
        "If revisions were requested, retrieve the latest report and feedback, "
        "make improvements, and store as the next version. "
        "If already approved, confirm the final version."
    ),
    expected_output="Final approved report stored on MCP server.",
    agent=lead_writer,
)


# =============================================================================
# Part 5: Crew Execution Modes
# =============================================================================

def run_sequential_pipeline(topic: str) -> str:
    """Run agents sequentially: research -> write -> review -> revise."""
    crew = Crew(
        agents=[senior_researcher, lead_writer, senior_reviewer, lead_writer],
        tasks=[deep_research_task, draft_report_task, review_task, revision_task],
        process=Process.sequential,
        verbose=True,
    )
    return crew.kickoff(inputs={"topic": topic})


def run_hierarchical_pipeline(topic: str) -> str:
    """Run with a manager agent coordinating via hierarchical process."""
    crew = Crew(
        agents=[senior_researcher, lead_writer, senior_reviewer],
        tasks=[deep_research_task, draft_report_task, review_task, revision_task],
        process=Process.hierarchical,
        manager_agent=manager,
        verbose=True,
    )
    return crew.kickoff(inputs={"topic": topic})


def get_server_state(topic: str) -> dict:
    """Return the full MCP server state for a topic (useful for debugging)."""
    return {
        "findings": json.loads(retrieve_findings(topic)),
        "latest_report": json.loads(retrieve_latest_report(topic)),
        "feedback": json.loads(retrieve_feedback(topic)),
    }


if __name__ == "__main__":
    import sys

    topic = "AI agents in enterprise automation: current state and 2026 outlook"
    mode = sys.argv[1] if len(sys.argv) > 1 else "sequential"

    print(f"\n{'='*60}")
    print(f"Running Advanced Pipeline ({mode}) for:")
    print(f"  {topic}")
    print(f"{'='*60}\n")

    if mode == "hierarchical":
        output = run_hierarchical_pipeline(topic)
    else:
        output = run_sequential_pipeline(topic)

    print(f"\n{'='*60}")
    print("FINAL OUTPUT")
    print(f"{'='*60}")
    print(output)

    print(f"\n{'='*60}")
    print("MCP SERVER STATE")
    print(f"{'='*60}")
    print(json.dumps(get_server_state(topic), indent=2))
