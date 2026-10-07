# OpenFDA API Reference Guide
## Complete Reference for Trajectory Evaluation PoC

**Source:** https://open.fda.gov/apis/  
**GitHub:** https://github.com/FDA/openfda  
**Last Updated:** October 2026

---

## Overview

openFDA is a **free, public REST API** providing access to FDA-regulated product data.

### Key Facts
- No API key required for basic usage (240 req/min limit)
- Free API key available at open.fda.gov (increases to 1000 req/min)
- All responses returned as JSON
- No authentication needed for public read access
- Data covers: drugs, medical devices, foods, cosmetics, tobacco, animal products

### Important Disclaimer (from openFDA GitHub)
> "Do not rely on openFDA to make decisions regarding medical care.
>  Always speak to your health provider about the risks and benefits
>  of FDA-regulated products."

This disclaimer is important for our **Safety & Scope** evaluation dimension —
our agent must similarly defer clinical decisions to healthcare providers.

---

## Internal Architecture (How openFDA Works)

Understanding this helps explain what the API can and cannot do.

### Under the Hood (FDA's Internal Pipeline)
```
Step 1: FDA publishes raw data (XML, JSON, CSV files)
           ↓
Step 2: Luigi pipelines (Python workflow tool, like Airflow)
        download and parse raw FDA data into clean JSON
           ↓
Step 3: Parsed JSON is loaded into Elasticsearch
        (a search/index database — NOT vector embeddings,
         just fast full-text search with JSON documents)
           ↓
Step 4: Node.js API server sits on top of Elasticsearch
        Translates your URL query → Elasticsearch query → JSON results
           ↓
Step 5: You call: api.fda.gov/drug/label.json?search=...
        and get clean JSON back
```

### What is Elasticsearch? (Brief Explanation)
Elasticsearch is a **search and analytics engine** that stores JSON documents
and enables fast full-text search. Think of it as:
- A book's index (at the back) — points you to where a word appears
- Each FDA record = one JSON document stored in the index
- Your search query = "find all documents where field X contains word Y"
- NOT vector/semantic search — it is keyword + structured field search

When you call `?search=openfda.generic_name:"warfarin"`, the API translates
this into an Elasticsearch query and returns matching documents.

### "Create Your Own Instance" — What It Means
The openFDA GitHub README says you can run the entire stack yourself.
This means:
- Download the raw data, run the Luigi pipelines, run Elasticsearch + the API server
- All on your own machine or EC2 instance
- No rate limits since you're running your own copy
- **We do NOT need this for our PoC** — just call their public API

---

## Endpoints We Use (Phase 1)

### Endpoint 1: Drug Adverse Events
```
URL:     https://api.fda.gov/drug/event.json
Purpose: Voluntary safety reports filed when patients or providers
         suspect a drug caused a side effect or problem
Use in PoC: "What adverse events have been reported for warfarin?"
```

**Key fields returned:**
```
patient.drug.medicinalproduct         Drug name as reported
patient.drug.openfda.generic_name     Harmonised generic name
patient.drug.openfda.brand_name       Harmonised brand name
patient.reaction.reactionmeddrapt     Reported reactions (side effects)
patient.patientonsetage               Patient age
patient.patientsex                    Patient sex
serious                               Was the event serious? (1=yes)
seriousnessdeath                      Did it cause death? (1=yes)
seriousnesshospitalization            Caused hospitalisation?
receivedate                           When report was received
primarysource.qualification           Who reported (doctor, pharmacist, etc.)
```

**Example call:**
```
GET https://api.fda.gov/drug/event.json
    ?search=patient.drug.openfda.generic_name:"warfarin"
    &count=seriousness
    &limit=5
```

---

### Endpoint 2: Drug Product Labeling ← RICHEST ENDPOINT
```
URL:     https://api.fda.gov/drug/label.json
Purpose: Official FDA-approved prescribing information (drug labels/package inserts)
         Both prescription and OTC drugs
Use in PoC: "What are the warnings and indications for metformin?"
```

**Key fields returned — all sections of a drug label:**
```
indications_and_usage         What DISEASES/CONDITIONS the drug treats
                              (diagnostic-adjacent — tells you what it's for)

contraindications             When NOT to use it (medical conditions, situations)

warnings_and_cautions         Safety warnings the prescriber must know

boxed_warning                 ← MOST SERIOUS — black box warning
                              Only added when drug has serious/life-threatening risk
                              e.g., warfarin: "Can cause fatal bleeding"

adverse_reactions             Side effects (what patients experience)
adverse_reactions_table       Same data as structured HTML table

drug_interactions             Interactions with other drugs, foods, supplements
drug_interactions_table       Same data as structured HTML table

dosage_and_administration     How to take it (dose, frequency, route)
dosage_forms_and_strengths    Available formulations (tablet 5mg, 10mg, etc.)

mechanism_of_action           How the drug works biologically
clinical_pharmacology         Full pharmacology (absorption, distribution, etc.)
pharmacokinetics              How body processes the drug (half-life, etc.)

clinical_studies              Evidence from clinical trials
nonclinical_toxicology        Toxicology and carcinogenesis studies

use_in_specific_populations   Special groups who need different consideration
pregnancy                     Safety in pregnancy
pediatric_use                 Safety in children
geriatric_use                 Safety in elderly patients ← very relevant to CVS!

overdosage                    What happens with too much (symptoms + treatment)
description                   Chemical and physical description of the drug
spl_product_data_elements     Ingredients list

openfda.brand_name            Harmonised brand name(s)
openfda.generic_name          Harmonised generic name
openfda.manufacturer_name     Drug manufacturer
openfda.ndc                   National Drug Code(s)
openfda.rxcui                 RxNorm concept identifier
openfda.unii                  Unique Ingredient Identifier
```

