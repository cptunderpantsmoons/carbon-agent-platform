# LLM Temperature Parameter Guide

**Date:** April 20, 2026  
**Applies to:** DeepSeek, OpenAI, Featherless AI, and other LLM providers

---

## What is Temperature?

Temperature controls the **randomness** or **creativity** of LLM outputs:

- **Low temperature (0.0-0.3):** Deterministic, focused, reproducible
- **Medium temperature (0.7-1.0):** Balanced creativity and accuracy
- **High temperature (1.3-1.5):** Creative, diverse, unpredictable

**Default:** Most providers use `1.0` as the default temperature.

---

## DeepSeek Temperature Recommendations

DeepSeek provides specific temperature recommendations based on extensive testing:

| Use Case | Temperature | Output Characteristics |
|----------|-------------|------------------------|
| **Coding / Math** | `0.0` | Deterministic, precise, reproducible |
| **Data Cleaning / Analysis** | `1.0` | Balanced, accurate, methodical |
| **General Conversation** | `1.3` | Engaging, natural, varied |
| **Translation** | `1.3` | Fluent, contextually appropriate |
| **Creative Writing / Poetry** | `1.5` | Imaginative, diverse, expressive |

---

## Temperature Spectrum

### 0.0 - Maximum Determinism

**Best for:**
- Code generation
- Mathematical calculations
- Algorithm implementation
- Tasks requiring exact, reproducible results

**Behavior:**
- Always produces the same output for the same input
- Selects the most probable token at each step
- Minimal variation between runs

**Example:**
```python
response = await llm.chat_completion(
    messages=[{"role": "user", "content": "Write a binary search algorithm in Python"}],
    temperature=0.0
)
# Will produce identical code every time
```

---

### 0.3 - High Precision

**Best for:**
- Technical documentation
- Fact-based Q&A
- Data extraction
- Code review

**Behavior:**
- Very focused responses
- Slight variation for natural language flow
- Highly reliable for factual content

---

### 0.7 - Balanced

**Best for:**
- General purpose tasks
- Summarization
- Email writing
- Business communication

**Behavior:**
- Good balance of creativity and accuracy
- Natural language with occasional variety
- Safe default for most applications

---

### 1.0 - Default/Balanced Creative

**Best for:**
- Data analysis
- Exploratory tasks
- Brainstorming (structured)
- General conversation

**Behavior:**
- Provider's default setting
- Good variety without being too random
- Suitable for most use cases

---

### 1.3 - Enhanced Creativity

**Best for:**
- General conversation
- Language translation
- Story outlines
- Idea generation

**Behavior:**
- More diverse responses
- Natural, engaging tone
- Good for interactive applications

---

### 1.5 - Maximum Creativity

**Best for:**
- Creative writing
- Poetry
- Fiction
- Artistic content
- Brainstorming (unstructured)

**Behavior:**
- Highly varied outputs
- Can produce surprising or novel responses
- May occasionally be less coherent
- Best for tasks where creativity > accuracy

---

## Provider-Specific Notes

### DeepSeek

- **Default:** 1.0
- **Range:** 0.0 to 2.0 (recommended: 0.0-1.5)
- **Optimized for:** Coding and reasoning tasks
- **Special:** Excels at temperature=0.0 for coding

### OpenAI (GPT-4, GPT-3.5)

- **Default:** 1.0
- **Range:** 0.0 to 2.0
- **Recommended:** 0.7 for most tasks
- **Note:** Higher temperatures may produce less factual content

### Featherless AI (LLaMA, Mistral)

- **Default:** 0.7 (varies by model)
- **Range:** 0.0 to 1.5
- **Recommended:** 0.7-1.0 for open-source models
- **Note:** Open-source models may behave differently at high temperatures

### Anthropic (Claude)

- **Default:** 1.0
- **Range:** 0.0 to 1.0 (Claude has stricter limits)
- **Recommended:** 0.7 for balanced output
- **Note:** Claude is more sensitive to temperature changes

