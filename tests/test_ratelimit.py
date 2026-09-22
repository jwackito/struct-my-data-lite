import time

import pytest

from app import ratelimit


def test_token_bucket_allows_within_limit():
    bucket = ratelimit.TokenBucket(rate=3, per_seconds=60)
    assert all(bucket.allow("k") for _ in range(3))


def test_token_bucket_blocks_over_limit():
    bucket = ratelimit.TokenBucket(rate=2, per_seconds=60)
    assert bucket.allow("k")
    assert bucket.allow("k")
    assert not bucket.allow("k")


def test_token_bucket_keys_are_independent():
    bucket = ratelimit.TokenBucket(rate=1, per_seconds=60)
    assert bucket.allow("a")
    assert not bucket.allow("a")
    assert bucket.allow("b")


def test_token_bucket_refills_over_time(monkeypatch):
    bucket = ratelimit.TokenBucket(rate=1, per_seconds=60)
    assert bucket.allow("k")
    assert not bucket.allow("k")
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: 1_000_000.0)
    bucket._state["k"] = (0.0, 0.0)
    assert bucket.allow("k")


def test_retry_after_positive_when_blocked():
    bucket = ratelimit.TokenBucket(rate=1, per_seconds=60)
    bucket.allow("k")
    bucket.allow("k")
    assert bucket.retry_after("k") >= 1
