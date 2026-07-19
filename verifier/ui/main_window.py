import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QProgressBar, QCheckBox, QTableView,
    QHeaderView, QSplitter,
    QFileDialog, QMessageBox, QMenu, QComboBox, QFrame,
)
from PySide6.QtGui import QAction, QColor, QIcon

from verifier.ui.theme import generate_verifier_stylesheet
from shared.constants import (
    CANVAS_CREAM, INK_BLACK, WHITE, SLATE_GRAY,
    SUCCESS_GREEN, ERROR_RED, WARNING_AMBER, INFO_BLUE, DUST_TAUPE,
    RADIUS_HERO, RADIUS_PILL, RADIUS_BUTTON,
    SPACING_MD, SPACING_LG, FONT_H2_SIZE, FONT_H3_SIZE,
    FONT_BODY_SIZE, FONT_EYEBROW_SIZE, FONT_MONO_SIZE,
)
from shared.hashing import hash_batch


class VerifierResultModel(QAbstractTableModel):
    COL_STATUS = 0
    COL_PATH = 1
    COL_EXPECTED = 2

    HEADERS = ["状态", "文件路径", "期望哈希值"]

    STATUS_ICONS = {
        "pass": "通过",
        "fail": "失败",
        "missing": "缺失",
        "extra": "多余",
        "error": "错误",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[dict] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._results)

    def columnCount(self, parent=QModelIndex()):
        return 3

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._results[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_STATUS:
                return self.STATUS_ICONS.get(row["status"], "?")
            elif col == self.COL_PATH:
                return row["path"]
            elif col == self.COL_EXPECTED:
                return row.get("expected", "")

        if role == Qt.ItemDataRole.ForegroundRole:
            colors = {
                "pass": QColor(SUCCESS_GREEN),
                "fail": QColor(ERROR_RED),
                "missing": QColor(WARNING_AMBER),
                "extra": QColor(INFO_BLUE),
                "error": QColor(ERROR_RED),
            }
            return colors.get(row["status"], QColor(INK_BLACK))

        if role == Qt.ItemDataRole.FontRole:
            if col == self.COL_PATH:
                f = QTableView().font()
                return f

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == self.COL_PATH:
                return row["path"]
            elif col == self.COL_EXPECTED:
                return f"期望: {row.get('expected', '')}"
            elif col == self.COL_STATUS:
                tips = {
                    "pass": "文件完整，哈希值与记录一致",
                    "fail": "哈希值不匹配，文件可能已被修改",
                    "missing": "文件在清单中但目录中不存在",
                    "extra": "目录中存在但不在校验清单中",
                    "error": "读取文件时发生错误",
                }
                return tips.get(row["status"], "")

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def set_results(self, results: list[dict]):
        self.beginResetModel()
        self._results = results
        self.endResetModel()

    def clear(self):
        self.beginResetModel()
        self._results.clear()
        self.endResetModel()


class VerifierMainWindow(QMainWindow):
    def __init__(self, embedded_config: dict | None = None, parent=None):
        super().__init__(parent)
        self._config = embedded_config or {}
        self._worker = None

        title = self._config.get("title", "文件完整性验证器")
        version = self._config.get("version", "1.0.0")
        self.setWindowTitle(f"{title}  v{version}")
        self.setMinimumSize(1000, 600)
        self.resize(1100, 650)
        self.setStyleSheet(generate_verifier_stylesheet())

        self._setup_ui()

        self._resolve_target_path()

        if self._auto_start_cb.isChecked():
            self._start_verification()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)

        title_row = QHBoxLayout()
        title = QLabel("文件完整性验证器")
        title.setProperty("cssClass", "h2")
        title.setToolTip("验证目标目录中文件的完整性，与内嵌的校验清单进行对比")
        title_row.addWidget(title)
        title_row.addStretch()

        checklist_label = QLabel("校验清单:")
        checklist_label.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        checklist_label.setToolTip("选择要使用的校验清单（如项目中配置了多套清单）")
        title_row.addWidget(checklist_label)
        self._checklist_combo = QComboBox()
        self._checklist_combo.addItem("默认")
        self._checklist_combo.setToolTip("切换不同的校验清单。每套清单对应一组校验文件数据")
        title_row.addWidget(self._checklist_combo)

        layout.addLayout(title_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QFrame()
        left.setStyleSheet(f"""
            QFrame {{
                background-color: {WHITE};
                border: 1px solid {DUST_TAUPE};
                border-radius: {RADIUS_HERO}px;
                padding: {SPACING_MD}px;
            }}
        """)
        left.setMinimumWidth(250)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        left_layout.setSpacing(SPACING_MD)

        path_label = QLabel("目标路径:")
        path_label.setProperty("cssClass", "eyebrow")
        path_label.setToolTip("要验证的目标文件夹。验证器将扫描此目录中的文件并与校验清单对比")
        left_layout.addWidget(path_label)

        path_row = QHBoxLayout()
        self._target_path = QLineEdit()
        self._target_path.setReadOnly(True)
        self._target_path.setToolTip(
            "当前验证目标路径。\n"
            "打包时根据路径规则自动配置，也可手动浏览选择"
        )
        path_row.addWidget(self._target_path, 1)
        browse_btn = QPushButton("浏览...")
        browse_btn.setProperty("cssClass", "secondary")
        browse_btn.setToolTip("手动选择要验证的目标文件夹")
        browse_btn.clicked.connect(self._browse_target)
        path_row.addWidget(browse_btn)
        left_layout.addLayout(path_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setToolTip("验证进度。显示已完成文件数占总数的百分比")
        left_layout.addWidget(self._progress)

        self._current_label = QLabel("就绪")
        self._current_label.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        self._current_label.setToolTip("当前正在验证的文件名")
        left_layout.addWidget(self._current_label)

        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        self._speed_label.setToolTip("验证速度（文件数/秒）")
        left_layout.addWidget(self._speed_label)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("开始验证")
        self._start_btn.setToolTip("开始扫描目标目录并计算文件哈希值，与内嵌校验清单进行对比")
        self._start_btn.clicked.connect(self._start_verification)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setProperty("cssClass", "secondary")
        self._stop_btn.setToolTip("停止当前正在进行的验证流程。已完成的结果将保留")
        self._stop_btn.clicked.connect(self._stop_verification)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._stop_btn)
        left_layout.addLayout(btn_row)

        opt_label = QLabel("选项:")
        opt_label.setProperty("cssClass", "eyebrow")
        opt_label.setToolTip("验证器运行选项")
        left_layout.addWidget(opt_label)

        self._auto_start_cb = QCheckBox("启动时自动验证")
        self._auto_start_cb.setChecked(True)
        self._auto_start_cb.setToolTip("验证器启动后自动开始验证。关闭则需手动点击「开始验证」")
        left_layout.addWidget(self._auto_start_cb)

        self._anomaly_only_cb = QCheckBox("仅显示异常项")
        self._anomaly_only_cb.toggled.connect(self._filter_results)
        self._anomaly_only_cb.setToolTip("只显示验证失败、缺失、多余或出错的文件，隐藏通过的文件")
        left_layout.addWidget(self._anomaly_only_cb)

        left_layout.addStretch()
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACING_MD)

        self._result_table = QTableView()
        self._result_model = VerifierResultModel()
        self._result_table.setModel(self._result_model)
        self._result_table.setSelectionBehavior(self._result_table.SelectionBehavior.SelectRows)
        self._result_table.setSortingEnabled(True)
        self._result_table.setShowGrid(False)
        self._result_table.setAlternatingRowColors(False)
        self._result_table.setToolTip(
            "验证结果列表。\n"
            "通过=文件完整  失败=哈希不匹配  缺失=文件不存在  多余=不在清单中\n"
            "右键查看更多操作（复制哈希值、打开文件位置）"
        )

        hh = self._result_table.horizontalHeader()
        hh.setSectionResizeMode(VerifierResultModel.COL_STATUS, QHeaderView.ResizeMode.Fixed)
        hh.resizeSection(VerifierResultModel.COL_STATUS, 70)
        hh.setSectionResizeMode(VerifierResultModel.COL_PATH, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(VerifierResultModel.COL_EXPECTED, QHeaderView.ResizeMode.ResizeToContents)

        vh = self._result_table.verticalHeader()
        vh.setVisible(False)

        self._result_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._result_table.customContextMenuRequested.connect(self._on_result_context)

        right_layout.addWidget(self._result_table, 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 800])

        layout.addWidget(splitter, 1)

        bottom = QHBoxLayout()

        self._passed_label = QLabel("通过: 0")
        self._passed_label.setStyleSheet(f"color: {SUCCESS_GREEN}; font-weight: 700; font-size: {FONT_BODY_SIZE}px;")
        self._passed_label.setToolTip("哈希值与记录完全一致的文件数")
        bottom.addWidget(self._passed_label)

        self._failed_label = QLabel("失败: 0")
        self._failed_label.setStyleSheet(f"color: {ERROR_RED}; font-weight: 700; font-size: {FONT_BODY_SIZE}px;")
        self._failed_label.setToolTip("哈希值与记录不匹配的文件数。这些文件可能已被修改或损坏")
        bottom.addWidget(self._failed_label)

        self._missing_label = QLabel("缺失: 0")
        self._missing_label.setStyleSheet(f"color: {WARNING_AMBER}; font-weight: 700; font-size: {FONT_BODY_SIZE}px;")
        self._missing_label.setToolTip("在校验清单中存在但在目标目录中找不到的文件数")
        bottom.addWidget(self._missing_label)

        self._extra_label = QLabel("多余: 0")
        self._extra_label.setStyleSheet(f"color: {INFO_BLUE}; font-weight: 700; font-size: {FONT_BODY_SIZE}px;")
        self._extra_label.setToolTip("在目标目录中存在但不在校验清单中的文件数")
        bottom.addWidget(self._extra_label)

        bottom.addStretch()

        export_btn = QPushButton("导出报告")
        export_btn.setProperty("cssClass", "secondary")
        export_btn.setToolTip("将验证结果导出为 CSV 或 TXT 格式的报告文件")
        export_btn.clicked.connect(self._export_report)
        bottom.addWidget(export_btn)

        copy_fail_btn = QPushButton("复制失败列表")
        copy_fail_btn.setProperty("cssClass", "secondary")
        copy_fail_btn.setToolTip("将验证失败/缺失/错误的文件路径复制到剪贴板，每行一个路径")
        copy_fail_btn.clicked.connect(self._copy_failed)
        bottom.addWidget(copy_fail_btn)

        layout.addLayout(bottom)


    def _resolve_target_path(self):
        rule = self._config.get("path_rule", "current_dir")

        if rule == "current_dir":
            path = os.path.dirname(sys.executable if getattr(sys, 'frozen', False)
                                   else os.path.dirname(__file__))
        elif rule == "subfolder":
            base = os.path.dirname(sys.executable if getattr(sys, 'frozen', False)
                                   else os.path.dirname(__file__))
            sub = self._config.get("subfolder", "")
            path = os.path.join(base, sub) if sub else base
        elif rule == "custom_template":
            template = self._config.get("custom_template", "")
            path = os.path.expandvars(template)
        else:
            path = os.path.dirname(sys.executable if getattr(sys, 'frozen', False)
                                   else os.path.dirname(__file__))

        self._target_path.setText(path)

        if not os.path.isdir(path):
            self._target_path.setStyleSheet(f"color: {ERROR_RED};")
            QMessageBox.warning(
                self, "路径不存在",
                f"配置的目标路径不存在:\n\n{path}\n\n"
                "请手动选择正确的目录。\n\n"
                "提示：您可以通过「浏览...」按钮选择其他目录。"
            )


    def _start_verification(self):
        entries = self._config.get("checksum_entries", [])
        if not entries:
            QMessageBox.information(
                self, "无校验数据",
                "此验证器不包含校验清单。\n\n"
                "请使用开发者端工具生成校验文件并重新打包。"
            )
            return

        target = self._target_path.text().strip()
        if not os.path.isdir(target):
            self._browse_target()
            target = self._target_path.text().strip()
            if not os.path.isdir(target):
                return

        algorithm = self._config.get("algorithm", "sha256")

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress.setValue(0)
        self._current_label.setText("正在扫描...")
        self._all_results = []

        paths_to_hash = []
        expected_map = {}
        for entry in entries:
            full = os.path.join(target, entry["path"])
            if os.path.isfile(full):
                paths_to_hash.append(full)
                expected_map[full] = entry.get("hash", "")
            else:
                self._all_results.append({
                    "path": entry["path"], "status": "missing",
                    "expected": entry.get("hash", ""),
                })

        manifest_paths = set(
            os.path.normpath(os.path.join(target, e["path"])).lower()
            for e in entries
        )
        for root, _, files in os.walk(target):
            for f in files:
                full = os.path.join(root, f)
                if os.path.normpath(full).lower() not in manifest_paths:
                    try:
                        rel = os.path.relpath(full, target)
                    except ValueError:
                        rel = full
                    self._all_results.append({
                        "path": rel, "status": "extra", "expected": "",
                    })

        total = len(paths_to_hash)
        self._result_model.clear()
        self._update_stats()

        if total == 0:
            self._on_verify_done()
            return

        from builder.ui.workers.hash_worker import HashWorker
        self._worker = HashWorker(paths_to_hash, algorithm)
        self._worker.progress.connect(self._on_verify_progress)
        self._worker.file_done.connect(
            lambda p, d, e: self._on_verify_file(p, d, e, expected_map, target)
        )
        self._worker.finished.connect(lambda _: self._on_verify_done())
        self._worker.error_occurred.connect(
            lambda msg: self._current_label.setText(f"错误: {msg}")
        )
        self._worker.start()

    def _on_verify_progress(self, completed: int, total: int, path: str):
        self._progress.setValue(int(completed / total * 100) if total else 0)
        self._current_label.setText(os.path.basename(path))

    def _on_verify_file(self, path: str, digest: str, error: str,
                        expected_map: dict, target_dir: str):
        try:
            rel = os.path.relpath(path, target_dir)
        except ValueError:
            rel = path

        expected = expected_map.get(path, "")

        if error:
            status = "error"
        elif digest == expected:
            status = "pass"
        else:
            status = "fail"

        self._all_results.append({
            "path": rel, "status": status,
            "expected": expected,
        })

    def _on_verify_done(self):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setValue(100)
        self._current_label.setText("验证完成")

        self._filter_results()

    def _filter_results(self):
        anomaly_only = self._anomaly_only_cb.isChecked()
        if anomaly_only:
            filtered = [r for r in self._all_results if r["status"] != "pass"]
        else:
            filtered = self._all_results

        self._result_model.set_results(filtered)
        self._update_stats()

    def _update_stats(self):
        all_r = self._all_results
        passed = sum(1 for r in all_r if r["status"] == "pass")
        failed = sum(1 for r in all_r if r["status"] == "fail")
        missing = sum(1 for r in all_r if r["status"] == "missing")
        extra = sum(1 for r in all_r if r["status"] == "extra")

        self._passed_label.setText(f"通过: {passed:,}")
        self._failed_label.setText(f"失败: {failed:,}")
        self._missing_label.setText(f"缺失: {missing:,}")
        self._extra_label.setText(f"多余: {extra:,}")

    def _stop_verification(self):
        if self._worker:
            self._worker.cancel()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)


    def _browse_target(self):
        path = QFileDialog.getExistingDirectory(self, "选择目标目录")
        if path:
            self._target_path.setText(path)
            self._target_path.setStyleSheet("")

    def _on_result_context(self, pos):
        menu = QMenu(self)
        idx = self._result_table.indexAt(pos)
        if idx.isValid():
            copy_hash = QAction("复制哈希值", self)
            copy_hash.setToolTip("将所选文件的期望哈希值复制到剪贴板")
            copy_hash.triggered.connect(lambda: self._copy_cell(idx.row(), 2))
            menu.addAction(copy_hash)

            open_file = QAction("打开文件位置", self)
            open_file.setToolTip("在 Windows 资源管理器中打开并定位到此文件")
            open_file.triggered.connect(lambda: self._open_file_location(idx.row()))
            menu.addAction(open_file)

            menu.exec(self._result_table.viewport().mapToGlobal(pos))

    def _copy_cell(self, row: int, col: int):
        from PySide6.QtWidgets import QApplication
        data = self._result_model.data(
            self._result_model.index(row, col),
            Qt.ItemDataRole.DisplayRole,
        )
        if data:
            QApplication.clipboard().setText(str(data))

    def _open_file_location(self, row: int):
        path = self._result_model.data(
            self._result_model.index(row, VerifierResultModel.COL_PATH),
        )
        if path:
            target = self._target_path.text().strip()
            full = os.path.join(target, str(path))
            if os.path.exists(full):
                os.system(f'explorer /select,"{full}"')

    def _export_report(self):
        if not self._all_results:
            QMessageBox.information(self, "无数据", "尚无验证结果可导出。请先执行验证。")
            return

        path, fmt = QFileDialog.getSaveFileName(
            self, "导出报告", "验证报告.csv",
            "CSV 文件 (*.csv);;文本文件 (*.txt);;所有文件 (*)"
        )
        if not path:
            return

        try:
            if path.endswith(".csv"):
                import csv
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["状态", "文件路径", "期望哈希值"])
                    for r in self._all_results:
                        writer.writerow([r["status"], r["path"], r.get("expected", "")])
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"文件完整性验证报告\n")
                    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"目标路径: {self._target_path.text()}\n")
                    f.write("-" * 60 + "\n")
                    for r in self._all_results:
                        status = VerifierResultModel.STATUS_ICONS.get(r["status"], "?")
                        f.write(f"[{status}] {r['path']}\n")

                    passed = sum(1 for r in self._all_results if r["status"] == "pass")
                    total = len(self._all_results)
                    f.write("-" * 60 + "\n")
                    f.write(f"汇总: {passed}/{total} 通过, {total - passed} 项异常\n")

            QMessageBox.information(self, "导出成功", f"报告已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出错误", str(e))

    def _copy_failed(self):
        failed = [r["path"] for r in self._all_results if r["status"] in ("fail", "missing", "error")]
        if failed:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText("\n".join(failed))
            QMessageBox.information(
                self, "已复制", f"{len(failed)} 个失败/缺失/错误文件路径已复制到剪贴板。"
            )
        else:
            QMessageBox.information(self, "无失败项", "没有验证失败的文件。")

