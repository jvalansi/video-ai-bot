# LLM Integration (Model-Agnostic)

The bot is designed so the LLM layer is swappable. Define a simple interface:

```python
class LLMProvider:
    def chat(self, messages: list[dict], stream: bool = False):
        raise NotImplementedError
```

Implementations:

```python
# OpenAI
from openai import OpenAI
class OpenAIProvider(LLMProvider):
    def __init__(self): self.client = OpenAI()
    def chat(self, messages, stream=False):
        return self.client.chat.completions.create(
            model="gpt-4o", messages=messages, stream=stream
        )

# Anthropic
import anthropic
class AnthropicProvider(LLMProvider):
    def __init__(self): self.client = anthropic.Anthropic()
    def chat(self, messages, stream=False):
        return self.client.messages.create(
            model="claude-opus-4-6", messages=messages, max_tokens=1024, stream=stream
        )

# Google
import google.generativeai as genai
class GeminiProvider(LLMProvider):
    def __init__(self): self.model = genai.GenerativeModel("gemini-1.5-pro")
    def chat(self, messages, stream=False):
        return self.model.generate_content(messages, stream=stream)
```

Set the provider via environment variable:

```bash
LLM_PROVIDER=openai   # or: anthropic, gemini
```
