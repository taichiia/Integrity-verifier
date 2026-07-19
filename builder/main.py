import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from builder.ui.main_window import BuilderMainWindow
from shared.constants import (
    CANVAS_CREAM, INK_BLACK,
    FONT_FAMILY, FONT_BODY_SIZE, FONT_H1_SIZE, FONT_H2_SIZE, FONT_H3_SIZE,
    FONT_BUTTON_SIZE, FONT_EYEBROW_SIZE,
)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("File Integrity Builder")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("FIT")

    font = QFont(FONT_FAMILY, FONT_BODY_SIZE)
    font.setWeight(QFont.Weight.DemiBold)
    app.setFont(font)

    window = BuilderMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

