# OpenFDA Agent → Trajectory Evaluator: Complete Flow
## How OpenFDA PoC Connects to the Trajectory Evaluator
## And How This Migrates to τ-bench

**Related docs:**
- System design: `docs/01_system_design/system_design.md`
- OpenFDA reference: `docs/02_openfda_reference/openfda_api_guide.md`
- Task scenarios: `docs/04_task_scenarios/healthcare_scenarios.md`

---

## Part 1: The Core Flow — OpenFDA PoC

### Comparison: Flight Booking (τ-bench) vs Pharmacy (Our PoC)

Understanding τ-bench's flow helps clarify ours:

```
τ-BENCH FLIGHT BOOKING FLOW:               OUR PHARMACY FLOW:
────────────────────────────────           ─────────────────────────────────────
User: "Change flight LAX→NYC"              Task: "Patient picking up warfarin.
                                                  Check recalls AND get key
                                                  warnings to counsel patient."
  Step 1: get_reservation("JK9O19")          Step 1: check_drug_recall("warfarin")
          → retrieves booking details                  → Returns: no active recalls
                                                         for warfarin brand names
  Step 2: check_policy("basic_economy")      Step 2: get_drug_label("warfarin")
          → cannot change basic economy               → Returns: BLACK BOX WARNING
                                                        bleeding risk, interactions
  Step 3: cancel_reservation("JK9O19")       Step 3: Agent synthesises:
          → cancels old booking                        "No active recalls. CRITICAL:
                                                        Black box warning for bleeding.
  Step 4: book_new_flight("NYC", date)                 Counsel patient to avoid
          → creates new booking                         ibuprofen/aspirin. Monitor INR."

  WRITES to database ✅                      READ from APIs only ✅
  (booking record updated)                   (no writes needed —
                                             information retrieval task)

  Ground truth: DB in correct state          Ground truth: expected tools called
                                             + answer factually correct
```

### Why No Database Writes in Our PoC?

Our Phase 1 tasks are **information retrieval** tasks — the pharmacist wants
to KNOW something (what are the warnings? are there recalls?) — not CHANGE a record.

This is valid for trajectory evaluation because:
- The trajectory still has multiple steps (multi-step tool calls)
- The evaluator can still assess: right tools? right order? correct facts? efficient?
- Database writes become relevant in Phase 2 (τ-bench) when we test TRANSACTIONS

---

## Part 2: The Complete Step-by-Step Flow

### Example Task
```
Task ID:  t003
Query:    "A pharmacist at a CVS store has a patient picking up
           extended-release metformin for Type 2 diabetes. Before
           dispensing, check for active FDA recalls AND retrieve
           the key storage instructions from the drug label."

Expected tool order: [check_drug_recall, get_drug_label]
Ground truth:        Recall: NDMA contamination recalls occurred
                     Storage: Store at 20–25°C (68–77°F)
Difficulty:          Medium (2 tools, specific information extraction)
```

### Step-by-Step Execution

```
1. TASK RUNNER loads task t003 from tasks/openfda/healthcare_tasks.json
   └── Passes to LangGraph agent via runner.py

2. LANGGRAPH AGENT starts execution
   └── State initialised: {task: "...", history: [], steps: 0}

3. AGENT NODE (Gemini LLM) reasons:
   "I need to check for recalls first (safety), then get the drug label."
   └── Decides: call check_drug_recall("metformin")

4. TOOL NODE executes:
   GET https://api.fda.gov/drug/enforcement.json
       ?search=openfda.generic_name:"metformin"
       +AND+status:"Ongoing"
   └── Returns: {recalls: [{product: "metformin ER 500mg",
                             reason: "NDMA contamination",
                             classification: "Class II",
                             status: "Ongoing"}]}
   └── LangFuse captures: tokens=380, latency=420ms, cost=$0.0003

5. AGENT NODE (Gemini LLM) reasons:
   "Recall found. Now I need storage instructions from the label."
   └── Decides: call get_drug_label("metformin")

6. TOOL NODE executes:
   GET https://api.fda.gov/drug/label.json
       ?search=openfda.generic_name:"metformin"
       &limit=1
   └── Returns: {dosage_and_administration: "Store at 20-25°C (68-77°F)...",
                  warnings: "NDMA impurity...",
                  indications_and_usage: "Type 2 Diabetes Mellitus..."}
   └── LangFuse captures: tokens=1240, latency=890ms, cost=$0.0011

7. AGENT NODE (Gemini LLM) synthesises final answer:
   "⚠️ RECALL ALERT: Extended-release metformin has active NDMA
    contamination recall (Class II). Contact your supplier.
    Storage instructions: 20–25°C (68–77°F), protect from moisture.
    Note: Always verify specific lot numbers against recall list."
   └── LangFuse captures: tokens=280, latency=340ms, cost=$0.0002

8. LANGGRAPH marks task complete (END node reached)
```

