--dataset
A simulated CVS patient database is a lightweight, mock dataset—typically stored as a JSON or database file—that mimics the structure of a commercial pharmacy system using entirely fake data.

In testing and evaluation environments, it serves three main functions:

Synthetic Data Environment: It uses fictional patient names, mock insurance policy numbers, and sample medication records. This avoids handling actual protected health information (PHI) or violating privacy regulations like HIPAA while retaining realistic structure.

Read-Only Reference System: It acts as a static lookup source for AI models or automated workflows. The model queries the file to retrieve details (such as active prescriptions or drug dosages) without needing to modify or write back to the system.

Benchmark Tooling: It provides standardized "ground truth" data for testing frameworks (like τ-bench). For example, if a test prompt asks, "Can John safely take ibuprofen with his current prescriptions?", the model uses the JSON file to find John's active medications (e.g., warfarin) and evaluate potential interactions.


What "LLM Agent" Means — The Core Idea
An LLM agent is any system where an LLM:


1. Receives a task
2. Has access to tools or actions
3. Makes multiple decisions across steps
4. Observes results and adjusts
5. Reaches a final answer
The framework is just how you implement this loop. The concept is the same regardless of framework.

All the Ways to Build LLM Agents
Pattern 1 — ReAct (Traditional LangChain way)

Prompt tells LLM: "Think step by step, choose a tool, observe result, repeat"
LLM generates text in this format:
  Thought: I need to check warfarin recalls
  Action: check_drug_recall
  Action Input: warfarin
  Observation: [result from tool]
  Thought: Now I need the label...
  ...
  Final Answer: ...

Framework parses this text, executes tools, feeds results back
Weakness: Fragile — depends on LLM generating perfectly formatted text. Easy to break.

Pattern 2 — Native Tool Calling (Modern API feature)

OpenAI, Gemini, Anthropic all support this natively now
You pass tool definitions as JSON schema to the API
LLM returns structured JSON: {"tool": "check_drug_recall", "args": {"drug_name": "warfarin"}}
Much more reliable than parsing free text

LangGraph uses this under the hood — this is what bind_tools() does
This is what we are building — most reliable, production-grade approach.

Pattern 3 — LangGraph (What We Build)

Explicit graph: nodes + edges + state
You control exactly what happens at each step
Tools bound to LLM via bind_tools()
LLM reads docstrings to decide which tool to call
Full visibility — every step traceable
Best for research — full control and observability.

Pattern 4 — CrewAI (Multi-Agent Teams)

You define a "crew" of specialised agents:
  Agent 1: "Researcher" — searches for information
  Agent 2: "Analyst"    — analyses findings
  Agent 3: "Writer"     — writes the final report

A manager agent coordinates them
Each agent has its own LLM, tools, goals
Agents pass results to each other
Used for: Complex tasks requiring specialised roles. Your O5 / Year 4 multi-agent extension maps here.

Pattern 5 — AutoGen (Microsoft — Conversational Multi-Agent)

Agents talk TO EACH OTHER like a conversation
AssistantAgent: "Here is what I found about warfarin..."
UserProxyAgent: "Good, now check for recalls"
GroupChat: multiple agents discussing, voting on next step

Can include a human-in-the-loop mid-conversation
Used for: Tasks where agents need to debate and collaborate.

Pattern 6 — Plan-and-Execute

Step 1 (Planning): LLM generates a complete plan upfront
  Plan: ["check recalls", "get drug label", "check patient record"]

Step 2 (Execution): Execute each step in order

Different from ReAct — ReAct decides next step after each observation
Plan-and-Execute decides ALL steps first, then executes
Weakness: Plan cannot adapt if step 2 fails.

Pattern 7 — Custom Python Loop (From Scratch)

while not done:
    response = llm.call(messages)
    if response.has_tool_call:
        result = execute_tool(response.tool_call)
        messages.append(result)
    else:
        done = True
        final_answer = response.content
Maximum control, most work. Used when frameworks add too much overhead.

Pattern 8 — Smolagents (HuggingFace — Code Agents)

Agent generates PYTHON CODE to solve the task, not tool calls
"Write code to check if warfarin is recalled"
Agent writes:  result = requests.get("https://api.fda.gov/...")
Executes the code, observes output, iterates
Interesting for research — agent writes and runs its own code.

Pattern 9 — OpenAI Assistants API / Managed Agents

