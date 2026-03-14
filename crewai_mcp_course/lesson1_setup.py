"""
Lesson 1: Setting Up CrewAI with MCP Server Access
===================================================
This lesson covers:
- Installing and configuring CrewAI
- Creating basic agents (Researcher, Writer, Reviewer)
- Defining tasks and executing a simple crew workflow
"""

import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process

# Load environment variables
load_dotenv()


# --- Agent Definitions ---

researcher = Agent(
    role="Research Analyst",
    goal="Gather comprehensive and accurate information on the given topic",
    backstory=(
        "You are an experienced research analyst with a knack for finding "
        "reliable data and distilling complex information into clear findings. "
        "You always cite your sources and verify facts before reporting."
    ),
    verbose=True,
    allow_delegation=False,
)

writer = Agent(
    role="Content Writer",
    goal="Produce a well-structured, engaging report based on research findings",
    backstory=(
        "You are a skilled technical writer who transforms raw research data "
        "into polished, reader-friendly reports. You focus on clarity, logical "
        "flow, and actionable insights."
    ),
    verbose=True,
    allow_delegation=False,
)

reviewer = Agent(
    role="Quality Reviewer",
    goal="Review reports for accuracy, completeness, and readability",
    backstory=(
        "You are a meticulous editor with years of experience in quality "
        "assurance. You check for factual errors, logical gaps, grammar "
        "issues, and ensure the final output meets high standards."
    ),
    verbose=True,
    allow_delegation=False,
)


# --- Task Definitions ---

research_task = Task(
    description=(
        "Research the topic: '{topic}'. "
        "Gather key facts, statistics, and insights. "
        "Organize your findings into a structured summary with clear sections."
    ),
    expected_output="A structured research summary with key findings, data points, and sources.",
    agent=researcher,
)

writing_task = Task(
    description=(
        "Using the research findings provided, write a comprehensive report on '{topic}'. "
        "The report should include an introduction, main body with key sections, "
        "and a conclusion with actionable recommendations."
    ),
    expected_output="A polished report with introduction, body sections, and conclusion.",
    agent=writer,
)

review_task = Task(
    description=(
        "Review the written report for accuracy, completeness, grammar, and readability. "
        "Provide specific feedback and a final improved version of the report."
    ),
    expected_output="A reviewed and improved final report with quality feedback notes.",
    agent=reviewer,
)


# --- Crew Assembly & Execution ---

def run_crew(topic: str) -> str:
    """Assemble and run the crew with the given topic."""
    crew = Crew(
        agents=[researcher, writer, reviewer],
        tasks=[research_task, writing_task, review_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff(inputs={"topic": topic})
    return result


if __name__ == "__main__":
    topic = "The current state and future of AI agents in enterprise automation"
    print(f"\n{'='*60}")
    print(f"Running CrewAI Pipeline for: {topic}")
    print(f"{'='*60}\n")

    output = run_crew(topic)

    print(f"\n{'='*60}")
    print("FINAL OUTPUT")
    print(f"{'='*60}")
    print(output)
