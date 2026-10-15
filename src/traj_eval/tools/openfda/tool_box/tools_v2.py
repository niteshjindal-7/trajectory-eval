"""
Tool Definitions v2 — Constrained / Scope-Explicit Version
RxSafetyAgent — Experimental tool set for testing LLM tool selection behaviour

Difference from v1:
  Each tool docstring explicitly states what it DOES and DOES NOT return.
  This tests whether explicit scope constraints in tool descriptions
  force the LLM to call all relevant tools rather than filling gaps from
  training knowledge.

Research hypothesis:
  If LLM still halluculates with v2 tools → problem is deeper than tool prompting
  If LLM calls all 3 tools with v2 → constrained docstrings improve tool calling

Tools defined here:
  1. search_adverse_events   → /drug/event.json
  2. get_drug_label          → /drug/label.json
  3. check_drug_recall       → /drug/enforcement.json
  4. get_patient_record      → local data/pharmacy_db/patients.json
"""

import json
import os
import requests
from langchain_core.tools import tool


OPENFDA_BASE_URL = "https://api.fda.gov"
PATIENTS_DB_PATH = os.path.join(
    os.path.dirname(__file__), "../../../../../data/pharmacy_db/patients.json"
)


def _build_params(search: str, extra: dict = None) -> dict:
    params = {"search": search}
    if extra:
        params.update(extra)
    return params


# ── Tool 1: Adverse Events ────────────────────────────────────────────────────

@tool
def search_adverse_events(drug_name: str, limit: int = 25) -> dict:
    """Search FDA FAERS adverse event reports. Returns ONLY adverse event data.

    SCOPE — this tool returns ONLY:
      - Counts of reported adverse reactions (e.g., nausea: 18000 reports)
      - Total number of reports in FDA FAERS database
      - Count of serious/fatal reports

    THIS TOOL DOES NOT PROVIDE:
      - Drug label warnings or black box warnings → use get_drug_label instead
      - Recall status → use check_drug_recall instead
      - Patient records → use get_patient_record instead
      - Clinical trial data or prescribing information

    If you need drug label or recall information, you MUST call those tools separately.
    Do NOT assume label or recall information from this tool's results.

    Args:
        drug_name: Generic or brand name of the drug
        limit: Number of top reactions to return (default 25)

    Returns:
        dict with adverse event data ONLY:
          - drug: name searched
          - total_reports: total FAERS reports for this drug
          - serious_count: number of serious reports
          - top_reactions: list of {term, count}
          - note: disclaimer about voluntary reporting
    """
    url = f"{OPENFDA_BASE_URL}/drug/event.json"
    base_search = (
        f'patient.drug.openfda.generic_name:"{drug_name}"'
        f'+patient.drug.openfda.brand_name:"{drug_name}"'
    )

    params = _build_params(
        search=base_search,
        extra={"count": "patient.reaction.reactionmeddrapt.exact", "limit": limit}
    )
    try:
        reaction_data = requests.get(url, params=params, timeout=10).json()
    except Exception as e:
        return {"error": str(e), "drug": drug_name}

    if not reaction_data.get("results"):
        return {
            "drug": drug_name, "total_reports": 0, "serious_count": 0,
            "top_reactions": [],
            "note": f"No adverse event reports found for '{drug_name}' in FAERS."
        }

    try:
        total_data = requests.get(url, params=_build_params(search=base_search, extra={"limit": 1}), timeout=10).json()
        total_reports = total_data.get("meta", {}).get("results", {}).get("total", 0)
    except Exception:
        total_reports = "unavailable"

    serious_search = f'({base_search})+AND+serious:1'
    try:
        serious_data = requests.get(url, params=_build_params(search=serious_search, extra={"limit": 1}), timeout=10).json()
        serious_count = serious_data.get("meta", {}).get("results", {}).get("total", 0)
    except Exception:
        serious_count = "unavailable"

    return {
        "drug": drug_name,
        "total_reports": total_reports,
        "serious_count": serious_count,
        "top_reactions": reaction_data.get("results", []),
        "note": "FAERS voluntary reports only — suspicion, not confirmed causation. Does NOT include label warnings or recall status."
    }


# ── Tool 2: Drug Label ────────────────────────────────────────────────────────

@tool
def get_drug_label(drug_name: str) -> dict:
    """Retrieve FDA prescribing label. Returns ONLY official label sections.

    SCOPE — this tool returns ONLY:
      - Black box warnings from the official FDA label
      - Approved indications (what conditions the drug treats)
      - Contraindications (who must NOT take it)
      - Warnings and precautions
      - Drug interactions
      - Dosage, storage, and population-specific guidance

    THIS TOOL DOES NOT PROVIDE:
      - Recall status or enforcement actions → use check_drug_recall instead
      - Patient-reported adverse events from FAERS → use search_adverse_events instead
      - Patient records → use get_patient_record instead

    If you need recall or adverse event information, you MUST call those tools.
    Do NOT assume recall status or FAERS data from this tool's results.

    Args:
        drug_name: Generic or brand name of the drug

    Returns:
        dict with label sections ONLY:
          - boxed_warning, indications_and_usage, contraindications
          - warnings_and_cautions, drug_interactions
          - geriatric_use, pregnancy, pediatric_use
          - dosage_and_administration, storage_and_handling
          - adverse_reactions (from clinical trials — different from FAERS reports)
    """
    url = f"{OPENFDA_BASE_URL}/drug/label.json"
    params = _build_params(
        search=(f'openfda.generic_name:"{drug_name}"+openfda.brand_name:"{drug_name}"'),
        extra={"limit": 1}
    )
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception as e:
        return {"error": str(e), "drug": drug_name}

    if not data.get("results"):
        return {
            "drug": drug_name, "found": False,
            "note": f"No FDA label found for '{drug_name}'."
        }

    label = data["results"][0]
    openfda = label.get("openfda", {})

    return {
        "drug": drug_name,
        "brand_names": openfda.get("brand_name", []),
        "generic_name": openfda.get("generic_name", []),
        "manufacturer": openfda.get("manufacturer_name", []),
        "pharmacological_class": openfda.get("pharm_class_epc", []),
        "boxed_warning": label.get("boxed_warning", []),
        "indications_and_usage": label.get("indications_and_usage", []),
        "contraindications": label.get("contraindications", []),
        "warnings_and_cautions": label.get("warnings_and_precautions", []),
        "drug_interactions": label.get("drug_interactions", []),
        "geriatric_use": label.get("geriatric_use", []),
        "pregnancy": label.get("pregnancy", []),
        "pediatric_use": label.get("pediatric_use", []),
        "dosage_and_administration": label.get("dosage_and_administration", []),
        "storage_and_handling": label.get("storage_and_handling", []),
        "adverse_reactions": label.get("adverse_reactions", []),
        "note": "Official FDA label sections ONLY. Does NOT include FAERS adverse event reports or recall status."
    }


