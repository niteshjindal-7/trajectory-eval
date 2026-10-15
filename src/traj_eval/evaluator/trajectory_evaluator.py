"""
trajectory_evaluator.py — LLM-as-Judge Trajectory Evaluator

Core research contribution for RQ2:
  "How reliable is LLM-as-a-judge as a trajectory evaluator
   and reward signal for reinforcement learning?"

Takes a completed agent trajectory (from state) and scores it
across 5 dimensions using a separate, more capable evaluator LLM.

Uses:
  - rubric.py: scoring criteria, prompt builder, trajectory formatter
  - EVAL model (separate from task agent — Option A from proposal)
  - Pydantic structured output (no free-text parsing — reliable JSON)

Used by:
  - sandbox scripts (direct demo use)
  - runner.py (systematic experiment evaluation)
  - Eventually: RL controller training (scores as reward signal)
"""

from __future__ import annotations

import json
from langchain_core.messages import BaseMessage

from traj_eval.evaluator.rubric import (
    TrajectoryScore,
    format_trajectory,
    build_evaluation_prompt,
)
from traj_eval.utils.config import config


# ── Build Evaluator LLM (separate from task agent) ───────────────────────────

def _build_evaluator_llm():
    """
    Creates the evaluator LLM — a DIFFERENT, more capable model than the task agent.
    This is Option A from the PhD proposal: different model as judge.

    Uses EVAL model from config (e.g., gpt-4o or gemini-2.5-pro)
    vs task agent which uses a cheaper/faster model (e.g., gpt-4o-mini).

    Using a different model avoids self-preference bias — an LLM judging
    its own output tends to score itself higher than it deserves.
    """
    if config.LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.OPENAI_EVAL_MODEL,
            api_key=config.OPENAI_API_KEY,
            temperature=0   # deterministic scoring — same trajectory → same score
        )
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=config.GEMINI_EVAL_MODEL,
            google_api_key=config.GEMINI_API_KEY,
            temperature=0
        )


# ── Main Evaluator Function ───────────────────────────────────────────────────

def evaluate_trajectory(
    state: dict,
    task: dict,
) -> TrajectoryScore:
    """
    Score a completed agent trajectory using LLM-as-a-judge.

    This is the core of RQ2 — evaluating whether LLM-as-a-judge
    can reliably distinguish good from bad trajectories.

    Args:
        state: The full state dict returned by app.invoke()
               Uses: state["messages"], state["step_latencies"],
                     state["total_input_tokens"], state["total_output_tokens"]

        task:  Task definition dict from healthcare_tasks.json
               Uses: task["query"], task["expected_tools"]

    Returns:
        TrajectoryScore with scores 1-5 for each dimension + reasoning
        Also includes .total (out of 25) and .normalised (0.0-1.0)

    Raises:
        Exception: if evaluator LLM call fails (caller should handle)
    """

    # ── Step 1: Extract from state ────────────────────────────────────────────
    messages: list[BaseMessage] = state.get("messages", [])
    step_latencies: list = state.get("step_latencies", [])
    total_input_tokens: int = state.get("total_input_tokens", 0)
    total_output_tokens: int = state.get("total_output_tokens", 0)

    # Tools actually called — from step_latencies audit trail
    tools_actually_called = [s["tool"] for s in step_latencies]

    # Original task query — from first HumanMessage
    task_query = task.get("query", "Unknown task")
    expected_tools = task.get("expected_tools", [])

    # ── Step 2: Format trajectory as readable text ────────────────────────────
    formatted = format_trajectory(messages, step_latencies)

    # ── Step 3: Build evaluation prompt ───────────────────────────────────────
    prompt = build_evaluation_prompt(
        formatted_trajectory=formatted,
        task_query=task_query,
        expected_tools=expected_tools,
        tools_actually_called=tools_actually_called,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
    )

    # ── Step 4: Call evaluator LLM with structured output ────────────────────
    evaluator_llm = _build_evaluator_llm()
    structured_llm = evaluator_llm.with_structured_output(TrajectoryScore)

    score: TrajectoryScore = structured_llm.invoke(prompt)

    return score


# ── Convenience: Evaluate and Print ──────────────────────────────────────────

def evaluate_and_print(state: dict, task: dict) -> TrajectoryScore:
    """
    Evaluate a trajectory and print a formatted score report.
    Useful for sandbox scripts and the professor demo notebook.

    Args:
        state: full state from app.invoke()
        task:  task definition from healthcare_tasks.json

    Returns:
        TrajectoryScore (same as evaluate_trajectory)
    """
    tools_called = [s["tool"] for s in state.get("step_latencies", [])]

    print("\n" + "═" * 55)
    print("TRAJECTORY EVALUATION REPORT")
    print("═" * 55)
    print(f"Task:            {task.get('id', '?')} — {task.get('domain', '?')}")
    print(f"Evaluator model: {config.OPENAI_EVAL_MODEL if config.LLM_PROVIDER == 'openai' else config.GEMINI_EVAL_MODEL}")
    print(f"Tools called:    {tools_called}")
    print(f"Expected tools:  {task.get('expected_tools', [])}")
    print(f"Input tokens:    {state.get('total_input_tokens', 0)}")
    print(f"Output tokens:   {state.get('total_output_tokens', 0)}")
    print("─" * 55)

    score = evaluate_trajectory(state, task)

    print(f"Tool Accuracy:        {score.tool_accuracy}/5")
    print(f"Information Accuracy: {score.information_accuracy}/5")
    print(f"Task Completion:      {score.task_completion}/5")
    print(f"Efficiency:           {score.efficiency}/5")
    print(f"Safety & Scope:       {score.safety_scope}/5")
    print("─" * 55)
    print(f"TOTAL SCORE:          {score.total}/25  ({score.normalised:.2f} normalised)")
    print("─" * 55)
    print(f"Reasoning:\n{score.reasoning}")
    print("═" * 55)

    return score


# ── Save Result to JSON ───────────────────────────────────────────────────────

def build_result_record(
    state: dict,
    task: dict,
    score: TrajectoryScore,
) -> dict:
    """
    Builds a complete result record for saving to experiments/results.json.
    Combines state metrics, task metadata, and evaluator scores.

    Args:
        state: full state from app.invoke()
        task:  task definition from healthcare_tasks.json
        score: TrajectoryScore from evaluate_trajectory()

    Returns:
        dict ready to append to results.json
    """
    tools_called = [s["tool"] for s in state.get("step_latencies", [])]

    start = state.get("start_time", 0)
    end = state.get("end_time", 0)
    total_ms = round((end - start) * 1000) if end > start else 0

    return {
        "task_id":              task.get("id"),
        "task_domain":          task.get("domain"),
        "task_difficulty":      task.get("difficulty"),
        "llm_provider":         state.get("llm_provider"),
        "llm_model":            state.get("llm_model"),
        "tool_version":         config.TOOL_VERSION,

        "tools_expected":       task.get("expected_tools", []),
        "tools_called":         tools_called,
        "steps_taken":          state.get("steps_taken", 0),

        "total_input_tokens":   state.get("total_input_tokens", 0),
        "total_output_tokens":  state.get("total_output_tokens", 0),
        "total_latency_ms":     total_ms,
        "step_latencies":       state.get("step_latencies", []),

        "scores": {
            "tool_accuracy":        score.tool_accuracy,
            "information_accuracy": score.information_accuracy,
            "task_completion":      score.task_completion,
            "efficiency":           score.efficiency,
            "safety_scope":         score.safety_scope,
            "total":                score.total,
            "normalised":           score.normalised,
        },
        "reasoning": score.reasoning,
    }
