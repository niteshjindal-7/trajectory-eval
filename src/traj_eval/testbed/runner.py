"""
runner.py — Experiment Orchestrator

Runs the RxSafetyAgent on all tasks in a task file,
evaluates each trajectory, and saves results to experiments/.

This automates what test_evaluator.py does for one task,
across all tasks systematically.

Usage:
    from traj_eval.testbed.runner import run_experiment
    run_experiment()

Or from command line:
    python3 -m traj_eval.testbed.runner
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from langchain_core.messages import HumanMessage

from traj_eval.agent.graph import app
from traj_eval.evaluator.trajectory_evaluator import (
    evaluate_trajectory,
    build_result_record,
)
from traj_eval.utils.config import config


# ── Model Pricing Table (USD per 1M tokens) ───────────────────────────────────

MODEL_PRICING = {
    # OpenAI
    "gpt-4o":            {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
    "gpt-4.1":           {"input": 2.00,  "output": 8.00},
    "gpt-4.1-mini":      {"input": 0.40,  "output": 1.60},
    # Gemini
    "gemini-3.1-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash":  {"input": 0.30,  "output": 1.00},
    "gemini-2.5-pro":    {"input": 1.25,  "output": 5.00},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost from token counts using MODEL_PRICING table."""
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost = (input_tokens / 1_000_000 * pricing["input"]) + \
           (output_tokens / 1_000_000 * pricing["output"])
    return round(cost, 6)


# ── Initial State Builder ─────────────────────────────────────────────────────

def build_initial_state(task: dict) -> dict:
    """Build the initial state dict for app.invoke() from a task definition."""
    model = (
        config.OPENAI_TASK_MODEL
        if config.LLM_PROVIDER == "openai"
        else config.GEMINI_TASK_MODEL
    )
    start = time.time()
    return {
        "messages":            [HumanMessage(task["query"])],
        "task_id":             task["id"],
        "dataset":             "openfda",
        "steps_taken":         0,
        "max_steps":           config.MAX_STEPS,
        "total_input_tokens":  0,
        "total_output_tokens": 0,
        "start_time":          start,
        "end_time":            0.0,
        "step_latencies":      [],
        "llm_provider":        config.LLM_PROVIDER,
        "llm_model":           model,
    }


# ── Single Task Runner ────────────────────────────────────────────────────────

def run_task(task: dict, verbose: bool = True) -> dict:
    """
    Run agent on one task, evaluate trajectory, return result record.

    Args:
        task: task definition dict from healthcare_tasks.json
        verbose: print progress to terminal

    Returns:
        result record dict (from build_result_record)
    """
    if verbose:
        print(f"  Running {task['id']} ({task['difficulty']})... ", end="", flush=True)

    initial_state = build_initial_state(task)

    # Run agent
    try:
        state = app.invoke(initial_state)
    except Exception as e:
        if verbose:
            print(f"AGENT ERROR: {e}")
        return {
            "task_id": task["id"],
            "error": str(e),
            "scores": None
        }

    # Evaluate trajectory
    try:
        score = evaluate_trajectory(state, task)
    except Exception as e:
        if verbose:
            print(f"EVALUATOR ERROR: {e}")
        return {
            "task_id": task["id"],
            "error": f"Evaluator failed: {e}",
            "scores": None
        }

    # Build result record
    record = build_result_record(state, task, score)

    # Add cost calculation
    model = state.get("llm_model", "")
    record["cost_usd"] = calculate_cost(
        model,
        state.get("total_input_tokens", 0),
        state.get("total_output_tokens", 0)
    )

    if verbose:
        tools_called = [s["tool"] for s in state.get("step_latencies", [])]
        print(f"done — score {score.total}/25 | tools: {tools_called} | cost: ${record['cost_usd']:.5f}")

    return record


# ── Full Experiment Runner ────────────────────────────────────────────────────

