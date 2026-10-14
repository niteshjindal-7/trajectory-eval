"""
graph.py — RxSafetyAgent LangGraph Workflow

Builds and compiles the agent graph for the healthcare/pharmacy domain.

Graph structure:
    START → agent_node → should_continue → tool_node_with_tracking → agent_node → ...
                                         → END

Nodes:
    agent_node              — LLM reasoning: reads messages, decides next action
    tool_node_with_tracking — executes whichever tool agent requested + tracks latency

Exported:
    app — compiled graph, used by runner.py
"""

import time

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI

from traj_eval.agent.state import AgentState
from traj_eval.datasets.openfda.tools import OPENFDA_TOOLS
from traj_eval.utils.config import settings


# ── 1. LLM with tools bound ───────────────────────────────────────────────────

llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_TASK_MODEL,
    google_api_key=settings.GEMINI_API_KEY
)
llm_with_tools = llm.bind_tools(OPENFDA_TOOLS)
# LLM now knows all 4 tools by name and can request them via tool_calls


# ── 2. Prebuilt ToolNode ──────────────────────────────────────────────────────

_tool_node = ToolNode(OPENFDA_TOOLS)
# Prebuilt by LangGraph — reads AIMessage.tool_calls, executes matching tool,
# returns ToolMessage. We wrap it below to add latency tracking on top.


# ── 3. agent_node ─────────────────────────────────────────────────────────────

def agent_node(state: AgentState) -> dict:
    """
    LLM reasoning node — the brain of the agent.

    Receives full message history (all previous steps).
    Calls LLM which returns either:
      (a) AIMessage with tool_calls  → agent wants to call a tool
      (b) AIMessage with content     → agent has final answer, task complete

    Also tracks token usage for cost calculation.
    """
    response = llm_with_tools.invoke(state["messages"])

    # Extract token counts for cost tracking
    usage = response.usage_metadata or {}
    input_tokens  = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # Record end_time only when giving final answer (no tool calls pending)
    end_time = time.time() if not response.tool_calls else state.get("end_time", 0.0)

    return {
        "messages":            [response],
        "total_input_tokens":  state.get("total_input_tokens", 0)  + input_tokens,
        "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
        "end_time":            end_time
    }


# ── 4. tool_node_with_tracking ────────────────────────────────────────────────

def tool_node_with_tracking(state: AgentState) -> dict:
    """
    Wrapper around LangGraph's prebuilt ToolNode.

    Adds per-tool latency tracking on top of the standard tool execution.
    Records which tool was called, how long it took, and appends to step_latencies.

    Increments steps_taken counter — used by should_continue to enforce max_steps.
    """
    step_start = time.time()

    # Find out which tool the agent requested
    tool_name = state["messages"][-1].tool_calls[0]["name"]

    # Execute the tool using LangGraph's prebuilt ToolNode
    result = _tool_node.invoke(state)

    # Measure how long the tool call took
    duration_ms = round((time.time() - step_start) * 1000)

    # Build the step record for latency tracking
    new_step = {
        "step":        state.get("steps_taken", 0) + 1,
        "tool":        tool_name,
        "duration_ms": duration_ms
    }

    return {
        "messages":       result["messages"],
        "steps_taken":    state.get("steps_taken", 0) + 1,
        "step_latencies": state.get("step_latencies", []) + [new_step]
    }


# ── 5. should_continue (conditional edge function) ────────────────────────────

def should_continue(state: AgentState) -> str:
    """
    Reads the last message and decides routing:

    Returns "continue" → go to tool_node_with_tracking
    Returns "end"      → go to END (task complete or max steps reached)
    """
    last_message = state["messages"][-1]

    if last_message.tool_calls:
        # Agent wants to call a tool — but check safety limit first
        if state.get("steps_taken", 0) >= state.get("max_steps", settings.MAX_STEPS):
            return "end"   # force stop — prevents infinite loops
        return "continue"

    # No tool calls in last message = agent gave final answer
    return "end"


# ── 6. Build and compile the graph ───────────────────────────────────────────

def build_graph():
    """
    Assembles all nodes and edges into the RxSafetyAgent graph.

    Flow:
        START → agent → (continue) → tools → agent → ... → (end) → END
    """
    builder = StateGraph(AgentState)

    # Register nodes
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node_with_tracking)

    # Entry point
    builder.add_edge(START, "agent")

    # After agent: route based on should_continue decision
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end":      END
        }
    )

    # After tools: always return to agent for next decision
    builder.add_edge("tools", "agent")

    return builder.compile()


# Compiled graph — import this in runner.py
app = build_graph()