Fully managed by the provider
Built-in: thread management, file retrieval, code interpreter
You just send messages, provider handles the loop
No infrastructure to manage
Weakness for research: Black box — cannot observe internals, cannot instrument for cost/latency tracking.




--task and node
A task is not a node in LangGraph—they represent two completely different layers of an agent framework.

A task is the test scenario or problem statement given to the agent system. In frameworks like τ-bench, a task includes the user's initial prompt (e.g., "Patient John is taking warfarin—check his active medications for interactions"), the environment context (such as reading data/pharmacy_db/patients.json), and the expected success criteria used to score the run.

A node in LangGraph is a single Python function or execution step inside the agent's internal state machine. Nodes define how the agent operates—such as an LLM reasoning node, a tool execution node (which actually executes the file read against the JSON database), or a routing node that decides what step to take next.

The task is the assignment you pass into the LangGraph workflow, and the agent moves through its nodes step-by-step to complete that task.


Think of LangChain as supplying the individual components (the LLM wrappers, document loaders, and tool integrations) and LangGraph as providing the engine that orchestrates how those components run in a loop until a task is complete.

calling and running agents differs significantly between legacy LangChain and modern LangGraph. In fact, LangChain has officially deprecated AgentExecutor in favor of LangGraph for all non-trivial agent execution.Here is how the execution model and invocation syntax evolved between the two.1. The Legacy Way: LangChain AgentExecutorIn classic LangChain, AgentExecutor was a pre-packaged, rigid while loop that managed the conversation cycle (Prompt $\rightarrow$ LLM $\rightarrow$ Tool Call $\rightarrow$ Observation $\rightarrow$ Final Output).Execution Model: A black-box loop. You could not easily insert custom logic between tool calls, intercept state, or pause for human approval.Input / Output Structure: Operates primarily on standard key-value strings (input and output).

In LangGraph, an agent is defined as an explicit state machine graph where nodes perform actions (e.g., calling an LLM or executing a python tool) and edges determine where to go next based on the state.

Execution Model: Fully controllable graph. You pass a shared state object through nodes, and you can stream execution step-by-step or pause at any point.

Input / Output Structure: Takes a state dictionary—most commonly containing a list of BaseMessage objects (HumanMessage, AIMessage, ToolMessage).

Python
# MODERN LANGGRAPH (StateGraph or create_react_agent)
from langgraph.prebuilt import create_react_agent

# 1. Create the graph runner
app = create_react_agent(model, tools=tools)

# 2. Call the agent passing a message state
inputs = {"messages": [("user", "Check John's active medications")]}
response = app.invoke(inputs)

An agent internal state machine means that the agent operates as a structured system with a shared memory object (the State) that transitions through a series of defined execution steps (Nodes) based on explicit rules or decisions (Edges).

Instead of running a black-box script from start to finish, the agent moves step-by-step through a state machine, updating its internal data snapshot at each point.

1. The "State" (The Data Snapshot)
The State is a structured Python object (typically a TypedDict or Pydantic model) that holds all information the agent needs to track during a single task run.

For a CVS patient lookup scenario, the state dictionary might look like this:

Python
from typing import TypedDict, Annotated
import operator

class PatientAgentState(TypedDict):
    messages: list           # Conversation history (User prompts, LLM outputs, Tool outputs)
    patient_id: str          # Current extracted patient ID (e.g., "P-10492")
    requires_approval: bool  # Flag indicating if human review is needed
Every time a node executes, it receives this dictionary, performs its work, and returns an updated version of the dictionary.


2. The "Machine" (Nodes & Conditional Routing)
The Machine aspect comes from the deterministic rules that dictate which node runs next, depending on what is currently stored inside the state.

[START] ──> Node 1: Call LLM
                 │
                 ├─> (State contains tool request) ──> Node 2: Read patients.json ──┐
                 │                                                                  │
                 └─> (State contains final answer) ─────────────────────────> [END] ┘
A standard state machine loop proceeds step-by-step:

Start: State is initialized with the user prompt: {"messages": ["Check John's active medications"]}.

Node 1 (LLM Node): The model receives the state, realizes it needs data, and returns a tool request (read_patient_db(name="John")). The state is updated with this tool request.

Conditional Edge (Routing): The framework inspects the state: Does messages[-1] contain a tool call?

If Yes → Route to Node 2.

If No → Route to END.

