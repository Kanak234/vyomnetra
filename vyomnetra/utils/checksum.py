"""Data hashing and integrity verification utilities."""

import hashlib
from typing import Union

def compute_sha256(data: Union[str, bytes]) -> str:
    """Computes SHA-256 hash of a string or byte payload.
    
    Args:
        data: String or bytes to hash.
        
    Returns:
        Hexadecimal SHA-256 string.
    """
    hasher = hashlib.sha256()
    if isinstance(data, str):
        hasher.update(data.encode("utf-8"))
    else:
        hasher.update(data)
    return hasher.hexdigest()

def verify_tle_checksum(line: str) -> bool:
    """Validates the standard TLE line checksum (modulo 10).
    
    Line 1 or Line 2 end with a 1-digit checksum calculated by:
    - Digits have their numeric value.
    - Minus signs (-) count as 1.
    - All other characters (spaces, letters, plus signs, periods) count as 0.
    - Sum modulo 10 must equal the final digit on the line.
    
    Args:
        line: Single line of TLE string.
        
    Returns:
        True if valid checksum, False otherwise.
    """
    clean_line = line.rstrip("\r\n")
    if len(clean_line) < 69:
        return False
        
    content, expected_checksum_str = clean_line[:68], clean_line[68]
    if not expected_checksum_str.isdigit():
        return False
        
    expected_checksum = int(expected_checksum_str)
    
    total = 0
    for char in content:
        if char.isdigit():
            total += int(char)
        elif char == "-":
            total += 1
            
    return (total % 10) == expected_checksum
