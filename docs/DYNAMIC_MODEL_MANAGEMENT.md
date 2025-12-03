# Dynamic Model Management Feature

## Overview

Transform the AI CLI's model configuration from static YAML-based to dynamic runtime management with Redis persistence. This allows users to add, remove, and switch between different LLM models on-the-fly without restarting the application.

## Current Architecture

### Model Types
1. **Tinyollama (Local)** - Lightweight fallback model
   - URL: `http://localhost:11434`
   - Model: `tinyllama`
   - Kept in config.yaml (static)
   - Has disabled features list

2. **General Model** - Main conversational model
   - Currently: `llama3.1:8b` at `http://192.168.31.23:11434`
   - Used for regular chat interactions
   - Stored in config.yaml (will become dynamic)

3. **Coder Model** - Specialized for code tasks
   - Currently: `qwen2.5-coder:7b` at same URL
   - Used for `/code` command and code editing
   - Stored in config.yaml (will become dynamic)

### Current Usage Points
- `src/config/manager.py`: `get_ollama_model()`, `get_coder_model()`
- `src/config/llm_availability.py`: Availability checking and fallback logic
- `main.py:1411`: Coder model used for file editing operations
- `main.py:1101`: Code mode disabled check for tinyollama
- `src/ui/routes/chat.py`: UI model retrieval
- `src/ui/routes/commands.py`: Code command execution

## Proposed Architecture

### 1. New Model Registry (Redis-backed)

Create `src/model_registry/manager.py`:

```python
@dataclass
class ModelConfig:
    """Configuration for a dynamically registered model."""
    model_id: str          # Unique identifier (auto-generated)
    model_type: str        # 'general' or 'coder'
    url: str               # Ollama service URL
    model_name: str        # Model name (e.g., 'llama3.1:8b')
    timeout: int           # Request timeout (default: 120)
    is_active: bool        # Whether this is the active model for its type
    added_at: datetime     # When the model was registered
    last_checked: datetime # Last availability check
    is_available: bool     # Current availability status

class ModelRegistry:
    """Manages dynamic model registration with Redis persistence."""

    def add_model(self, model_type: str, url: str, model_name: str,
                  timeout: int = 120, set_active: bool = True) -> ModelConfig
    def remove_model(self, model_id: str) -> bool
    def list_models(self, model_type: str = None) -> List[ModelConfig]
    def get_active_model(self, model_type: str) -> Optional[ModelConfig]
    def set_active_model(self, model_id: str) -> bool
    def update_availability(self, model_id: str, is_available: bool) -> bool
    def get_model(self, model_id: str) -> Optional[ModelConfig]
```

**Redis Storage Schema:**
- `models:{model_type}:active` - String: Active model ID for type
- `models:{model_id}` - Hash: Model configuration
- `models:index:{model_type}` - Set: Model IDs by type

### 2. New CLI Commands

```bash
# Add models
/model general add <url> <model_name> [--timeout SECONDS]
/model coder add <url> <model_name> [--timeout SECONDS]

# List models
/model general list
/model coder list
/model list  # Lists all models

# Switch active model
/model general use <model_id>
/model coder use <model_id>

# Remove models
/model general remove <model_id>
/model coder remove <model_id>

# Check availability
/model check [model_id]  # Check specific or all models
/model status  # Show current active models and availability
```

### 3. Graceful Degradation Strategy

Instead of exiting the CLI when models are unavailable, implement feature-level disabling:

**No General Model Available:**
- Disable chat prompt (show warning)
- Display: "⚠️  No general model available. Use '/model general add' to configure a model."
- Allow command execution: `/model`, `/session`, `/help`, etc.
- Still allow code execution if coder model is available

**No Coder Model Available:**
- Disable `/code` command
- Disable code-related MCP tools
- Fall back to general model for simple code editing
- Display warning when trying to use code features

**Only Tinyollama Available:**
- Continue current behavior with disabled_features list
- Show clear warnings about limitations

### 4. Modified Components

#### 4.1 ConfigManager Changes
`src/config/manager.py`:
- Keep tinyollama methods (static config)
- Remove `get_ollama_model()` and `get_coder_model()`
- Add `get_fallback_model()` for tinyollama
- Add `get_default_timeout()` for backward compatibility

#### 4.2 LLMAvailabilityChecker Refactor
`src/config/llm_availability.py`:
- Rename to `src/model_registry/availability.py`
- Integrate with ModelRegistry
- `get_available_llm()` checks ModelRegistry first, falls back to tinyollama
- Add `get_available_model(model_type: str)` for type-specific retrieval
- Maintain current fallback logic

#### 4.3 Main.py Updates
`main.py`:
- Initialize ModelRegistry alongside other managers
- Update chat loop to check model availability before prompting
- Modify `/code` command to check coder model availability
- Update edit operations (line 1411) to use ModelRegistry.get_active_model('coder')
- Add new `/model` command handlers
- Display model status in banner or on startup

#### 4.4 UI Route Updates
`src/ui/routes/chat.py`:
- Update model retrieval to use ModelRegistry
- Add endpoint: `GET /models` - List all models
- Add endpoint: `GET /models/<type>` - Get active model for type
- Update chat endpoint to handle missing model gracefully

