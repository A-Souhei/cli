"""
Integration tests for CodeBERT endpoints in the transformer service.

These tests require the transformer service to be running (port 16050).
"""

import pytest
import requests


def is_transformer_available():
    """Check if transformer service is available."""
    try:
        response = requests.get("http://localhost:16050/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


requires_transformer = pytest.mark.skipif(
    not is_transformer_available(),
    reason="Transformer service not available"
)

BASE_URL = "http://localhost:16050"


@pytest.mark.integration
@requires_transformer
class TestCodeEmbedEndpoint:
    """Test /code/embed endpoint for single code snippet embeddings."""

    def test_embed_python_code(self):
        """Test embedding a simple Python code snippet."""
        code = "def hello():\n    print('Hello, world!')"
        response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"code": code, "language": "python"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'embedding' in data
        assert isinstance(data['embedding'], list)
        assert data['dimension'] == 768  # CodeBERT dimension
        assert data['model'] == 'microsoft/codebert-base'
        assert all(isinstance(x, float) for x in data['embedding'])

    def test_embed_javascript_code(self):
        """Test embedding JavaScript code."""
        code = "function add(a, b) { return a + b; }"
        response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"code": code, "language": "javascript"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['dimension'] == 768

    def test_embed_code_without_language(self):
        """Test embedding code without specifying language."""
        code = "x = 5 + 3"
        response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"code": code}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['language'] == ''

    def test_embed_missing_code(self):
        """Test error handling when code is missing."""
        response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"language": "python"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'
        assert 'Missing code' in data['message']

    def test_embed_empty_code(self):
        """Test embedding empty code string."""
        response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"code": ""}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert len(data['embedding']) == 768

    def test_embed_long_code(self):
        """Test embedding code that exceeds max length (should truncate)."""
        # Create a long code snippet
        code = "\n".join([f"def function_{i}(): pass" for i in range(100)])
        response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"code": code, "language": "python"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['dimension'] == 768


