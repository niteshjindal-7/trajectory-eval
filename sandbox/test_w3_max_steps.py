"""
W3 Test — Verify end_time stays positive when max_steps is hit.

Sets max_steps=1 on a 3-tool task so agent is force-stopped after 1 tool call.
Before fix: end_time = 0.0 → negative duration
After fix:  end_time = time.time() → positive duration
"""

import time
from langchain_core.messages import HumanMessage
from traj_eval.agent.graph import app
from traj_eval.utils.config import config

print("=" * 50)
print("W3 TEST — max_steps=1 force stop")
print("Provider:", config.LLM_PROVIDER)
print("=" * 50)

start = time.time()

result = app.invoke({
    "messages": [HumanMessage(
        "Is lisinopril 10mg safe to dispense to a Medicare patient?"
    )],
    "task_id": "w3_test",
    "dataset": "openfda",
    "steps_taken": 0,
    "max_steps": 1,           # ← deliberate: force stop after 1 tool call
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "start_time": start,
    "end_time": 0.0,
    "step_latencies": [],
    "llm_provider": config.LLM_PROVIDER,
    "llm_model": config.OPENAI_TASK_MODEL if config.LLM_PROVIDER == "openai" else config.GEMINI_TASK_MODEL
})

total_ms = round((time.time() - start) * 1000)

print("\n--- W3 RESULTS ---")
print("Steps taken:   ", result["steps_taken"])
print("Tools called:  ", [s["tool"] for s in result["step_latencies"]])
print("start_time:    ", round(result["start_time"], 2))
print("end_time:      ", round(result["end_time"], 2))

duration_ms = round((result["end_time"] - result["start_time"]) * 1000)
print("Duration ms:   ", duration_ms)

if duration_ms < 0:
    print("\n❌ W3 BUG PRESENT — negative duration:", duration_ms, "ms")
elif result["end_time"] == 0.0:
    print("\n❌ W3 BUG PRESENT — end_time is 0.0")
else:
    print("\n✅ W3 FIXED — end_time is positive, duration is:", duration_ms, "ms")
