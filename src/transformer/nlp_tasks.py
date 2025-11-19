"""
NLP Task Functions

This module provides functions for various NLP tasks including
sentiment analysis and text summarization.
"""

from transformers import pipeline
from typing import Dict, List, Any


# Lazy load pipelines
_sentiment_pipeline = None
_summarization_pipeline = None


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
