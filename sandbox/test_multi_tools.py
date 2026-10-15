"""
Multi-tool test with clearer natural query.
Task: Pharmacist needs FDA recalls, label warnings, and adverse event data
      before dispensing lisinopril — query explicitly names all 3 data sources
      but does NOT instruct the agent which tools to call or in what order.

Expected: 3 tool calls (check_drug_recall, get_drug_label, search_adverse_events)
"""

import time
from langchain_core.messages import HumanMessage
from traj_eval.agent.graph import app
from traj_eval.utils.config import config

print("=" * 50)
print("Provider:", config.LLM_PROVIDER)
print("Model:   ", config.OPENAI_TASK_MODEL if config.LLM_PROVIDER == "openai" else config.GEMINI_TASK_MODEL)
print("=" * 50)

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
print("Provider:      ", result.get("llm_provider"))
print("Model:         ", result.get("llm_model"))
print("Steps taken:   ", result["steps_taken"])
print("Total time ms: ", total_ms)
print("Input tokens:  ", result["total_input_tokens"])
print("Output tokens: ", result["total_output_tokens"])

print("\nTools called in order:")
for step in result["step_latencies"]:
    print(f"  Step {step['step']}: {step['tool']} ({step['duration_ms']}ms)")

# W3 check
duration_ms = round((result["end_time"] - result["start_time"]) * 1000)
print(f"\nDuration from state: {duration_ms}ms", "✅" if duration_ms > 0 else "❌ W3 BUG")

print("\nFinal answer:\n")
content = result["messages"][-1].content
if isinstance(content, list):
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            print(block["text"])
else:
    print(content)