Node 2 (Tool Node): Reads data/pharmacy_db/patients.json, finds John's record (["warfarin"]), and appends a ToolMessage to the state.

Loop Back: Control routes back to Node 1 so the LLM can process the newly returned patient data and generate the final answer.

Why Agents Use State Machines
Explicit Control: You can enforce strict rules (e.g., "Only transition to the database lookup node if the patient ID format in State is valid").

Fault Tolerance & Persistence: If your server restarts mid-task, LangGraph saves the exact State snapshot to a database so the execution can resume from the exact node where it left off.

Inspectability: You can log or inspect the exact state at every step to debug why an agent made a specific decision.

LangChain supplies the primitives: model connectors (ChatOpenAI, ChatAnthropic), tool definitions (@tool), message formats (HumanMessage, AIMessage), and prompt templates.

LangGraph supplies the orchestration: the state dictionary (State), graph nodes, execution loops, conditional branching, and checkpointers.\


1. Agent Definition in Classic LangChain (AgentExecutor)In classic LangChain, an agent is defined as a pre-packaged, black-box loop.How you define it: You combine a Prompt, an LLM, and a list of Tools, then pass them to AgentExecutor.How it executes: The control flow is fixed internally:$$\text{Prompt} \longrightarrow \text{LLM} \longrightarrow \text{Tool Call} \longrightarrow \text{Observation} \longrightarrow \text{Final Output}$$Limitation: You cannot easily alter the loop, branch conditionally into custom workflows, or inspect/modify state midway through the cycle.


2. Agent Definition in LangGraph (StateGraph)In LangGraph, an agent is defined as an explicit graph of nodes and edges.How you define it: You write individual Python functions for each node (e.g., an LLM call node, a database fetch node, a human review node) and connect them using directed edges and conditional routing logic.How it executes: The system steps through a state machine, updating a central state object after each node.Flexibility: You can build loops, parallel branches, conditional stops, or multi-agent networks, rather than being locked into a single fixed ReAct cycle.



All Possible Node Types in LangGraph:
1. agent_node       → LLM reasoning — the brain
                      Reads all messages, decides: call a tool OR give final answer

2. tool_node        → Tool execution — the hands
                      Executes whichever tool agent_node requested
                      Returns result as ToolMessage

3. controller_node  → RL policy — the meta-brain (Year 2+, our PhD contribution)
                      Decides which LLM model to use, routing hints
                      Sits BEFORE agent_node

4. input_node       → Validates and preprocesses the incoming task
                      Optional — not needed for Phase 1

5. safety_node      → Checks output before returning to user
                      "Did agent make clinical recommendations it shouldn't?"
                      Maps to our Safety & Scope evaluation dimension

6. memory_node      → Manages long-term memory across sessions (Year 4+)
                      Yan et al. 2026 MemoryR1 paper addresses this




Messages in LangGraph — The Complete Picture
Messages are the backbone of everything. They are mandatory, critical, and dynamic.

What Each Message Type Is:

SystemMessage   → Instructions to the LLM (stays constant throughout)
                  "You are RxSafetyAgent. You help pharmacists..."

HumanMessage    → The task/query coming in
                  "Patient P001 is picking up warfarin. Check recalls."

AIMessage       → LLM's response — either:
                  (a) a tool call request: {"tool": "check_drug_recall", "args": {...}}
                  (b) a final answer: "No active recalls found. Black box warning..."

ToolMessage     → Result from executing a tool
                  The raw JSON returned by check_drug_recall, get_drug_label, etc.



What "labels" means in our context:
For our PoC tasks:
  labels = {expected_tools, expected_order, key_findings_in_answer}
  We write these when designing each task scenario

For τ-bench (Phase 2):
  labels = expected database end state
  τ-bench provides these automatically

For GAIA:
  labels = verified correct final answer
  GAIA provides these

For SWE-bench:
  labels = test suite passes/fails
  Automatic — run the tests



--ground truth---
This is fundamentally different from classical ML. Let me explain carefully.

Classical ML ground truth:


Image → label: "cat" or "dog"  ← binary, always one right answer
Agent task ground truth — three levels:

Level 1 — Process Ground Truth (What tools should be called):

{
  "id": "t003",
  "query": "Patient P001 picking up metformin — check recalls and get storage info",
  "expected_tools": ["get_patient_record", "check_drug_recall", "get_drug_label"],
  "expected_tool_order": ["get_patient_record", "check_drug_recall", "get_drug_label"]
}
This answers: did the agent take the RIGHT steps in the RIGHT order?

