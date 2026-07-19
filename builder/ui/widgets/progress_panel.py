from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QLabel,
    QPlainTextEdit, QPushButton, QFrame,
)
from PySide6.QtGui import QTextCharFormat, QColor, QFont

from shared.constants import (
    INK_BLACK, SLATE_GRAY, SUCCESS_GREEN, ERROR_RED, WARNING_AMBER,
    SIGNAL_ORANGE, LIFTED_CREAM, DUST_TAUPE, WHITE, RADIUS_HERO,
    SPACING_SM, SPACING_MD, SPACING_LG, FONT_BODY_SIZE, FONT_MONO_SIZE, FONT_EYEBROW_SIZE,
)


class ProgressPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProgressPanel")
        self.setStyleSheet(f"""
                background-color: {LIFTED_CREAM};
                border: 1px solid {DUST_TAUPE};
                border-radius: {RADIUS_HERO}px;
                padding: {SPACING_MD}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        title = QLabel("计算进度")
        title.setProperty("cssClass", "h3")
        title.setToolTip("实时显示哈希计算的进度、当前文件和速度")
        layout.addWidget(title)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setToolTip("哈希计算完成百分比。绿色填充表示进度")
        layout.addWidget(self._progress)

        self._current_label = QLabel("等待中...")
        self._current_label.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        self._current_label.setWordWrap(True)
        self._current_label.setToolTip("当前正在计算哈希值的文件路径")
        layout.addWidget(self._current_label)

        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        self._speed_label.setToolTip("计算速度（文件数/秒）。受磁盘I/O和CPU性能影响")
        layout.addWidget(self._speed_label)

        log_label = QLabel("日志:")
        log_label.setProperty("cssClass", "eyebrow")
        log_label.setToolTip("详细操作日志。不同颜色表示不同级别")
        layout.addWidget(log_label)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(1000)
        self._log.setToolTip(
            "日志详情。白色=信息  黄色=警告  红色=错误  绿色=成功\n"
            "最多保留 1000 行，超出后自动清除旧记录"
        )
        self._log.setStyleSheet(f"""
            QPlainTextEdit {{
                font-family: "Consolas", "JetBrains Mono", monospace;
                font-size: {FONT_MONO_SIZE}px;
                font-weight: 450;
                background-color: {WHITE};
                border: 1px solid {DUST_TAUPE};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self._log, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_progress(self, completed: int, total: int):
        pct = int(completed / total * 100) if total > 0 else 0
        self._progress.setValue(pct)
        self._progress.setFormat(f"{completed:,} / {total:,} ({pct}%)")

    def set_current_file(self, path: str):
        self._current_label.setText(path if path else "")

    def set_speed(self, files_per_sec: float):
        self._speed_label.setText(f"速度: {files_per_sec:.1f} 文件/秒")

    def log_info(self, message: str):
        self._append_log("信息", message, QColor(INK_BLACK))

    def log_warning(self, message: str):
        self._append_log("警告", message, QColor(WARNING_AMBER))

    def log_error(self, message: str):
        self._append_log("错误", message, QColor(ERROR_RED))

    def log_success(self, message: str):
        self._append_log("成功", message, QColor(SUCCESS_GREEN))

    def _append_log(self, level: str, message: str, color: QColor):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {level:4s} {message}"

        cursor = self._log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(color)
        fmt.setFont(QFont("Consolas", FONT_MONO_SIZE))
        cursor.insertText(line + "\n", fmt)

        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

    def clear(self):
        self._progress.setValue(0)
        self._current_label.setText("等待中...")
        self._speed_label.setText("")
        self._log.clear()

