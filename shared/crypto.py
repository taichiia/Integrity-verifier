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


SIGNED_PAYLOAD_MAGIC = b"FITSP1"
SIGNED_PAYLOAD_VERSION = 1
_ALGORITHM_IDS = {b"RSA": 1, b"ECDSA": 2}
_ALGORITHM_NAMES = {value: key.decode("ascii") for key, value in _ALGORITHM_IDS.items()}


def generate_aes_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def derive_key_from_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    key = kdf.derive(password.encode("utf-8"))
    return key, salt


def encrypt_with_password(plaintext: bytes, password: str) -> bytes:
    key, salt = derive_key_from_password(password)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return salt + nonce + ciphertext


def decrypt_with_password(payload: bytes, password: str) -> bytes:
    salt, nonce, ciphertext = payload[:16], payload[16:28], payload[28:]
    key, _ = derive_key_from_password(password, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


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

    algorithm = signature_algorithm.encode("ascii")
    if algorithm not in _ALGORITHM_IDS:
        raise ValueError(f"Unknown signature algorithm: {signature_algorithm}")

    try:
        if signature_algorithm == "RSA":
            private_key = load_rsa_private(private_key_pem)
        else:
            private_key = load_ecdsa_private(private_key_pem)
    except Exception as exc:
        raise ValueError(f"Unable to load private key: {exc}") from exc

    algorithm_id = _ALGORITHM_IDS[algorithm]
    # Sign the algorithm with the data so an envelope cannot be re-labelled
    # as a different signature scheme after the fact.
    signed_bytes = bytes((SIGNED_PAYLOAD_VERSION, algorithm_id)) + json_bytes
    if signature_algorithm == "RSA":
        sig = rsa_sign(signed_bytes, private_key)
    else:
        sig = ecdsa_sign(signed_bytes, private_key)

    return (
        SIGNED_PAYLOAD_MAGIC
        + bytes((SIGNED_PAYLOAD_VERSION, algorithm_id))
        + len(sig).to_bytes(4, "big")
        + sig
        + json_bytes
    )


def verify_signed_payload(
    payload: bytes,
    public_key_pem: bytes,
) -> dict | None:
    try:
        if payload.startswith(SIGNED_PAYLOAD_MAGIC):
            offset = len(SIGNED_PAYLOAD_MAGIC)
            version = payload[offset]
            algorithm_id = payload[offset + 1]
            if version != SIGNED_PAYLOAD_VERSION or algorithm_id not in _ALGORITHM_NAMES:
                return None
            offset += 2
            signature_length = int.from_bytes(payload[offset:offset + 4], "big")
            offset += 4
            sig = payload[offset:offset + signature_length]
            if len(sig) != signature_length:
                return None
            json_bytes = payload[offset + signature_length:]
            algorithm = _ALGORITHM_NAMES[algorithm_id]
            signed_bytes = (
                payload[len(SIGNED_PAYLOAD_MAGIC):len(SIGNED_PAYLOAD_MAGIC) + 2]
                + json_bytes
            )
        else:
            # Payloads written by FIT releases before the compact envelope
            # remain verifiable, but new files no longer pay for JSON+base64.
            wrapper = json.loads(base64.b64decode(payload).decode("utf-8"))
            json_bytes = base64.b64decode(wrapper["data"])
            sig = base64.b64decode(wrapper["signature"])
            algorithm = wrapper["algorithm"]
            signed_bytes = json_bytes

        if algorithm == "RSA":
            public_key = load_rsa_public(public_key_pem)
            valid = rsa_verify(sig, signed_bytes, public_key)
        elif algorithm == "ECDSA":
            public_key = load_ecdsa_public(public_key_pem)
            valid = ecdsa_verify(sig, signed_bytes, public_key)
        else:
            return None

        if not valid:
            return None

        return json.loads(json_bytes.decode("utf-8"))
    except Exception:
        return None

