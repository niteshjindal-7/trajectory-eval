"""
Multi-tool test using v2 constrained tools.
Tests whether explicit scope constraints in tool docstrings
force the LLM to call all 3 tools vs hallucinating from training knowledge.

Set TOOL_VERSION=v2 in .env before running.
Compare results with test_multi_tools.py (v1 tools).
"""

import time
from langchain_core.messages import HumanMessage
from traj_eval.agent.graph import app
from traj_eval.utils.config import config

print("=" * 50)
print("Provider:", config.LLM_PROVIDER)
print("Model:   ", config.OPENAI_TASK_MODEL if config.LLM_PROVIDER == "openai" else config.GEMINI_TASK_MODEL)
print("Tool version:", config.TOOL_VERSION)
print("=" * 50)

if config.TOOL_VERSION != "v2":
    print("⚠️  WARNING: TOOL_VERSION is not v2 in .env — set TOOL_VERSION=v2 to test constrained tools")

start = time.time()

result = app.invoke({
    "messages": [HumanMessage(
        "Before dispensing lisinopril 10mg to a Medicare patient, "
        "what do FDA recalls, label warnings, and adverse event reports say?"
    )],
    "task_id": "t006",
    "dataset": "openfda",
    "steps_taken": 0,
    "max_steps": 10,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "start_time": start,
    "end_time": 0.0,
    "step_latencies": [],
    "llm_provider": config.LLM_PROVIDER,
    "llm_model": config.OPENAI_TASK_MODEL if config.LLM_PROVIDER == "openai" else config.GEMINI_TASK_MODEL
})

total_ms = round((time.time() - start) * 1000)

print("\n--- RESULTS ---")
print("Tool version:  ", config.TOOL_VERSION)
print("Provider:      ", result.get("llm_provider"))
print("Model:         ", result.get("llm_model"))
print("Steps taken:   ", result["steps_taken"])
print("Total time ms: ", total_ms)
print("Input tokens:  ", result["total_input_tokens"])
print("Output tokens: ", result["total_output_tokens"])

print("\nTools called in order:")
for step in result["step_latencies"]:
    print(f"  Step {step['step']}: {step['tool']} ({step['duration_ms']}ms)")

expected = {"check_drug_recall", "get_drug_label", "search_adverse_events"}
called   = {s["tool"] for s in result["step_latencies"]}
missing  = expected - called

if not missing:
    print("\n✅ All 3 expected tools called")
else:
    print(f"\n❌ Missing tool calls: {missing}")
    print("   → LLM still hallucinating from training knowledge")

print("\nFinal answer:\n")
content = result["messages"][-1].content
if isinstance(content, list):
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            print(block["text"])
else:
    print(content)
