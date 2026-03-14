"""
Lesson 2: Integrating MCP Server with CrewAI
=============================================
This lesson covers:
- Setting up a FastMCP server with research tools
- Creating custom CrewAI tools that connect to the MCP server
- Authentication and error handling for server communication
- Agents using MCP-backed tools to store and retrieve data
"""

import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from pydantic import Field
from fastmcp import FastMCP

load_dotenv()


# =============================================================================
# Part 1: FastMCP Server Definition
# =============================================================================

mcp_server = FastMCP("ResearchServer")

# In-memory store for research findings
_research_store: dict[str, list[dict]] = {}


@mcp_server.tool()
def store_finding(topic: str, title: str, content: str, source: str = "") -> str:
    """Store a research finding on the MCP server."""
    if topic not in _research_store:
        _research_store[topic] = []

    finding = {"title": title, "content": content, "source": source}
    _research_store[topic].append(finding)
    return json.dumps({"status": "stored", "topic": topic, "finding": title})


@mcp_server.tool()
def retrieve_findings(topic: str) -> str:
    """Retrieve all stored findings for a given topic."""
    findings = _research_store.get(topic, [])
    return json.dumps({"topic": topic, "count": len(findings), "findings": findings})


@mcp_server.tool()
def list_topics() -> str:
    """List all topics that have stored findings."""
    topics = list(_research_store.keys())
    return json.dumps({"topics": topics, "count": len(topics)})


@mcp_server.tool()
def clear_findings(topic: str) -> str:
    """Clear all findings for a given topic."""
    removed = len(_research_store.pop(topic, []))
    return json.dumps({"status": "cleared", "topic": topic, "removed_count": removed})


# =============================================================================
# Part 2: Custom CrewAI Tools wrapping MCP Server calls
# =============================================================================

class StoreResearchTool(BaseTool):
    name: str = "Store Research Finding"
    description: str = (
        "Store a research finding on the MCP server. "
        "Input should be a JSON string with keys: topic, title, content, source (optional)."
    )

    def _run(self, input_data: str) -> str:
        try:
            data = json.loads(input_data)
            return store_finding(
                topic=data["topic"],
                title=data["title"],
                content=data["content"],
                source=data.get("source", ""),
            )
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON input"})
        except KeyError as e:
            return json.dumps({"error": f"Missing required field: {e}"})


class RetrieveResearchTool(BaseTool):
    name: str = "Retrieve Research Findings"
    description: str = (
        "Retrieve all stored research findings for a given topic from the MCP server. "
        "Input should be the topic name as a plain string."
    )

    def _run(self, topic: str) -> str:
        return retrieve_findings(topic=topic.strip())


class ListTopicsTool(BaseTool):
    name: str = "List Research Topics"
    description: str = "List all topics that have stored findings on the MCP server."

    def _run(self, _input: str = "") -> str:
        return list_topics()


# =============================================================================
# Part 3: Agents with MCP-backed Tools
# =============================================================================

store_tool = StoreResearchTool()
retrieve_tool = RetrieveResearchTool()
list_topics_tool = ListTopicsTool()

researcher = Agent(
    role="MCP Research Analyst",
    goal="Research topics and store findings on the MCP server for team access",
    backstory=(
        "You are a diligent researcher who uses the MCP server to persist "
        "your findings so other team members can access them. You always "
        "store your data in a structured format with clear titles and sources."
    ),
    tools=[store_tool, retrieve_tool, list_topics_tool],
    verbose=True,
    allow_delegation=False,
)

writer = Agent(
    role="MCP-Integrated Writer",
    goal="Retrieve research findings from the MCP server and produce polished reports",
    backstory=(
        "You are a writer who pulls data from the shared MCP research store "
        "to create comprehensive reports. You always retrieve the latest "
        "findings before writing."
    ),
    tools=[retrieve_tool, list_topics_tool],
    verbose=True,
    allow_delegation=False,
)

reviewer = Agent(
    role="Quality Reviewer",
    goal="Review reports for accuracy and completeness against stored research",
    backstory=(
        "You cross-reference written reports against the original research "
        "findings stored on the MCP server to ensure nothing was missed "
        "or misrepresented."
    ),
    tools=[retrieve_tool],
    verbose=True,
    allow_delegation=False,
)


# =============================================================================
# Part 4: Tasks & Execution
# =============================================================================

research_task = Task(
    description=(
        "Research the topic: '{topic}'. "
        "Find at least 3 key findings and store each one on the MCP server "
        "using the Store Research Finding tool. Include titles, content, and sources."
    ),
    expected_output="Confirmation that findings have been stored on the MCP server.",
    agent=researcher,
)

writing_task = Task(
    description=(
        "Retrieve all findings for '{topic}' from the MCP server. "
        "Write a comprehensive report incorporating all stored research findings."
    ),
    expected_output="A complete report based on MCP-stored research findings.",
    agent=writer,
)

review_task = Task(
    description=(
        "Retrieve the original findings for '{topic}' from the MCP server. "
        "Compare them against the written report. Flag any inaccuracies or "
        "missing information. Produce a final improved version."
    ),
    expected_output="A reviewed final report with quality notes.",
    agent=reviewer,
)


def run_mcp_crew(topic: str) -> str:
    """Run the MCP-integrated crew pipeline."""
    crew = Crew(
        agents=[researcher, writer, reviewer],
        tasks=[research_task, writing_task, review_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff(inputs={"topic": topic})
    return result


if __name__ == "__main__":
    topic = "Large Language Model agents and tool use"
    print(f"\n{'='*60}")
    print(f"Running MCP-Integrated CrewAI Pipeline for: {topic}")
    print(f"{'='*60}\n")

    output = run_mcp_crew(topic)

    print(f"\n{'='*60}")
    print("FINAL OUTPUT")
    print(f"{'='*60}")
    print(output)

    # Show what was stored on the MCP server
    print(f"\n{'='*60}")
    print("MCP SERVER STATE")
    print(f"{'='*60}")
    print(retrieve_findings(topic))
