# Embedding Similarity Metrics Tests

This directory contains tests for the embedding similarity metrics implementation.

## Overview

The `embedding_similarity.py` module implements three common distance/similarity metrics for comparing embeddings:

1. **Euclidean Distance** - Measures straight-line distance between vectors
2. **Dot Product** - Multiplies corresponding elements and sums them
3. **Cosine Similarity** - Measures the angle between vectors (most common for text)

## Running the Tests

Activate the virtual environment and run the test file:

```bash
source venv/bin/activate
python tests/test_embedding_similarity.py
```

## Test Cases

### Test 1: Basic Pairwise Similarity
Compares two pairs of embeddings (similar and dissimilar) using all three metrics.

### Test 2: Unified calculate_similarity() Function
Demonstrates using the `calculate_similarity()` function with different metrics via parameter.

### Test 3: Batch Similarity Search
Shows how to efficiently search through multiple document embeddings to find the most similar ones to a query.

### Test 4: Normalized vs Unnormalized Vectors
Demonstrates how normalization affects each metric, particularly showing that:
- Cosine similarity is unaffected by magnitude
- Dot product varies with magnitude
- For normalized vectors, cosine ≈ dot product

### Test 5: Real-World Semantic Search
Simulates a realistic scenario of searching for similar papers in a collection.

## Usage Examples

### Basic Comparison

```python
from transformer.embedding_similarity import calculate_similarity
import numpy as np

vec1 = np.array([0.8, 0.6, 0.1])
vec2 = np.array([0.7, 0.5, 0.2])

# Using different metrics
cosine_score = calculate_similarity(vec1, vec2, metric="cosine")
dot_score = calculate_similarity(vec1, vec2, metric="dot_product")
euclidean_dist = calculate_similarity(vec1, vec2, metric="euclidean")
```

### Batch Search

```python
from transformer.embedding_similarity import batch_similarity
import numpy as np

query = np.array([0.8, 0.6, 0.1])
documents = np.array([
    [0.7, 0.5, 0.2],
    [0.1, 0.2, 0.9],
    [0.75, 0.55, 0.15]
])

scores, indices = batch_similarity(query, documents, metric="cosine", top_k=2)
```

### Compare All Metrics

```python
from transformer.embedding_similarity import compare_metrics
import numpy as np

vec1 = np.array([0.8, 0.6, 0.1])
vec2 = np.array([0.7, 0.5, 0.2])

results = compare_metrics(vec1, vec2)
# Returns: {"cosine": 0.98, "dot_product": 0.88, "euclidean": 0.22}
```

## Choosing the Right Metric

| Metric | Best For | Advantages | Considerations |
|--------|----------|------------|----------------|
| **Euclidean Distance** | General ML tasks, when absolute position matters | Intuitive geometric interpretation | Lower = more similar (inverse). Sensitive to magnitude |
| **Dot Product** | Normalized embeddings, vector databases | Fastest computation | Only equivalent to cosine when normalized |
| **Cosine Similarity** | Text embeddings, semantic search | Standard for NLP. Normalized (0-1). Magnitude-independent | Slightly more expensive than dot product |

**Recommendation:** Use **cosine similarity** for text embeddings as it's the industry standard and produces interpretable scores.

## Reference

Based on the article: [Measuring Similarity and Distance between Embeddings](https://www.dataquest.io/blog/measuring-similarity-and-distance-between-embeddings/)
