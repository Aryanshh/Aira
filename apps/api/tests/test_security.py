from datetime import timedelta
import pytest
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_elder_access_code,
    generate_elder_pin,
    hash_password,
    hash_pin,
    hash_token,
    verify_password,
    verify_pin,
)


def test_argon2id_password_hashing():
    password = "SuperSecurePassword123!"
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_argon2id_pin_hashing():
    pin = "4829"
    hashed = hash_pin(pin)

    assert hashed.startswith("$argon2id$")
    assert verify_pin(pin, hashed) is True
    assert verify_pin("1234", hashed) is False


def test_access_token_creation_and_decoding():
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    token = create_access_token(
        subject=user_id,
        claims={"role": "user", "email": "test@example.com"},
        expires_delta=timedelta(minutes=15),
    )

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "user"
    assert payload["email"] == "test@example.com"
    assert payload["type"] == "access"


def test_expired_access_token_fails():
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    token = create_access_token(
        subject=user_id,
        claims={"role": "user"},
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(ValueError, match="expired"):
        decode_access_token(token)


def test_elder_code_and_pin_format():
    code = generate_elder_access_code()
    assert code.startswith("AIRA-")
    assert len(code) == 9  # AIRA-XXXX
    # Must not contain ambiguous characters 0, O, 1, I
    for char in code.split("-")[1]:
        assert char not in "01OI"

    pin = generate_elder_pin()
    assert len(pin) == 4
    assert pin.isdigit()


def test_token_hash_deterministic():
    token = "random_test_token_string"
    h1 = hash_token(token)
    h2 = hash_token(token)
    assert h1 == h2
    assert len(h1) == 64