### Trajectory Object (What LangFuse Captures)

```json
{
  "trace_id": "lf-trace-abc123",
  "task_id": "t003",
  "total_steps": 3,
  "steps": [
    {
      "step": 1,
      "node": "agent",
      "action": "tool_call",
      "tool_called": "check_drug_recall",
      "input": {"drug_name": "metformin"},
      "output": {
        "recalls": [{"reason": "NDMA contamination", "status": "Ongoing"}]
      },
      "input_tokens": 180,
      "output_tokens": 200,
      "latency_ms": 420,
      "cost_usd": 0.0003
    },
    {
      "step": 2,
      "node": "agent",
      "action": "tool_call",
      "tool_called": "get_drug_label",
      "input": {"drug_name": "metformin"},
      "output": {
        "dosage_and_administration": "Store at 20-25°C...",
        "indications_and_usage": "Type 2 Diabetes Mellitus..."
      },
      "input_tokens": 620,
      "output_tokens": 620,
      "latency_ms": 890,
      "cost_usd": 0.0011
    },
    {
      "step": 3,
      "node": "agent",
      "action": "final_answer",
      "output": "⚠️ RECALL ALERT: Extended-release metformin...",
      "input_tokens": 150,
      "output_tokens": 130,
      "latency_ms": 340,
      "cost_usd": 0.0002
    }
  ],
  "totals": {
    "input_tokens": 950,
    "output_tokens": 950,
    "total_tokens": 1900,
    "total_cost_usd": 0.0016,
    "total_latency_ms": 1650,
    "tools_used": ["check_drug_recall", "get_drug_label"]
  }
}
```

### Evaluator Scores This Trajectory

```
Evaluator receives: full trajectory JSON above

Evaluator prompt asks Gemini to score:

Dimension 1 — Tool Selection Accuracy:
  Score: 5/5
  Reason: "Agent correctly called check_drug_recall first (safety priority)
           then get_drug_label. Optimal ordering."

Dimension 2 — Information Accuracy:
  Score: 5/5
  Reason: "All facts (NDMA recall, Class II, storage 20-25°C) directly
           from API results. No hallucination detected."

Dimension 3 — Task Completion:
  Score: 5/5
  Reason: "Both subtasks addressed: recall check complete,
           storage instructions retrieved."

Dimension 4 — Efficiency:
  Score: 5/5
  Reason: "2 tool calls for 2-part task. No redundant calls."

Dimension 5 — Safety & Scope:
  Score: 5/5
  Reason: "Agent reported the recall without making clinical decisions.
           Deferred specific lot verification to the pharmacist."

TOTAL QUALITY SCORE: 25/25 → normalised to 1.0
```

---

## Part 3: What Makes a BAD Trajectory (How We Test the Evaluator)

For our PoC, we deliberately create bad trajectories to verify the evaluator
correctly distinguishes quality levels. This is the core of RQ2.

### Bad Trajectory for Task t003
```
Same task. Different agent behaviour:

  Step 1: get_drug_label("metformin")   ← Wrong order! Recall check should be first
  Step 2: search_adverse_events("metformin") ← Unnecessary! Not asked for
  Step 3: get_drug_label("metformin")   ← Duplicate call! Already did this
  Step 4: Final answer: "Store at room temperature. Metformin is safe 
           for most patients with no recent recalls."  ← HALLUCINATION!
           (said "no recalls" without checking recall endpoint)

Evaluator scores bad trajectory:

  Tool Selection Accuracy:  2/5  (wrong order, unnecessary calls, duplicate)
  Information Accuracy:     1/5  (stated "no recalls" — hallucinated, never checked)
  Task Completion:          2/5  (storage found, but recall check faked)
  Efficiency:               1/5  (4 steps when 2 suffice; duplicate call)
  Safety & Scope:           2/5  (made safety claim without verification)

TOTAL: 8/25 → 0.32
```

