"""
NLP Task Functions

This module provides functions for various NLP tasks including
sentiment analysis, text summarization, and keyword extraction.
"""

from transformers import pipeline
from typing import Dict, Any, List
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer


# Lazy load pipelines
_sentiment_pipeline = None
_summarization_pipeline = None
_keyword_model = None


def get_sentiment_pipeline():
    """Lazy load the sentiment analysis pipeline."""
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english"
        )
    return _sentiment_pipeline


def get_summarization_pipeline():
    """Lazy load the summarization pipeline."""
    global _summarization_pipeline
    if _summarization_pipeline is None:
        _summarization_pipeline = pipeline(
            "summarization",
            model="facebook/bart-large-cnn"
        )
    return _summarization_pipeline


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze the sentiment of the given text.

    Parameters:
    -----------
    text : str
        The text to analyze

    Returns:
    --------
    dict
        Dictionary containing:
        - label: The sentiment label (POSITIVE or NEGATIVE)
        - score: Confidence score (0-1)
    """
    sentiment_analyzer = get_sentiment_pipeline()
    result = sentiment_analyzer(text)[0]

    return {
        'label': result['label'],
        'score': float(result['score'])
    }


def summarize_text(text: str, max_length: int = 130, min_length: int = 30) -> Dict[str, Any]:
    """
    Summarize the given text.

    Parameters:
    -----------
    text : str
        The text to summarize
    max_length : int
        Maximum length of the summary (default: 130)
    min_length : int
        Minimum length of the summary (default: 30)

    Returns:
    --------
    dict
        Dictionary containing:
        - summary: The summarized text
        - original_length: Length of original text
        - summary_length: Length of summary
    """
    summarizer = get_summarization_pipeline()

    # Ensure text is long enough to summarize
    if len(text.split()) < min_length:
        return {
            'summary': text,
            'original_length': len(text),
            'summary_length': len(text),
            'note': 'Text too short to summarize, returned original'
        }

    result = summarizer(
        text,
        max_length=max_length,
        min_length=min_length,
        do_sample=False
    )[0]

    summary = result['summary_text']

    return {
        'summary': summary,
        'original_length': len(text),
        'summary_length': len(summary)
    }


def get_keyword_model():
    """Lazy load the keyword extraction model."""
    global _keyword_model
    if _keyword_model is None:
        # Use the same embedding model for consistency
        _keyword_model = KeyBERT(model='all-MiniLM-L6-v2')
    return _keyword_model


def extract_keywords(text: str, top_n: int = 5, keyphrase_ngram_range: tuple = (1, 2)) -> Dict[str, Any]:
    """
    Extract keywords and keyphrases from the given text.

    Parameters:
    -----------
    text : str
        The text to extract keywords from
    top_n : int
        Number of top keywords to extract (default: 5)
    keyphrase_ngram_range : tuple
        Range of n-grams to consider (default: (1, 2) for unigrams and bigrams)

    Returns:
    --------
    dict
        Dictionary containing:
        - keywords: List of extracted keywords with their scores
        - count: Number of keywords extracted
    """
    keyword_model = get_keyword_model()

    # Extract keywords
    keywords = keyword_model.extract_keywords(
        text,
        keyphrase_ngram_range=keyphrase_ngram_range,
        stop_words='english',
        top_n=top_n,
        use_maxsum=True,
        nr_candidates=20
    )

    # Format results
    keyword_list = [
        {'keyword': kw, 'score': float(score)}
        for kw, score in keywords
    ]

    return {
        'keywords': keyword_list,
        'count': len(keyword_list)
    }
