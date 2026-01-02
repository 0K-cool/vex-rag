"""
Reciprocal Rank Fusion (RRF) - Combine results from multiple search methods

RRF is a simple yet effective method to combine rankings from different
retrieval systems (vector + BM25). It outperforms simple score averaging
and handles score normalization automatically.

Formula: RRF_score(d) = Σ 1 / (k + rank_i(d))
Where k is a constant (typically 60) and rank_i is the rank in system i.

Reference:
- Cormack et al. (2009): "Reciprocal Rank Fusion outperforms Condorcet"
- Anthropic Contextual Retrieval: Uses RRF for hybrid search
"""

from typing import List, Dict
from collections import defaultdict


def reciprocal_rank_fusion(
    vector_results: List[Dict],
    bm25_results: List[Dict],
    k: int = 60,
    top_k: int = 10
) -> List[Dict]:
    """
    Combine vector and BM25 results using Reciprocal Rank Fusion

    Args:
        vector_results: Results from vector search (ranked by similarity)
        bm25_results: Results from BM25 search (ranked by keyword relevance)
        k: RRF constant (default: 60, standard value from literature)
        top_k: Number of top results to return

    Returns:
        Combined and re-ranked list of chunks with RRF scores
    """
    # Dictionary to accumulate RRF scores
    rrf_scores = defaultdict(float)
    chunk_map = {}  # Store full chunk data by chunk_id

    # Process vector results
    for rank, chunk in enumerate(vector_results, start=1):
        chunk_id = chunk.get('chunk_id')
        if chunk_id:
            rrf_scores[chunk_id] += 1.0 / (k + rank)
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk.copy()
                chunk_map[chunk_id]['vector_rank'] = rank
                chunk_map[chunk_id]['bm25_rank'] = None
            else:
                chunk_map[chunk_id]['vector_rank'] = rank

    # Process BM25 results
    for rank, chunk in enumerate(bm25_results, start=1):
        chunk_id = chunk.get('chunk_id')
        if chunk_id:
            rrf_scores[chunk_id] += 1.0 / (k + rank)
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = chunk.copy()
                chunk_map[chunk_id]['vector_rank'] = None
                chunk_map[chunk_id]['bm25_rank'] = rank
            else:
                chunk_map[chunk_id]['bm25_rank'] = rank

    # Sort by RRF score (higher is better)
    sorted_chunk_ids = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Build final result list
    fused_results = []
    for chunk_id, rrf_score in sorted_chunk_ids[:top_k]:
        chunk = chunk_map[chunk_id]
        chunk['rrf_score'] = rrf_score
        chunk['fusion_rank'] = len(fused_results) + 1
        fused_results.append(chunk)

    return fused_results


def get_fusion_stats(fused_results: List[Dict]) -> Dict:
    """
    Get statistics about the fusion results

    Args:
        fused_results: Results from RRF fusion

    Returns:
        Dictionary with fusion statistics
    """
    if not fused_results:
        return {
            'total_results': 0,
            'vector_only': 0,
            'bm25_only': 0,
            'both_methods': 0
        }

    vector_only = sum(1 for r in fused_results if r.get('vector_rank') and not r.get('bm25_rank'))
    bm25_only = sum(1 for r in fused_results if r.get('bm25_rank') and not r.get('vector_rank'))
    both = sum(1 for r in fused_results if r.get('vector_rank') and r.get('bm25_rank'))

    return {
        'total_results': len(fused_results),
        'vector_only': vector_only,
        'bm25_only': bm25_only,
        'both_methods': both,
        'fusion_algorithm': 'RRF (Reciprocal Rank Fusion)'
    }


def simple_score_fusion(
    vector_results: List[Dict],
    bm25_results: List[Dict],
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    top_k: int = 10
) -> List[Dict]:
    """
    Alternative: Combine results using weighted score fusion

    This is simpler but less effective than RRF. Requires score normalization.
    Provided as alternative for comparison.

    Args:
        vector_results: Results from vector search
        bm25_results: Results from BM25 search
        vector_weight: Weight for vector scores (default: 0.7)
        bm25_weight: Weight for BM25 scores (default: 0.3)
        top_k: Number of top results to return

    Returns:
        Combined and re-ranked list of chunks
    """
    combined_scores = defaultdict(float)
    chunk_map = {}

    # Process vector results (assume _distance field exists)
    if vector_results:
        max_distance = max(r.get('_distance', 0) for r in vector_results)
        for chunk in vector_results:
            chunk_id = chunk.get('chunk_id')
            if chunk_id:
                # Normalize distance to similarity (lower distance = higher similarity)
                distance = chunk.get('_distance', max_distance)
                normalized_score = 1.0 - (distance / max_distance if max_distance > 0 else 0)
                combined_scores[chunk_id] += vector_weight * normalized_score
                chunk_map[chunk_id] = chunk.copy()

    # Process BM25 results (assume _score field exists)
    if bm25_results:
        max_score = max(r.get('_score', 0) for r in bm25_results)
        for chunk in bm25_results:
            chunk_id = chunk.get('chunk_id')
            if chunk_id:
                score = chunk.get('_score', 0)
                normalized_score = score / max_score if max_score > 0 else 0
                combined_scores[chunk_id] += bm25_weight * normalized_score
                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = chunk.copy()

    # Sort by combined score
    sorted_chunks = sorted(
        combined_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Build final result list
    fused_results = []
    for chunk_id, score in sorted_chunks[:top_k]:
        chunk = chunk_map[chunk_id]
        chunk['combined_score'] = score
        chunk['fusion_rank'] = len(fused_results) + 1
        fused_results.append(chunk)

    return fused_results
