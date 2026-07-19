from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QGroupBox, QFormLayout, QProgressBar,
    QTextEdit, QRadioButton, QButtonGroup, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView,
)
from shared.constants import (
    INK_BLACK, CANVAS_CREAM, RADIUS_BUTTON, FONT_H3_SIZE,
    SPACING_MD, SPACING_LG, SLATE_GRAY, FONT_EYEBROW_SIZE,
)


class ExternalTestDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加载外部校验文件")
        self.setMinimumWidth(520)
        self.resize(560, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)

        title = QLabel("外部校验文件测试")
        title.setProperty("cssClass", "h2")
        title.setToolTip("不依赖当前项目，直接加载 .csv/.sfv 校验文件对目标目录进行验证")
        layout.addWidget(title)

        desc = QLabel("加载现有的 .csv 或 .sfv 校验文件，对比目标目录中的实际文件完整性。")
        desc.setWordWrap(True)
        desc.setProperty("cssClass", "muted")
        layout.addWidget(desc)

        cs_layout = QHBoxLayout()
        cs_label = QLabel("校验文件:")
        cs_label.setToolTip("要加载的校验文件（.csv 或 .sfv 格式），包含文件路径和哈希值")
        cs_layout.addWidget(cs_label)
        self._cs_path = QLineEdit()
        self._cs_path.setPlaceholderText("校验文件路径（.csv / .sfv / .sha256）...")
        self._cs_path.setToolTip("支持 CSV（推荐，含相对路径）和 SFV（仅文件名）两种格式")
        cs_layout.addWidget(self._cs_path, 1)
        cs_browse = QPushButton("浏览...")
        cs_browse.setProperty("cssClass", "secondary")
        cs_browse.setToolTip("打开文件对话框选择校验文件")
        cs_browse.clicked.connect(self._browse_cs)
        cs_layout.addWidget(cs_browse)
        layout.addLayout(cs_layout)

        td_layout = QHBoxLayout()
        td_label = QLabel("目标目录:")
        td_label.setToolTip("要验证的目标文件夹。系统将扫描此目录中的文件并与校验数据对比")
        td_layout.addWidget(td_label)
        self._target_path = QLineEdit()
        self._target_path.setPlaceholderText("待验证的目标文件夹路径...")
        self._target_path.setToolTip("选择包含待校验文件的目录。模拟验证将比较此目录中的文件")
        td_layout.addWidget(self._target_path, 1)
        td_browse = QPushButton("浏览...")
        td_browse.setProperty("cssClass", "secondary")
        td_browse.setToolTip("打开文件对话框选择目标目录")
        td_browse.clicked.connect(self._browse_target)
        td_layout.addWidget(td_browse)
        layout.addLayout(td_layout)

        algo_layout = QHBoxLayout()
        algo_label = QLabel("哈希算法:")
        algo_label.setToolTip("计算哈希值使用的算法。必须与校验文件生成时使用的算法一致")
        algo_layout.addWidget(algo_label)
        self._algo_combo = QComboBox()
        self._algo_combo.addItems(["sha256", "sha512", "md5"])
        self._algo_combo.setToolTip("SHA256（推荐）、SHA512（更安全但更慢）、MD5（快速但不安全）")
        algo_layout.addWidget(self._algo_combo)
        algo_layout.addStretch()
        layout.addLayout(algo_layout)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel = QPushButton("取消")
        cancel.setProperty("cssClass", "secondary")
        cancel.setToolTip("关闭对话框，不执行测试")
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(cancel)
        run = QPushButton("开始验证")
        run.setToolTip("加载校验文件并立即对目标目录执行模拟验证")
        run.clicked.connect(self.accept)
        btn_layout.addWidget(run)
        layout.addLayout(btn_layout)

    def _browse_cs(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择校验文件", "",
            "校验文件 (*.csv *.sfv *.sha256 *.sha512 *.md5);;所有文件 (*)"
        )
        if path:
            self._cs_path.setText(path)

    def _browse_target(self):
        path = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if path:
            self._target_path.setText(path)

    def get_values(self) -> dict:
        return {
            "checksum_path": self._cs_path.text().strip(),
            "target_dir": self._target_path.text().strip(),
            "algorithm": self._algo_combo.currentText(),
        }


class PackOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("打包验证器")
        self.setMinimumWidth(480)
        self.resize(500, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)

        title = QLabel("打包选项")
        title.setProperty("cssClass", "h2")
        title.setToolTip("配置 PyInstaller 打包参数，将验证器生成为独立的 EXE 文件")
        layout.addWidget(title)

        desc = QLabel("设置输出路径和打包后行为。打包过程可能需要数分钟。")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        layout.addWidget(desc)

        out_layout = QHBoxLayout()
        out_label = QLabel("输出路径:")
        out_label.setToolTip("验证器 EXE 文件的保存目录。将生成单个独立 EXE 文件")
        out_layout.addWidget(out_label)
        self._out_path = QLineEdit()
        self._out_path.setPlaceholderText("验证器 EXE 输出目录...")
        self._out_path.setToolTip("打包后的独立 EXE 文件保存目录。请确保有足够的磁盘空间（约 100MB）")
        out_layout.addWidget(self._out_path, 1)
        out_browse = QPushButton("浏览...")
        out_browse.setProperty("cssClass", "secondary")
        out_browse.setToolTip("选择验证器 EXE 的保存位置")
        out_browse.clicked.connect(self._browse_out)
        out_layout.addWidget(out_browse)
        layout.addLayout(out_layout)

        self._run_after = QCheckBox("打包完成后自动运行验证器")
        self._run_after.setChecked(True)
        self._run_after.setToolTip("打包成功后立即启动验证器进行测试。建议首次打包时启用")
        layout.addWidget(self._run_after)

        self._obfuscate = QCheckBox("启用代码混淆（如可用）")
        self._obfuscate.setToolTip("使用 PyInstaller 的混淆选项增强反逆向保护。可能增加打包时间")
        layout.addWidget(self._obfuscate)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel = QPushButton("取消")
        cancel.setProperty("cssClass", "secondary")
        cancel.setToolTip("关闭对话框，不执行打包")
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(cancel)
        pack = QPushButton("打包")
        pack.setToolTip("确认选项并开始 PyInstaller 打包流程")
        pack.clicked.connect(self.accept)
        btn_layout.addWidget(pack)
        layout.addLayout(btn_layout)

    def _browse_out(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存验证器", "verifier.exe",
            "可执行文件 (*.exe);;所有文件 (*)"
        )
        if path:
            self._out_path.setText(path)

    def get_values(self) -> dict:
        return {
            "output_path": self._out_path.text().strip(),
            "run_after": self._run_after.isChecked(),
            "obfuscate": self._obfuscate.isChecked(),
        }


class ChecklistEditDialog(QDialog):
    def __init__(self, entries: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑校验清单")
        self.setMinimumWidth(650)
        self.resize(700, 480)
        self._entries = [dict(e) for e in entries]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)

        title = QLabel("校验清单编辑器")
        title.setProperty("cssClass", "h2")
        title.setToolTip("管理校验清单中的文件条目。可移除不需要的文件或添加外部文件")
        layout.addWidget(title)

        info = QLabel(f"共 {len(self._entries)} 个文件条目")
        info.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        layout.addWidget(info)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["状态", "文件路径", "哈希值"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.setToolTip(
            "校验文件清单。可多选按 Delete 键或「移除选中」按钮删除条目。\n"
            "状态: ✓=已计算 ✗=错误 - =待处理"
        )

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.resizeSection(0, 50)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        vh = self._table.verticalHeader()
        vh.setVisible(False)

        self._populate_table()
        layout.addWidget(self._table, 1)

        btn_row = QHBoxLayout()

        remove_btn = QPushButton("移除选中")
        remove_btn.setProperty("cssClass", "secondary")
        remove_btn.setToolTip("从清单中移除选中的文件条目。多选可批量移除")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)

        add_btn = QPushButton("添加外部文件...")
        add_btn.setProperty("cssClass", "secondary")
        add_btn.setToolTip("添加不在当前项目目录中的外部文件到校验清单")
        add_btn.clicked.connect(self._add_files)
        btn_row.addWidget(add_btn)

        btn_row.addStretch()

        cancel = QPushButton("取消")
        cancel.setProperty("cssClass", "secondary")
        cancel.setToolTip("放弃所有修改并关闭对话框")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("保存修改")
        save.setToolTip("保存对校验清单的修改并返回")
        save.clicked.connect(self.accept)
        btn_row.addWidget(save)

        layout.addLayout(btn_row)

    def _populate_table(self):
        self._table.setRowCount(len(self._entries))
        for i, entry in enumerate(self._entries):
            st = entry.get("status", "pending")
            icon = "✓" if st == "ok" else "✗" if st == "error" else "-"
            self._table.setItem(i, 0, QTableWidgetItem(icon))
            self._table.setItem(i, 1, QTableWidgetItem(entry.get("path", "")))
            self._table.setItem(i, 2, QTableWidgetItem(entry.get("hash", "")))

    def _remove_selected(self):
        rows = sorted(set(idx.row() for idx in self._table.selectedIndexes()), reverse=True)
        if not rows:
            return
        reply = QMessageBox.question(
            self, "确认移除",
            f"确定要从清单中移除 {len(rows)} 个文件条目吗？\n\n"
            "这些文件将不再参与完整性校验。",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for row in rows:
            self._table.removeRow(row)
            del self._entries[row]

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "添加外部文件", "",
            "所有文件 (*);;可执行文件 (*.exe *.dll);;文档文件 (*.pdf *.doc *.docx)"
        )
        if not paths:
            return
        for p in paths:
            entry = {"path": p, "hash": "", "status": "pending"}
            self._entries.append(entry)
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem("-"))
            self._table.setItem(row, 1, QTableWidgetItem(p))
            self._table.setItem(row, 2, QTableWidgetItem(""))

    def get_entries(self) -> list[dict]:
        return self._entries

