import json
import os
import time
import unicodedata

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford Base32: no I, L, O, U

def _encode(value: int, length: int) -> str:
    """
    Render an integer as `length` Crockford Base32 chars, most-significant first.

    Args:
        value: the non-negative integer to encode.
        length: how many base-32 chars to emit (zero-padded on the left).

    Returns:
        The Base32 string.
    """
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))

def ulid() -> str:
    """
    Generate a ULID: a 26-char, lexicographically sortable, unique ID.

    Layout: 48-bit millisecond timestamp (high bits) + 80-bit randomness (low bits).

    Returns:
        The 26-char Crockford Base32 ULID.
    """
    timestamp = int(time.time() * 1000)              # 48 bits: ms since the epoch
    randomness = int.from_bytes(os.urandom(10))      # 80 bits: 10 random bytes
    value = (timestamp << 80) | randomness
    return _encode(value, 26)

def canonical(op: dict) -> bytes:
    """
    Serialize an op to its canonical byte form for hashing.

    Deterministic across machines: NFC-normalized string values, sorted keys,
    no incidental whitespace, UTF-8, no trailing newline.

    Args:
        op: the op as a flat dict (str keys; str or int values).

    Returns:
        The canonical UTF-8 bytes.
    """
    normalized = {
        key: unicodedata.normalize("NFC", value) if isinstance(value, str) else value
        for key, value in op.items()
    }
    text = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode()
