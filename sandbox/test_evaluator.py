"""
Agent run + trajectory evaluation test.

Runs the RxSafetyAgent on a healthcare task, then scores
the trajectory using the LLM-as-judge evaluator.

Run: python3 sandbox/test_evaluator.py
"""

import json
import time
from langchain_core.messages import HumanMessage

from traj_eval.agent.graph import app
from traj_eval.evaluator.trajectory_evaluator import evaluate_and_print, build_result_record
from traj_eval.utils.config import config

# ── Load task definition ──────────────────────────────────────────────────────

TASK_FILE = "tasks/openfda/healthcare_tasks.json"

with open(TASK_FILE) as f:
    all_tasks = json.load(f)

# Use task t006 — full safety check for lisinopril (expects 3 tools)
task = next(t for t in all_tasks if t["id"] == "t006")

print("=" * 55)
print("RxSafetyAgent — Trajectory Evaluation")
print("=" * 55)
print(f"Task ID:    {task['id']}")
print(f"Domain:     {task['domain']}")
print(f"Difficulty: {task['difficulty']}")
print(f"Provider:   {config.LLM_PROVIDER}")
print(f"Task model: {config.OPENAI_TASK_MODEL if config.LLM_PROVIDER == 'openai' else config.GEMINI_TASK_MODEL}")
print(f"Eval model: {config.OPENAI_EVAL_MODEL if config.LLM_PROVIDER == 'openai' else config.GEMINI_EVAL_MODEL}")
print(f"Tool ver:   {config.TOOL_VERSION}")
print("─" * 55)
print(f"Query: {task['query']}")
print("=" * 55)

# ── Run the agent ─────────────────────────────────────────────────────────────

print("\n[1/2] Running agent...\n")

start = time.time()

state = app.invoke({
    "messages": [HumanMessage(task["query"])],
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
    "llm_model":           config.OPENAI_TASK_MODEL if config.LLM_PROVIDER == "openai" else config.GEMINI_TASK_MODEL
})

total_ms = round((time.time() - start) * 1000)

print(f"Steps taken:   {state['steps_taken']}")
print(f"Total time ms: {total_ms}")
print(f"Input tokens:  {state['total_input_tokens']}")
print(f"Output tokens: {state['total_output_tokens']}")
print("\nTools called in order:")
for step in state["step_latencies"]:
    print(f"  Step {step['step']}: {step['tool']} ({step['duration_ms']}ms)")

print("\nAgent final answer:")
print("─" * 55)
content = state["messages"][-1].content
if isinstance(content, list):
    content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
print(content)

# ── Evaluate the trajectory ───────────────────────────────────────────────────

print("\n[2/2] Evaluating trajectory...\n")

score = evaluate_and_print(state, task)

# ── Save result ───────────────────────────────────────────────────────────────

result = build_result_record(state, task, score)

output_path = f"experiments/exp_001_evaluator_v1/result_{task['id']}.json"
import os
os.makedirs("experiments/exp_001_evaluator_v1", exist_ok=True)
with open(output_path, "w") as f:
    json.dump(result, f, indent=2)

print(f"\nResult saved to: {output_path}")
