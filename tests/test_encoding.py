from url_shortener.encoding import CODE_OFFSET, base62_decode, base62_encode, code_from_counter


def test_base62_zero():
    assert base62_encode(0) == "0"
    assert base62_decode("0") == 0


def test_base62_round_trip():
    for n in (1, 61, 62, 63, 123456, CODE_OFFSET, CODE_OFFSET + 99):
        assert base62_decode(base62_encode(n)) == n


def test_generated_codes_are_at_least_six_chars():
    assert len(code_from_counter(0)) == 6
    assert code_from_counter(0) == "100000"
    assert code_from_counter(1) == "100001"
    assert code_from_counter(0) != code_from_counter(1)
