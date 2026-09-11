"""Base62 encoding for monotonic counter ids."""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)
# First generated codes are 6 characters (62^5 → "100000" in this alphabet).
CODE_OFFSET = BASE**5


def base62_encode(n: int) -> str:
    if n < 0:
        raise ValueError("n must be >= 0")
    if n == 0:
        return ALPHABET[0]
    chars: list[str] = []
    while n:
        n, rem = divmod(n, BASE)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))


def base62_decode(code: str) -> int:
    n = 0
    for ch in code:
        idx = ALPHABET.find(ch)
        if idx < 0:
            raise ValueError(f"invalid base62 character: {ch!r}")
        n = n * BASE + idx
    return n


def code_from_counter(counter_id: int) -> str:
    return base62_encode(counter_id + CODE_OFFSET)
