"""
Tool Definitions — Healthcare / Pharmacy Domain (OpenFDA)
RxSafetyAgent — Phase 1 PoC

These tools are registered with the LangGraph agent.
The LLM reads each tool's docstring to decide WHEN to call it.
Each tool hits one OpenFDA API endpoint and returns clean JSON.

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


# ── Constants ────────────────────────────────────────────────────────────────

OPENFDA_BASE_URL = "https://api.fda.gov"
OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY", "")  # optional — increases rate limit
PATIENTS_DB_PATH = os.path.join(
    os.path.dirname(__file__), "../../../../data/pharmacy_db/patients.json"
)


def _build_params(search: str, extra: dict = None) -> dict:
    """Build query parameters for OpenFDA API calls."""
    params = {"search": search}
    if OPENFDA_API_KEY:
        params["api_key"] = OPENFDA_API_KEY
    if extra:
        params.update(extra)
    return params


# ── Tool 1: Adverse Events ────────────────────────────────────────────────────

@tool
def search_adverse_events(drug_name: str, limit: int = 10) -> dict:
    """Search FDA adverse event reports (FAERS) for a drug.

    Use this tool when the task involves:
    - Finding what side effects or reactions have been reported for a drug
    - Understanding the safety profile of a medication
    - Checking how many serious events (hospitalisations, deaths) were reported
    - Comparing reaction patterns for a drug

    The data comes from voluntary reports submitted to FDA — these are
    suspicions, not confirmed causes. More reports = more monitoring, not
    necessarily more danger.

    Args:
        drug_name: Generic or brand name of the drug (e.g., "warfarin", "metformin")
        limit: Number of top reactions to return (default 10, max 100)

    Returns:
        dict with:
          - drug: name searched
          - total_reports: total number of adverse event reports in FDA database
          - serious_count: number of reports flagged as serious
          - top_reactions: list of {term, count} — most frequently reported reactions
          - serious_reactions: list of {term, count} — top reactions from serious reports only
                               (clinically important rare reactions like lactic acidosis appear here)
          - note: disclaimer about voluntary reporting nature of FAERS data
    """
    url = f"{OPENFDA_BASE_URL}/drug/event.json"
    base_search = (
        f'patient.drug.openfda.generic_name:"{drug_name}"'
        f'+patient.drug.openfda.brand_name:"{drug_name}"'
    )

    # Step 1: Get top reactions by frequency (most commonly reported)
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
            "drug": drug_name,
            "total_reports": 0,
            "serious_count": 0,
            "top_reactions": [],
            "serious_reactions": [],
            "note": f"No adverse event reports found for '{drug_name}' in FDA FAERS database."
        }

    # Step 2: Get total report count
    try:
        total_data = requests.get(url, params=_build_params(search=base_search, extra={"limit": 1}), timeout=10).json()
        total_reports = total_data.get("meta", {}).get("results", {}).get("total", 0)
    except Exception:
        total_reports = "unavailable"

    # Step 3: Get serious report count — parenthesise OR group to fix precedence (W2 fix)
    serious_search = f'({base_search})+AND+serious:1'
    try:
        serious_data = requests.get(url, params=_build_params(search=serious_search, extra={"limit": 1}), timeout=10).json()
        serious_count = serious_data.get("meta", {}).get("results", {}).get("total", 0)
    except Exception:
        serious_count = "unavailable"

    # Step 4: Get top reactions specifically from serious reports (W1 fix)
    # Rare but serious reactions (e.g., lactic acidosis) appear here even if rare overall
    try:
        serious_reactions_data = requests.get(
            url,
            params=_build_params(
                search=serious_search,
                extra={"count": "patient.reaction.reactionmeddrapt.exact", "limit": 10}
            ),
            timeout=10
        ).json()
        serious_reactions = serious_reactions_data.get("results", [])
    except Exception:
        serious_reactions = []

    return {
        "drug": drug_name,
        "total_reports": total_reports,
        "serious_count": serious_count,
        "top_reactions": reaction_data.get("results", []),
        "serious_reactions": serious_reactions,
        "note": "Voluntary reports to FDA — suspicion of cause, not confirmed. serious_reactions shows top reactions from serious/fatal cases only."
    }


# ── Tool 2: Drug Label ────────────────────────────────────────────────────────

@tool
def get_drug_label(drug_name: str) -> dict:
    """Retrieve the official FDA prescribing label for a drug.

    Use this tool when the task involves:
    - Finding what conditions a drug is approved to treat (indications)
    - Checking black box warnings (most serious safety warnings)
    - Finding contraindications (when NOT to use the drug)
    - Getting drug interaction information
    - Finding dosage instructions or storage requirements
    - Checking safety for specific populations (elderly, pregnant, children)
    - Finding side effects observed in clinical trials (adverse_reactions)

    Args:
        drug_name: Generic or brand name of the drug (e.g., "warfarin", "metformin")

    Returns:
        dict with key label sections:
          - drug: name searched
          - brand_names: list of brand names
          - generic_name: standardised generic name
          - manufacturer: drug manufacturer name
          - pharmacological_class: drug class (e.g., "Vitamin K Antagonist")
          - boxed_warning: black box warning text (most serious — empty list if none)
          - indications_and_usage: what conditions it treats
          - contraindications: when NOT to use
          - warnings_and_cautions: important safety information
          - drug_interactions: interactions with other drugs/foods
          - geriatric_use: safety information for elderly patients
          - pregnancy: safety in pregnancy
          - pediatric_use: safety in children
          - dosage_and_administration: how to take it (dose, frequency, route)
          - storage_and_handling: storage temperature and conditions
          - adverse_reactions: side effects from clinical trials
    """
    url = f"{OPENFDA_BASE_URL}/drug/label.json"
    params = _build_params(
        search=(
            f'openfda.generic_name:"{drug_name}"'
            f'+openfda.brand_name:"{drug_name}"'
        ),
        extra={"limit": 1}
    )

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception as e:
        return {"error": str(e), "drug": drug_name}

    # C1 fix: structured empty response instead of error dict
    if not data.get("results"):
        return {
            "drug": drug_name,
            "found": False,
            "note": f"No FDA label found for '{drug_name}'. Drug may not be in FDA database or spelling may differ."
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
        "storage_and_handling": label.get("storage_and_handling", []),   # C2 fix
        "adverse_reactions": label.get("adverse_reactions", []),
    }


# ── Tool 3: Drug Recall ───────────────────────────────────────────────────────

@tool
def check_drug_recall(drug_name: str, status: str = "Ongoing") -> dict:
    """Check FDA recall and enforcement actions for a drug.

    Use this tool when the task involves:
    - Verifying if a drug is under active recall before dispensing
    - Finding the reason for a recall (contamination, mislabelling, etc.)
    - Checking recall classification (Class I = most serious)
    - Determining distribution scope of a recall (nationwide vs specific states)
    - Finding which manufacturer (firm) initiated the recall
    - Checking if a recall was voluntary or FDA-mandated
    - Finding when a recall was initiated and its current status

    Recall Classifications:
      Class I  → Serious health hazard — may cause death or serious injury
      Class II → May cause temporary adverse health consequences
      Class III→ Unlikely to cause harm but violates FDA regulations

    Args:
        drug_name: Generic or brand name of the drug
        status: "Ongoing" for active recalls, "Terminated" for resolved,
                or "" for all recalls (default: "Ongoing")

    Returns:
        dict with:
          - drug: name searched
          - status_filter: which status was applied ("Ongoing", "Terminated", "all")
          - active_recalls_found: True if any recalls found, False if none
          - total_recalls: total number of matching recalls in FDA database
          - recalls: list of up to 5 recall records, each containing:
              - recall_number: unique FDA recall identifier
              - status: "Ongoing" or "Terminated"
              - classification: "Class I", "Class II", or "Class III"
              - reason_for_recall: why it was recalled (e.g., NDMA contamination)
              - product_description: exact product name, strength, lot number
              - recalling_firm: manufacturer who initiated the recall
              - recall_initiation_date: when recall started (YYYYMMDD format)
              - distribution_pattern: geographic scope (e.g., "Nationwide")
              - voluntary_mandated: "Voluntary" or "Mandated" by FDA
    """
    url = f"{OPENFDA_BASE_URL}/drug/enforcement.json"

    # Single OR query — works whether user passes generic name or brand name
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

    # C1 fix: structured empty response — "no recalls found" is a VALID result, not an error
    if not data.get("results"):
        return {
            "drug": drug_name,
            "status_filter": status or "all",
            "active_recalls_found": False,
            "total_recalls": 0,
            "recalls": [],
            "note": f"No {'active ' if status == 'Ongoing' else ''}recalls found for '{drug_name}'. Safe to proceed with dispensing from a recall perspective."
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
    }


# ── Tool 4: Patient Record (Local DB) ────────────────────────────────────────

@tool
def get_patient_record(patient_id: str) -> dict:
    """Look up a patient's record from the CVS pharmacy database.

    Use this tool when the task mentions a specific patient ID (e.g., P001)
    and you need to know:
    - What medications the patient is currently taking
    - Patient's medical conditions
    - Patient's insurance type
    - Patient's age or allergies

    This tool reads from the local pharmacy database (not OpenFDA).
    After retrieving the patient record, use other tools (check_drug_recall,
    get_drug_label) to look up information about their specific medications.

    Args:
        patient_id: Patient identifier (e.g., "P001", "P002")

    Returns:
        dict with:
          - patient_id: unique patient identifier (e.g., "P001")
          - name: patient full name
          - age: patient age in years
          - sex: "male" or "female"
          - conditions: list of medical conditions (e.g., ["atrial fibrillation", "hypertension"])
          - current_medications: list of drug names the patient is currently taking
          - insurance: insurance type (e.g., "Medicare Part D", "Commercial")
          - last_visit: date of last pharmacy visit (YYYY-MM-DD)
          - allergies: list of known drug allergies (empty list if none)
          - pharmacy_notes: pharmacist notes about this patient
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
        return {"error": "Patient database not yet initialised. "
                         "Create data/pharmacy_db/patients.json first."}
    except Exception as e:
        return {"error": str(e)}


# ── Tool Registry — export all tools ─────────────────────────────────────────

OPENFDA_TOOLS = [
    search_adverse_events,
    get_drug_label,
    check_drug_recall,
    get_patient_record,
]
