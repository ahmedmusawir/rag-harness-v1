#!/usr/bin/env python3
"""
Utility: Calculate File Search costs
Helps estimate what you'll pay for embeddings
"""

def calculate_embedding_cost(file_size_bytes):
    """
    Calculate estimated embedding cost
    
    Args:
        file_size_bytes: Size of file in bytes
        
    Returns:
        dict with cost breakdown
    """
    # Rough estimates (Google uses text-embedding-005)
    # ~1 token = 4 characters for English text
    chars_per_token = 4
    estimated_tokens = file_size_bytes / chars_per_token
    
    # Embedding cost: $0.00015 per 1,000 tokens
    cost_per_1k_tokens = 0.00015
    embedding_cost = (estimated_tokens / 1000) * cost_per_1k_tokens
    
    return {
        'file_size_bytes': file_size_bytes,
        'estimated_tokens': int(estimated_tokens),
        'embedding_cost': round(embedding_cost, 6),
        'storage_cost': 0.0  # Always free!
    }

def print_cost_estimate(file_size_bytes):
    """Print a nice cost breakdown"""
    costs = calculate_embedding_cost(file_size_bytes)
    
    print("\n💰 Cost Estimate:")
    print(f"   File size: {costs['file_size_bytes']:,} bytes")
    print(f"   Est. tokens: {costs['estimated_tokens']:,}")
    print(f"   Embedding cost: ${costs['embedding_cost']:.6f}")
    print(f"   Storage cost: $0.00 (FREE!)")
    print(f"   Total: ${costs['embedding_cost']:.6f}")