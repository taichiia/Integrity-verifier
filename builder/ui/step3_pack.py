import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QRadioButton, QButtonGroup, QComboBox,
    QMessageBox, QFrame, QScrollArea, QPlainTextEdit, QInputDialog,
)
from shared.project import ProjectData
from shared.constants import (
    SPACING_MD, SPACING_LG, SPACING_SM,
    FONT_H2_SIZE, FONT_H3_SIZE, FONT_BODY_SIZE, FONT_EYEBROW_SIZE,
    SUCCESS_GREEN, ERROR_RED, WARNING_AMBER,
    SLATE_GRAY, INK_BLACK, LIFTED_CREAM, DUST_TAUPE, SIGNAL_ORANGE,
    RADIUS_HERO,
)
from builder.ui.widgets.card_widget import CardWidget
from builder.ui.workers.verify_worker import VerifyWorker
from builder.ui.workers.pack_worker import PackWorker


class Step3Pack(QWidget):
    def __init__(self, project: ProjectData, parent=None):
        super().__init__(parent)
        self._project = project
        self._verify_worker: VerifyWorker | None = None
        self._sim_passed = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, SPACING_MD, 0, 0)
        outer_layout.setSpacing(SPACING_MD)

        title = QLabel("打包验证器")
        title.setProperty("cssClass", "h2")
        title.setToolTip("配置验证器外观、路径规则和安全选项，打包为独立可执行文件")
        outer_layout.addWidget(title)

        desc = QLabel("将校验数据和验证逻辑打包为独立的客户端 EXE 程序。打包前必须执行模拟验证。")
        desc.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_BODY_SIZE}px;")
        desc.setWordWrap(True)
        outer_layout.addWidget(desc)

        card_grid = QHBoxLayout()
        card_grid.setSpacing(SPACING_LG)

        left_col = QVBoxLayout()
        left_col.setSpacing(SPACING_MD)

        self._appearance_card = CardWidget("外观定制")
        self._setup_appearance_card()
        left_col.addWidget(self._appearance_card)

        self._path_card = CardWidget("路径规则")
        self._setup_path_card()
        left_col.addWidget(self._path_card)

        self._security_card = CardWidget("安全与保护")
        self._setup_security_card()
        left_col.addWidget(self._security_card)

        left_col.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(SPACING_MD)

        self._checklist_card = CardWidget("校验清单")
        self._setup_checklist_card()
        right_col.addWidget(self._checklist_card)

        self._sim_card = CardWidget("模拟验证（预检）")
        self._setup_simulation_card()
        right_col.addWidget(self._sim_card)

        right_col.addStretch()

        card_grid.addLayout(left_col, 1)
        card_grid.addLayout(right_col, 1)
        outer_layout.addLayout(card_grid, 1)

        from PySide6.QtWidgets import QProgressBar
        self._build_progress = QProgressBar()
        self._build_progress.setRange(0, 100)
        self._build_progress.setValue(0)
        self._build_progress.setVisible(False)
        self._build_progress.setToolTip("PyInstaller 打包进度")
        outer_layout.addWidget(self._build_progress)

        self._build_status = QLabel("")
        self._build_status.setStyleSheet(f"font-size: {FONT_EYEBROW_SIZE}px; font-weight: 500;")
        self._build_status.setVisible(False)
        self._build_status.setWordWrap(True)
        outer_layout.addWidget(self._build_status)

        bottom = QHBoxLayout()
        bottom.addStretch()

        self._save_proj_btn = QPushButton("保存项目")
        self._save_proj_btn.setProperty("cssClass", "secondary")
        self._save_proj_btn.setToolTip("将当前所有配置保存到 .fvp 项目文件")
        self._save_proj_btn.clicked.connect(self._save_project)
        bottom.addWidget(self._save_proj_btn)

        self._pack_btn = QPushButton("← 打包生成验证器")
        self._pack_btn.setEnabled(False)
        self._pack_btn.setToolTip(
            "将验证器打包为独立 EXE。\n"
            "⚠ 必须先通过模拟验证才能启用此按钮。\n"
            "打包过程中请勿关闭窗口。"
        )
        self._pack_btn.clicked.connect(self._do_pack)
        bottom.addWidget(self._pack_btn)

        outer_layout.addLayout(bottom)
        scroll.setWidget(outer)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        self._pack_worker: PackWorker | None = None

    def _setup_appearance_card(self):
        cw = self._appearance_card.content_widget()
        layout = cw.layout()

        row = QHBoxLayout()
        lab = QLabel("窗口标题:")
        lab.setToolTip("验证器窗口顶部显示的标题文字")
        row.addWidget(lab)
        self._title_edit = QLineEdit("文件完整性验证器")
        self._title_edit.setToolTip("显示在验证器窗口标题栏的名称")
        row.addWidget(self._title_edit, 1)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        lab2 = QLabel("图标 (.ico):")
        lab2.setToolTip("验证器 EXE 文件的图标。留空使用默认图标")
        row2.addWidget(lab2)
        self._icon_edit = QLineEdit()
        self._icon_edit.setPlaceholderText("图标文件路径（可选）...")
        self._icon_edit.setToolTip(".ico 格式的图标文件路径")
        row2.addWidget(self._icon_edit, 1)
        icon_btn = QPushButton("浏览...")
        icon_btn.clicked.connect(lambda: self._browse_file(self._icon_edit, "图标", "*.ico;;*.*"))
        row2.addWidget(icon_btn)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        lab3 = QLabel("版本号:")
        lab3.setToolTip("验证器的版本号，显示在标题栏")
        row3.addWidget(lab3)
        self._ver_edit = QLineEdit("1.0.0.0")
        row3.addWidget(self._ver_edit, 1)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        lab4 = QLabel("公司名称:")
        lab4.setToolTip("可选的公司/组织名称，嵌入到 EXE 元数据中")
        row4.addWidget(lab4)
        self._company_edit = QLineEdit()
        self._company_edit.setPlaceholderText("公司名称（可选）")
        row4.addWidget(self._company_edit, 1)
        layout.addLayout(row4)

        row5 = QHBoxLayout()
        lab5 = QLabel("版权信息:")
        lab5.setToolTip("版权声明文字，嵌入到 EXE 元数据中")
        row5.addWidget(lab5)
        self._copyright_edit = QLineEdit()
        self._copyright_edit.setPlaceholderText("版权声明（可选）")
        row5.addWidget(self._copyright_edit, 1)
        layout.addLayout(row5)

    def _setup_path_card(self):
        cw = self._path_card.content_widget()
        layout = cw.layout()

        hint = QLabel("验证器启动时自动定位目标文件的规则")
        hint.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._path_group = QButtonGroup(self)
        paths = [
            ("验证器所在目录", "current_dir", "验证器 EXE 所在的文件夹"),
            ("验证器下的子文件夹", "subfolder", "验证器 EXE 所在目录下的子文件夹"),
            ("自定义路径模板", "custom_template", "使用环境变量自定义路径（如 %ProgramData%\\App）"),
        ]
        for label, value, tip in paths:
            rb = QRadioButton(label)
            rb.setToolTip(tip)
            self._path_group.addButton(rb)
            layout.addWidget(rb)

        self._subfolder_edit = QLineEdit()
        self._subfolder_edit.setPlaceholderText("子文件夹名（如 data）")
        self._subfolder_edit.setToolTip("验证器所在目录下的子文件夹名称")
        layout.addWidget(self._subfolder_edit)

        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("如 %ProgramData%\\MyApp\\data")
        self._custom_edit.setToolTip("支持 %ProgramData%、%AppData% 等 Windows 环境变量")
        layout.addWidget(self._custom_edit)

        env_hint = QLabel("支持 %ProgramData%、%AppData%、%USERPROFILE% 等环境变量")
        env_hint.setStyleSheet(f"color: {SLATE_GRAY}; font-size: 10px;")
        env_hint.setWordWrap(True)
        layout.addWidget(env_hint)

    def _setup_security_card(self):
        cw = self._security_card.content_widget()
        layout = cw.layout()

        self._embed_cb = QCheckBox("内嵌校验数据并加密")
        self._embed_cb.setChecked(True)
        self._embed_cb.setToolTip("将校验文件内容加密后嵌入验证器 EXE，防止被外部查看或修改")
        layout.addWidget(self._embed_cb)

        self._sig_cb = QCheckBox("启用数字签名验证")
        self._sig_cb.setChecked(True)
        self._sig_cb.setToolTip("验证器启动时使用公钥验证校验数据的签名，确保数据未被篡改")
        layout.addWidget(self._sig_cb)

        self._antidebug_cb = QCheckBox("启用反调试保护")
        self._antidebug_cb.setToolTip("检测调试器附着，使用加权评分系统，不会误伤合法用户")
        layout.addWidget(self._antidebug_cb)

        self._antisanbox_cb = QCheckBox("启用反沙箱检测")
        self._antisanbox_cb.setToolTip("检测虚拟机/沙箱环境，发现时询问用户是否继续，不会直接退出")
        layout.addWidget(self._antisanbox_cb)

    def _setup_checklist_card(self):
        cw = self._checklist_card.content_widget()
        layout = cw.layout()

        row = QHBoxLayout()
        lab = QLabel("当前清单:")
        lab.setToolTip("选择要使用的校验清单。可管理多套清单用于不同版本")
        row.addWidget(lab)
        self._checklist_combo = QComboBox()
        self._checklist_combo.setToolTip("切换不同的校验清单。每套清单对应一组校验文件数据")
        self._checklist_combo.currentTextChanged.connect(self._on_checklist_changed)
        row.addWidget(self._checklist_combo, 1)
        layout.addLayout(row)

        self._cl_info = QLabel("文件数: 0 | 状态: 未就绪")
        self._cl_info.setStyleSheet(f"color: {SLATE_GRAY}; font-size: {FONT_EYEBROW_SIZE}px;")
        self._cl_info.setToolTip("当前清单的统计信息")
        layout.addWidget(self._cl_info)

        btn_row = QHBoxLayout()
        edit_btn = QPushButton("编辑")
        edit_btn.setProperty("cssClass", "secondary")
        edit_btn.setToolTip("查看/编辑当前清单中的文件列表")
        edit_btn.clicked.connect(self._edit_checklist)
        btn_row.addWidget(edit_btn)
        add_btn = QPushButton("新建")
        add_btn.setProperty("cssClass", "secondary")
        add_btn.setToolTip("创建新的校验清单（需先生成校验文件）")
        add_btn.clicked.connect(self._new_checklist)
        btn_row.addWidget(add_btn)
        del_btn = QPushButton("删除")
        del_btn.setProperty("cssClass", "secondary")
        del_btn.setToolTip("删除当前选中的校验清单")
        del_btn.clicked.connect(self._delete_checklist)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

    def _on_checklist_changed(self, name: str):
        if not name:
            return
        self._project.verifier_active_checklist = name
        self._update_checklist_info()

    def _update_checklist_info(self):
        name = self._checklist_combo.currentText()
        if not name:
            return
        checklists = self._project.verifier_checklists
        entries = checklists.get(name, [])
        n = len(entries)
        has_entries = self._project.checksum_entries and len(self._project.checksum_entries) > 0
        ok_count = sum(1 for e in entries if e.get("status") == "ok") if entries else 0
        if ok_count > 0:
            self._cl_info.setText(f"文件数: {n} | 状态: 已就绪 ({ok_count} 已计算)")
        elif has_entries:
            self._cl_info.setText(f"文件数: {n} | 状态: 待生成")
        else:
            self._cl_info.setText(f"文件数: {n} | 状态: 未就绪")

    def _edit_checklist(self):
        entries = self._project.checksum_entries
        if not entries:
            QMessageBox.information(
                self, "校验清单为空",
                "当前还没有校验数据。\n\n"
                "请先回到「生成校验文件」步骤计算哈希值，\n"
                "或从步骤一重新选择文件后完成哈希计算。"
            )
            return
        from builder.ui.widgets.dialogs import ChecklistEditDialog
        dlg = ChecklistEditDialog(entries, self)
        if dlg.exec():
            self._project.checksum_entries = dlg.get_entries()
            self._update_checklist_info()
            QMessageBox.information(self, "已保存", "校验清单已更新。")

    def _new_checklist(self):
        name, ok = QInputDialog.getText(
            self, "新建校验清单",
            "请输入清单名称:",
            text=""
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._project.verifier_checklists:
            QMessageBox.warning(self, "名称重复", f"清单「{name}」已存在。")
            return
        self._project.verifier_checklists[name] = []
        self._checklist_combo.addItem(name)
        self._checklist_combo.setCurrentText(name)

    def _delete_checklist(self):
        name = self._checklist_combo.currentText()
        if not name:
            return
        if name == "默认":
            QMessageBox.warning(self, "无法删除", "默认清单不可删除。")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除校验清单「{name}」吗？\n\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._project.verifier_checklists.pop(name, None)
        idx = self._checklist_combo.findText(name)
        if idx >= 0:
            self._checklist_combo.removeItem(idx)
        self._project.verifier_active_checklist = self._checklist_combo.currentText()

    def _setup_simulation_card(self):
        cw = self._sim_card.content_widget()
        layout = cw.layout()

        hint = QLabel("打包前必须运行模拟验证，确保校验清单与实际文件一致")
        hint.setStyleSheet(f"color: {SIGNAL_ORANGE}; font-size: {FONT_EYEBROW_SIZE}px; font-weight: 500;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        lab = QLabel("测试目录:")
        lab.setToolTip("用于模拟验证的测试目标路径。应包含待校验的文件")
        row.addWidget(lab)
        self._sim_path = QLineEdit()
        self._sim_path.setPlaceholderText("模拟验证的目标目录...")
        self._sim_path.setToolTip("选择一个目录来模拟运行验证流程，检查文件完整性")
        row.addWidget(self._sim_path, 1)
        sim_browse = QPushButton("浏览...")
        sim_browse.clicked.connect(lambda: self._browse_dir(self._sim_path))
        row.addWidget(sim_browse)
        layout.addLayout(row)

        self._sim_run_btn = QPushButton("▶ 开始模拟验证")
        self._sim_run_btn.setToolTip("使用当前校验清单对目标目录执行模拟验证。结果必须在打包前通过")
        self._sim_run_btn.clicked.connect(self._run_simulation)
        layout.addWidget(self._sim_run_btn)

        self._sim_status = QLabel("未执行")
        self._sim_status.setStyleSheet(f"font-size: {FONT_BODY_SIZE}px; font-weight: 500;")
        layout.addWidget(self._sim_status)

        self._sim_detail = QPlainTextEdit()
        self._sim_detail.setReadOnly(True)
        self._sim_detail.setMaximumHeight(120)
        self._sim_detail.setToolTip("模拟验证的详细结果。通过/失败/缺失/多余文件的统计")
        layout.addWidget(self._sim_detail)

        row2 = QHBoxLayout()
        self._ext_test_btn = QPushButton("加载外部校验文件测试...")
        self._ext_test_btn.setProperty("cssClass", "secondary")
        self._ext_test_btn.setToolTip("不依赖当前项目，直接加载 .csv/.sha256 文件进行对比验证")
        self._ext_test_btn.clicked.connect(self._external_test)
        row2.addWidget(self._ext_test_btn)
        layout.addLayout(row2)

    def _browse_file(self, edit: QLineEdit, title: str, filter_str: str):
        path, _ = QFileDialog.getOpenFileName(self, f"选择{title}", "", filter_str)
        if path:
            edit.setText(path)

    def _browse_dir(self, edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            edit.setText(path)

    def _save_project(self):
        self.sync_to_project()
        w = self.window()
        if hasattr(w, '_save_project'):
            w._save_project()
        else:
            QMessageBox.warning(self, "无法保存", "无法访问主窗口的保存功能。")

    def sync_to_project(self):
        p = self._project
        p.verifier_title = self._title_edit.text().strip()
        p.verifier_icon_path = self._icon_edit.text().strip()
        p.verifier_version = self._ver_edit.text().strip()
        p.verifier_company = self._company_edit.text().strip()
        p.verifier_copyright = self._copyright_edit.text().strip()

        checked = self._path_group.checkedButton()
        if checked:
            for label, value, _ in [
                ("验证器所在目录", "current_dir", ""),
                ("验证器下的子文件夹", "subfolder", ""),
                ("自定义路径模板", "custom_template", ""),
            ]:
                if checked.text() == label:
                    p.verifier_path_rule = value
                    break

        p.verifier_subfolder = self._subfolder_edit.text().strip()
        p.verifier_custom_template = self._custom_edit.text().strip()
        p.verifier_embed_encrypted = self._embed_cb.isChecked()
        p.verifier_enable_signature_verify = self._sig_cb.isChecked()
        p.verifier_enable_antidebug = self._antidebug_cb.isChecked()
        p.verifier_enable_antisanbox = self._antisanbox_cb.isChecked()

        active = self._checklist_combo.currentText()
        if active:
            p.verifier_active_checklist = active
            p.verifier_checklists[active] = p.checksum_entries

    def refresh_from_project(self):
        p = self._project
        self._title_edit.setText(p.verifier_title)
        self._icon_edit.setText(p.verifier_icon_path)
        self._ver_edit.setText(p.verifier_version)
        self._company_edit.setText(p.verifier_company)
        self._copyright_edit.setText(p.verifier_copyright)
        self._embed_cb.setChecked(p.verifier_embed_encrypted)
        self._sig_cb.setChecked(p.verifier_enable_signature_verify)
        self._antidebug_cb.setChecked(p.verifier_enable_antidebug)
        self._antisanbox_cb.setChecked(p.verifier_enable_antisanbox)

        self._checklist_combo.blockSignals(True)
        self._checklist_combo.clear()
        checklists = p.verifier_checklists
        if not checklists:
            checklists["默认"] = []
            p.verifier_checklists = checklists
        for name in checklists:
            self._checklist_combo.addItem(name)
        active = p.verifier_active_checklist or "默认"
        idx = self._checklist_combo.findText(active)
        if idx >= 0:
            self._checklist_combo.setCurrentIndex(idx)
        self._checklist_combo.blockSignals(False)
        self._update_checklist_info()

    def _run_simulation(self):
        target = self._sim_path.text().strip()
        if not target or not os.path.isdir(target):
            QMessageBox.warning(self, "路径无效", "请选择用于模拟验证的有效目录。")
            return

        entries = self._project.checksum_entries
        ok_entries = [e for e in entries if e.get("status") == "ok"]
        if not ok_entries:
            QMessageBox.warning(
                self, "无校验数据",
                "请先在「生成校验文件」步骤中计算哈希值。\n"
                "只有成功计算的条目才能用于验证。"
            )
            return

        self._sim_run_btn.setEnabled(False)
        self._sim_status.setText("正在模拟验证...")
        self._sim_status.setStyleSheet(f"font-size: {FONT_BODY_SIZE}px; font-weight: 500;")

        self._verify_worker = VerifyWorker(
            ok_entries, target, self._project.checksum_algorithm
        )
        self._verify_worker.finished.connect(self._on_sim_finished)
        self._verify_worker.error_occurred.connect(self._on_sim_error)
        self._verify_worker.start()

    def _on_sim_finished(self, report: dict):
        self._sim_run_btn.setEnabled(True)
        passed = report["passed"]
        failed = report["failed"]
        missing = report["missing"]
        extra = report.get("extra_count", 0)
        total = report["total"]
        all_pass = (failed == 0 and missing == 0)

        if all_pass:
            self._sim_passed = True
            self._pack_btn.setEnabled(True)
            self._sim_status.setText(f"✓ 验证通过 — {passed:,} / {total:,} 文件一致")
            self._sim_status.setStyleSheet(
                f"font-size: {FONT_BODY_SIZE}px; font-weight: 700; color: {SUCCESS_GREEN};"
            )
        else:
            self._sim_passed = False
            self._pack_btn.setEnabled(False)
            self._sim_status.setText(
                f"✗ 存在问题 — 通过:{passed} 失败:{failed} 缺失:{missing} 多余:{extra}"
            )
            self._sim_status.setStyleSheet(
                f"font-size: {FONT_BODY_SIZE}px; font-weight: 700; color: {ERROR_RED};"
            )

        lines = [f"总计条目: {total}"]
        lines.append(f"通过: {passed}  |  失败: {failed}  |  缺失: {missing}  |  多余: {extra}")
        if failed > 0 or missing > 0:
            lines.append("")
            lines.append("异常详情:")
            for d in report["details"]:
                if d["status"] in ("fail", "missing"):
                    lines.append(f"  [{d['status'].upper()}] {d['path']}")
        self._sim_detail.setPlainText("\n".join(lines))

    def _on_sim_error(self, msg: str):
        self._sim_run_btn.setEnabled(True)
        self._sim_status.setText(f"错误: {msg}")
        self._sim_status.setStyleSheet(f"color: {ERROR_RED};")

    def _external_test(self):
        from builder.ui.widgets.dialogs import ExternalTestDialog
        dlg = ExternalTestDialog(self)
        if dlg.exec():
            vals = dlg.get_values()
            cs_path = vals["checksum_path"]
            target_dir = vals["target_dir"]
            algo = vals["algorithm"]
            if not cs_path or not target_dir:
                return
            try:
                if cs_path.lower().endswith(".csv"):
                    _, entries = __import__("shared.checksum_file", fromlist=["read_csv"]).read_csv(cs_path)
                else:
                    entries = __import__("shared.checksum_file", fromlist=["read_sfv"]).read_sfv(cs_path)

                checksum_entries = [
                    {"path": p, "hash": h, "status": "ok"}
                    for p, h in (entries if isinstance(entries[0], tuple) else [(e[0], e[1]) for e in entries])
                ]
                self._sim_path.setText(target_dir)
                self._project.checksum_entries = checksum_entries
                self._project.checksum_algorithm = algo
                self._run_simulation()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载校验文件失败:\n{e}")

    def _do_pack(self):
        from builder.ui.widgets.dialogs import PackOptionsDialog
        dlg = PackOptionsDialog(self)
        if not dlg.exec():
            return

        vals = dlg.get_values()
        self.sync_to_project()
        p = self._project

        ok_entries = [e for e in p.checksum_entries if e.get("status") == "ok"]
        if not ok_entries:
            QMessageBox.warning(
                self, "无校验数据",
                "没有成功计算的校验文件，无法打包。\n\n"
                "请先回到「生成校验文件」步骤计算哈希值。"
            )
            return

        project_dict = {
            "checksum_entries": p.checksum_entries,
            "checksum_algorithm": p.checksum_algorithm,
            "output_path": vals.get("output_path", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output")),
            "verifier_title": p.verifier_title or "文件完整性验证器",
            "verifier_version": p.verifier_version or "1.0.0.0",
            "verifier_path_rule": p.verifier_path_rule or "current_dir",
            "verifier_subfolder": p.verifier_subfolder or "",
            "verifier_custom_template": p.verifier_custom_template or "",
            "icon_path": p.verifier_icon_path or "",
        }

        self._build_progress.setVisible(True)
        self._build_progress.setValue(0)
        self._build_status.setVisible(True)
        self._build_status.setText("正在启动 PyInstaller 打包...")
        self._build_status.setStyleSheet(f"font-size: {FONT_EYEBROW_SIZE}px; font-weight: 500;")
        self._pack_btn.setEnabled(False)

        self._pack_worker = PackWorker(project_dict)
        self._pack_worker.progress.connect(self._on_build_progress)
        self._pack_worker.finished.connect(self._on_build_finished)
        self._pack_worker.error_occurred.connect(self._on_build_error)
        self._pack_worker.start()

    def _on_build_progress(self, pct: int, status: str):
        self._build_progress.setValue(pct)
        self._build_status.setText(status)

    def _on_build_finished(self, output_path: str):
        self._build_progress.setValue(100)
        self._build_status.setText(f"打包完成! 输出: {output_path}")
        self._build_status.setStyleSheet(
            f"font-size: {FONT_BODY_SIZE}px; font-weight: 700; color: {SUCCESS_GREEN};"
        )
        self._pack_btn.setEnabled(True)
        QMessageBox.information(
            self, "打包完成",
            f"验证器已成功打包为单个 EXE 文件!\n\n"
            f"输出路径:\n{output_path}\n\n"
            f"此 EXE 文件已包含所有依赖和校验数据，\n可直接分发给用户运行。"
        )

    def _on_build_error(self, msg: str):
        self._build_progress.setValue(0)
        self._build_status.setText(f"打包失败: {msg}")
        self._build_status.setStyleSheet(
            f"font-size: {FONT_BODY_SIZE}px; font-weight: 700; color: {ERROR_RED};"
        )
        self._pack_btn.setEnabled(True)
        QMessageBox.critical(self, "打包失败", f"验证器打包过程中出现错误:\n\n{msg}")

