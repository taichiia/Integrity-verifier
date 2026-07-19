import os
import json
import base64
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding as asym_padding
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    encode_dss_signature,
    decode_dss_signature,
)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature


def generate_aes_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def aes_encrypt(plaintext: bytes, key: bytes) -> bytes:
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def aes_decrypt(payload: bytes, key: bytes) -> bytes:
    nonce, ciphertext = payload[:12], payload[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


@dataclass
class RSAKeyPair:
    private_pem: bytes
    public_pem: bytes


def generate_rsa_keypair(key_size: int = 2048) -> RSAKeyPair:
    private = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return RSAKeyPair(private_pem=private_pem, public_pem=public_pem)


def load_rsa_private(pem_data: bytes):
    return serialization.load_pem_private_key(pem_data, password=None)


def load_rsa_public(pem_data: bytes):
    return serialization.load_pem_public_key(pem_data)


def rsa_sign(data: bytes, private_key) -> bytes:
    return private_key.sign(data, asym_padding.PSS(
        mgf=asym_padding.MGF1(hashes.SHA256()),
        salt_length=asym_padding.PSS.MAX_LENGTH,
    ), hashes.SHA256())


def rsa_verify(signature: bytes, data: bytes, public_key) -> bool:
    try:
        public_key.verify(signature, data, asym_padding.PSS(
            mgf=asym_padding.MGF1(hashes.SHA256()),
            salt_length=asym_padding.PSS.MAX_LENGTH,
        ), hashes.SHA256())
        return True
    except InvalidSignature:
        return False


@dataclass
class ECDSAKeyPair:
    private_pem: bytes
    public_pem: bytes


def generate_ecdsa_keypair(curve: ec.EllipticCurve = None) -> ECDSAKeyPair:
    if curve is None:
        curve = ec.SECP256R1()
    private = ec.generate_private_key(curve)
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return ECDSAKeyPair(private_pem=private_pem, public_pem=public_pem)


def load_ecdsa_private(pem_data: bytes):
    return serialization.load_pem_private_key(pem_data, password=None)


def load_ecdsa_public(pem_data: bytes):
    return serialization.load_pem_public_key(pem_data)


def ecdsa_sign(data: bytes, private_key) -> bytes:
    chosen_hash = hashes.SHA256()
    digest = hashes.Hash(chosen_hash)
    digest.update(data)
    hash_bytes = digest.finalize()
    raw_sig = private_key.sign(hash_bytes, ec.ECDSA(Prehashed(chosen_hash)))
    return raw_sig


def ecdsa_verify(signature: bytes, data: bytes, public_key) -> bool:
    try:
        chosen_hash = hashes.SHA256()
        digest = hashes.Hash(chosen_hash)
        digest.update(data)
        hash_bytes = digest.finalize()
        public_key.verify(signature, hash_bytes, ec.ECDSA(Prehashed(chosen_hash)))
        return True
    except InvalidSignature:
        return False


def create_signed_payload(
    data: dict,
    private_key_pem: bytes,
    signature_algorithm: str = "RSA",
) -> bytes:
    json_bytes = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")

    if signature_algorithm == "RSA":
        private_key = load_rsa_private(private_key_pem)
        sig = rsa_sign(json_bytes, private_key)
    elif signature_algorithm == "ECDSA":
        private_key = load_ecdsa_private(private_key_pem)
        sig = ecdsa_sign(json_bytes, private_key)
    else:
        raise ValueError(f"Unknown signature algorithm: {signature_algorithm}")

    return base64.b64encode(json.dumps({
        "data": base64.b64encode(json_bytes).decode("ascii"),
        "signature": base64.b64encode(sig).decode("ascii"),
        "algorithm": signature_algorithm,
    }, ensure_ascii=False).encode("utf-8"))


def verify_signed_payload(
    payload: bytes,
    public_key_pem: bytes,
) -> dict | None:
    try:
        wrapper = json.loads(base64.b64decode(payload).decode("utf-8"))
        json_bytes = base64.b64decode(wrapper["data"])
        sig = base64.b64decode(wrapper["signature"])
        algorithm = wrapper["algorithm"]

        if algorithm == "RSA":
            public_key = load_rsa_public(public_key_pem)
            valid = rsa_verify(sig, json_bytes, public_key)
        elif algorithm == "ECDSA":
            public_key = load_ecdsa_public(public_key_pem)
            valid = ecdsa_verify(sig, json_bytes, public_key)
        else:
            return None

        if not valid:
            return None

        return json.loads(json_bytes.decode("utf-8"))
    except Exception:
        return None

