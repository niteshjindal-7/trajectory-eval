"""
AgentState — Shared memory container for RxSafetyAgent

Travels through every node in the LangGraph graph.
Every node reads from it and returns updated fields back to it.

Design:
  - messages field  → handles LLM conversation and tool calling (mandatory for tool-calling agents)
  - custom fields   → our research tracking (task metadata, cost, latency)

Mirrors the course pattern (state_schema.py) but adds messages
for dynamic tool-calling support.
"""

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):

    # ── LLM Conversation ──────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]
    # Accumulates the full conversation:
    #   HumanMessage  → initial task query
    #   AIMessage     → LLM decision (tool call request OR final answer)
    #   ToolMessage   → result returned after a tool executes
    #
    # add_messages reducer: APPENDS new messages instead of replacing the list
    # This preserves the full history so LLM sees all previous steps

    # ── Task Tracking ─────────────────────────────────────────────────────────
    task_id: str
    # Which task is running e.g. "t003"
    # Used by runner.py to match results back to task definitions

    dataset: str
    # Which dataset/domain e.g. "openfda", "tau_bench"
    # Allows same graph to work across different domains

    # ── Safety Limit ──────────────────────────────────────────────────────────
    steps_taken: int
    # Increments by 1 each time tool_node executes
    # Prevents infinite loops if agent keeps calling tools

    max_steps: int
    # Maximum allowed tool calls per task e.g. 10
    # should_continue checks this — forces END if exceeded

    # ── Cost Tracking ─────────────────────────────────────────────────────────
    total_input_tokens: int
    # Accumulates input tokens across all LLM calls in this task
    # input tokens = tokens in the prompt sent to LLM

    total_output_tokens: int
    # Accumulates output tokens across all LLM calls in this task
    # output tokens = tokens in LLM's response

    # ── Latency Tracking ──────────────────────────────────────────────────────
    start_time: float
    # Unix timestamp when task started (set by runner.py before invoke)
    # Used to calculate total task duration

    end_time: float
    # Unix timestamp when final answer is ready (set by agent_node at END)
    # total_duration_ms = (end_time - start_time) * 1000

    step_latencies: list
    # Per-tool-call timing — appended by tool_node after each tool executes
    # Format: [
    #   {"step": 1, "tool": "get_patient_record",  "duration_ms": 12},
    #   {"step": 2, "tool": "check_drug_recall",    "duration_ms": 420},
    #   {"step": 3, "tool": "get_drug_label",        "duration_ms": 890},
    # ]
    # Reveals which tools are slowest — important for latency optimisation
