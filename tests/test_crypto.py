import base64
import json

import pytest

from shared.crypto import (
    SIGNED_PAYLOAD_MAGIC,
    aes_decrypt,
    aes_encrypt,
    create_signed_payload,
    decrypt_with_password,
    derive_key_from_password,
    ecdsa_sign,
    ecdsa_verify,
    encrypt_with_password,
    generate_aes_key,
    generate_ecdsa_keypair,
    generate_rsa_keypair,
    load_ecdsa_private,
    load_ecdsa_public,
    load_rsa_private,
    load_rsa_public,
    rsa_sign,
    rsa_verify,
    verify_signed_payload,
    load_rsa_private,
    rsa_sign,
)


def test_aes_roundtrip():
    key = generate_aes_key()
    plaintext = b"hello world"
    ciphertext = aes_encrypt(plaintext, key)
    assert ciphertext != plaintext
    assert aes_decrypt(ciphertext, key) == plaintext


def test_aes_encrypt_nonces_unique():
    key = generate_aes_key()
    first = aes_encrypt(b"data", key)
    second = aes_encrypt(b"data", key)
    assert first[:12] != second[:12]


def test_aes_decrypt_wrong_key_fails():
    from cryptography.exceptions import InvalidTag
    key = generate_aes_key()
    wrong = generate_aes_key()
    ciphertext = aes_encrypt(b"data", key)
    with pytest.raises(InvalidTag):
        aes_decrypt(ciphertext, wrong)


def test_derive_key_deterministic_with_salt():
    key1, _ = derive_key_from_password("pw", b"0123456789abcdef")
    key2, _ = derive_key_from_password("pw", b"0123456789abcdef")
    assert key1 == key2
    assert len(key1) == 32


def test_derive_key_different_passwords():
    key1, _ = derive_key_from_password("a", b"0123456789abcdef")
    key2, _ = derive_key_from_password("b", b"0123456789abcdef")
    assert key1 != key2


def test_encrypt_with_password_roundtrip():
    plaintext = b"sensitive data"
    payload = encrypt_with_password(plaintext, "secret")
    assert decrypt_with_password(payload, "secret") == plaintext
    assert plaintext not in payload


def test_decrypt_with_password_wrong_password_fails():
    from cryptography.exceptions import InvalidTag
    payload = encrypt_with_password(b"data", "correct")
    with pytest.raises(InvalidTag):
        decrypt_with_password(payload, "wrong")


def test_rsa_sign_verify_roundtrip():
    kp = generate_rsa_keypair()
    private = load_rsa_private(kp.private_pem)
    public = load_rsa_public(kp.public_pem)
    data = b"payload"
    sig = rsa_sign(data, private)
    assert rsa_verify(sig, data, public)
    assert not rsa_verify(sig, b"tampered", public)


def test_ecdsa_sign_verify_roundtrip():
    kp = generate_ecdsa_keypair()
    private = load_ecdsa_private(kp.private_pem)
    public = load_ecdsa_public(kp.public_pem)
    data = b"payload"
    sig = ecdsa_sign(data, private)
    assert ecdsa_verify(sig, data, public)
    assert not ecdsa_verify(sig, b"tampered", public)


def test_signed_payload_roundtrip_rsa():
    kp = generate_rsa_keypair()
    payload = create_signed_payload({"hello": "world"}, kp.private_pem, "RSA")
    decoded = verify_signed_payload(payload, kp.public_pem)
    assert decoded == {"hello": "world"}


def test_signed_payload_roundtrip_ecdsa():
    kp = generate_ecdsa_keypair()
    payload = create_signed_payload({"hello": "world"}, kp.private_pem, "ECDSA")
    decoded = verify_signed_payload(payload, kp.public_pem)
    assert decoded == {"hello": "world"}


def test_verify_signed_payload_tampered_returns_none():
    kp = generate_rsa_keypair()
    payload = create_signed_payload({"hello": "world"}, kp.private_pem, "RSA")
    decoded = verify_signed_payload(payload, kp.public_pem)
    assert decoded is not None
    signature_length = int.from_bytes(
        payload[len(SIGNED_PAYLOAD_MAGIC) + 2:len(SIGNED_PAYLOAD_MAGIC) + 6],
        "big",
    )
    body_offset = len(SIGNED_PAYLOAD_MAGIC) + 6 + signature_length
    body = json.loads(payload[body_offset:].decode("utf-8"))
    body["hello"] = "tampered"
    tampered = payload[:body_offset] + json.dumps(body).encode("utf-8")
    assert verify_signed_payload(tampered, kp.public_pem) is None


def test_verify_signed_payload_wrong_key_returns_none():
    kp1 = generate_rsa_keypair()
    kp2 = generate_rsa_keypair()
    payload = create_signed_payload({"hello": "world"}, kp1.private_pem, "RSA")
    assert verify_signed_payload(payload, kp2.public_pem) is None


def test_create_signed_payload_unknown_algorithm():
    kp = generate_rsa_keypair()
    with pytest.raises(ValueError, match="Unknown signature algorithm"):
        create_signed_payload({}, kp.private_pem, "UNKNOWN")


def test_verify_legacy_signed_payload_format():
    kp = generate_rsa_keypair()
    data = {"hello": "legacy"}
    json_bytes = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    private_key = load_rsa_private(kp.private_pem)
    signature = rsa_sign(json_bytes, private_key)
    wrapper = {
        "data": base64.b64encode(json_bytes).decode("ascii"),
        "signature": base64.b64encode(signature).decode("ascii"),
        "algorithm": "RSA",
    }
    payload = base64.b64encode(json.dumps(wrapper).encode("utf-8"))

    assert verify_signed_payload(payload, kp.public_pem) == data


def test_verify_rejects_unknown_payload_version():
    kp = generate_rsa_keypair()
    payload = create_signed_payload({"hello": "world"}, kp.private_pem, "RSA")
    tampered = payload[:6] + bytes((255,)) + payload[7:]
    assert verify_signed_payload(tampered, kp.public_pem) is None
