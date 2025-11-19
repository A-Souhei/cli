"""
Test script for embedding similarity metrics

Run this script to see examples of all three distance/similarity metrics in action.
"""

from transformer.embedding_similarity import (
    calculate_similarity,
    compare_metrics,
    batch_similarity,
)
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_basic_similarity():
    """Test basic pairwise similarity calculations"""
    print("=" * 70)
    print("TEST 1: Basic Pairwise Similarity")
    print("=" * 70)

    # Create two sample embeddings
    embedding1 = np.array([0.8, 0.6, 0.1, 0.3, 0.5])
    embedding2 = np.array([0.7, 0.5, 0.2, 0.4, 0.6])
    embedding3 = np.array([0.1, 0.2, 0.9, 0.1, 0.05])

    print("\nComparing SIMILAR embeddings:")
    print(f"Embedding 1: {embedding1}")
    print(f"Embedding 2: {embedding2}")
    print("-" * 70)

    # Compare all metrics
    results = compare_metrics(embedding1, embedding2)
    print(f"Cosine Similarity:    {results['cosine']:.6f} (higher = more similar)")
    print(f"Dot Product:          {results['dot_product']:.6f} (higher = more similar)")
    print(f"Euclidean Distance:   {results['euclidean']:.6f} (lower = more similar)")

    print("\n" + "=" * 70)
    print("\nComparing DISSIMILAR embeddings:")
    print(f"Embedding 1: {embedding1}")
    print(f"Embedding 3: {embedding3}")
    print("-" * 70)

    results = compare_metrics(embedding1, embedding3)
    print(f"Cosine Similarity:    {results['cosine']:.6f} (higher = more similar)")
    print(f"Dot Product:          {results['dot_product']:.6f} (higher = more similar)")
    print(f"Euclidean Distance:   {results['euclidean']:.6f} (lower = more similar)")
    print()


def test_calculate_similarity_function():
    """Test the unified calculate_similarity function with different metrics"""
    print("=" * 70)
    print("TEST 2: Using calculate_similarity() with Different Metrics")
    print("=" * 70)

    vec1 = np.array([1.0, 0.5, 0.2])
    vec2 = np.array([0.9, 0.6, 0.3])

    print(f"\nVector 1: {vec1}")
    print(f"Vector 2: {vec2}")
    print("-" * 70)

    for metric in ["cosine", "dot_product", "euclidean"]:
        score = calculate_similarity(vec1, vec2, metric=metric)
        print(f"{metric.upper():15} = {score:.6f}")
    print()


def test_batch_similarity():
    """Test batch similarity search"""
    print("=" * 70)
    print("TEST 3: Batch Similarity Search")
    print("=" * 70)

    # Create a query embedding
    query = np.array([0.8, 0.6, 0.1, 0.3, 0.5])

    # Create a collection of document embeddings
    documents = np.array([
        [0.7, 0.5, 0.2, 0.4, 0.6],    # Similar to query
        [0.1, 0.2, 0.9, 0.1, 0.05],   # Very different
        [0.75, 0.55, 0.15, 0.35, 0.55],  # Very similar to query
        [0.5, 0.5, 0.5, 0.5, 0.5],    # Somewhat similar
        [0.2, 0.3, 0.8, 0.2, 0.1]     # Different
    ])

    print(f"\nQuery embedding: {query}")
    print(f"Searching through {len(documents)} document embeddings")
    print("-" * 70)

    # Test each metric
    for metric in ["cosine", "dot_product", "euclidean"]:
        scores, indices = batch_similarity(query, documents, metric=metric, top_k=3)
        print(f"\n{metric.upper()} - Top 3 results:")
        for rank, idx in enumerate(indices, 1):
            print(f"  {rank}. Document {idx}: score = {scores[idx]:.6f}")
            print(f"     Embedding: {documents[idx]}")
    print()


def test_normalized_vs_unnormalized():
    """Test how metrics behave with normalized vs unnormalized vectors"""
    print("=" * 70)
    print("TEST 4: Normalized vs Unnormalized Vectors")
    print("=" * 70)

    # Create a vector and its normalized version
    vec1 = np.array([3.0, 4.0, 0.0])
    vec1_normalized = vec1 / np.linalg.norm(vec1)

    vec2 = np.array([6.0, 8.0, 0.0])  # Same direction, different magnitude
    vec2_normalized = vec2 / np.linalg.norm(vec2)

    print("\nVectors pointing in SAME direction, different magnitudes:")
    print(f"Vec 1:            {vec1} (magnitude: {np.linalg.norm(vec1):.2f})")
    print(f"Vec 2:            {vec2} (magnitude: {np.linalg.norm(vec2):.2f})")
    print("-" * 70)

    print("\nUnnormalized vectors:")
    results = compare_metrics(vec1, vec2)
    print(f"  Cosine Similarity:  {results['cosine']:.6f}")
    print(f"  Dot Product:        {results['dot_product']:.6f}")
    print(f"  Euclidean Distance: {results['euclidean']:.6f}")

    print("\nNormalized vectors:")
    results_norm = compare_metrics(vec1_normalized, vec2_normalized)
    print(f"  Cosine Similarity:  {results_norm['cosine']:.6f}")
    print(f"  Dot Product:        {results_norm['dot_product']:.6f}")
    print(f"  Euclidean Distance: {results_norm['euclidean']:.6f}")

    print("\nObservation:")
    print("  - Cosine similarity is IDENTICAL (measures angle, not magnitude)")
    print("  - Dot product is DIFFERENT (affected by magnitude)")
    print("  - For normalized vectors, cosine ≈ dot product")
    print()


def test_real_world_example():
    """Simulate a real-world semantic search scenario"""
    print("=" * 70)
    print("TEST 5: Real-World Semantic Search Example")
    print("=" * 70)

    # Simulate embeddings for different topics
    # In reality, these would come from an embedding model
    np.random.seed(42)

    # Create topic clusters
    ml_topic = np.random.randn(128) + np.array([1] * 128)
    cv_topic = np.random.randn(128) + np.array([0] * 64 + [2] * 64)
    nlp_topic = np.random.randn(128) + np.array([2] * 64 + [0] * 64)

    # Query about machine learning
    query = ml_topic + np.random.randn(128) * 0.1

    # Collection of papers
    papers = np.array([
        ml_topic + np.random.randn(128) * 0.1,  # ML paper
        cv_topic + np.random.randn(128) * 0.1,  # CV paper
        nlp_topic + np.random.randn(128) * 0.1,  # NLP paper
        ml_topic + np.random.randn(128) * 0.1,  # Another ML paper
        cv_topic + np.random.randn(128) * 0.1,  # Another CV paper
    ])

    paper_topics = [
        "Machine Learning",
        "Computer Vision",
        "NLP",
        "Machine Learning",
        "Computer Vision"]

    print("\nQuery: Machine Learning paper")
    print(f"Searching through {len(papers)} papers")
    print("-" * 70)

    # Use cosine similarity (most common for text)
    scores, indices = batch_similarity(query, papers, metric="cosine", top_k=5)

    print("\nRanked results (Cosine Similarity):")
    for rank, idx in enumerate(indices, 1):
        print(f"  {rank}. {paper_topics[idx]:20} - Score: {scores[idx]:.4f}")
    print()


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "EMBEDDING SIMILARITY METRICS TESTS" + " " * 19 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    test_basic_similarity()
    test_calculate_similarity_function()
    test_batch_similarity()
    test_normalized_vs_unnormalized()
    test_real_world_example()

    print("=" * 70)
    print("ALL TESTS COMPLETED!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
