# Plan: Add Anthropic Models Support

## Overview
Add Anthropic Claude models as a model provider using an adapter/wrapper pattern that converts Anthropic API responses to Ollama-compatible format, keeping existing Ollama implementation untouched.

## File Changes

### New Files
| File | Purpose |
|------|---------|
| `secrets.example.yaml` | Template for API keys (tracked) |
| `secrets.yaml` | User's actual API keys (gitignored) |
| `src/config/secrets.py` | Secrets loading and validation |
| `src/llm_client/__init__.py` | Package init |
| `src/llm_client/factory.py` | Factory to create appropriate client |
| `src/anthropic_client/__init__.py` | Package init |
| `src/anthropic_client/client.py` | Anthropic adapter with format conversion |

### Modified Files
| File | Changes |
|------|---------|
| `.gitignore` | Add `secrets.yaml` |
| `src/model_registry/manager.py` | Add `provider` field to ModelConfig |
| `src/model_registry/availability.py` | Add Anthropic availability check |
| `src/cli/initialization.py` | Use factory pattern |
| `main.py` | Integrate factory for client creation/switching |
| `requirements.txt` | Add `anthropic>=0.40.0` |

---

## Implementation Steps

### Step 1: Secrets Management
1. Create `secrets.example.yaml`:
```yaml
# Copy to secrets.yaml and add your keys
anthropic:
  api_key: ""
```
2. Add `secrets.yaml` to `.gitignore`
3. Create `src/config/secrets.py` with `SecretsManager` class to load YAML

### Step 2: Anthropic Client Adapter
Create `src/anthropic_client/client.py`:

**Key conversions:**
- Extract system prompt from messages (Anthropic uses separate `system` param)
- Convert streaming events to yield content strings
- Convert response `{"content": [{"text": "..."}]}` to `{"message": {"content": "..."}}`

```python
class AnthropicClient:
    """Anthropic client matching OllamaClient interface."""

    def __init__(self, model: str, api_key: str = None, timeout: int = 120):
        self.model = model
        self.timeout = timeout
        self.client = Anthropic(api_key=api_key, timeout=timeout)

    def chat(self, messages, stream=True, temperature=0.7, ...):
        # 1. Extract system prompt from messages
        system_prompt, anthropic_messages = self._convert_messages(messages)

        # 2. Call Anthropic API
        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=anthropic_messages,
            stream=stream,
            temperature=temperature,
            max_tokens=num_predict or 4096
        )

        # 3. Convert response format
        if stream:
            return self._stream_response(response)
        return self._convert_response(response)
```

### Step 3: Update ModelRegistry
Add `provider` field to `ModelConfig`:
```python
@dataclass
class ModelConfig:
    # ... existing fields ...
    provider: str = "ollama"  # NEW: 'ollama' or 'anthropic'
```

Update `add_model()` to accept `provider` parameter.

### Step 4: Client Factory
Create `src/llm_client/factory.py`:
```python
class LLMClientFactory:
    @staticmethod
    def create_client(model_config, secrets_manager=None):
        if model_config.provider == 'anthropic':
            api_key = secrets_manager.get_anthropic_api_key()
            return AnthropicClient(model_config.model_name, api_key, ...)
        return OllamaClient(model_config.url, model_config.model_name, ...)
```

### Step 5: Update Availability Checker
Add `check_anthropic_available()` method that validates API key works.

### Step 6: CLI Integration
Update `/model` command with auto-detection:
- If first arg is `http://...` URL -> Ollama provider
- If first arg is `anthropic` -> Anthropic provider

Example usage:
```
/model general add anthropic claude-sonnet-4-20250514
/model coder add anthropic claude-sonnet-4-20250514
/model general add http://localhost:11434 llama3.1:8b
```

**Note:** OllamaClient stays as-is (no refactor to base class). Only AnthropicClient is new, designed to match OllamaClient's interface.

### Step 7: Main Loop Integration
- Use factory to create client based on active model's provider
- When switching models via `/model use`, recreate client with factory

---

## Message Format Conversion

**Ollama Input:**
```python
[
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Hello"}
]
```

**Anthropic Output:**
```python
system = "You are helpful"
messages = [{"role": "user", "content": "Hello"}]
```

**Anthropic Response:**
```python
{"content": [{"type": "text", "text": "Hi!"}], "role": "assistant"}
```

**Converted to Ollama Format:**
```python
{"message": {"role": "assistant", "content": "Hi!"}}
```

---

## Critical Files

- `src/ollama_client/client.py` - Reference interface to match
- `src/model_registry/manager.py` - Add provider field
- `src/cli/initialization.py` - Factory integration
- `main.py` - Client switching logic

---

## Dependencies
Add to `requirements.txt`:
```
anthropic>=0.40.0
```
