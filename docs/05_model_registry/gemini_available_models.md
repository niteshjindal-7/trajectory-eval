# Available Models Registry
## Fetched October 2026 — Update periodically

---

## ⚠️ Important Warnings Observed

1. **`google.generativeai` is deprecated** — switch to `google.genai` package
   - See: https://github.com/google-gemini/deprecated-generative-ai-python
   - Action: update `pyproject.toml` when we integrate Gemini directly

2. **Python 3.10 EOL warning** — google.api_core will drop support
   - Action: upgrade virtual environment to Python 3.11+ when convenient

---

## How to Refresh This List

```bash
# Install (one-time)
pip install google-generativeai

# Fetch current models
python3 -c "
import google.generativeai as genai
genai.configure(api_key='YOUR_KEY')
for m in genai.list_models():
    print(m.name)
"
```

---

## Google Gemini Models (fetched Oct 2026)

### Recommended for Our PoC

| Role | Model ID | Reason |
|---|---|---|
| Task agent | `gemini-2.5-flash` | Cheap, fast, capable |
| Evaluator (judge) | `gemini-2.5-pro` | More capable for judging |

### Full List (as of Oct 2026)

```
# Stable / Production
models/gemini-2.5-flash
models/gemini-2.5-pro
models/gemini-2.5-flash-lite
models/gemini-3.5-flash
models/gemini-3.5-flash-lite
models/gemini-3.6-flash
models/gemini-3.7-flash
models/gemini-3.8-flash

# Preview / Experimental
models/gemini-3-flash-preview
models/gemini-3.1-pro-preview
models/gemini-3.1-flash-lite
models/gemini-3.1-flash-lite-preview
models/gemini-3.1-flash-image
models/gemini-flash-latest
models/gemini-flash-lite-latest
models/gemini-pro-latest

# Image models
models/gemini-2.5-flash-image
models/gemini-3-pro-image
models/gemini-3.1-flash-image

# TTS (Text-to-Speech)
models/gemini-2.5-flash-preview-tts
models/gemini-2.5-pro-preview-tts
models/gemini-3.1-flash-tts-preview
models/gemini-3.8-flash-tts
models/gemini-3.8-flash-lite-tts

# Audio / Live
models/gemini-2.5-flash-native-audio-latest
models/gemini-3.8-live
models/gemini-3.8-live-extended-thinking
models/gemini-omni-flash-preview
models/gemini-omni-1.1-flash

# Embedding
models/gemini-embedding-001
models/gemini-embedding-2
models/gemini-embedding-2-preview

# Gemma (open weights)
models/gemma-4-26b-a4b-it
models/gemma-4-31b-it

# Research / Specialised
models/deep-research-max-preview-04-2026
models/deep-research-preview-04-2026
models/gemini-2.5-computer-use-preview-10-2025
models/gemini-robotics-er-2-preview
models/gemini-3.5-transcribe
models/antigravity-preview-latest

# Video generation
models/veo-3.1-generate-preview
models/veo-3.1-fast-generate-preview

# Music
models/lyria-3.5
models/lyria-3-pro-preview

# QA
models/aqa
```

---

## HuggingFace Models (add here when explored)

_To be populated when HuggingFace models are evaluated._

```
# Example format:
# Model ID | Size | Task | Notes
# meta-llama/Llama-3.1-8B-Instruct | 8B | Task agent | Free, needs HF token
```

---

## Notes on Model Selection for Research

- For **trajectory evaluation**, the evaluator model should ideally be
  **different and more capable** than the task agent (Option A in proposal)
- Start with `gemini-2.5-flash` (task) + `gemini-2.5-pro` (evaluator)
- When extending to open-source models (Year 2), Ollama on EC2 handles
  Llama/Gemma models — already proven in project_m6_ollama_server_deployment
