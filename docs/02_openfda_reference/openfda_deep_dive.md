# OpenFDA Dataset — Deep Dive Reference
## Thorough In-Depth Understanding for Trajectory Evaluation Research

---

## 1. What OpenFDA Actually Is

OpenFDA is NOT a single dataset. It is a **collection of multiple independent datasets**
all exposed through a unified REST API. Each dataset comes from a different FDA
regulatory system and covers a different category of FDA-regulated products.

Think of it like a building with many departments:
- Drug Department (FAERS, SPL, NDC, Recalls)
- Device Department (MAUDE, 510k, Classifications)
- Food Department (CFSAN adverse events, food recalls)
- Cosmetics Department
- Tobacco Department

We primarily use the **Drug Department** for our PoC.

---

## 2. All Drug API Endpoints — What They Are and Contain

### 2.1 Drug Adverse Events — `/drug/event.json`
**Source system:** FDA Adverse Event Reporting System (FAERS)

**What it is:**
Voluntary safety reports submitted to FDA when a patient, doctor, pharmacist,
or manufacturer suspects a drug caused a side effect or problem. These are NOT
confirmed — they are REPORTS of suspicion. Not every reported event was caused
by the drug.

**Volume:** ~25 million reports (1969 to present)
**Coverage:** 1969–present (electronic reporting standardised from 2004)
**Updated:** Quarterly

**Key fields:**
```
safetyreportid                   Unique report ID (primary key)
receivedate                      When FDA received the report
serious                          1=serious, 2=not serious
seriousnessdeath                 1=death resulted
seriousnesshospitalization       1=hospitalisation resulted
seriousnesslifethreatening       1=life-threatening
primarysource.qualification      Who reported: 1=physician, 2=pharmacist,
                                 3=other health professional, 5=consumer

patient.patientonsetage          Patient age when event occurred
patient.patientsex               1=male, 2=female
patient.patientweight            Weight in kg

patient.drug[].medicinalproduct  Drug name as reported (free text — messy)
patient.drug[].drugindication    Why the drug was being taken
patient.drug[].drugdosage        Dose taken
patient.drug[].drugcharacterization  1=suspect drug, 2=concomitant, 3=interacting

patient.reaction[].reactionmeddrapt  Reaction description (MedDRA term)
patient.reaction[].reactionoutcome   1=recovered, 5=fatal, 6=unknown

openfda.generic_name             Harmonised generic name (reliable for search)
openfda.brand_name               Harmonised brand name
openfda.manufacturer_name        Drug manufacturer
```

**Example query:**
```
GET https://api.fda.gov/drug/event.json
    ?search=patient.drug.openfda.generic_name:"warfarin"
    +AND+serious:1
    &count=patient.reaction.reactionmeddrapt.exact
    &limit=10
```
Returns: top 10 most reported serious reactions for warfarin

**What tools we can build from this endpoint:**
```python
search_adverse_events(drug_name, limit=10)
    → What adverse events are reported for this drug?

get_serious_adverse_events(drug_name)
    → Filter only serious/fatal reports

compare_adverse_event_rates(drug1, drug2)
    → Compare reporting volume between two drugs

get_adverse_events_by_age_group(drug_name, age_group)
    → Paediatric vs geriatric adverse event patterns
    → Very relevant to CVS/Signify Health elderly patient context

count_deaths_reported(drug_name)
    → How many death reports exist for this drug?

get_recent_adverse_events(drug_name, year)
    → Filter by recent years (2023-present)
```

---

### 2.2 Drug Product Labeling — `/drug/label.json`
**Source system:** Structured Product Labeling (SPL) — official drug package inserts

**What it is:**
The official FDA-approved prescribing information for drugs. This is what you find
inside a drug package or on the FDA drug label. Both prescription and OTC drugs.

**Volume:** ~150,000 label documents
**Coverage:** Current approved labels (continuously updated)
**Updated:** When manufacturers submit label changes to FDA

