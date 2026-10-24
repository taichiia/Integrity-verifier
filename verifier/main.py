import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


if "--target" in sys.argv[1:]:
    # CLI automation must not pay for the GUI stack.  The imports below stay
    # visible to PyInstaller so the frozen executable still contains Qt.
    from verifier.cli import main as cli_main
    sys.exit(cli_main(sys.argv[1:]))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from verifier.ui.main_window import VerifierMainWindow
from verifier.embedded import EmbeddedConfigError, load_embedded_config, manifest_mismatch_message
from shared.constants import FONT_FAMILY, FONT_BODY_SIZE


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("文件完整性验证器")
    app.setApplicationVersion("1.0.0")

    font = QFont(FONT_FAMILY, FONT_BODY_SIZE)
    font.setWeight(QFont.Weight.Normal)
    app.setFont(font)

    from shared.protection import verify_self_integrity
    self_ok, self_detail = verify_self_integrity()
    if not self_ok:
        QMessageBox.critical(
            None,
            "Verifier 自校验失败",
            f"验证器自身校验失败:\n\n{self_detail}\n\n"
            "程序已停止，验证结果不可信任。"
        )
        return 5

    EMBEDDED_CONFIG = _load_embedded_config()
    if not _run_protection_checks(EMBEDDED_CONFIG):
        return 0

    window = VerifierMainWindow(EMBEDDED_CONFIG)
    window.show()

    sys.exit(app.exec())


def _load_embedded_config():
    try:
        config = load_embedded_config()
    except EmbeddedConfigError as e:
        if e.severity == "warning":
            QMessageBox.warning(None, e.title, e.message)
        else:
            QMessageBox.critical(None, e.title, e.message)
        return None

    mismatch = manifest_mismatch_message(config)
    if mismatch:
        QMessageBox.warning(None, "签名验证失败", mismatch)
    return config


def _run_protection_checks(config):
    enable_antidebug = (config or {}).get("enable_antidebug", False)
    enable_antisanbox = (config or {}).get("enable_antisanbox", False)

    if not enable_antidebug and not enable_antisanbox:
        return True

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
            return _confirm_continue(
                None, "环境异常",
                f"检测到可疑运行环境:\n\n{details}\n\n"
                "验证结果可能不可靠。是否仍要继续？"
            )
    except Exception as exc:
        return _confirm_continue(
            None,
            "保护检查异常",
            f"运行环境保护检查未能完整执行:\n\n{exc}\n\n"
                "验证结果可能不可靠，请检查运行环境或重新获取验证器。是否仍要继续？"
        )
    return True


def _confirm_continue(parent, title: str, message: str) -> bool:
    answer = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


if __name__ == "__main__":
    main()

