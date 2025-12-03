# Embedding Model Dynamization Plan

## Overview
Dynamize embedding models to support external embedding service URLs while maintaining local Docker transformer service as fallback, following the same pattern as general/coder model management.

## User Requirements
1. Support external embedding model URLs (generic endpoint)
2. Keep local Docker transformer service as fallback when no URL configured
3. Use `/model add` command pattern (stored in Redis, not config.yaml)
4. Auto-detect and store embedding dimensions from first API call
5. Create a new git branch for implementation

## Current State
- **Embedding Service**: Local Docker transformer on port 16050 (internal 5050)
- **Default Model**: all-MiniLM-L6-v2 (384 dimensions)
- **Consumers**: PostgreSQL API (MCP tools), Redis API (RAG), Ratings system
- **Storage**: Redis-backed ModelRegistry for general/coder models only

## Implementation Plan

### Phase 1: Extend ModelRegistry for Embedding Type

#### 1.1 Update ModelConfig Dataclass
**File**: `src/model_registry/manager.py`

Add optional field for embedding dimensions:
```python
@dataclass
class ModelConfig:
    # ... existing fields ...
    embedding_dimensions: Optional[int] = None  # For embedding models only
```

#### 1.2 Add Embedding Model Type Support
**File**: `src/model_registry/manager.py`

- Update `VALID_MODEL_TYPES` to include `'embedding'`
- Modify `add_model()` to handle embedding type (no model_name validation for embeddings)
- Update validation logic to allow embedding-specific fields

#### 1.3 Update Model Registry Methods
- `get_active_embedding_model()` - convenience method
- `set_embedding_dimensions()` - update dimensions after auto-detection
- Ensure all existing methods work with 'embedding' type

### Phase 2: Create EmbeddingClient Abstraction

#### 2.1 Create New EmbeddingClient Class
**File**: `src/embedding_client/client.py` (new file)

```python
class EmbeddingClient:
    def __init__(self, model_registry: ModelRegistry, fallback_url: str):
        """
        Args:
            model_registry: ModelRegistry instance
            fallback_url: Local transformer service URL (e.g., http://localhost:16050)
        """

    def embed(self, text: str) -> List[float]:
        """Generate embedding for single text"""

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""

    def get_similarity(self, text1: str, text2: str, metric: str = "cosine") -> float:
        """Calculate similarity between two texts"""

    def get_dimensions(self) -> int:
        """Get embedding dimensions (auto-detected)"""

    def _call_external_service(self, url: str, endpoint: str, params: dict) -> dict:
        """Call external embedding service"""

    def _call_local_service(self, endpoint: str, params: dict) -> dict:
        """Call local transformer service (fallback)"""

    def _auto_detect_dimensions(self, embedding: List[float]) -> int:
        """Auto-detect and store dimensions"""
```

#### 2.2 Fallback Logic
- Check if active embedding model exists via `model_registry.get_active_model('embedding')`
- If yes: use external URL
- If no: use local transformer service (fallback)
- If external service fails: log warning, fallback to local
- Auto-detect dimensions on first successful embedding call

#### 2.3 Generic Embedding Endpoint Protocol
Expected external API format:
```
POST /embed
{
    "text": "single text"  // OR
    "texts": ["text1", "text2"]
}

Response:
{
    "embedding": [0.1, 0.2, ...],  // for single text
    "embeddings": [[0.1, 0.2], [0.3, 0.4]],  // for batch
    "dimensions": 384  // optional
}
```

### Phase 3: Update Embedding Consumers

#### 3.1 PostgreSQL API
**File**: `src/postgresql/app/app.py`

- Replace direct transformer service calls with `EmbeddingClient`
- Initialize `EmbeddingClient` in app setup
- Update `/mcp-tools/store` and `/mcp-tools/match` endpoints
- Handle dimension changes (warn if switching models)

#### 3.2 Redis API
**File**: `src/redis/flask-app/app.py`

- Replace direct transformer service calls with `EmbeddingClient`
- Initialize `EmbeddingClient` in app setup
- Update `/context/store` and `/context/search` endpoints
- Validate dimension consistency

#### 3.3 Ratings System
**File**: `src/utils/ratings.py`

- Replace transformer service URL with `EmbeddingClient`
- Update `get_similar_prompts()` and `extract_keywords()` functions
- Pass `EmbeddingClient` instance from main.py

#### 3.4 Main CLI
**File**: `main.py`

- Initialize `EmbeddingClient` with `model_registry` and fallback URL
- Pass `embedding_client` to components that need it

### Phase 4: Add CLI Commands

#### 4.1 Update `/model` Command Handler
**File**: `main.py` (lines 458-681)

Add support for:
```
/model embedding add <url> [timeout]
/model embedding list
/model embedding use <model_id>
/model embedding remove <model_id>
/model embedding status
```

Note: No `<model_name>` parameter for embedding models (just URL)

#### 4.2 Validation for Embedding Models
- Check URL is reachable via simple GET/POST to /health or /embed
- Test embedding generation with sample text
- Auto-detect and display dimensions
- Store dimensions in ModelConfig

#### 4.3 Display Enhancements
- Show embedding dimensions in `/model status`
- Show embedding dimensions in `/model embedding list`
- Indicate if using fallback (local transformer)

### Phase 5: Update Web UI

#### 5.1 API Endpoints
**File**: `src/ui/routes/models.py`

Add embedding model support:
- Update `/models/add` to accept 'embedding' type
- Update validation (no model_name required for embedding)
- Update `/models/list` to include embedding models
- Add dimension display in response

#### 5.2 Frontend Updates (if needed)
**File**: `src/ui/templates/` (if applicable)

