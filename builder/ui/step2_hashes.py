import os
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton,
    QLabel, QLineEdit, QComboBox, QFileDialog, QRadioButton,
    QButtonGroup, QFrame, QMessageBox, QGroupBox, QPlainTextEdit,
    QProgressBar,
)

from shared.project import ProjectData
from shared.checksum_file import write_csv, write_sfv
from shared.crypto import (
    create_signed_payload, generate_rsa_keypair, generate_ecdsa_keypair,
)
from builder.ui.widgets.progress_panel import ProgressPanel
from builder.ui.workers.hash_worker import HashWorker
from shared.constants import (
    SPACING_MD, SPACING_LG, SPACING_XL, SPACING_SM,
    FONT_H3_SIZE, FONT_BODY_SIZE, FONT_EYEBROW_SIZE,
    DUST_TAUPE, RADIUS_HERO, RADIUS_BUTTON,
    INK_BLACK, SLATE_GRAY, LIFTED_CREAM, SIGNAL_ORANGE,
)


class Step2Hashes(QWidget):
    def __init__(self, project: ProjectData, parent=None):
        super().__init__(parent)
        self._project = project
        self._worker: HashWorker | None = None
        self._checksum_entries: list[dict] = []
        self._is_running = False
        self._is_paused = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, SPACING_MD, 0, 0)
        layout.setSpacing(SPACING_MD)

        config = QFrame()
        config.setObjectName("configBar")
        config.setStyleSheet(f"""
                background-color: {LIFTED_CREAM};
                border: 1px solid {DUST_TAUPE};
                border-radius: {RADIUS_HERO}px;
                padding: {SPACING_MD}px;
            }}
        """)
        config_layout = QHBoxLayout(config)
        config_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        config_layout.setSpacing(SPACING_MD)

        algo_label = QLabel("算法:")
        algo_label.setToolTip("哈希算法。SHA256 推荐用于通用场景，SHA512 更安全但更慢")
        config_layout.addWidget(algo_label)
        self._algo_combo = QComboBox()
        self._algo_combo.addItems(["sha256", "sha512", "md5"])
        config_layout.addWidget(self._algo_combo)

        fmt_label = QLabel("格式:")
        fmt_label.setToolTip("校验文件保存格式。CSV 可保存相对路径；SFV 仅保存文件名")
        config_layout.addWidget(fmt_label)
        self._format_csv = QRadioButton("CSV")
        self._format_csv.setChecked(True)
        self._format_sfv = QRadioButton("SFV")
        fmt_group = QButtonGroup(self)
        fmt_group.addButton(self._format_csv)
        fmt_group.addButton(self._format_sfv)
        config_layout.addWidget(self._format_csv)
        config_layout.addWidget(self._format_sfv)

        out_label = QLabel("保存到:")
        out_label.setToolTip("校验文件的输出路径")
        config_layout.addWidget(out_label)
        self._out_path = QLineEdit()
        self._out_path.setPlaceholderText("输出路径...")
        self._out_path.setToolTip("生成的校验文件 (.csv/.sfv) 的保存位置")
        config_layout.addWidget(self._out_path, 1)

        browse_btn = QPushButton("浏览...")
        browse_btn.setToolTip("选择校验文件保存位置")
        browse_btn.clicked.connect(self._browse_output)
        config_layout.addWidget(browse_btn)

        self._advanced_btn = QPushButton("⛭ 高级签名加密 ▾")
        self._advanced_btn.setProperty("cssClass", "secondary")
        self._advanced_btn.setToolTip("展开/收起数字签名和加密选项。签名可防止校验数据被篡改")
        self._advanced_btn.clicked.connect(self._toggle_advanced)
        config_layout.addWidget(self._advanced_btn)

        layout.addWidget(config)

        self._advanced_panel = QGroupBox("数字签名与加密")
        self._advanced_panel.setVisible(False)
        self._advanced_panel.setToolTip(
            "数字签名：使用私钥对校验数据签名，验证器用公钥验证，防止伪造。\n"
            "加密：使用密码加密校验数据，防止他人查看文件清单和哈希值。"
        )
        adv_layout = QVBoxLayout(self._advanced_panel)
        adv_layout.setContentsMargins(SPACING_MD, SPACING_LG, SPACING_MD, SPACING_MD)
        adv_layout.setSpacing(SPACING_SM)

        key_row = QHBoxLayout()
        key_label = QLabel("私钥文件:")
        key_label.setToolTip("加载用于签名的 PEM 格式私钥文件")
        key_label.setFixedWidth(60)
        key_row.addWidget(key_label)
        self._key_path = QLineEdit()
        self._key_path.setPlaceholderText("私钥文件路径 (.pem)...")
        self._key_path.setToolTip("签名用的私钥。对应的公钥将在打包时内嵌到验证器中")
        key_row.addWidget(self._key_path, 1)
        key_browse = QPushButton("浏览...")
        key_browse.clicked.connect(self._browse_key)
        key_row.addWidget(key_browse)
        adv_layout.addLayout(key_row)

        key_gen_row = QHBoxLayout()
        key_gen_row.addWidget(QLabel("密钥生成:"))
        gen_rsa = QPushButton("生成 RSA 密钥对")
        gen_rsa.setToolTip("生成新的 RSA 2048 位密钥对。私钥用于签名，公钥嵌入验证器用于验签")
        gen_rsa.clicked.connect(lambda: self._generate_keypair("RSA"))
        key_gen_row.addWidget(gen_rsa)
        gen_ecdsa = QPushButton("生成 ECDSA 密钥对")
        gen_ecdsa.setToolTip("生成新的 ECDSA secp256r1 密钥对。密钥更小，签名速度更快")
        gen_ecdsa.clicked.connect(lambda: self._generate_keypair("ECDSA"))
        key_gen_row.addWidget(gen_ecdsa)
        key_gen_row.addStretch()
        adv_layout.addLayout(key_gen_row)

        sig_pwd_row = QHBoxLayout()
        sig_label = QLabel("签名算法:")
        sig_label.setToolTip("数字签名算法。RSA 兼容性更好，ECDSA 密钥更小更快")
        sig_pwd_row.addWidget(sig_label)
        self._sig_combo = QComboBox()
        self._sig_combo.addItems(["RSA", "ECDSA"])
        self._sig_combo.setToolTip("选择签名算法类型。需与使用的私钥类型匹配")
        sig_pwd_row.addWidget(self._sig_combo)

        sig_pwd_row.addSpacing(SPACING_LG)

        pwd_label = QLabel("加密密码:")
        pwd_label.setToolTip("设置 AES-256-GCM 加密密码。留空则不加密校验数据")
        sig_pwd_row.addWidget(pwd_label)
        self._pwd_input = QLineEdit()
        self._pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd_input.setPlaceholderText("留空则跳过加密")
        self._pwd_input.setToolTip("密码将用于 AES-256-GCM 加密校验数据。务必妥善保管！")
        sig_pwd_row.addWidget(self._pwd_input, 1)
        adv_layout.addLayout(sig_pwd_row)

        layout.addWidget(self._advanced_panel)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(SPACING_SM)

        left_title = QLabel("• 文件清单预览")
        left_title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {INK_BLACK}; "
            f"text-transform: uppercase; letter-spacing: 0.5px;"
        )
        left_title.setToolTip("待校验的文件清单。路径基于根目录。OK=已计算 PEND=待更新 ERR=错误")
        left_layout.addWidget(left_title)

        self._manifest = QPlainTextEdit()
        self._manifest.setReadOnly(True)
        self._manifest.setToolTip("文件清单预览。格式：[状态] 哈希值  文件路径")
        left_layout.addWidget(self._manifest, 1)

        splitter.addWidget(left_widget)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(SPACING_SM)

        right_title = QLabel("• 计算进度")
        right_title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {INK_BLACK}; "
            f"text-transform: uppercase; letter-spacing: 0.5px;"
        )
        right_title.setToolTip("实时显示哈希计算进度、速度和日志")
        right_layout.addWidget(right_title)

        self._progress_panel = ProgressPanel()
        right_layout.addWidget(self._progress_panel, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)

        btn_row = QHBoxLayout()

        self._start_btn = QPushButton("▶ 开始计算")
        self._start_btn.setToolTip("开始异步计算所有勾选文件的哈希值。使用多线程并行计算")
        self._start_btn.clicked.connect(self._start_hash)
        btn_row.addWidget(self._start_btn)

        self._pause_btn = QPushButton("暂停")
        self._pause_btn.setProperty("cssClass", "secondary")
        self._pause_btn.setEnabled(False)
        self._pause_btn.setToolTip("暂停/恢复哈希计算。已计算的结果会保留")
        self._pause_btn.clicked.connect(self._toggle_pause)
        btn_row.addWidget(self._pause_btn)

        self._save_btn = QPushButton("保存校验文件")
        self._save_btn.setProperty("cssClass", "secondary")
        self._save_btn.setToolTip("将计算结果保存为 CSV 或 SFV 格式的校验文件")
        self._save_btn.clicked.connect(self._save_checksum)
        btn_row.addWidget(self._save_btn)

        btn_row.addStretch()

        self._step_complete_btn = QPushButton("✓ 完成，进入下一步")
        self._step_complete_btn.setToolTip("确认校验文件已就绪，进入打包配置步骤")
        self._step_complete_btn.clicked.connect(self._mark_complete)
        btn_row.addWidget(self._step_complete_btn)

        layout.addLayout(btn_row)

    def _mark_complete(self):
        w = self.window()
        if hasattr(w, '_step_nav'):
            w._step_nav.set_completed(1, True)
            w._step_nav.step_changed.emit(2)

    def sync_to_project(self):
        p = self._project
        p.checksum_algorithm = self._algo_combo.currentText()
        p.checksum_output_path = self._out_path.text().strip()
        p.checksum_format = "csv" if self._format_csv.isChecked() else "sfv"
        p.checksum_entries = self._checksum_entries
        p.private_key_path = self._key_path.text().strip()
        p.enable_signing = self._key_path.text().strip() != ""
        p.enable_encryption = self._pwd_input.text() != ""
        p.signature_algorithm = self._sig_combo.currentText()

    def refresh_from_project(self):
        p = self._project
        idx = self._algo_combo.findText(p.checksum_algorithm)
        if idx >= 0:
            self._algo_combo.setCurrentIndex(idx)
        self._out_path.setText(p.checksum_output_path)
        self._format_csv.setChecked(p.checksum_format != "sfv")
        self._format_sfv.setChecked(p.checksum_format == "sfv")
        self._key_path.setText(p.private_key_path)
        if p.checksum_entries:
            self._checksum_entries = p.checksum_entries
            self._update_manifest()

    def _toggle_advanced(self):
        visible = not self._advanced_panel.isVisible()
        self._advanced_panel.setVisible(visible)
        self._advanced_btn.setText(
            "⛭ 高级签名加密 ▴" if visible else "⛭ 高级签名加密 ▾"
        )

    def _browse_output(self):
        ext = ".csv" if self._format_csv.isChecked() else ".sfv"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存校验文件", f"integrity{ext}",
            f"校验文件 (*{ext});;所有文件 (*)"
        )
        if path:
            self._out_path.setText(path)

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择私钥", "",
            "PEM 文件 (*.pem);;所有文件 (*)"
        )
        if path:
            self._key_path.setText(path)

    def _generate_keypair(self, algorithm: str):
        path, _ = QFileDialog.getSaveFileName(
            self, f"保存{algorithm}私钥", f"{algorithm.lower()}_private.pem",
            "PEM 文件 (*.pem);;所有文件 (*)"
        )
        if not path:
            return

        try:
            if algorithm == "RSA":
                kp = generate_rsa_keypair()
            else:
                kp = generate_ecdsa_keypair()

            with open(path, "wb") as f:
                f.write(kp.private_pem)
            pub_path = path.replace(".pem", "_public.pem").replace("_private", "_public")
            with open(pub_path, "wb") as f:
                f.write(kp.public_pem)
            self._key_path.setText(path)
            self._progress_panel.log_success(f"{algorithm} 密钥对已生成")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"密钥生成失败:\n{e}")

    def _start_hash(self):
        entries = self._project.checksum_entries
        if not entries:
            QMessageBox.information(
                self, "无文件",
                "请先回到「选择文件」步骤添加文件。\n\n"
                "提示：选择根目录后系统会自动扫描所有文件。"
            )
            return

        paths = []
        base = self._project.base_directory
        for entry in entries:
            path = entry["path"]
            if base and not os.path.isabs(path):
                path = os.path.join(base, path)
            if os.path.isfile(path):
                paths.append(path)

        if not paths:
            QMessageBox.warning(self, "无有效文件", "清单中的文件在磁盘上均不存在。")
            return

        self._is_running = True
        self._is_paused = False
        self._start_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)
        self._pause_btn.setText("暂停")
        self._checksum_entries.clear()

        self._progress_panel.clear()
        self._progress_panel.log_info(f"开始计算 {len(paths):,} 个文件的哈希值...")
        self._progress_panel.log_info(f"算法: {self._algo_combo.currentText()}")
        self._progress_panel.log_info(f"线程数: {max(1, (os.cpu_count() or 4) - 1)}")

        self._worker = HashWorker(paths, algorithm=self._algo_combo.currentText())
        self._worker.progress.connect(self._on_progress)
        self._worker.speed.connect(self._on_speed)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _toggle_pause(self):
        if not self._worker:
            return
        if self._is_paused:
            self._worker.resume_worker()
            self._is_paused = False
            self._pause_btn.setText("暂停")
            self._progress_panel.log_info("已恢复计算")
        else:
            self._worker.pause()
            self._is_paused = True
            self._pause_btn.setText("继续")
            self._progress_panel.log_info("已暂停 — 当前批次完成后将停止")

    def _on_progress(self, completed: int, total: int, path: str):
        self._progress_panel.set_progress(completed, total)
        self._progress_panel.set_current_file(path)

    def _on_speed(self, fps: float):
        self._progress_panel.set_speed(fps)

    def _on_file_done(self, path: str, digest: str, error: str):
        rel_path = path
        base = self._project.base_directory
        if base:
            try:
                rel_path = os.path.relpath(path, base)
            except ValueError:
                pass

        if error:
            self._checksum_entries.append({"path": rel_path, "hash": "", "status": "error"})
            self._progress_panel.log_warning(f"{rel_path}: {error}")
        else:
            self._checksum_entries.append({"path": rel_path, "hash": digest, "status": "ok"})

    def _on_finished(self, results: list):
        self._is_running = False
        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)

        ok_count = sum(1 for e in self._checksum_entries if e["status"] == "ok")
        err_count = sum(1 for e in self._checksum_entries if e["status"] == "error")
        self._progress_panel.log_success(f"完成: {ok_count:,} 文件已哈希, {err_count} 错误")
        self._update_manifest()

        out = self._out_path.text().strip()
        if out and ok_count > 0:
            self._save_checksum()

    def _on_error(self, msg: str):
        self._progress_panel.log_error(msg)

    def _update_manifest(self):
        lines = []
        for e in self._checksum_entries:
            status = " OK " if e["status"] == "ok" else "ERR " if e["status"] == "error" else "PEND"
            lines.append(f"[{status}] {e['hash']}  {e['path']}")
        self._manifest.setPlainText("\n".join(lines) if lines else "暂无数据 — 请点击「开始计算」")

    def _save_checksum(self):
        out = self._out_path.text().strip()
        if not out:
            self._browse_output()
            out = self._out_path.text().strip()
            if not out:
                return

        ok_entries = [(e["path"], e["hash"]) for e in self._checksum_entries if e["status"] == "ok"]
        if not ok_entries:
            QMessageBox.warning(self, "无数据", "没有成功计算的文件可保存。")
            return

        try:
            fmt = "csv" if self._format_csv.isChecked() else "sfv"
            if fmt == "csv":
                write_csv(ok_entries, out, self._algo_combo.currentText())
            else:
                write_sfv(ok_entries, out)
            self._progress_panel.log_success(f"校验文件已保存: {out}")

            key_path = self._key_path.text().strip()
            if key_path:
                self._sign_and_encrypt(out, key_path)
        except Exception as e:
            QMessageBox.critical(self, "保存错误", str(e))

    def _sign_and_encrypt(self, checksum_path: str, key_path: str):
        try:
            with open(key_path, "rb") as f:
                private_key_pem = f.read()
            with open(checksum_path, "rb") as f:
                data = f.read()

            payload = create_signed_payload(
                {"checksum_data": data.hex(), "file": os.path.basename(checksum_path)},
                private_key_pem,
                self._sig_combo.currentText(),
            )

            password = self._pwd_input.text()
            if password:
                from shared.crypto import aes_encrypt
                from hashlib import sha256
                key = sha256(password.encode()).digest()
                payload = aes_encrypt(payload, key)

            signed_path = checksum_path + ".signed"
            with open(signed_path, "wb") as f:
                f.write(payload)
            self._progress_panel.log_success(f"已签名: {signed_path}")
        except Exception as e:
            self._progress_panel.log_error(f"签名失败: {e}")

