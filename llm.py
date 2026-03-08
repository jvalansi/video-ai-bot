"""
Model-agnostic LLM provider interface.
Set LLM_PROVIDER env var to: openai | anthropic | gemini
"""
import os


class LLMProvider:
    def chat(self, messages: list[dict]) -> str:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

    def chat(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content


class AnthropicProvider(LLMProvider):
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

    def chat(self, messages: list[dict]) -> str:
        # Anthropic requires system message separate from messages array
        system = next(
            (m["content"] for m in messages if m["role"] == "system"), None
        )
        filtered = [m for m in messages if m["role"] != "system"]
        kwargs = {"model": self.model, "max_tokens": 1024, "messages": filtered}
        if system:
            kwargs["system"] = system
        response = self.client.messages.create(**kwargs)
        return response.content[0].text


class GeminiProvider(LLMProvider):
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel(
            os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        )

    def chat(self, messages: list[dict]) -> str:
        # Convert OpenAI-style messages to Gemini format
        parts = []
        for m in messages:
            role = "user" if m["role"] in ("user", "system") else "model"
            parts.append({"role": role, "parts": [m["content"]]})
        response = self.model.generate_content(parts)
        return response.text


_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_llm_provider() -> LLMProvider:
    name = os.getenv("LLM_PROVIDER", "openai").lower()
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Choose: {list(_PROVIDERS)}")
    return cls()