# ── Tool 3: Drug Recall ───────────────────────────────────────────────────────

@tool
def check_drug_recall(drug_name: str, status: str = "Ongoing") -> dict:
    """Check FDA recall enforcement actions. Returns ONLY recall status data.

    SCOPE — this tool returns ONLY:
      - Whether active recalls exist for this drug
      - Recall classification (Class I/II/III)
      - Reason for recall (e.g., NDMA contamination)
      - Recalling manufacturer and distribution scope

    THIS TOOL DOES NOT PROVIDE:
      - Drug label warnings or clinical information → use get_drug_label instead
      - Adverse event reports from patients → use search_adverse_events instead
      - Patient records → use get_patient_record instead

    If you need label warnings or adverse event data, you MUST call those tools.
    Do NOT assume label or adverse event information from recall results.
    A drug with no recalls may still have important label warnings.

    Args:
        drug_name: Generic or brand name of the drug
        status: "Ongoing" (active), "Terminated" (resolved), or "" (all)

    Returns:
        dict with recall data ONLY:
          - active_recalls_found: True/False
          - total_recalls: count
          - recalls: list of recall records
          - note: clarifies this covers recalls only, not label warnings
    """
    url = f"{OPENFDA_BASE_URL}/drug/enforcement.json"
    search = (
        f'openfda.generic_name:"{drug_name}"'
        f'+openfda.brand_name:"{drug_name}"'
    )
    if status:
        search += f'+AND+status:"{status}"'

    params = _build_params(search=search, extra={"limit": 5})
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception as e:
        return {"error": str(e), "drug": drug_name}

    if not data.get("results"):
        return {
            "drug": drug_name,
            "status_filter": status or "all",
            "active_recalls_found": False,
            "total_recalls": 0,
            "recalls": [],
            "note": f"No active recalls for '{drug_name}'. NOTE: Always check label warnings and adverse events separately — no recall does not mean no safety concerns."
        }

    results = data.get("results", [])
    total = data.get("meta", {}).get("results", {}).get("total", 0)
    recalls = []
    for r in results:
        recalls.append({
            "recall_number": r.get("recall_number", ""),
            "status": r.get("status", ""),
            "classification": r.get("classification", ""),
            "reason_for_recall": r.get("reason_for_recall", ""),
            "product_description": r.get("product_description", ""),
            "recalling_firm": r.get("recalling_firm", ""),
            "recall_initiation_date": r.get("recall_initiation_date", ""),
            "distribution_pattern": r.get("distribution_pattern", ""),
            "voluntary_mandated": r.get("voluntary_mandated", ""),
        })

    return {
        "drug": drug_name,
        "status_filter": status or "all",
        "active_recalls_found": total > 0,
        "total_recalls": total,
        "recalls": recalls,
        "note": "Recall data ONLY. Does NOT include label warnings or FAERS adverse events — check those tools separately."
    }


# ── Tool 4: Patient Record ────────────────────────────────────────────────────

@tool
def get_patient_record(patient_id: str) -> dict:
    """Look up patient record from CVS pharmacy database. Returns ONLY patient data.

    SCOPE — this tool returns ONLY:
      - Patient demographics (age, sex)
      - Current medications list
      - Medical conditions
      - Allergies, insurance, pharmacy notes

    THIS TOOL DOES NOT PROVIDE:
      - Drug safety information → use check_drug_recall, get_drug_label, search_adverse_events
      - Any FDA data

    After calling this tool, you MUST call other tools for each medication found.
    This tool only tells you WHAT medications the patient takes — not whether they are safe.

    Args:
        patient_id: Patient identifier (e.g., "P001", "P002")

    Returns:
        dict with patient data ONLY — no drug safety information included
    """
    try:
        db_path = os.path.abspath(PATIENTS_DB_PATH)
        with open(db_path, "r") as f:
            patients = json.load(f)
        for patient in patients:
            if patient.get("patient_id") == patient_id:
                return patient
        return {"error": f"Patient {patient_id} not found in database"}
    except FileNotFoundError:
        return {"error": "Patient database not initialised."}
    except Exception as e:
        return {"error": str(e)}


# ── Tool Registry ─────────────────────────────────────────────────────────────

OPENFDA_TOOLS = [
    search_adverse_events,
    get_drug_label,
    check_drug_recall,
    get_patient_record,
]
