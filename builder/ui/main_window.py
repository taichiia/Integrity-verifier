import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget,
    QStatusBar, QLabel, QMessageBox, QFileDialog,
)

from builder.ui.step_nav import StepNav
from builder.ui.step1_files import Step1Files
from builder.ui.step2_hashes import Step2Hashes
from builder.ui.step3_pack import Step3Pack
from builder.ui.theme import generate_builder_stylesheet
from shared.project import ProjectData, save_project, load_project
from shared.constants import (
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    INK_BLACK, CANVAS_CREAM, SPACING_MD,
)


class BuilderMainWindow(QMainWindow):
    project_saved = Signal(str)
    project_loaded = Signal(str)

    def __init__(self):
        super().__init__()
        self._project = ProjectData()

        self.setWindowTitle("文件完整性验证工具 — 开发者端")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        self.setStyleSheet(generate_builder_stylesheet())

        self._setup_menu()
        self._setup_central()
        self._setup_status()

        self._step_nav.step_changed.connect(self._on_step_changed)

    def _setup_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        new_action = QAction("新建项目(&N)", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.setToolTip("创建一个新的空白项目")
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("打开项目(&O)...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setToolTip("从 .fvp 文件加载已有项目")
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        save_action = QAction("保存项目(&S)", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setToolTip("保存当前项目状态到 .fvp 文件")
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("另存为(&A)...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.setToolTip("将项目保存到新的 .fvp 文件")
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = mb.addMenu("工具(&T)")
        ext_test_action = QAction("加载外部校验文件测试...", self)
        ext_test_action.setToolTip("不依赖当前项目，直接加载 .csv/.sha256 文件和目录进行验证测试")
        ext_test_action.triggered.connect(self._external_test)
        tools_menu.addAction(ext_test_action)

        help_menu = mb.addMenu("帮助(&H)")
        about_action = QAction("关于(&A)", self)
        about_action.setToolTip("查看软件版本与说明")
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_central(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(SPACING_MD, 0, SPACING_MD, 0)
        layout.setSpacing(0)

        self._step_nav = StepNav()
        layout.addWidget(self._step_nav)

        self._stack = QStackedWidget()
        self._step1 = Step1Files(self._project)
        self._step2 = Step2Hashes(self._project)
        self._step3 = Step3Pack(self._project)

        self._stack.addWidget(self._step1)
        self._stack.addWidget(self._step2)
        self._stack.addWidget(self._step3)

        layout.addWidget(self._stack, 1)

    def _setup_status(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet(f"color: {INK_BLACK}; padding: 4px 12px;")
        self._status.addWidget(self._status_label, 1)

    def _on_step_changed(self, index: int):
        current_idx = self._stack.currentIndex()
        if current_idx == 0:
            self._step1.sync_to_project()
        elif current_idx == 1:
            self._step2.sync_to_project()
        elif current_idx == 2:
            self._step3.sync_to_project()

        self._step_nav.set_current(index)
        self._stack.setCurrentIndex(index)

        if index == 0:
            self._step1.refresh_from_project()
        elif index == 1:
            self._step2.refresh_from_project()
        elif index == 2:
            self._step3.refresh_from_project()

        self._update_status()

    def _new_project(self):
        self._project = ProjectData()
        self._refresh_all_steps()
        self._status_label.setText("已创建新项目")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "",
            "FVP 项目文件 (*.fvp);;所有文件 (*)"
        )
        if path:
            try:
                self._project = load_project(path)
                self._refresh_all_steps()
                self._status_label.setText(f"已加载: {path}")
                self.project_loaded.emit(path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载项目失败:\n{e}")

    def _save_project(self):
        if self._project.project_file_path:
            self._do_save(self._project.project_file_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "另存项目", "project.fvp",
            "FVP 项目文件 (*.fvp);;所有文件 (*)"
        )
        if path:
            self._do_save(path)

    def _do_save(self, path: str):
        try:
            self._sync_project_from_steps()
            save_project(self._project, path)
            self._status_label.setText(f"已保存: {path}")
            self.project_saved.emit(path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{e}")

    def _external_test(self):
        from builder.ui.widgets.dialogs import ExternalTestDialog
        dlg = ExternalTestDialog(self)
        dlg.exec()

    def _show_about(self):
        QMessageBox.about(
            self, "关于 — 文件完整性验证工具",
            "文件完整性验证工具 v1.0.0\n\n"
            "生成签名/加密的校验文件\n"
            "并打包为独立的验证器可执行程序。\n\n"
            "好用的話請到https://github.com/taichiia/Integrity-verifier打個star吧"
        )

    def _sync_project_from_steps(self):
        self._step1.sync_to_project()
        self._step2.sync_to_project()
        self._step3.sync_to_project()

    def _refresh_all_steps(self):
        self._step1.refresh_from_project()
        self._step2.refresh_from_project()
        self._step3.refresh_from_project()

    def _update_status(self):
        step_names = ["正在选择文件...", "正在生成校验...", "正在配置打包..."]
        self._status_label.setText(step_names[self._stack.currentIndex()])

    @property
    def project(self) -> ProjectData:
        return self._project

