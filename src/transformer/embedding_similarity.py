"""
Embedding Similarity and Distance Metrics

This module implements three common distance/similarity metrics for comparing embeddings:
1. Euclidean Distance: Measures straight-line distance between vectors
2. Dot Product: Multiplies corresponding elements and sums them
3. Cosine Similarity: Measures the angle between vectors

Based on: https://www.dataquest.io/blog/measuring-similarity-and-distance-between-embeddings/
"""

import numpy as np
from typing import Literal, Union, Optional
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances


DistanceMetric = Literal["euclidean", "dot_product", "cosine"]


def euclidean_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Calculate Euclidean distance between two vectors.
    
    Euclidean distance measures the straight-line distance between two points
    in high-dimensional space. Lower distance means higher similarity.
    
    Formula: √(Σ(A_i - B_i)²)
    
    Parameters:
    -----------
    vec1 : np.ndarray
        First vector to compare
    vec2 : np.ndarray
        Second vector to compare
    
    Returns:
    --------
    float
        Euclidean distance (lower means more similar)
    
    Notes:
    ------
    - Sensitive to vector magnitude
    - Lower scores indicate higher similarity (inverse relationship)
    - Common in general machine learning tasks
    """
    return float(np.linalg.norm(vec1 - vec2))


def dot_product_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Calculate dot product between two vectors.
    
    The dot product multiplies corresponding elements and sums them up.
    Higher scores mean higher similarity. Works best when embeddings
    are normalized to unit length.
    
    Formula: A·B = Σ(A_i × B_i)
    
    Parameters:
    -----------
    vec1 : np.ndarray
        First vector to compare
    vec2 : np.ndarray
        Second vector to compare
    
    Returns:
    --------
    float
        Dot product score (higher means more similar)
    
    Notes:
    ------
    - Fastest computation among the three metrics
    - Equivalent to cosine similarity when vectors are normalized
    - Many vector databases optimize for this metric
    """
    return np.dot(vec1, vec2)