**Key fields — all sections of a drug label:**
```
id                               SPL document ID (primary key)
set_id                           Groups versions of the same drug's label

indications_and_usage            ← What DISEASES/CONDITIONS it treats
                                   "Type 2 Diabetes Mellitus..."
                                   (diagnostic-adjacent)

contraindications                ← When NOT to use: specific conditions,
                                   allergies, combinations that are forbidden

warnings_and_cautions            ← Important safety info the prescriber needs

boxed_warning                    ← BLACK BOX WARNING — most serious level
                                   Only added for life-threatening risks
                                   Example warfarin: "Can cause fatal bleeding"
                                   Example atorvastatin: "Contraindicated in pregnancy"

adverse_reactions                ← Side effects observed in clinical trials
adverse_reactions_table          ← Same data as HTML table

drug_interactions                ← Interactions with other drugs/foods/supplements
drug_interactions_table          ← Same as HTML table

dosage_and_administration        ← How to take it (dose, frequency, route)
dosage_forms_and_strengths       ← Available formulations (5mg tablet, 10mg tablet...)

mechanism_of_action              ← How it works biologically
clinical_pharmacology            ← Full pharmacology section
pharmacokinetics                 ← How body processes it (absorption, half-life, etc.)

clinical_studies                 ← Evidence from clinical trials
carcinogenesis_and_mutagenesis...← Cancer risk studies

use_in_specific_populations      ← Special patient groups
pregnancy                        ← Section 8.1 — pregnancy safety
lactation                        ← Breastfeeding safety
pediatric_use                    ← Children safety
geriatric_use                    ← Elderly patients ← KEY for CVS/Signify Health

overdosage                       ← What happens with too much (symptoms + treatment)
description                      ← Chemical and physical description
spl_product_data_elements        ← Ingredients list

openfda.brand_name               Harmonised brand name (e.g., "Coumadin")
openfda.generic_name             Harmonised generic name (e.g., "warfarin sodium")
openfda.manufacturer_name        Manufacturer
openfda.ndc                      National Drug Code(s) — list
openfda.rxcui                    RxNorm concept ID — cross-reference identifier
openfda.unii                     Unique Ingredient Identifier
openfda.pharm_class_epc          Pharmacological class (e.g., "Anticoagulant")
```

**Example query:**
```
GET https://api.fda.gov/drug/label.json
    ?search=openfda.generic_name:"warfarin"
    &limit=1
```
Returns: Complete prescribing information for warfarin

**What tools we can build from this endpoint:**
```python
get_drug_label(drug_name)
    → Full label for a drug

get_drug_indications(drug_name)
    → What conditions does this drug treat?

get_black_box_warning(drug_name)
    → Is there a black box warning? What does it say?

get_drug_interactions(drug_name)
    → What drugs/foods interact with this one?

get_geriatric_use_info(drug_name)
    → What does label say about elderly patients?

get_pregnancy_safety(drug_name)
    → Is this safe in pregnancy?

get_pediatric_use_info(drug_name)
    → Is this safe for children?

get_dosage_info(drug_name)
    → Standard dosing information
```

---

### 2.3 Drug Recall Enforcement — `/drug/enforcement.json`
**Source system:** FDA Recalls, Market Withdrawals & Safety Alerts

**What it is:**
Official records of drug recalls. A recall happens when a product is defective,
contaminated, mislabelled, or otherwise unsafe.

**Volume:** ~50,000 records (2004-present)
**Coverage:** 2004–present
**Updated:** Weekly

**Recall Classifications:**
```
Class I    → Serious health hazard — may cause death or serious injury
Class II   → May cause temporary adverse health consequences
Class III  → Unlikely to cause harm but violates FDA regulations
```

**Key fields:**
```
recall_number                    Unique recall ID (primary key)
status                           "Ongoing" or "Terminated"
classification                   "Class I", "Class II", "Class III"

product_description              What was recalled (drug name, formulation, lot)
reason_for_recall                Why: "NDMA contamination", "superpotent",
                                 "mislabelled dosage", "microbial contamination"

recalling_firm                   Company that initiated the recall
voluntary_mandated               "Voluntary" (firm initiated) or "Mandated" (FDA ordered)
initial_firm_notification        How patients/providers were notified

distribution_pattern             Where was it distributed?
                                 "Nationwide", specific states, etc.
product_quantity                 How many units recalled

recall_initiation_date           When recall started
termination_date                 When recall ended (null if ongoing)
center_classification_date       When FDA classified it

openfda.generic_name             Harmonised drug name for searching
openfda.brand_name               Brand name
openfda.manufacturer_name        Manufacturer
```

**What tools we can build:**
```python
check_drug_recall(drug_name, status="Ongoing")
    → Are there active recalls for this drug?

get_recall_details(recall_number)
    → Full details of a specific recall

get_recalls_by_reason(reason_keyword)
    → Find all NDMA contamination recalls, for example

get_class_one_recalls(drug_name)
    → Only the most serious recalls

get_recalls_by_manufacturer(firm_name)
    → All recalls by a specific company (e.g., Aurobindo Pharma)
```