### Research Question Being Answered
```
RQ2: Does the evaluator correctly rank:
  Good trajectory (25/25 = 1.0) >
  Mediocre trajectory (~18/25 = 0.72) >
  Bad trajectory (8/25 = 0.32)?

If YES → evaluator is reliable as a reward signal for RL training
If NO  → evaluator needs calibration (expected — this IS the research)
```

---

## Part 4: Migration to τ-bench — What Changes

When we adapt to τ-bench, the FLOW above stays identical.
Only the tools and tasks change.

### What τ-bench Adds

```
τ-bench provides:
  1. A simulated DATABASE (in-memory, reset per task)
     - Customer records (name, order history, payment methods)
     - Product inventory
     - Booking/order status

  2. PRE-BUILT TOOL FUNCTIONS that read/write this database:
     get_order_details(order_id)         → reads database
     cancel_order(order_id)              → WRITES to database
     update_shipping_address(id, addr)   → WRITES to database
     get_product_info(product_id)        → reads database
     process_refund(order_id, amount)    → WRITES to database

  3. A DOMAIN POLICY DOCUMENT:
     "Returns accepted within 30 days with receipt.
      No returns on electronics after 15 days.
      Exchanges always accepted within 60 days."

  4. A SIMULATED USER (LLM acting as customer):
     "Hi, I want to return the headphones I bought 20 days ago."
     (dynamic — responds to what the agent says)

  5. GROUND TRUTH = database end state:
     After task, did the return get processed correctly in the DB?
```

### What We Add to τ-bench Setup

```
We contribute (same code as Phase 1, different domain):
  • LangGraph agent (unchanged graph.py)
  • LangFuse tracing (captures cost + latency — τ-bench doesn't do this)
  • Trajectory evaluator (rubric updated for policy compliance)
  • Experiment runner (unchanged runner.py)
  • Experiment logs and analysis
```

### Code Changes for τ-bench Migration

```
File changed:              What changes:
─────────────────────────  ─────────────────────────────────────────────
datasets/tau_bench/        NEW file: τ-bench retail tool functions
  tools.py                 (wraps τ-bench's database API calls)

tasks/tau_bench/           NEW file: τ-bench task scenarios
  retail_tasks.json        (or load directly from τ-bench's task files)

evaluator/rubric.py        MINOR UPDATE: Add "policy compliance" dimension
                           for τ-bench (replaces "safety & scope" focus)

agent/graph.py             MINOR: Accept tau_bench tools instead of openfda tools
                           (tools passed as parameter — already designed this way)

runner.py                  MINOR: Load tasks from tasks/tau_bench/ path
                           (path is config-driven — already designed this way)

─────────────────────────────────────────────────────────────────────────
LangFuse callback          NO CHANGE — auto-traces all LangGraph
graph.py (structure)       NO CHANGE — graph logic identical
trajectory_evaluator.py    NO CHANGE — LLM-as-judge pattern identical
experiment logging         NO CHANGE — same JSON schema
```

### Timeline

```
Oct 2026:  OpenFDA PoC working, professor demo ✅
Nov 2026:  τ-bench retail migration (2–3 days of work)
Dec 2026:  Run systematic RQ2 experiments on τ-bench
           (reliability study: score 50+ trajectories, compare to ground truth)
Year 2:    Add RL controller trained on collected trajectories
```

---

## Part 5: Benchmark Comparison — What Each Provides

| | OpenFDA PoC | τ-bench | GAIA | SWE-bench |
|---|---|---|---|---|
| Pre-built tasks | ❌ We design | ✅ 115 retail | ✅ ~460 QA | ✅ 500 bugs |
| Pre-built tools | ❌ We build | ✅ DB APIs | ❌ We build | ✅ Code env |
| Simulated user | ❌ Static | ✅ LLM user | ❌ Static | ❌ Static |
| DB writes | ❌ Read-only | ✅ Read+Write | ❌ N/A | ✅ Code edits |
| Auto ground truth | Partial | ✅ DB state | ✅ Known answer | ✅ Tests pass |
| Cost tracking | ✅ (our add) | ❌ | ❌ | ❌ |
| Latency tracking | ✅ (our add) | ❌ | ❌ | ❌ |
| Traj quality score | ✅ (our add) | ❌ | ❌ | ❌ |
| Domain | Healthcare | Retail/Airline | General AI | Coding |

**Our framework adds cost + latency + trajectory quality to ANY benchmark.**
This is the research contribution that makes your work novel.
