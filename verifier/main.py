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

    try:
        from shared.protection import run_full_assessment
        assessment = run_full_assessment()
    except Exception as e:
        QMessageBox.warning(
            None, "完整性检查失败",
            f"完整性验证系统遇到错误:\n\n{e}\n\n"
            "应用程序将继续运行，但验证结果可能不可靠。"
        )

    try:
        from verifier._embedded_data import EMBEDDED_CONFIG
    except ImportError:
        EMBEDDED_CONFIG = None
        QMessageBox.warning(
            None, "无校验数据",
            "此验证器不包含内嵌的校验数据。\n"
            "它可能是在没有校验清单的情况下构建的。\n\n"
            "请使用开发者端工具生成校验文件并重新打包。"
        )

    window = VerifierMainWindow(EMBEDDED_CONFIG)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