---

## Configuration Examples

### Environment Variables

```bash
# .env file

# Coding assistant
LLM_PROVIDER=deepseek
LLM_MODEL_NAME=deepseek-coder
LLM_TEMPERATURE=0.0

# Data analysis
LLM_PROVIDER=deepseek
LLM_MODEL_NAME=deepseek-chat
LLM_TEMPERATURE=1.0

# Chat application
LLM_PROVIDER=deepseek
LLM_MODEL_NAME=deepseek-chat
LLM_TEMPERATURE=1.3

# Creative writing tool
LLM_PROVIDER=deepseek
LLM_MODEL_NAME=deepseek-chat
LLM_TEMPERATURE=1.5
```

### Dynamic Temperature in Code

```python
from app.llm_provider import create_provider

llm = create_provider()

# Adjust temperature based on task type
async def respond_to_user(message: str, task_type: str):
    temperature_map = {
        "coding": 0.0,
        "math": 0.0,
        "data_analysis": 1.0,
        "translation": 1.3,
        "conversation": 1.3,
        "creative_writing": 1.5,
        "default": 1.0
    }
    
    temperature = temperature_map.get(task_type, 1.0)
    
    return await llm.chat_completion(
        messages=[{"role": "user", "content": message}],
        temperature=temperature
    )
```

---

## Performance Impact

### Response Quality vs Temperature

```
Accuracy │
         │  ■
         │    ■
         │      ■
         │        ■
         │          ■
         │            ■
         │              ■
         │                ■
         └───────────────────────▶
         0.0  0.5  1.0  1.5  2.0
                   Temperature

Creativity │
           │                    ■
           │                  ■
           │                ■
           │              ■
           │            ■
           │          ■
           │        ■
           │      ■
           └───────────────────────▶
           0.0  0.5  1.0  1.5  2.0
                     Temperature
```

**Trade-off:** As temperature increases, creativity increases but accuracy may decrease.

---

## Best Practices

### 1. Match Temperature to Task

✅ **Do:**
```python
# Code generation - precise
temperature=0.0

# Creative writing - varied
temperature=1.5
```

❌ **Don't:**
```python
# High temperature for code = unpredictable results
temperature=1.5  # Bad for coding!

# Low temperature for creativity = boring output
temperature=0.0  # Bad for creative writing!
```

### 2. Test Different Temperatures

```python
# A/B test temperatures for your use case
for temp in [0.0, 0.5, 1.0, 1.3, 1.5]:
    response = await llm.chat_completion(
        messages=[{"role": "user", "content": "Write a joke about AI"}],
        temperature=temp
    )
    print(f"Temp {temp}: {response[:50]}...")
```

### 3. Use System Prompts with Temperature

```python
# Combine temperature with system prompts for best results
messages = [
    {"role": "system", "content": "You are an expert Python developer"},
    {"role": "user", "content": "Implement merge sort"}
]

response = await llm.chat_completion(
    messages=messages,
    temperature=0.0  # Precise code
)
```

### 4. Monitor Output Quality

```python
# Log temperature and user feedback
logger.info(
    "chat_response",
    temperature=0.7,
    user_rating="helpful",
    task_type="coding"
)
```

---

## Common Mistakes

### 1. Using High Temperature for Code

```python
# ❌ BAD: Unpredictable code output
response = await llm.chat_completion(
    messages=[{"role": "user", "content": "Write a sorting function"}],
    temperature=1.5  # Too creative for code!
)
# May produce buggy or non-functional code
```

**Fix:** Use `temperature=0.0` for coding tasks.

### 2. Using Low Temperature for Creative Tasks

```python
# ❌ BAD: Boring, repetitive creative content
response = await llm.chat_completion(
    messages=[{"role": "user", "content": "Write a sci-fi story"}],
    temperature=0.0  # Too rigid for creativity!
)
# May produce generic, uninteresting content
```

**Fix:** Use `temperature=1.5` for creative writing.