---

### 2.4 NDC Directory — `/drug/ndc.json`
**Source system:** National Drug Code Directory

**What it is:**
The official catalog of all drug products marketed in the USA.
Every drug product has a unique NDC (National Drug Code) — a 10-digit identifier.

**Volume:** ~300,000 products
**Coverage:** All currently marketed US drugs
**Updated:** Daily

**Key fields:**
```
product_ndc                      NDC code (primary key, e.g., "0056-0170-70")
generic_name                     Generic drug name
brand_name                       Brand name
dosage_form                      Tablet, capsule, injection, patch, etc.
route                            How taken: oral, intravenous, topical, etc.
active_ingredients               List of active ingredients with strength
inactive_ingredients             Inactive ingredients
manufacturer_name                Manufacturer
marketing_start_date             When it entered the market
listing_expiration_date          When listing expires
pharm_class                      Pharmacological class
```

**What tools we can build:**
```python
get_drug_ndc(drug_name)
    → What NDC codes exist for this drug? What formulations?

get_drug_formulations(drug_name)
    → What strengths and forms are available? (5mg, 10mg, 20mg tablets)

find_generic_alternatives(brand_name)
    → Find generic versions of a brand-name drug
    → VERY relevant to CVS cost management

get_drug_route(drug_name)
    → Is this an oral drug or injectable? (important for Signify Health)
```

---

### 2.5 Drug Shortages — `/drug/drugshortages.json`
**What it is:** Current and historical drug shortage information

**Key fields:**
```
drug_name                        Drug in shortage
status                           "Current", "Resolved", "Discontinued"
shortage_reason                  Why: manufacturing issues, raw material, demand
availability                     When it might be available again
```

**Tool:**
```python
check_drug_shortage(drug_name)
    → Is this drug currently in shortage? Why?
```

---

## 3. Device API Endpoints (Future Use — Year 2+)

### `/device/event.json` — Medical Device Adverse Events (MAUDE)
- 18+ million reports of device malfunctions, injuries, deaths
- Relevant: glucose monitors, insulin pumps, home health monitoring devices
- Use case: Signify Health home health monitoring context

### `/device/recall.json` — Device Recalls
- Recalled medical devices with classification and reason

### `/device/510k.json` — 510(k) Clearances
- Database of FDA-cleared medical devices

---

## 4. Data Volume and Coverage Summary

| Endpoint | Records | Years | Update Freq |
|---|---|---|---|
| Drug adverse events (FAERS) | ~25 million | 1969–present | Quarterly |
| Drug labels (SPL) | ~150,000 | Current | Continuous |
| Drug recalls | ~50,000 | 2004–present | Weekly |
| NDC directory | ~300,000 | Current | Daily |
| Device adverse events | ~18 million | 1992–present | Quarterly |
| Device recalls | ~40,000 | 2002–present | Weekly |

---

## 5. Cross-Dataset Linking — How to Join Data

OpenFDA provides harmonised `openfda{}` fields in every endpoint so you can
cross-reference between datasets. This is the "primary key" equivalent.

```
Shared identifier fields (in openfda{} block):

openfda.generic_name        Works across: events, labels, recalls, NDC
openfda.brand_name          Works across: events, labels, recalls, NDC
openfda.ndc                 Works across: events, labels, NDC (exact match)
openfda.rxcui               RxNorm ID — cross-reference to external drug databases
openfda.unii                Unique Ingredient Identifier — very stable identifier
openfda.manufacturer_name   Works across: labels, recalls, NDC
openfda.pharm_class_epc     Pharmacological class — works across events, labels
```

**Example cross-dataset query — linking adverse events to recall:**
```
Task: "Is the warfarin that caused this patient's bleeding event 
       under any recall?"

Step 1: /drug/event.json → get adverse event, extract openfda.ndc
Step 2: /drug/enforcement.json?search=openfda.ndc:"extracted_ndc"
        → find recalls for that specific NDC
```

This multi-step cross-dataset query is exactly the kind of trajectory we want
to evaluate — requiring logical ordering of tool calls.

---

## 6. Query Syntax — How to Search

### Basic search:
```
?search=field_name:"value"
```

### AND search:
```
?search=field1:"value1"+AND+field2:"value2"
```

### OR search:
```
?search=field1:"value1"+field2:"value2"
```