@pytest.mark.integration
@requires_transformer
class TestCodeEmbedBatchEndpoint:
    """Test /code/embed/batch endpoint for batch code embeddings."""

    def test_embed_batch_multiple_snippets(self):
        """Test batch embedding of multiple code snippets."""
        codes = [
            "def add(a, b): return a + b",
            "def subtract(a, b): return a - b",
            "def multiply(a, b): return a * b"
        ]
        response = requests.post(
            f"{BASE_URL}/code/embed/batch",
            json={"codes": codes}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert len(data['embeddings']) == 3
        assert data['count'] == 3
        assert data['dimension'] == 768
        assert all(len(emb) == 768 for emb in data['embeddings'])

    def test_embed_batch_with_languages(self):
        """Test batch embedding with language specifications."""
        codes = [
            "def hello(): pass",
            "function hello() {}",
            "public void hello() {}"
        ]
        languages = ["python", "javascript", "java"]
        response = requests.post(
            f"{BASE_URL}/code/embed/batch",
            json={"codes": codes, "languages": languages}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['languages'] == languages
        assert len(data['embeddings']) == 3

    def test_embed_batch_single_snippet(self):
        """Test batch endpoint with single code snippet."""
        codes = ["x = 42"]
        response = requests.post(
            f"{BASE_URL}/code/embed/batch",
            json={"codes": codes}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert len(data['embeddings']) == 1

    def test_embed_batch_missing_codes(self):
        """Test error handling when codes array is missing."""
        response = requests.post(
            f"{BASE_URL}/code/embed/batch",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'
        assert 'Missing codes array' in data['message']

    def test_embed_batch_empty_array(self):
        """Test error handling with empty codes array."""
        response = requests.post(
            f"{BASE_URL}/code/embed/batch",
            json={"codes": []}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'
        assert 'non-empty array' in data['message']

    def test_embed_batch_not_array(self):
        """Test error handling when codes is not an array."""
        response = requests.post(
            f"{BASE_URL}/code/embed/batch",
            json={"codes": "not an array"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'

    def test_embed_batch_consistency(self):
        """Test that embeddings are consistent for same code."""
        codes = ["def test(): pass"] * 3
        response = requests.post(
            f"{BASE_URL}/code/embed/batch",
            json={"codes": codes}
        )
        
        assert response.status_code == 200
        data = response.json()
        embeddings = data['embeddings']
        
        # All embeddings should be identical for identical code
        assert embeddings[0] == embeddings[1]
        assert embeddings[1] == embeddings[2]


@pytest.mark.integration
@requires_transformer
class TestCodeSimilarityEndpoint:
    """Test /code/similarity endpoint for comparing code snippets."""

    def test_similarity_identical_code(self):
        """Test similarity of identical code snippets."""
        code = "def add(a, b): return a + b"
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={"code1": code, "code2": code}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['metric'] == 'cosine'
        # Identical code should have very high similarity (close to 1.0)
        assert data['similarity'] > 0.99

    def test_similarity_similar_functions(self):
        """Test similarity of similar but not identical functions."""
        code1 = "def add(x, y): return x + y"
        code2 = "def add(a, b): return a + b"
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={"code1": code1, "code2": code2}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        # Similar functions should have high similarity
        assert data['similarity'] > 0.8

    def test_similarity_different_languages(self):
        """Test similarity across different programming languages."""
        code1 = "def add(a, b): return a + b"
        code2 = "function add(a, b) { return a + b; }"
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={
                "code1": code1,
                "code2": code2,
                "language1": "python",
                "language2": "javascript"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        # Similar logic should still have some similarity
        assert data['similarity'] > 0.5

    def test_similarity_different_code(self):
        """Test similarity of completely different code."""
        code1 = "def sort_list(items): return sorted(items)"
        code2 = "def calculate_tax(amount): return amount * 0.15"
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={"code1": code1, "code2": code2}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        # Different code should have lower similarity
        assert data['similarity'] < 0.9

    def test_similarity_euclidean_metric(self):
        """Test similarity using Euclidean distance."""
        code1 = "x = 1"
        code2 = "y = 2"
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={
                "code1": code1,
                "code2": code2,
                "metric": "euclidean"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['metric'] == 'euclidean'
        assert isinstance(data['similarity'], (int, float))

    def test_similarity_dot_product_metric(self):
        """Test similarity using dot product."""
        code1 = "def test(): pass"
        code2 = "def test(): pass"
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={
                "code1": code1,
                "code2": code2,
                "metric": "dot_product"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['metric'] == 'dot_product'

    def test_similarity_invalid_metric(self):
        """Test error handling with invalid metric."""
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={
                "code1": "x = 1",
                "code2": "y = 2",
                "metric": "invalid_metric"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'
        assert 'Invalid metric' in data['message']

    def test_similarity_missing_code1(self):
        """Test error handling when code1 is missing."""
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={"code2": "test"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'

    def test_similarity_missing_code2(self):
        """Test error handling when code2 is missing."""
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={"code1": "test"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'

    def test_similarity_includes_interpretation(self):
        """Test that response includes human-readable interpretation."""
        code1 = "def test(): pass"
        code2 = "def test(): pass"
        response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={"code1": code1, "code2": code2}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'interpretation' in data
        assert isinstance(data['interpretation'], str)
        assert len(data['interpretation']) > 0


@pytest.mark.integration
@requires_transformer
class TestCodeBERTEndpointsIntegration:
    """Integration tests for CodeBERT endpoints working together."""

    def test_embed_and_similarity_consistency(self):
        """Test that manual similarity calculation matches endpoint."""
        code1 = "def add(a, b): return a + b"
        code2 = "def add(x, y): return x + y"
        
        # Get embeddings separately
        emb1_response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"code": code1}
        )
        emb2_response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"code": code2}
        )
        
        # Get similarity directly
        sim_response = requests.post(
            f"{BASE_URL}/code/similarity",
            json={"code1": code1, "code2": code2}
        )
        
        assert emb1_response.status_code == 200
        assert emb2_response.status_code == 200
        assert sim_response.status_code == 200
        
        # Calculate cosine similarity manually
        import numpy as np
        emb1 = np.array(emb1_response.json()['embedding'])
        emb2 = np.array(emb2_response.json()['embedding'])
        manual_similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        
        endpoint_similarity = sim_response.json()['similarity']
        
        # Should be approximately equal (within floating point error)
        assert abs(manual_similarity - endpoint_similarity) < 0.001

    def test_batch_vs_single_embed_consistency(self):
        """Test that batch and single embeddings produce same results."""
        code = "def test(): return 42"
        
        # Get single embedding
        single_response = requests.post(
            f"{BASE_URL}/code/embed",
            json={"code": code}
        )
        
        # Get batch embedding
        batch_response = requests.post(
            f"{BASE_URL}/code/embed/batch",
            json={"codes": [code]}
        )
        
        assert single_response.status_code == 200
        assert batch_response.status_code == 200
        
        single_emb = single_response.json()['embedding']
        batch_emb = batch_response.json()['embeddings'][0]
        
        # Should produce identical embeddings
        assert single_emb == batch_emb
