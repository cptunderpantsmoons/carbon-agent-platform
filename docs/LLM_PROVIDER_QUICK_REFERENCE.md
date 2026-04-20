# LLM Provider Quick Reference

## Switch Providers (3 Steps)

### 1. Update `.env`

```bash
# Choose your provider
LLM_PROVIDER=featherless  # agent-zero | openai | featherless | anthropic
LLM_API_KEY=your-api-key-here
LLM_MODEL_NAME=model-name-here
```

### 2. Restart

```bash
docker compose restart adapter
```

### 3. Verify

```bash
curl http://localhost:8001/v1/models
```

---

## Provider Cheat Sheet

### Agent Zero (Default)
```bash
LLM_PROVIDER=agent-zero
LLM_BASE_URL=http://agent-zero:5000
LLM_API_KEY=
LLM_MODEL_NAME=carbon-agent
```
**Best for:** Self-hosted, full control, custom tools

---

### OpenAI
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-key
LLM_MODEL_NAME=gpt-4o
```
**Best for:** Production reliability, GPT-4 quality

---

### Featherless AI ⭐ NEW
```bash
LLM_PROVIDER=featherless
LLM_API_KEY=fl-your-featherless-key
LLM_MODEL_NAME=meta-llama-3.1-70b-instruct
```
**Best for:** Open-source models, 5-20x cost savings

**Popular Models:**
- `meta-llama-3.1-70b-instruct` - High quality
- `meta-llama-3.1-8b-instruct` - Fast & cheap
- `mistral-large-2` - Multilingual
- `qwen2.5-72b-instruct` - Code generation

---

### Anthropic Claude
```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-anthropic-key
LLM_MODEL_NAME=claude-3-sonnet-20240229
```
**Best for:** Claude-specific features, long context

---

### DeepSeek ⭐ NEW
```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your-deepseek-key
LLM_MODEL_NAME=deepseek-chat
```
**Best for:** Coding tasks, complex reasoning, 97% cost savings

**Available Models:**
- `deepseek-chat` - General purpose, reasoning
- `deepseek-coder` - Code generation, debugging
- `deepseek-reasoner` - Complex math, logic

---

## Code Migration (External Scripts)

### From OpenAI to Featherless

**Before:**
```python
from openai import OpenAI
client = OpenAI(api_key="sk-openai-key")
```

**After:**
```python
from openai import OpenAI
import os

client = OpenAI(
    base_url="https://api.featherless.ai/v1",
    api_key=os.environ['FEATHERLESS_API_KEY']
)
```

**Only 2 changes:**
1. Add `base_url` parameter
2. Use Featherless API key

---

## Cost Comparison

| Provider | Model | Cost/1M tokens | Savings |
|----------|-------|---------------|---------|
| OpenAI | gpt-4o | $10.00 (output) | Baseline |
| **DeepSeek** | **deepseek-chat** | **$0.28** | **97% cheaper** |
| Featherless | llama-3.1-70b | $0.75 | 92% cheaper |
| Featherless | llama-3.1-8b | $0.15 | 98% cheaper |
| Anthropic | claude-3-sonnet | $15.00 | 50% more expensive |

---

## DeepSeek Temperature Guide

DeepSeek's recommended temperature settings by use case:

| Use Case | Temperature | When to Use |
|----------|-------------|-------------|
| Coding / Math | `0.0` | Algorithm generation, debugging, calculations |
| Data Analysis | `1.0` | Data cleaning, analysis, reporting |
| General Chat | `1.3` | Conversations, Q&A, explanations |
| Translation | `1.3` | Language translation tasks |
| Creative Writing | `1.5` | Poetry, stories, brainstorming |

```bash
# Update .env for your use case
LLM_TEMPERATURE=0.0  # Coding
LLM_TEMPERATURE=1.0  # Data tasks
LLM_TEMPERATURE=1.3  # Chat (default)
LLM_TEMPERATURE=1.5  # Creative
```

---

## Troubleshooting

### "Authentication failed"
```bash
# Verify API key
echo $LLM_API_KEY

# Test directly
curl https://api.featherless.ai/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY"
```

### "Model not found"
```bash
# List available models
curl https://api.featherless.ai/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY"

# Update .env with valid model
```

### High latency
```bash
# Try smaller model
LLM_MODEL_NAME=meta-llama-3.1-8b-instruct
```

---

## Files Modified

| File | Lines | Purpose |
|------|-------|---------|
| `adapter/app/llm_provider.py` | 360 | Provider abstraction layer (5 providers) |
| `adapter/app/config.py` | +9 | LLM provider settings |
| `adapter/app/main.py` | +47 | Provider routing logic |
| `adapter/tests/test_llm_provider.py` | 504 | Unit tests (31 tests) |
| `.env.example` | +28 | Configuration templates |
| `docs/FEATHERLESS_AI_INTEGRATION.md` | 488 | Featherless documentation |
| `docs/DEEPSEEK_INTEGRATION.md` | 592 | DeepSeek documentation |
| `docs/LLM_PROVIDER_QUICK_REFERENCE.md` | 218 | Quick reference |
| `adapter/requirements.txt` | +1 | OpenAI SDK dependency |

**Total:** 2,247 lines added (code + docs + tests)

---

## API Endpoints

### Check Current Provider
```bash
curl http://localhost:8001/v1/models
```

Returns:
```json
{
  "object": "list",
  "data": [{
    "id": "meta-llama-3.1-70b-instruct",
    "object": "model",
    "owned_by": "featherless"
  }]
}
```

### Test Chat
```bash
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "meta-llama-3.1-70b-instruct",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## Next Steps

1. ✅ Integration complete (Featherless + DeepSeek)
2. ⏳ Get API keys for your chosen provider(s)
3. ⏳ Update `.env` configuration
4. ⏳ Test with your workflows
5. ⏳ Monitor costs and performance

---

## Supported Providers

| Provider | Best For | Cost | Setup |
|----------|----------|------|-------|
| Agent Zero | Self-hosted, full control | Server costs | Complex |
| OpenAI | Production reliability | $$$ | Simple |
| Featherless AI | Open-source models | $ | Simple |
| **DeepSeek** | **Coding, reasoning** | **$** | **Simple** |
| Anthropic | Claude features | $$$ | Simple |

**Full Documentation:** `docs/DEEPSEEK_INTEGRATION.md` | `docs/FEATHERLESS_AI_INTEGRATION.md`

**Full Documentation:** `docs/FEATHERLESS_AI_INTEGRATION.md`