### Count/aggregation (for analytics):
```
?count=patient.reaction.reactionmeddrapt.exact
```
Returns: frequency count of each reaction type — useful for "what are the most common side effects?"

### Limit:
```
&limit=10    (default 1, max 1000)
```

### Date range:
```
?search=receivedate:[20230101+TO+20241231]
```

---

## 7. Is It API-Only or Are There Other Ways?

**Three ways to access OpenFDA data:**

### Way 1: Real-time API (what we use)
```
Hit URL → get JSON response
No storage, always current data
Our tools.py uses this method exclusively
```

### Way 2: Bulk download
```
https://download.open.fda.gov/
Download entire datasets as zipped JSON files
Use when you need ALL records for offline analysis
Could be used to build a local database for research
FAERS download = ~15GB compressed
```

### Way 3: Self-hosted instance (advanced)
```
Run FDA's Elasticsearch + API server on your own EC2
No rate limits
See: github.com/FDA/openfda
Would use if we exceed rate limits in large-scale experiments
```

**For our PoC: Way 1 only** (real-time API calls)

---

## 8. Complete Tool Inventory — Phase 1 vs Phase 2

### Phase 1 Tools (PoC — OpenFDA only):
```python
# Immediate implementation (Session 2)
search_adverse_events(drug_name: str, limit: int = 10) -> dict
get_drug_label(drug_name: str) -> dict
check_drug_recall(drug_name: str, status: str = "Ongoing") -> dict

# Easy additions after PoC:
get_drug_ndc(drug_name: str) -> dict
check_drug_shortage(drug_name: str) -> dict
get_serious_adverse_events(drug_name: str) -> dict
get_drug_indications(drug_name: str) -> dict
count_adverse_events_by_reaction(drug_name: str) -> dict
```

### Phase 2 Additions (CMS + Device):
```python
# CMS Part D Drug Spending
get_medicare_drug_cost(drug_name: str) -> dict

# Device endpoints (Signify Health context)
search_device_adverse_events(device_name: str) -> dict
check_device_recall(device_name: str) -> dict
```

---

## 9. Example JSON Response — What We Actually Get

### Calling `/drug/label.json?search=openfda.generic_name:"warfarin"&limit=1`

```json
{
  "meta": {
    "results": {"total": 351, "limit": 1}
  },
  "results": [
    {
      "id": "a4f4e3c0-...",
      "set_id": "5d798c5f-...",
      "boxed_warning": ["WARNING: BLEEDING RISK. Warfarin sodium can cause
                         major or fatal bleeding..."],
      "indications_and_usage": ["Warfarin sodium tablets are indicated for:
                                  Prophylaxis and treatment of venous
                                  thromboembolism and its extension,
                                  pulmonary embolism..."],
      "contraindications": ["Pregnancy... Hemorrhagic tendencies..."],
      "geriatric_use": ["Elderly patients (65+ years) appear to exhibit
                         greater than expected PT/INR response to warfarin..."],
      "drug_interactions": ["Anticoagulant effect may be enhanced by:
                              amiodarone, fluoroquinolones, NSAIDs..."],
      "openfda": {
        "brand_name": ["Coumadin", "Jantoven"],
        "generic_name": ["warfarin sodium"],
        "manufacturer_name": ["Bristol-Myers Squibb"],
        "ndc": ["0056-0170-70", "0056-0171-70"],
        "rxcui": ["202421"],
        "pharm_class_epc": ["Vitamin K Antagonist [EPC]"]
      }
    }
  ]
}
```

This JSON is what our `get_drug_label()` tool returns to the agent.
The agent then reads this and uses it in its reasoning.

---

## 10. Limitations and Caveats

```
Adverse events:
  - Voluntary reports — NOT all side effects, just what was reported
  - Cannot establish causation — correlation only
  - Underreporting is common (estimated 10% of events reported)
  - "Stimulated reporting" — more reports after media coverage ≠ more events

Labels:
  - Not all labels are current — some older drugs have sparse labels
  - Field completeness varies by drug/manufacturer

Recalls:
  - Only covers FDA recalls (not state-level or voluntary market withdrawals)
  - Terminated recalls stay in database (check status field)

Rate limits:
  - 240 req/min without key
  - 1000 req/min with free API key
  - For production experiments: consider self-hosted instance

No patient-level data:
  - Individual patient records are NOT available
  - All data is either aggregate, anonymised, or about products (not patients)
```
