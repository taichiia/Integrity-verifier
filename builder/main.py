import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from builder.ui.main_window import BuilderMainWindow
from shared.constants import FONT_FAMILY, FONT_BODY_SIZE


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("File Integrity Builder")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("FIT")

    font = QFont(FONT_FAMILY, FONT_BODY_SIZE)
    font.setWeight(QFont.Weight.Normal)
    app.setFont(font)

    window = BuilderMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

