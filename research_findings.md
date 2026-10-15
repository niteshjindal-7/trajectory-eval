Layer 1 — Agent failure:
  Agent called 1 tool, hallucinated 2 data sources
  Looks correct to human reader

Layer 2 — Evaluator failure:
  LLM-as-judge also fooled by the convincing answer
  Gave 24/25 despite explicit evidence of only 1 tool call
  This is evaluator unreliability — exactly what RQ2 studies