`src/ui/routes/commands.py`:
- Add `/code` endpoint availability check
- Return proper error if coder model not available
- Add new model management endpoints:
  - `POST /models/<type>` - Add model
  - `DELETE /models/<model_id>` - Remove model
  - `PUT /models/<model_id>/activate` - Set active
  - `GET /models/status` - Get all models status

### 5. Database Migrations

**Redis Schema Setup:**
Create migration script `migrations/add_model_registry.py`:
- Initialize model registry keys
- Migrate existing config.yaml models to Redis (one-time)
- Set current models as active

### 6. Backward Compatibility

**Migration Path:**
1. On first startup with new code:
   - Check if models exist in Redis
   - If not, read from config.yaml and populate Redis
   - Mark migrated models as active
   - Keep config.yaml untouched (for rollback)

2. Environment variable override:
   - `AI_CLI_SKIP_MODEL_MIGRATION=true` - Don't auto-migrate
   - `AI_CLI_FORCE_CONFIG_YAML=true` - Ignore Redis, use config.yaml

### 7. User Experience Improvements

**Startup Behavior:**
```
AI CLI v1.0.0

✓ General Model: llama3.1:8b @ 192.168.31.23:11434 (reachable)
✓ Coder Model: qwen2.5-coder:7b @ 192.168.31.23:11434 (reachable)
ℹ Fallback: tinyllama @ localhost:11434 (reachable)

Type /help for available commands or start chatting!
```

**When models unavailable:**
```
AI CLI v1.0.0

⚠️  General Model: Not configured
✓ Coder Model: qwen2.5-coder:7b @ 192.168.31.23:11434 (reachable)
ℹ Fallback: tinyllama @ localhost:11434 (unreachable)

Limited mode: Use '/model general add' to enable chat features.
Code features available via '/code' command.

Type /help for available commands.
```

**Interactive model addition:**
```
> /model general add http://192.168.31.23:11434 llama3.1:8b

Checking availability... ✓
Model registered successfully!
  ID: model_abc123
  Type: general
  Model: llama3.1:8b
  URL: http://192.168.31.23:11434
  Status: Active

You can now start chatting!
```

### 8. Testing Strategy

**Unit Tests:**
- `tests/test_model_registry.py`: Model CRUD operations
- `tests/test_model_availability.py`: Availability checking with mocked Redis
- `tests/test_model_migration.py`: Config.yaml to Redis migration

**Integration Tests:**
- `tests/test_model_commands.py`: CLI command parsing and execution
- `tests/test_ui_model_routes.py`: UI endpoints with real Redis
- `tests/test_graceful_degradation.py`: Feature disabling when models unavailable

### 9. Implementation Order

1. **Phase 1: Core Infrastructure**
   - Create ModelRegistry class with Redis backend
   - Add model availability checking
   - Write unit tests

2. **Phase 2: CLI Integration**
   - Add `/model` commands to main.py
   - Update chat loop for graceful degradation
   - Modify code command to check coder model
   - Update edit operations

3. **Phase 3: Migration & Backward Compatibility**
   - Create migration script
   - Add auto-migration on startup
   - Test config.yaml fallback

4. **Phase 4: UI Integration**
   - Add UI endpoints for model management
   - Update existing endpoints to use ModelRegistry
   - Add UI components for model switching

5. **Phase 5: Polish & Documentation**
   - Update help text
   - Add user documentation
   - Create migration guide
   - Update CLAUDE.md

### 10. Files to Create

```
src/model_registry/
├── __init__.py
├── manager.py          # ModelRegistry class
└── availability.py     # Refactored LLMAvailabilityChecker

migrations/
└── add_model_registry.py

tests/
├── test_model_registry.py
├── test_model_availability.py
├── test_model_migration.py
├── test_model_commands.py
└── test_graceful_degradation.py

docs/
└── MODEL_MANAGEMENT.md  # User-facing documentation
```

### 11. Files to Modify

```
src/config/manager.py              # Remove dynamic model methods
src/config/llm_availability.py     # Move to model_registry/availability.py
main.py                            # Add /model commands, update model usage
src/ui/routes/chat.py              # Update model retrieval
src/ui/routes/commands.py          # Add model management endpoints
src/session/manager.py             # Possibly store active models in session
config.yaml                        # Keep only tinyollama config
CLAUDE.md                          # Update development docs
```

### 12. Breaking Changes

**None for end users** - Migration is automatic and backward compatible.

**For developers:**
- `ConfigManager.get_ollama_model()` → `ModelRegistry.get_active_model('general')`
- `ConfigManager.get_coder_model()` → `ModelRegistry.get_active_model('coder')`
- Direct config.yaml model access is deprecated

### 13. Future Enhancements

- **Model Templates**: Pre-configured model presets (e.g., "fast", "accurate", "coding")
- **Auto-discovery**: Detect available models from Ollama server
- **Load balancing**: Distribute requests across multiple models
- **Model metrics**: Track usage, response times, success rates
- **Model groups**: Group models by capability (vision, code, chat, etc.)
- **Per-session models**: Different models for different sessions

## Success Criteria

- ✅ Users can add/remove models without editing config.yaml
- ✅ CLI doesn't exit when models are unavailable
- ✅ Clear feedback about which features are available
- ✅ Backward compatible with existing config.yaml
- ✅ All tests pass
- ✅ UI can manage models dynamically
- ✅ Session persistence works with dynamic models
- ✅ Code command gracefully handles missing coder model