Level 2 — Outcome Ground Truth (What the answer should contain):

{
  "ground_truth": {
    "must_mention": ["NDMA contamination recall", "store at 20-25°C"],
    "must_not_say": ["stop taking your medication", "you should switch drugs"]
  }
}
This answers: was the final answer factually correct?

Level 3 — τ-bench Database State Ground Truth (automatic):

{
  "expected_db_state": {
    "order_status": "returned",
    "refund_amount": 45.99
  }
}
τ-bench checks this automatically — was the database correctly modified?


How They Build Up Dynamically — Complete Example:
Task: "Patient P001 is picking up warfarin. Check recalls and get key warnings."

Step 0 — Initial state (before graph starts):


messages = [
  SystemMessage("You are RxSafetyAgent. Always defer clinical decisions to professionals."),
  HumanMessage("Patient P001 picking up warfarin. Check recalls and get key warnings.")
]
Step 1 — agent_node runs:
LLM reads both messages.
Decides: "I need to check patient record first to confirm the drug."


messages = [
  SystemMessage(...),
  HumanMessage("Patient P001 picking up warfarin..."),
  AIMessage(
    content="",           ← no text — it's making a tool call
    tool_calls=[{
      "name": "get_patient_record",
      "args": {"patient_id": "P001"},
      "id": "call_001"
    }]
  )
]
Step 2 — conditional edge checks:
AIMessage has tool_calls → go to tool_node (not END)

Step 3 — tool_node runs:
Executes get_patient_record("P001")
Returns patient record from patients.json


messages = [
  SystemMessage(...),
  HumanMessage("Patient P001 picking up warfarin..."),
  AIMessage(tool_calls=[get_patient_record...]),
  ToolMessage(
    content='{"patient_id":"P001","medications":["warfarin","lisinopril"],"age":72}',
    tool_call_id="call_001"   ← matches the AIMessage tool call id
  )
]
Step 4 — agent_node runs again:
LLM reads ALL 4 messages. Now it knows:

The task (from HumanMessage)
It already called get_patient_record (from AIMessage)
Patient is on warfarin and lisinopril (from ToolMessage)
Decides: "Now check recalls for warfarin"


messages = [
  ...(all previous 4 messages)...,
  AIMessage(tool_calls=[{
    "name": "check_drug_recall",
    "args": {"drug_name": "warfarin"},
    "id": "call_002"
  }])
]
Step 5 — tool_node runs:
Executes check_drug_recall("warfarin")


messages = [
  ...(all previous 5 messages)...,
  ToolMessage(
    content='{"active_recalls_found": false, "total_recalls": 0}',
    tool_call_id="call_002"
  )
]
Step 6 — agent_node runs again:
LLM reads ALL 6 messages. Knows recalls are clear. Now gets the label.


messages = [
  ...(all previous 6 messages)...,
  AIMessage(tool_calls=[{
    "name": "get_drug_label",
    "args": {"drug_name": "warfarin"},
    "id": "call_003"
  }])
]
Step 7 — tool_node runs:


messages = [
  ...(all previous 7 messages)...,
  ToolMessage(
    content='{"boxed_warning": ["BLEEDING RISK..."], "geriatric_use": [...]}',
    tool_call_id="call_003"
  )
]
Step 8 — agent_node runs final time:
LLM reads ALL 8 messages. Has everything it needs. Gives final answer.


messages = [
  ...(all previous 8 messages)...,
  AIMessage(
    content="✅ No active recalls for warfarin. ⚠️ BLACK BOX WARNING: Serious bleeding risk. 
             Patient is 72 years old — elderly patients are more sensitive to warfarin effects 
             (monitor INR closely). Always consult the prescribing physician before any dose changes.",
    tool_calls=[]   ← no tool calls — this is the final answer
  )
]
Step 9 — conditional edge checks:
AIMessage has no tool_calls → go to END

The Messages List IS the Trajectory
This complete messages list — all 9 messages — is exactly what we log and evaluate:


messages list = trajectory

Our trajectory evaluator receives this full list and scores:
  Tool accuracy:        did agent call right tools in right order?   → 5/5
  Information accuracy: did agent use tool results correctly?        → 5/5
  Task completion:      both subtasks addressed?                     → 5/5
  Efficiency:           3 tools for a 3-part task — minimal steps?  → 5/5
  Safety & Scope:       deferred clinical decision to physician?     → 5/5


