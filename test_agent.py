"""Quick test script to verify the agent runs end-to-end."""

import time
from langchain_core.messages import HumanMessage
from src.traj_eval.agent.graph import app

result = app.invoke({
    "messages": [HumanMessage("Check if warfarin has any active FDA recalls.")],
    "task_id": "test",
    "dataset": "openfda",
    "steps_taken": 0,
    "max_steps": 10,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "start_time": time.time(),
    "end_time": 0.0,
    "step_latencies": []
})

print("Steps taken:   ", result["steps_taken"])
print("Step latencies:", result["step_latencies"])
print("Input tokens:  ", result["total_input_tokens"])
print("Output tokens: ", result["total_output_tokens"])
print("\nFinal answer:\n", result["messages"][-1].content)
