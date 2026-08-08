"""Tests for auth module."""

import pytest

from devps_agent.auth import hash_password, verify_password


class TestHashPassword:
    def test_hash_password_generates_salt(self) -> None:
        hash_hex, salt_hex = hash_password("mypassword")

        assert isinstance(hash_hex, str)
        assert isinstance(salt_hex, str)
        assert len(hash_hex) == 64  # SHA256 = 32 bytes = 64 hex chars
        assert len(salt_hex) == 32  # 16 bytes = 32 hex chars

    def test_hash_password_with_custom_salt(self) -> None:
        salt = bytes.fromhex("0123456789abcdef0123456789abcdef")
        hash_hex, salt_hex = hash_password("password", salt)

        assert salt_hex == "0123456789abcdef0123456789abcdef"
        assert isinstance(hash_hex, str)

    def test_same_password_same_salt_same_hash(self) -> None:
        salt = bytes.fromhex("0123456789abcdef0123456789abcdef")
        hash1, _ = hash_password("password", salt)
        hash2, _ = hash_password("password", salt)

        assert hash1 == hash2

    def test_same_password_different_salt_different_hash(self) -> None:
        hash1, salt1 = hash_password("password")
        hash2, salt2 = hash_password("password")

        assert hash1 != hash2  # Different salts = different hashes
        assert salt1 != salt2


class TestVerifyPassword:
    def test_verify_correct_password(self) -> None:
        password = "mypassword"
        hash_hex, salt_hex = hash_password(password)

        assert verify_password(password, salt_hex, hash_hex) is True

    def test_verify_incorrect_password(self) -> None:
        password = "correct_password"
        hash_hex, salt_hex = hash_password(password)

        assert verify_password("wrong_password", salt_hex, hash_hex) is False

    def test_verify_empty_password(self) -> None:
        password = ""
        hash_hex, salt_hex = hash_password(password)

        assert verify_password("", salt_hex, hash_hex) is True
        assert verify_password("nonempty", salt_hex, hash_hex) is False

    def test_verify_case_sensitive(self) -> None:
        password = "Password123"
        hash_hex, salt_hex = hash_password(password)

        assert verify_password(password, salt_hex, hash_hex) is True
        assert verify_password("password123", salt_hex, hash_hex) is False

    def test_verify_unicode_password(self) -> None:
        password = "contraseña_con_ñ_🔒"
        hash_hex, salt_hex = hash_password(password)

        assert verify_password(password, salt_hex, hash_hex) is True
        assert verify_password("contraseña_con_ñ", salt_hex, hash_hex) is False

    def test_timing_attack_resistance(self) -> None:
        password = "password"
        hash_hex, salt_hex = hash_password(password)

        # secrets.compare_digest should be used internally
        # Both should take roughly the same time (not testable easily, but verify it works)
        assert verify_password("password", salt_hex, hash_hex) is True
        assert verify_password("wrongwrongwrongwrongwrong", salt_hex, hash_hex) is False
