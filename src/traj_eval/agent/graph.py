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
from langchain_core.messages import SystemMessage

from traj_eval.agent.state import AgentState
from traj_eval.utils.config import config

if config.TOOL_VERSION == "v2":
    from traj_eval.tools.openfda.tool_box.tools_v2 import OPENFDA_TOOLS
else:
    from traj_eval.tools.openfda.tool_box.tools_v1 import OPENFDA_TOOLS


# ── System prompt — injected on every agent_node call ─────────────────────────
SYSTEM_PROMPT = SystemMessage(content="""You are RxSafetyAgent, a pharmacy \
information assistant that helps pharmacists verify drug safety before dispensing.

CRITICAL RULES — follow strictly:
1. ALWAYS retrieve information by calling tools — never answer from your training knowledge
2. Every fact in your final answer MUST come directly from a tool result
3. Call ALL relevant tools before giving your final answer
4. If a task requires checking recalls, labels, AND adverse events — call all three tools
5. Always recommend the pharmacist consult appropriate healthcare professionals
6. Never make clinical prescribing decisions or recommend specific treatments
7. If you are unsure whether a tool result contains the information — call the tool, but never re-call the same tool with the same arguments
8. If a tool returns no results or active_recalls_found is False — that IS a valid answer; report it clearly and move on
9. If a task mentions a patient ID (e.g., P001, P002) — call get_patient_record FIRST to find their medications, then call other tools for each medication found"""
)


# ── 1. LLM with tools bound ───────────────────────────────────────────────────
# Switch between Gemini and OpenAI via LLM_PROVIDER in .env

if config.LLM_PROVIDER == "openai":
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=config.OPENAI_TASK_MODEL,
        api_key=config.OPENAI_API_KEY
    )
else:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model=config.GEMINI_TASK_MODEL,
        google_api_key=config.GEMINI_API_KEY
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
    # Prepend system prompt — ensures LLM uses tools, not training knowledge
    messages = [SYSTEM_PROMPT] + list(state["messages"])
    response = llm_with_tools.invoke(messages)

    # Extract token counts for cost tracking
    usage = response.usage_metadata or {}
    input_tokens  = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # Always update end_time — ensures valid duration even if max_steps is hit (W3 fix)
    end_time = time.time()

    # Determine model name for tracking
    model_name = (
        config.OPENAI_TASK_MODEL
        if config.LLM_PROVIDER == "openai"
        else config.GEMINI_TASK_MODEL
    )

    return {
        "messages":            [response],
        "total_input_tokens":  state.get("total_input_tokens", 0)  + input_tokens,
        "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
        "end_time":            end_time,
        "llm_provider":        config.LLM_PROVIDER,
        "llm_model":           model_name
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
        if state.get("steps_taken", 0) >= state.get("max_steps", config.MAX_STEPS):
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