def cosine_similarity_score(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Cosine similarity measures the angle between vectors. If two vectors
    point in the same direction, they're similar, regardless of their length.
    This is the most common metric for text embeddings.
    
    Formula: cos(θ) = (A·B) / (|A| × |B|)
    
    Parameters:
    -----------
    vec1 : np.ndarray
        First vector to compare
    vec2 : np.ndarray
        Second vector to compare
    
    Returns:
    --------
    float
        Cosine similarity score between -1 and 1
        - 1: vectors point in exactly the same direction (identical meaning)
        - 0: vectors are perpendicular (unrelated)
        - -1: vectors point in opposite directions (opposite meaning)
    
    Notes:
    ------
    - Most common metric for text embeddings
    - Normalized output (0 to 1 for text embeddings)
    - Not affected by vector magnitude, only direction
    """
    # Calculate dot product (numerator)
    dot_product = np.dot(vec1, vec2)
    
    # Calculate magnitudes (denominator)
    magnitude1 = np.linalg.norm(vec1)
    magnitude2 = np.linalg.norm(vec2)
    
    # Avoid division by zero
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    # Divide dot product by product of magnitudes
    similarity = dot_product / (magnitude1 * magnitude2)
    
    return similarity


def calculate_similarity(
    vec1: np.ndarray,
    vec2: np.ndarray,
    metric: DistanceMetric = "cosine"
) -> float:
    """
    Calculate similarity or distance between two vectors using the specified metric.
    
    Parameters:
    -----------
    vec1 : np.ndarray
        First vector to compare
    vec2 : np.ndarray
        Second vector to compare
    metric : DistanceMetric, default="cosine"
        The distance/similarity metric to use:
        - "euclidean": Euclidean distance (lower = more similar)
        - "dot_product": Dot product similarity (higher = more similar)
        - "cosine": Cosine similarity (higher = more similar)
    
    Returns:
    --------
    float
        Similarity or distance score depending on the metric
    
    Raises:
    -------
    ValueError
        If an unsupported metric is specified
    
    Examples:
    ---------
    >>> vec1 = np.array([0.8, 0.6, 0.1])
    >>> vec2 = np.array([0.7, 0.5, 0.2])
    >>> 
    >>> # Cosine similarity (default)
    >>> calculate_similarity(vec1, vec2)
    0.9876...
    >>> 
    >>> # Euclidean distance
    >>> calculate_similarity(vec1, vec2, metric="euclidean")
    0.1732...
    >>> 
    >>> # Dot product
    >>> calculate_similarity(vec1, vec2, metric="dot_product")
    0.8800...
    """
    if metric == "euclidean":
        return euclidean_distance(vec1, vec2)
    elif metric == "dot_product":
        return dot_product_similarity(vec1, vec2)
    elif metric == "cosine":
        return cosine_similarity_score(vec1, vec2)
    else:
        raise ValueError(
            f"Unknown metric: {metric}. "
            "Supported metrics: 'euclidean', 'dot_product', 'cosine'"
        )


def batch_similarity(
    query_embedding: np.ndarray,
    embeddings: np.ndarray,
    metric: DistanceMetric = "cosine",
    top_k: Optional[int] = None
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate similarity between one query embedding and multiple embeddings efficiently.
    
    This function is optimized for searching through large collections of embeddings
    by using vectorized operations instead of loops.
    
    Parameters:
    -----------
    query_embedding : np.ndarray
        Query vector (1D array)
    embeddings : np.ndarray
        Collection of embeddings (2D array where each row is an embedding)
    metric : DistanceMetric, default="cosine"
        The distance/similarity metric to use
    top_k : int, optional
        If specified, only return the top-k results
    
    Returns:
    --------
    scores : np.ndarray
        Similarity/distance scores for all embeddings
    indices : np.ndarray
        Indices sorted by score (best to worst)
    
    Examples:
    ---------
    >>> query = np.array([0.8, 0.6, 0.1])
    >>> docs = np.array([
    ...     [0.7, 0.5, 0.2],
    ...     [0.1, 0.2, 0.9],
    ...     [0.8, 0.6, 0.15]
    ... ])
    >>> scores, indices = batch_similarity(query, docs, metric="cosine", top_k=2)
    >>> print(f"Top 2 most similar: indices {indices}, scores {scores[indices]}")
    """
    # Reshape query to 2D for sklearn functions
    query_reshaped = query_embedding.reshape(1, -1)
    
    if metric == "cosine":
        # Calculate cosine similarity for all embeddings
        scores = cosine_similarity(query_reshaped, embeddings)[0]
        # Sort in descending order (higher = more similar)
        indices = np.argsort(scores)[::-1]
        
    elif metric == "dot_product":
        # Efficient dot product using matrix multiplication
        scores = np.dot(embeddings, query_embedding)
        # Sort in descending order (higher = more similar)
        indices = np.argsort(scores)[::-1]
        
    elif metric == "euclidean":
        # Calculate Euclidean distances for all embeddings
        scores = euclidean_distances(query_reshaped, embeddings)[0]
        # Sort in ascending order (lower = more similar)
        indices = np.argsort(scores)
        # Convert to similarity scores (inverse relationship)
        scores = 1 / (1 + scores)
        
    else:
        raise ValueError(
            f"Unknown metric: {metric}. "
            "Supported metrics: 'euclidean', 'dot_product', 'cosine'"
        )
    
    # Return only top-k if specified
    if top_k is not None:
        indices = indices[:top_k]
    
    return scores, indices


def compare_metrics(vec1: np.ndarray, vec2: np.ndarray) -> dict:
    """
    Compare all three metrics for the same pair of vectors.
    
    Useful for understanding how different metrics evaluate the same comparison.
    
    Parameters:
    -----------
    vec1 : np.ndarray
        First vector to compare
    vec2 : np.ndarray
        Second vector to compare
    
    Returns:
    --------
    dict
        Dictionary containing scores for all three metrics
    
    Examples:
    ---------
    >>> vec1 = np.array([0.8, 0.6, 0.1])
    >>> vec2 = np.array([0.7, 0.5, 0.2])
    >>> results = compare_metrics(vec1, vec2)
    >>> print(f"Cosine: {results['cosine']:.4f}")
    >>> print(f"Dot Product: {results['dot_product']:.4f}")
    >>> print(f"Euclidean: {results['euclidean']:.4f}")
    """
    return {
        "cosine": cosine_similarity_score(vec1, vec2),
        "dot_product": dot_product_similarity(vec1, vec2),
        "euclidean": euclidean_distance(vec1, vec2)
    }