### 3. Not Testing Temperature Impact

```python
# ❌ BAD: Using default without testing
response = await llm.chat_completion(
    messages=[{"role": "user", "content": "Analyze this data"}],
    # No temperature specified - uses default 1.0
)
# Default may not be optimal for your specific task
```

**Fix:** Test multiple temperatures and choose the best for your use case.

---

## Temperature vs Other Parameters

### Temperature vs Top-P

| Parameter | Controls | Recommended |
|-----------|----------|-------------|
| **Temperature** | Overall randomness | 0.0-1.5 |
| **Top-P** | Token selection diversity | 0.9-1.0 |

**Use together:**
```python
response = await llm.chat_completion(
    messages=[...],
    temperature=1.0,  # Control creativity
    top_p=0.95        # Limit to top 95% probable tokens
)
```

### Temperature vs Max Tokens

| Parameter | Controls | Impact |
|-----------|----------|--------|
| **Temperature** | Output randomness | Quality/variety |
| **Max Tokens** | Output length | Completeness |

**Use together:**
```python
response = await llm.chat_completion(
    messages=[...],
    temperature=0.7,     # Balanced creativity
    max_tokens=2048      # Allow long responses
)
```

---

## Quick Reference Card

### DeepSeek Temperature Settings

| Task | Temperature | Example |
|------|-------------|---------|
| 🔧 **Coding** | `0.0` | Algorithm, debugging, refactoring |
| 🧮 **Math** | `0.0` | Calculations, proofs, formulas |
| 📊 **Data Analysis** | `1.0` | Cleaning, visualization, insights |
| 💬 **Conversation** | `1.3` | Chat, Q&A, explanations |
| 🌐 **Translation** | `1.3` | Language translation |
| ✍️ **Creative Writing** | `1.5` | Poetry, stories, brainstorming |

### OpenAI Temperature Settings

| Task | Temperature | Notes |
|------|-------------|-------|
| Code | `0.0-0.2` | Precise, reproducible |
| Factual Q&A | `0.3-0.5` | Accurate, focused |
| General | `0.7-1.0` | Balanced |
| Creative | `1.0-1.3` | Varied output |

---

## Monitoring & Optimization

### Track Temperature Performance

```python
# Log temperature usage and outcomes
import structlog

logger = structlog.get_logger()

async def handle_request(message: str, task_type: str):
    temperature = get_temperature_for_task(task_type)
    
    response = await llm.chat_completion(
        messages=[{"role": "user", "content": message}],
        temperature=temperature
    )
    
    logger.info(
        "llm_request",
        task_type=task_type,
        temperature=temperature,
        response_length=len(response),
        user_satisfaction="pending"
    )
    
    return response
```

### A/B Testing Framework

```python
# Test which temperature works best for your users
async def ab_test_temperature(message: str):
    results = {}
    
    for temp in [0.7, 1.0, 1.3]:
        response = await llm.chat_completion(
            messages=[{"role": "user", "content": message}],
            temperature=temp
        )
        results[temp] = response
    
    # Collect user feedback to determine optimal temperature
    return results
```

---

## Summary

### Key Takeaways

1. **Temperature controls creativity vs accuracy trade-off**
2. **DeepSeek recommends specific temperatures per use case**
3. **Coding/Math = 0.0, Creative = 1.5**
4. **Test different temperatures for your specific application**
5. **Combine with system prompts for best results**

### Default Recommendations

```bash
# General purpose (safe default)
LLM_TEMPERATURE=1.0

# If unsure, start here and adjust based on output quality
```

---

## References

- **DeepSeek API Docs:** https://platform.deepseek.com/docs
- **OpenAI Temperature Guide:** https://platform.openai.com/docs/api-reference
- **Anthropic Parameter Guide:** https://docs.anthropic.com/claude/reference
- **Carbon Agent Platform:** `docs/DEEPSEEK_INTEGRATION.md`

---

**Last Updated:** April 20, 2026