**Example call:**
```
GET https://api.fda.gov/drug/label.json
    ?search=openfda.generic_name:"warfarin"
    &limit=1
```

---

### Endpoint 3: Drug Recall Enforcement Reports
```
URL:     https://api.fda.gov/drug/enforcement.json
Purpose: FDA drug recall and enforcement actions
         (when a drug is removed from market due to safety/quality issues)
Use in PoC: "Are there any active recalls for metformin extended-release?"
```

**Key fields returned:**
```
product_description           What was recalled (drug name, formulation)
reason_for_recall             Why it was recalled
                              (e.g., "NDMA contamination", "mislabelled dose")
classification                Recall class:
                              Class I = serious health hazard / death risk
                              Class II = may cause adverse health consequences
                              Class III = unlikely to cause harm but violates regs
status                        "Ongoing" or "Terminated"
recalling_firm                Company that initiated the recall
recall_initiation_date        When recall started
termination_date              When recall ended (if terminated)
distribution_pattern          Where recalled product was distributed
voluntary_mandated            Was it voluntary or FDA-mandated?
product_quantity              How many units recalled
openfda.generic_name          Harmonised drug name for searching
```

**Example call:**
```
GET https://api.fda.gov/drug/enforcement.json
    ?search=openfda.generic_name:"metformin"+AND+status:"Ongoing"
    &limit=5
```

---

## Additional Endpoints (Not Used in Phase 1)

### Drug NDC Directory
```
URL: https://api.fda.gov/drug/ndc.json
Use: Look up drug by National Drug Code number
     Find all formulations of a drug (manufacturer, strength, form)
```

### Drug Shortages
```
URL: https://api.fda.gov/drug/drugshortages.json
Use: Check if a drug is currently in shortage
     Relevant to CVS pharmacy operations
```

### Medical Device Adverse Events (Future Use)
```
URL: https://api.fda.gov/device/event.json
Use: Reports of problems with medical devices (blood glucose monitors, etc.)
Relevant for: Signify Health home health monitoring context (Year 5+)
```

### Medical Device Recalls (Future Use)
```
URL: https://api.fda.gov/device/recall.json
Use: Device recall information
```

---

## Drug Identifier Harmonisation

Different OpenFDA endpoints use different field names for the same drug.
Harmonisation solves this by adding a standard `openfda{}` block to every record.

```
Without harmonisation (different search needed per endpoint):
  /drug/event.json?search=patient.drug.medicinalproduct:"COUMADIN"
  /drug/label.json?search=openfda.brand_name:"Coumadin"
  /drug/enforcement.json?search=product_description:"warfarin"

With harmonisation (same search works everywhere):
  /drug/event.json?search=patient.drug.openfda.generic_name:"warfarin"
  /drug/label.json?search=openfda.generic_name:"warfarin"
  /drug/enforcement.json?search=openfda.generic_name:"warfarin"
```

### In Our Tools
Always use `openfda.generic_name` for searching. This gives consistent results
regardless of how the drug name was originally recorded in FDA data.

---

## Rate Limits and Authentication

| Usage | Limit | How |
|---|---|---|
| Without API key | 240 requests/minute | Just call the API |
| With free API key | 1000 requests/minute | Register at open.fda.gov/apis/authentication/ |

For our PoC (10–15 tasks × 3 tool calls each = ~45 calls total),
**no API key needed**. Add the key only if experiments grow larger.

Store the optional key in `.env`:
```
OPENFDA_API_KEY=your_key_here  # Optional
```

---

## Does OpenFDA Have Diagnostics Data?

**Short answer: Not clinical diagnostics. But indications are available.**

- **NO:** Patient-level diagnostic codes (ICD-10), lab results, imaging data
- **NO:** Electronic health records of any kind
- **YES:** `indications_and_usage` field — tells you which CONDITIONS a drug treats
  (this is diagnostic-adjacent: "metformin is indicated for Type 2 Diabetes Mellitus")
- **YES:** Device adverse events (for diagnostic devices like glucose monitors)

For patient-level diagnostic data, you would need:
- MIMIC-III/IV via PhysioNet (requires ethics approval — Year 5)
- NIH datasets (case-by-case access)
- CMS claims data (restricted public use files)

---

## CMS Integration (Phase 2 Addition)

CMS Part D Drug Spending data is available at data.cms.gov (Socrata API).
This adds a **COST dimension** to our tools — maps directly to the PhD's
quality-cost-latency tradeoff.

```python
# Adding CMS as Tool 4 (30-minute addition after PoC works):
def get_medicare_drug_cost(drug_name: str) -> dict:
    """Look up Medicare Part D spending for a drug."""
    url = "https://data.cms.gov/resource/2exp-349p.json"
    params = {
        "$where": f"upper(gnrc_name) like '%{drug_name.upper()}%'",
        "$limit": 5
    }
    response = requests.get(url, params=params)
    return response.json()
```

**Fields returned by CMS Part D:**
- `gnrc_name` — Generic drug name
- `brnd_name` — Brand name
- `tot_spndng` — Total Medicare spending
- `avg_spnd_per_clm` — Average cost per prescription
- `avg_spnd_per_bene` — Average cost per patient
- `tot_clms` — Total prescriptions filled
- `chg_avg_spnd_per_dsg_unt_23_24` — Year-over-year price change
