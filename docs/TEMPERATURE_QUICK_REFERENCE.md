# LLM Temperature Quick Reference

**Print this page for easy reference!**

---

## 🎯 DeepSeek Temperature Settings

| Icon | Use Case | Temperature | Example |
|------|----------|-------------|---------|
| 🔧 | **Coding** | `0.0` | Algorithms, debugging, code generation |
| 🧮 | **Math** | `0.0` | Calculations, proofs, formulas |
| 📊 | **Data Analysis** | `1.0` | Data cleaning, analysis, reporting |
| 💬 | **General Chat** | `1.3` | Conversations, Q&A, explanations |
| 🌐 | **Translation** | `1.3` | Language translation |
| ✍️ | **Creative Writing** | `1.5` | Poetry, stories, brainstorming |

---

## ⚡ Quick Configuration

```bash
# Update your .env file

# For coding tasks
LLM_TEMPERATURE=0.0

# For data tasks
LLM_TEMPERATURE=1.0

# For chat applications (default)
LLM_TEMPERATURE=1.3

# For creative content
LLM_TEMPERATURE=1.5
```

---

## 📊 Temperature Spectrum

```
0.0 ──────────────────────────────────── 1.5
│                                         │
DETERMINISTIC                           CREATIVE
│                                         │
• Same output every time                • Different each time
• Focused, precise                      • Diverse, varied
• Best for code/math                    • Best for creative tasks
```

---

## 💡 Rule of Thumb

- **Need accuracy?** → Lower temperature (0.0-0.3)
- **Need creativity?** → Higher temperature (1.3-1.5)
- **Not sure?** → Start with 1.0 and adjust

---

## 🚨 Common Mistakes

| ❌ Wrong | ✅ Right | Why |
|----------|----------|-----|
| `temp=1.5` for code | `temp=0.0` | Code needs precision |
| `temp=0.0` for poetry | `temp=1.5` | Poetry needs creativity |
| Using default without testing | Test multiple temps | Optimize for your use case |

---

## 🔬 Testing Template

```python
# Test which temperature works best
for temp in [0.0, 0.7, 1.0, 1.3, 1.5]:
    response = await llm.chat_completion(
        messages=[{"role": "user", "content": "Your test prompt"}],
        temperature=temp
    )
    print(f"Temperature {temp}: {response[:100]}...")
```

---

## 📝 Provider Defaults

| Provider | Default | Range | Recommended |
|----------|---------|-------|-------------|
| DeepSeek | 1.0 | 0.0-2.0 | Per use case (see above) |
| OpenAI | 1.0 | 0.0-2.0 | 0.7 for general use |
| Featherless | 0.7 | 0.0-1.5 | 0.7-1.0 |
| Anthropic | 1.0 | 0.0-1.0 | 0.7 for balanced |

---

## 🎨 Visual Guide

```
Temperature:  0.0        0.5        1.0        1.5
              │          │          │          │
Accuracy:     ████████   ██████     ████       ██
Creativity:   ██         ████       ██████     ████████
Variety:      Low        Medium     High       Maximum
Use for:      Code       Facts      General    Creative
```

---

## 🔗 Full Documentation

- **Complete Guide:** `docs/LLM_TEMPERATURE_GUIDE.md`
- **DeepSeek Integration:** `docs/DEEPSEEK_INTEGRATION.md`
- **Quick Reference:** `docs/LLM_PROVIDER_QUICK_REFERENCE.md`

---

**Tip:** Bookmark this page and adjust temperature based on your current task!
