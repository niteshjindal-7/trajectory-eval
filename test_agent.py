"""Quick test script to verify the agent runs end-to-end."""

import time
from langchain_core.messages import HumanMessage
from src.traj_eval.agent.graph import app
from src.traj_eval.utils.config import settings

# Show which model is being used
print("=" * 50)
print("Provider:", settings.LLM_PROVIDER)
print("Model:   ", settings.OPENAI_TASK_MODEL if settings.LLM_PROVIDER == "openai" else settings.GEMINI_TASK_MODEL)
print("=" * 50)

start = time.time()

result = app.invoke({
    "messages": [HumanMessage("Check if warfarin has any active FDA recalls.")],
    "task_id": "test",
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

print("Provider used: ", result.get("llm_provider"))
print("Model used:    ", result.get("llm_model"))
print("Steps taken:   ", result["steps_taken"])
print("Step latencies:", result["step_latencies"])
print("Input tokens:  ", result["total_input_tokens"])
print("Output tokens: ", result["total_output_tokens"])
print("Total time ms: ", total_ms)
print("\nFinal answer:\n", result["messages"][-1].content)
