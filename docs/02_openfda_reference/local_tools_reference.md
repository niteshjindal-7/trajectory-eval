# Local Tools Reference
## Tools That Read Local Data (Not External APIs)

These tools are SEPARATE from OpenFDA API tools.
They read from local files we maintain inside the project.

---

## Tool: get_patient_record(patient_id)

**Source:** `data/pharmacy_db/patients.json`
**Type:** Local file read (no API call, no network request)
**Purpose:** Simulates a CVS pharmacy patient database lookup

### What it returns:
```json
{
  "patient_id": "P001",
  "name": "John Smith",
  "age": 72,
  "conditions": ["atrial fibrillation", "hypertension"],
  "current_medications": ["warfarin", "lisinopril"],
  "insurance": "Medicare Part D",
  "last_visit": "2026-09-15",
  "allergies": ["penicillin"]
}
```

### Why we have this:
- Enables tasks like "Patient P001 is picking up a prescription — check their medications for recalls"
- Agent first calls get_patient_record() to know what drugs the patient is on
- Then calls OpenFDA tools based on those drug names
- Creates realistic multi-step trajectories mimicking CVS pharmacy workflows

### Relationship to τ-bench:
τ-bench has a similar simulated database (customer records).
Our patients.json plays the same role — a domain-specific data store
the agent queries through a tool before calling external APIs.

### Note on writes:
Phase 1 — READ ONLY (agent only reads patient records)
Phase 2+ — may add write capability (e.g., flag a drug as recalled in patient record)

---

## Where tools.py files live:

```
src/traj_eval/datasets/openfda/tools.py   ← OpenFDA API tools (3 tools)
src/traj_eval/datasets/openfda/tools.py   ← also includes get_patient_record()
                                             since it supports the same domain
```

All 4 Phase 1 tools live in the same `datasets/openfda/tools.py` file
because they all serve the healthcare/pharmacy domain together.
