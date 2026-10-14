"""
Multi-step agent test — 3 tool calls expected.
Task: Full safety check for lisinopril (recall + label + adverse events)
"""

import time
from langchain_core.messages import HumanMessage
from traj_eval.agent.graph import app
from traj_eval.utils.config import settings

print("=" * 50)
print("Provider:", settings.LLM_PROVIDER)
print("Model:   ", settings.OPENAI_TASK_MODEL if settings.LLM_PROVIDER == "openai" else settings.GEMINI_TASK_MODEL)
print("=" * 50)

start = time.time()

result = app.invoke({
    "messages": [HumanMessage(
        "A Medicare patient is picking up lisinopril 10mg from CVS. "
        "Perform a complete safety check: first check for any active FDA recalls, "
        "then retrieve the black box warning and contraindications from the drug label, "
        "and finally check what serious adverse events have been reported for lisinopril."
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
    "llm_provider": settings.LLM_PROVIDER,
    "llm_model": settings.OPENAI_TASK_MODEL if settings.LLM_PROVIDER == "openai" else settings.GEMINI_TASK_MODEL
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

print("\nFinal answer:\n")
content = result["messages"][-1].content
if isinstance(content, list):
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            print(block["text"])
else:
    print(content)
