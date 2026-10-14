# OpenAI Available Models Registry
## Fetched October 2026

---

## How to Refresh This List

```bash
python3 -c "
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
models = client.models.list()
chat_models = sorted([m.id for m in models.data if 'gpt' in m.id.lower()])
for m in chat_models: print(m)
"
```

---

## Recommended for Our PoC

| Role | Model ID | Reason |
|---|---|---|
| Task agent | `gpt-4o-mini` | Cheap, fast, capable tool-calling |
| Evaluator (judge) | `gpt-4o` | More capable for judging trajectories |

---

## Full List (fetched Oct 2026)

### Recommended (Chat / Tool-calling capable)
```
gpt-4o                  ← strong reasoning, tool calling
gpt-4o-mini             ← cheap + fast, good tool calling  ← USE THIS for task agent
gpt-4.1                 ← latest GPT-4 family
gpt-4.1-mini            ← cheaper GPT-4.1
gpt-4.1-nano            ← cheapest GPT-4.1
gpt-5                   ← most capable (expensive)
gpt-5-mini              ← GPT-5 but cheaper
```

### Older / Legacy
```
gpt-4
gpt-4-turbo
gpt-3.5-turbo
gpt-3.5-turbo-0125
```

### Specialised (not for our use)
```
gpt-audio-*             ← audio models
gpt-image-*             ← image generation
gpt-realtime-*          ← real-time streaming
gpt-transcribe          ← speech to text
```

---

## HuggingFace Models
_To be added when HuggingFace models are evaluated._
