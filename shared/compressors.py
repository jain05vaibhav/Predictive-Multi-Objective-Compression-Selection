"""
Compressor Registry
"""

from typing import Dict, Any, Callable

COMPRESSOR_REGISTRY: Dict[str, Any] = {}

def get_compressor(name: str) -> Callable:
    pass

def get_decompressor(name: str) -> Callable:
    pass
