import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from verifier.ui.main_window import VerifierMainWindow
from shared.constants import FONT_FAMILY, FONT_BODY_SIZE


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("文件完整性验证器")
    app.setApplicationVersion("1.0.0")

    font = QFont(FONT_FAMILY, FONT_BODY_SIZE)
    font.setWeight(QFont.Weight.DemiBold)
    app.setFont(font)

    EMBEDDED_CONFIG = _load_embedded_config()
    _run_protection_checks(EMBEDDED_CONFIG)

    window = VerifierMainWindow(EMBEDDED_CONFIG)
    window.show()

    sys.exit(app.exec())


def _load_embedded_config():
    import json
    import base64

    try:
        from verifier._embedded_data import EMBEDDED_CONFIG_B64, EMBEDDED_CONFIG_KEY
    except ImportError:
        try:
            from verifier._embedded_data import EMBEDDED_CONFIG
            return EMBEDDED_CONFIG
        except ImportError:
            QMessageBox.warning(
                None, "无校验数据",
                "此验证器不包含内嵌的校验数据。\n"
                "它可能是在没有校验清单的情况下构建的。\n\n"
                "请使用开发者端工具生成校验文件并重新打包。"
            )
            return None

    try:
        key = base64.b64decode(EMBEDDED_CONFIG_KEY)
        ciphertext = base64.b64decode(EMBEDDED_CONFIG_B64)
        from shared.crypto import aes_decrypt
        plaintext = aes_decrypt(ciphertext, key)
        config = json.loads(plaintext.decode("utf-8"))

        _verify_embedded_signature(config)
        return config
    except Exception as e:
        QMessageBox.critical(
            None, "校验数据加载失败",
            f"无法解密内嵌校验数据:\n\n{e}\n\n"
            "验证器可能已损坏或被篡改。"
        )
        return None


def _verify_embedded_signature(config):
    try:
        from verifier._embedded_data import EMBEDDED_PUBLIC_KEY
        import json
        import base64
        from cryptography.hazmat.primitives import serialization
        from shared.crypto import load_rsa_public, load_ecdsa_public

        sig_algo = config.get("signature_algorithm", "RSA")
        pub_pem = base64.b64decode(EMBEDDED_PUBLIC_KEY)
        public_key = load_ecdsa_public(pub_pem) if sig_algo == "ECDSA" else load_rsa_public(pub_pem)

        entries = config.get("checksum_entries", [])
        if not entries:
            return

        from shared.hashing import hash_file
        import hashlib
        manifest_bytes = json.dumps(
            sorted(entries, key=lambda e: e.get("path", "")),
            ensure_ascii=False, sort_keys=True,
        ).encode("utf-8")
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

        if config.get("manifest_hash") and config.get("manifest_hash") != manifest_hash:
            QMessageBox.warning(
                None, "签名验证失败",
                "内嵌校验清单与签名不匹配。\n数据可能已被篡改。"
            )
    except ImportError:
        pass
    except Exception:
        pass


def _run_protection_checks(config):
    enable_antidebug = (config or {}).get("enable_antidebug", False)
    enable_antisanbox = (config or {}).get("enable_antisanbox", False)

    if not enable_antidebug and not enable_antisanbox:
        return

    try:
        from shared.protection import (
            run_debugger_checks, run_vm_checks, run_timing_check, assess_environment,
        )

        debugger = run_debugger_checks() if enable_antidebug else []
        vm = run_vm_checks() if enable_antisanbox else []
        timing = run_timing_check() if enable_antidebug else []
        assessment = assess_environment(debugger, vm, timing)

        if assessment.level == "high_confidence":
            details = "\n".join(
                f"  - {c.name}" for c in assessment.checks
            ) or "  - (未知原因)"
            QMessageBox.warning(
                None, "环境异常",
                f"检测到可疑运行环境:\n\n{details}\n\n"
                "验证结果可能不可靠。"
            )
    except Exception:
        pass


if __name__ == "__main__":
    main()