- Add embedding model section
- Display dimensions
- Show fallback status

### Phase 6: Testing

#### 6.1 Unit Tests
**File**: `tests/test_embedding_client.py` (new file)

Test cases:
- `test_embed_single_text()` - Single embedding
- `test_embed_batch()` - Batch embeddings
- `test_fallback_to_local()` - Fallback when no external model
- `test_auto_detect_dimensions()` - Dimension detection
- `test_external_service_failure()` - Graceful failure handling
- `test_dimension_mismatch_warning()` - Warn on dimension change

#### 6.2 Integration Tests
**File**: `tests/test_model_registry.py` (update)

Add:
- `test_add_embedding_model()` - Add embedding model
- `test_get_active_embedding_model()` - Retrieve active embedding
- `test_embedding_model_validation()` - URL validation
- `test_set_embedding_dimensions()` - Update dimensions

#### 6.3 Integration Tests for Consumers
**Files**: Update existing tests

- `tests/test_ollama_api_integration.py` - Test with external embedding
- Test PostgreSQL API with EmbeddingClient
- Test Redis API with EmbeddingClient
- Test ratings system with EmbeddingClient

### Phase 7: Documentation and Migration

#### 7.1 Update Documentation
**Files**:
- `CLAUDE.md` - Update architecture section
- `README.md` - Add embedding model documentation
- `docs/embedding-models.md` (new) - Detailed guide

#### 7.2 Docker Compose Updates (if needed)
**File**: `docker-compose.yml`

- Ensure transformer service remains as fallback
- Add environment variables for embedding config
- Document fallback behavior

#### 7.3 Environment Variables
**File**: `.env.example`

Add (optional):
```
# Embedding model fallback URL (default: http://localhost:16050)
EMBEDDING_FALLBACK_URL=http://localhost:16050
```

## Implementation Order

1. **Branch Creation**: `git checkout -b feature/dynamic-embedding-models`
2. **Phase 1**: Extend ModelRegistry (1-2 hours)
3. **Phase 2**: Create EmbeddingClient (2-3 hours)
4. **Phase 3**: Update consumers (2-3 hours)
5. **Phase 4**: Add CLI commands (1-2 hours)
6. **Phase 5**: Update Web UI (1-2 hours)
7. **Phase 6**: Testing (2-3 hours)
8. **Phase 7**: Documentation (1 hour)

Total estimated time: 10-16 hours

## Files to Modify

### New Files
- `src/embedding_client/client.py` - EmbeddingClient class
- `src/embedding_client/__init__.py` - Module exports
- `tests/test_embedding_client.py` - Unit tests
- `docs/embedding-models.md` - Documentation

### Modified Files
- `src/model_registry/manager.py` - Add embedding type support
- `src/postgresql/app/app.py` - Use EmbeddingClient
- `src/redis/flask-app/app.py` - Use EmbeddingClient
- `src/utils/ratings.py` - Use EmbeddingClient
- `main.py` - Add embedding commands, initialize EmbeddingClient
- `src/ui/routes/models.py` - Add embedding model API support
- `tests/test_model_registry.py` - Add embedding tests
- `CLAUDE.md` - Update documentation
- `.env.example` - Add embedding fallback URL

## Risk Assessment

### Potential Risks

1. **Dimension Mismatch**: Switching between models with different dimensions breaks existing embeddings
   - **Mitigation**: Warn users when dimension changes, suggest clearing stored embeddings

2. **External Service Downtime**: External embedding service unavailable
   - **Mitigation**: Graceful fallback to local transformer service

3. **API Incompatibility**: External service doesn't match expected format
   - **Mitigation**: Clear error messages, validation during `/model add`

4. **Performance**: External service slower than local
   - **Mitigation**: Add timeout configuration, allow user to switch back

5. **Breaking Changes**: Existing code expects transformer service
   - **Mitigation**: EmbeddingClient provides backward-compatible interface

### Edge Cases

1. **No Active Model + Transformer Service Down**: Return clear error, suggest starting transformer or adding external model
2. **Dimension Auto-detection Fails**: Use default 384, log warning
3. **Partial Batch Failure**: Handle individual embedding failures in batch operations
4. **Concurrent Dimension Updates**: Use Redis transactions for atomic updates
5. **Migration from Old to New**: No migration needed (fresh feature)

## Testing Strategy

### Unit Testing
- Mock Redis for ModelRegistry tests
- Mock HTTP requests for EmbeddingClient tests
- Test all fallback scenarios
- Test dimension auto-detection logic

### Integration Testing
- Test with real Redis instance
- Test with real transformer service
- Test with mock external embedding service
- Test all CLI commands end-to-end

### Manual Testing Checklist
- [ ] Add external embedding model via CLI
- [ ] Verify fallback to local transformer when no model configured
- [ ] Switch between embedding models
- [ ] Test dimension auto-detection
- [ ] Verify PostgreSQL API uses new client
- [ ] Verify Redis API uses new client
- [ ] Verify ratings system uses new client
- [ ] Test Web UI embedding model management
- [ ] Test graceful failure when external service down
- [ ] Verify dimension mismatch warnings

## Success Criteria

1. Users can add external embedding service URLs via `/model embedding add <url>`
2. System falls back to local transformer when no external model configured
3. Embedding dimensions auto-detected and stored
4. All existing embedding functionality works with EmbeddingClient
5. Graceful fallback when external service fails
6. Clear warnings when switching models with different dimensions
7. All tests pass
8. Documentation updated

## Notes

- No migration from config.yaml needed (new feature)
- Follow existing model registry patterns for consistency
- Keep backward compatibility with local transformer service
- Use generic embedding endpoint (not provider-specific)
- Store dimensions in ModelConfig for future validation