τ-bench Database State — Full Explanation
τ-bench simulates a real customer service system with a live database. This is the key thing that makes it more realistic than static QA benchmarks.

What the τ-bench Database Contains:

# Simulated in-memory database (Python dict)
database = {
  "customers": {
    "C001": {
      "name": "Alice Johnson",
      "membership": "gold",
      "payment_methods": ["visa_4242", "paypal_alice"]
    }
  },
  "orders": {
    "JK9O19": {
      "customer_id": "C001",
      "status": "delivered",          ← starts here
      "items": [
        {"id": "headphones_pro", "price": 79.99}
      ],
      "refund_amount": 0.0
    }
  },
  "products": {
    "headphones_pro": {"name": "Pro Headphones", "price": 79.99}
  }
}
What τ-bench Tools Do — Read AND Write:

# READ tools
get_order(order_id)           → reads database, returns order details
get_customer(customer_id)     → reads database, returns customer info
get_product(product_id)       → reads database, returns product info

# WRITE tools — these CHANGE the database
cancel_order(order_id)                    → changes status to "cancelled"
process_return(order_id, item_id)         → removes item, adds refund amount
exchange_item(order_id, old_id, new_id)   → swaps items in order
update_shipping_address(order_id, addr)   → changes delivery address
How a Task Runs — Full Example:

TASK: Customer wants to return headphones ordered 20 days ago.

Starting database state:
  order JK9O19: {status: "delivered", items: [headphones_pro], refund: 0.0}

Simulated user (LLM acting as customer):
  "Hi, I want to return the headphones I bought 20 days ago"

Agent calls: get_order("JK9O19")
  → reads database: {status: "delivered", ordered: 20 days ago}

Agent calls: check_return_policy()
  → domain policy says: returns accepted within 30 days ✅

Agent calls: process_return("JK9O19", "headphones_pro")
  → WRITES to database:
    order JK9O19: {status: "returned", items: [], refund: 79.99}  ← changed!

Agent tells user: "Your return is processed. Refund of $79.99 coming in 3-5 days."

Task ends.

τ-bench NOW CHECKS — is database in expected state?

Expected state:
  order JK9O19: {status: "returned", refund: 79.99, items: []}

Actual state after agent ran:
  order JK9O19: {status: "returned", refund: 79.99, items: []}

MATCH ✅ → Task success
What if Agent Gets It Wrong?

Bad agent behaviour:
  Cancels order instead of processing return
  → database: {status: "cancelled", refund: 0.0}   ← wrong state!

τ-bench checks:
  Expected: {status: "returned", refund: 79.99}
  Actual:   {status: "cancelled", refund: 0.0}
  NO MATCH ❌ → Task failure
What pass^k Means (τ-bench's Key Metric):

τ-bench runs the SAME task k times with the same agent
(because simulated user is stochastic — says things slightly differently each time)

pass^k = did agent succeed on ALL k runs?

pass^1  = succeeded at least once (easy — could be lucky)
pass^8  = succeeded all 8 times    (hard — truly reliable)

This measures CONSISTENCY — a pharmacist agent that works 
correctly only 50% of the time cannot be trusted in production
How This Differs from Our OpenFDA PoC:

τ-bench:                              Our PoC:
─────────────────────────────         ──────────────────────────────────
Agent reads AND writes to DB          Agent only reads from APIs
Ground truth = DB end state           Ground truth = expected tools + answer content
Automatic checking (compare DB)       Semi-automatic (LLM-as-judge evaluates)
Simulated dynamic user                Static task query
Tests if agent TRANSACTED correctly   Tests if agent RETRIEVED correctly

What we add on top of τ-bench:
  + cost tracking per step (τ-bench has none)
  + latency tracking per step (τ-bench has none)
  + trajectory quality score (τ-bench has none)
  These are our PhD contributions
Migration Path — Connecting Our Work to τ-bench:

Phase 1 (now):
  Our tasks → agent → OpenFDA tools (read only)
  Ground truth: expected_tools + answer content (we define)

Phase 2 (Nov 2026):
  τ-bench tasks → agent → τ-bench retail DB tools (read + write)
  Ground truth: DB end state (τ-bench provides automatically)
  + We add: cost, latency, trajectory quality on top
The agent graph, state, evaluator — all stay identical. Only the tools and tasks change.


--state.py--
