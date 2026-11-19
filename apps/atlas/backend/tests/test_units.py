"""Pure-helper unit tests: mention parsing, Arabic normalisation, security helpers."""

from __future__ import annotations

import pytest

from app.models import ALLOWED_TRANSITIONS, MEMBER_FORBIDDEN_TRANSITIONS, TicketStatus
from app.security import (
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.services.mentions import extract_mentions, strip_code_and_links
from app.services.queries import make_snippet, normalize_ar


def test_extract_mentions_dedupes_and_lowercases():
    assert extract_mentions("@omar and @Omar and @youssef") == ["omar", "youssef"]


def test_extract_mentions_needs_three_chars():
    assert extract_mentions("@ab @abc") == ["abc"]
    assert extract_mentions("ab@cd") == []


def test_extract_mentions_ignores_code_and_links():
    text = "`@omar` ```\n@omar\n``` [x @omar](https://e.dev) @youssef"
    assert extract_mentions(text) == ["youssef"]
    assert "@omar" not in strip_code_and_links("`@omar`")


def test_password_hashing_roundtrip():
    digest = hash_password("correct-horse")
    assert verify_password("correct-horse", digest)
    assert not verify_password("nope", digest)
    with pytest.raises(ValueError):
        hash_password("short")


def test_jwt_roundtrip_and_tamper():
    import jwt

    token = create_access_token("user-1", "member")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-1" and payload["role"] == "member"
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token + "x")


def test_api_key_shape_and_hash():
    plaintext, prefix, digest = generate_api_key()
    assert plaintext.startswith("atl_")
    assert prefix == plaintext[:12]
    assert digest == hash_api_key(plaintext)
    assert len(digest) == 64


def test_transition_matrix_is_complete_but_blocks_member_reopen():
    assert set(ALLOWED_TRANSITIONS) == set(TicketStatus)
    for status, targets in ALLOWED_TRANSITIONS.items():
        assert status not in targets
        assert len(targets) == len(TicketStatus) - 1
    assert MEMBER_FORBIDDEN_TRANSITIONS
    assert all(source == TicketStatus.done for source, _ in MEMBER_FORBIDDEN_TRANSITIONS)


def test_arabic_normalisation():
    assert normalize_ar("إصلاح") == normalize_ar("اصلاح")
    assert normalize_ar("مُراجعة") == normalize_ar("مراجعه")
    assert "rtl" in normalize_ar("RTL Board")


def test_snippet_highlights_term():
    snippet = make_snippet("the board has RTL flicker on mobile", "RTL", width=40)
    assert "<em>RTL</em>" in snippet


def test_snippet_without_match_truncates():
    snippet = make_snippet("x" * 300, "absent", width=40)
    assert snippet.endswith("…")