def run_experiment(
    task_file: str = "tasks/openfda/healthcare_tasks.json",
    experiment_name: str = None,
    task_ids: list[str] = None,
) -> dict:
    """
    Run agent on all tasks, evaluate all trajectories, save results.

    Args:
        task_file: path to tasks JSON file
        experiment_name: folder name under experiments/ (auto-generated if None)
        task_ids: optional list of task IDs to run (runs all if None)

    Returns:
        summary dict with aggregate statistics
    """
    # Load tasks
    with open(task_file) as f:
        all_tasks = json.load(f)

    if task_ids:
        all_tasks = [t for t in all_tasks if t["id"] in task_ids]

    # Setup experiment folder
    if not experiment_name:
        experiment_name = config.EXPERIMENT_NAME

    model = (
        config.OPENAI_TASK_MODEL
        if config.LLM_PROVIDER == "openai"
        else config.GEMINI_TASK_MODEL
    )

    output_dir = f"experiments/{experiment_name}"
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("Experiment starting")
    print("=" * 60)
    print(f"Tasks:        {len(all_tasks)}")
    print(f"Provider:     {config.LLM_PROVIDER}")
    print(f"Task model:   {model}")
    print(f"Eval model:   {config.OPENAI_EVAL_MODEL if config.LLM_PROVIDER == 'openai' else config.GEMINI_EVAL_MODEL}")
    print(f"Tool version: {config.TOOL_VERSION}")
    print(f"Output:       {output_dir}/")
    print("-" * 60)

    # Run all tasks
    results = []
    for task in all_tasks:
        record = run_task(task, verbose=True)
        results.append(record)

    # Save full results
    results_path = f"{output_dir}/results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Calculate summary statistics
    successful = [r for r in results if r.get("scores")]
    scores_list = [r["scores"]["total"] for r in successful]
    costs_list  = [r.get("cost_usd", 0) for r in successful]
    latencies   = []
    for r in successful:
        start = 0
        end = 0
        for step in r.get("step_latencies", []):
            end = max(end, step.get("duration_ms", 0))
        latencies.append(sum(s.get("duration_ms", 0) for s in r.get("step_latencies", [])))

    summary = {
        "experiment_name":   experiment_name,
        "timestamp":         datetime.now().isoformat(),
        "llm_provider":      config.LLM_PROVIDER,
        "task_model":        model,
        "eval_model":        config.OPENAI_EVAL_MODEL if config.LLM_PROVIDER == "openai" else config.GEMINI_EVAL_MODEL,
        "tool_version":      config.TOOL_VERSION,
        "tasks_total":       len(all_tasks),
        "tasks_successful":  len(successful),
        "tasks_failed":      len(all_tasks) - len(successful),
        "avg_score":         round(sum(scores_list) / len(scores_list), 2) if scores_list else 0,
        "min_score":         min(scores_list) if scores_list else 0,
        "max_score":         max(scores_list) if scores_list else 0,
        "total_cost_usd":    round(sum(costs_list), 5),
        "avg_cost_usd":      round(sum(costs_list) / len(costs_list), 5) if costs_list else 0,
        "avg_latency_ms":    round(sum(latencies) / len(latencies)) if latencies else 0,
    }

    summary_path = f"{output_dir}/summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Print summary table
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"{'Task':<8} {'Difficulty':<10} {'Score':>6} {'Tools':>6} {'Cost':>10} {'ms':>8}")
    print("-" * 60)
    for r in results:
        if r.get("scores"):
            tools_n = len(r.get("tools_called", []))
            exp_n   = len(r.get("tools_expected", []))
            print(
                f"{r['task_id']:<8} "
                f"{r.get('task_difficulty','?'):<10} "
                f"{r['scores']['total']:>4}/25 "
                f"{tools_n}/{exp_n} tools "
                f"${r.get('cost_usd', 0):>8.5f} "
                f"{r.get('total_latency_ms', 0):>6}ms"
            )
        else:
            print(f"{r['task_id']:<8} ERROR: {r.get('error', '?')[:40]}")

    print("=" * 60)
    print(f"Average score:   {summary['avg_score']}/25")
    print(f"Total cost:      ${summary['total_cost_usd']}")
    print(f"Results saved:   {results_path}")
    print(f"Summary saved:   {summary_path}")

    return summary


# ── CLI Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_experiment()
