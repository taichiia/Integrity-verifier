import base64
import json
import zlib


class EmbeddedConfigError(Exception):
    def __init__(self, message: str, title: str, severity: str = "critical"):
        super().__init__(message)
        self.message = message
        self.title = title
        self.severity = severity


def load_embedded_config() -> dict:
    try:
        from verifier._embedded_data import EMBEDDED_CONFIG_B64, EMBEDDED_CONFIG_KEY
    except ImportError:
        try:
            from verifier._embedded_data import EMBEDDED_CONFIG
            return EMBEDDED_CONFIG
        except ImportError as exc:
            raise EmbeddedConfigError(
                "此验证器不包含内嵌的校验数据。\n"
                "它可能是在没有校验清单的情况下构建的。\n\n"
                "请使用开发者端工具生成校验文件并重新打包。",
                "无校验数据",
                severity="warning",
            ) from exc

    try:
        key = base64.b64decode(EMBEDDED_CONFIG_KEY)
        ciphertext = base64.b64decode(EMBEDDED_CONFIG_B64)
        from shared.crypto import aes_decrypt
        plaintext = aes_decrypt(ciphertext, key)
        try:
            plaintext = zlib.decompress(plaintext)
        except zlib.error:
            # Configs packed by older FIT releases were JSON without zlib.
            pass
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise EmbeddedConfigError(
            f"无法解密内嵌校验数据:\n\n{exc}\n\n验证器可能已损坏或被篡改。",
            "校验数据加载失败",
        ) from exc


def manifest_mismatch_message(config: dict) -> str | None:
    try:
        from verifier._embedded_data import EMBEDDED_PUBLIC_KEY
    except ImportError:
        return None

    entries = config.get("checksum_entries", [])
    if not entries:
        return None

    import hashlib
    from shared.crypto import verify_signed_payload
    manifest_bytes = json.dumps(
        sorted(entries, key=lambda e: e.get("path", "")),
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    if config.get("manifest_hash") and config.get("manifest_hash") != manifest_hash:
        return "内嵌校验清单与签名不匹配。数据可能已被篡改。"
    if config.get("enable_signature_verify", False):
        try:
            from verifier._embedded_data import EMBEDDED_PUBLIC_KEY
        except ImportError:
            return None

        try:
            from verifier._embedded_data import EMBEDDED_MANIFEST_SIGNATURE
        except ImportError:
            return "内嵌校验清单缺少签名。数据可能已被篡改。"

        decoded = verify_signed_payload(
            base64.b64decode(EMBEDDED_MANIFEST_SIGNATURE),
            base64.b64decode(EMBEDDED_PUBLIC_KEY),
        )
        if decoded is None or decoded.get("manifest_hash") != manifest_hash:
            return "内嵌校验清单签名验证失败。数据可能已被篡改。"
    return None
