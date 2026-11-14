"""
Unit tests for unimonitor.core.security — encryption utilities.
"""

from __future__ import annotations

import os

import pytest


class TestEncryptDecrypt:
    def test_encrypt_returns_different_string(self):
        from unimonitor.core.security import encrypt_secret

        plaintext = "my-super-secret-value"
        encrypted = encrypt_secret(plaintext)
        assert encrypted != plaintext
        assert isinstance(encrypted, str)

    def test_decrypt_round_trip(self):
        from unimonitor.core.security import decrypt_secret, encrypt_secret

        plaintext = "another-secret-123"
        assert decrypt_secret(encrypt_secret(plaintext)) == plaintext

    def test_decrypt_empty_string(self):
        from unimonitor.core.security import decrypt_secret, encrypt_secret

        assert decrypt_secret(encrypt_secret("")) == ""

    def test_encrypt_unicode(self):
        from unimonitor.core.security import decrypt_secret, encrypt_secret

        plaintext = "sécret-ünïcödé"
        assert decrypt_secret(encrypt_secret(plaintext)) == plaintext


class TestGenerateApiKey:
    def test_default_key_non_empty(self):
        from unimonitor.core.security import generate_api_key

        key = generate_api_key()
        assert len(key) > 0

    def test_different_calls_produce_unique_keys(self):
        from unimonitor.core.security import generate_api_key

        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10, "API keys should be unique"

    def test_custom_length_produces_longer_key(self):
        from unimonitor.core.security import generate_api_key

        key_short = generate_api_key(length=8)
        key_long = generate_api_key(length=64)
        assert len(key_long) > len(key_short)

    def test_key_is_url_safe(self):
        from unimonitor.core.security import generate_api_key

        import re

        key = generate_api_key()
        # base64url: letters, digits, hyphens, underscores only
        assert re.match(r"^[A-Za-z0-9_-]+$", key), f"Key contains non-URL-safe chars: {key}"


class TestConstantTimeCompare:
    def test_equal_strings(self):
        from unimonitor.core.security import constant_time_compare

        assert constant_time_compare("hello", "hello") is True

    def test_unequal_strings(self):
        from unimonitor.core.security import constant_time_compare

        assert constant_time_compare("hello", "world") is False

    def test_empty_equal(self):
        from unimonitor.core.security import constant_time_compare

        assert constant_time_compare("", "") is True

    def test_empty_vs_nonempty(self):
        from unimonitor.core.security import constant_time_compare

        assert constant_time_compare("", "x") is False

    def test_case_sensitive(self):
        from unimonitor.core.security import constant_time_compare

        assert constant_time_compare("Hello", "hello") is False
