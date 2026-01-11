"""
Security utilities for safe file operations.
"""

import os
from pathlib import Path
from typing import Union


def assert_safe_path(base_path: Union[str, Path], target_path: Union[str, Path]) -> bool:
    """
    Ensure that the target path is within the base path to prevent directory traversal.
    
    Args:
        base_path: The allowed base directory
        target_path: The target path to validate
        
    Returns:
        bool: True if path is safe, raises ValueError otherwise
    """
    base_path = Path(base_path).resolve()
    target_path = Path(target_path).resolve()
    
    try:
        target_path.relative_to(base_path)
        return True
    except ValueError:
        raise ValueError(f"Path traversal detected: {target_path} is not within {base_path}")


def safe_open_text(base_path: Union[str, Path], file_path: Union[str, Path], encoding: str = "utf-8") -> str:
    """
    Safely open and read a text file, ensuring it's within the allowed base path.
    
    Args:
        base_path: The allowed base directory
        file_path: Path to the file to read
        encoding: Text encoding (default: utf-8)
        
    Returns:
        str: File content as string
    """
    assert_safe_path(base_path, file_path)
    
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read()