import os
import json
import re
import sys
import subprocess
import tempfile
import logging
import zlib

from PySide6.QtCore import QThread, Signal
from PyInstaller.__main__ import run as run_pyinstaller


def resolve_hooks_dir() -> str:
    """Locate the PyInstaller hook pack for the current run mode.

    The hooks live in ``<repo>/build_hooks`` (one level above ``builder``);
    an early version pointed at ``<repo>/builder/build_hooks``, silently
    skipping the Qt trimming hooks and adding ~17 MB to every packed verifier.
    """
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "build_hooks")
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "..",
        "build_hooks",
    ))


class PackWorker(QThread):
    progress = Signal(int, str)
    # QThread already owns ``finished``; using it here made the no-argument
    # QThread.finished emission call the slot that expects an output path.
    completed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, project_data: dict, parent=None):
        super().__init__(parent)
        self._project = project_data
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if getattr(sys, "frozen", False):
                verifier_dir = os.path.join(sys._MEIPASS, "verifier")
            else:
                verifier_dir = os.path.normpath(os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "..", "verifier",
                ))
            verifier_main = os.path.join(verifier_dir, "main.py")

            if not os.path.isfile(verifier_main):
                self.error_occurred.emit(f"未找到验证器源码: {verifier_main}")
                return

            self.progress.emit(5, "准备验证器源码...")

            embedded_data_path = os.path.join(verifier_dir, "_embedded_data.py")
            self._write_embedded_data(embedded_data_path)

            self.progress.emit(10, "启动 PyInstaller 打包...")

            output_dir = self._project.get("output_path", "")
            if not output_dir or not os.path.isdir(output_dir):
                output_dir = os.path.dirname(verifier_dir)
            os.makedirs(output_dir, exist_ok=True)

            hooks_dir = resolve_hooks_dir()

            with tempfile.TemporaryDirectory(prefix="fit_build_") as build_tmp:
                pre_name_args = []
                if os.path.isdir(hooks_dir):
                    pre_name_args.append(f"--additional-hooks-dir={hooks_dir}")

                for module in [
                    "PySide6.QtNetwork",
                    "PySide6.QtOpenGL",
                    "PySide6.QtPdf",
                    "PySide6.QtQml",
                    "PySide6.QtQuick",
                    "PySide6.QtSvg",
                    "PySide6.QtVirtualKeyboard",
                    # The client verifier never builds anything, so PyInstaller
                    # and its hooks only add ~14 MB to the shipped EXE.
                    "PyInstaller",
                    "PyInstaller.hooks",
                ]:
                    pre_name_args.append(f"--exclude-module={module}")

                icon_path = self._project.get("icon_path", "")
                if icon_path and os.path.isfile(icon_path):
                    pre_name_args.append(f"--icon={icon_path}")

                if os.name == "nt":
                    version_file = os.path.join(build_tmp, "verifier_version.py")
                    self._write_version_file(version_file)
                    pre_name_args.append(f"--version-file={version_file}")

                pyi_args = [
                    "--onefile",
                    "--noconsole",
                    "--clean",
                    *pre_name_args,
                    "--name", "FileIntegrityVerifier",
                    "--distpath", output_dir,
                    "--workpath", os.path.join(build_tmp, "build"),
                    "--specpath", os.path.join(build_tmp, "spec"),
                    verifier_main,
                ]

                if getattr(sys, "frozen", False):
                    returncode, output_lines = self._run_pyinstaller_in_process(pyi_args)
                else:
                    returncode, output_lines = self._run_pyinstaller_subprocess(pyi_args, verifier_dir)

            if returncode != 0:
                self.error_occurred.emit(
                    f"PyInstaller 打包失败 (退出码 {returncode}):\n" +
                    "\n".join(output_lines[-20:])
                )
                return

            self.progress.emit(100, "打包完成!")

            exe_path = os.path.join(output_dir, "FileIntegrityVerifier.exe")
            if os.path.isfile(exe_path):
                self.progress.emit(98, "写入 EXE 自校验数据...")
                self._apply_self_integrity(exe_path)
                if self._project.get("generate_fitrec", False):
                    self._generate_fitrec(exe_path)
                self.completed.emit(exe_path)
            else:
                for f in os.listdir(output_dir):
                    if f.endswith(".exe"):
                        self.completed.emit(os.path.join(output_dir, f))
                        return
                self.completed.emit(output_dir)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _generate_fitrec(self, exe_path: str):
        from shared.fitrec_bridge import build_fit_document, run_fitrec_generate

        checklists = self._project.get("verifier_checklists") or {}
        active_checklist = self._project.get("verifier_active_checklist") or ""
        checksum_entries = self._project.get("checksum_entries") or []
        if not checklists:
            checklists = {"default": checksum_entries}
            active_checklist = active_checklist or "default"
        if active_checklist not in checklists:
            active_checklist = next(iter(checklists))

        document = build_fit_document(
            checklists,
            active_checklist,
            self._project.get("checksum_algorithm", "sha256"),
            self._project.get("exclude_paths") or [],
            self._project.get("exclude_rules") or {},
            self._project.get("base_directory") or "",
            self._project.get("fitrec_data_shards", 8),
            self._project.get("fitrec_parity_shards", 4),
        )
        record_path = os.path.splitext(exe_path)[0] + ".fitrec"
        key_path = self._project.get("fitrec_private_key_path", "")
        self.progress.emit(99, "正在生成 .fitrec 恢复文件...")
        run_fitrec_generate(document, record_path, key_path)

    def _apply_self_integrity(self, exe_path: str) -> None:
        from shared.protection import append_self_integrity

        append_self_integrity(
            exe_path,
            self._project.get("private_key_pem") or None,
            self._project.get("signature_algorithm", "RSA"),
        )

    def _write_version_file(self, path: str) -> None:
        """Create a Windows version resource for the packed verifier."""
        raw_parts = re.findall(
            r"\d+",
            str(self._project.get("verifier_version", "1.0.0.0")),
        )[:4]
        parts = [min(int(part), 65535) for part in raw_parts]
        parts.extend([0] * (4 - len(parts)))
        company = str(self._project.get("verifier_company", "")).strip()
        copyright_text = str(self._project.get("verifier_copyright", "")).strip()
        product_name = str(self._project.get("verifier_title", "")).strip()

        contents = "\n".join([
            "VSVersionInfo(",
            "    ffi=FixedFileInfo(",
            f"        filevers=({', '.join(map(str, parts))}),",
            f"        prodvers=({', '.join(map(str, parts))}),",
            "        mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,",
            "        subtype=0x0, date=(0, 0)",
            "    ),",
            "    kids=[",
            "        StringFileInfo([",
            "            StringTable('040904B0', [",
            f"                StringStruct('CompanyName', {json.dumps(company)}),",
            f"                StringStruct('FileDescription', {json.dumps(product_name)}),",
            f"                StringStruct('FileVersion', {json.dumps(self._project.get('verifier_version', '1.0.0.0'))}),",
            f"                StringStruct('LegalCopyright', {json.dumps(copyright_text)}),",
            f"                StringStruct('ProductName', {json.dumps(product_name)}),",
            f"                StringStruct('ProductVersion', {json.dumps(self._project.get('verifier_version', '1.0.0.0'))}),",
            "            ])",
            "        ]),",
            "        VarFileInfo([VarStruct('Translation', [1033, 1200])]),",
            "    ]",
            ")",
        ])
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(contents)

    def _run_pyinstaller_subprocess(self, pyi_args: list[str], cwd: str) -> tuple[int, list[str]]:
        cmd = [sys.executable, "-m", "PyInstaller", *pyi_args]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        output_lines = []
        for line in process.stdout:
            if self._cancelled:
                process.terminate()
                return 1, output_lines

            stripped = line.strip()
            output_lines.append(stripped)
            self._emit_progress_from_line(stripped)

        return process.wait(), output_lines

    def _run_pyinstaller_in_process(self, pyi_args: list[str]) -> tuple[int, list[str]]:
        output_lines = []

        class SignalLogHandler(logging.Handler):
            def __init__(self, worker):
                super().__init__(logging.INFO)
                self.worker = worker

            def emit(self, record):
                stripped = record.getMessage().strip()
                output_lines.append(stripped)
                self.worker._emit_progress_from_line(stripped)

        handler = SignalLogHandler(self)
        pyi_logger = logging.getLogger("PyInstaller")
        pyi_logger.addHandler(handler)

        try:
            self.progress.emit(30, "正在构建 Verifier...")
            was_frozen = getattr(sys, "frozen", False)
            was_isolated = getattr(sys, "_pyi_isolated_subprocess", False)
            if was_frozen:
                sys.frozen = False
                # PyInstaller launches isolated helpers with sys.executable. In a
                # frozen Builder that would relaunch this app, so keep them in-process.
                sys._pyi_isolated_subprocess = True
            try:
                run_pyinstaller(pyi_args)
            finally:
                if was_frozen:
                    sys.frozen = True
                    sys._pyi_isolated_subprocess = was_isolated
            return 0, output_lines
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if code and str(exc.code) not in output_lines:
                output_lines.append(str(exc.code))
            return code, output_lines
        finally:
            pyi_logger.removeHandler(handler)

    def _emit_progress_from_line(self, line: str):
        if "INFO: Building" in line:
            self.progress.emit(30, "正在构建 PKG...")
        elif "INFO: Bootloader" in line:
            self.progress.emit(50, "引导加载程序...")
        elif "INFO: checking" in line:
            self.progress.emit(60, "检查依赖项...")
        elif "INFO: Building" in line and "COLLECT" in line:
            self.progress.emit(80, "收集文件...")
        elif "INFO: Building" in line and "EXE" in line:
            self.progress.emit(90, "生成 EXE...")
        elif "INFO: Appending" in line:
            self.progress.emit(95, "附加资源...")

    def _write_embedded_data(self, path: str):
        import json
        import base64
        from shared.crypto import (
            aes_encrypt, create_signed_payload, generate_aes_key,
        )
        import hashlib

        checksum_entries = self._project.get("checksum_entries", [])
        checklists = self._project.get("verifier_checklists", {})
        active_checklist = self._project.get("verifier_active_checklist", "")

        if not checklists:
            checklists = {"default": checksum_entries}
            active_checklist = active_checklist or "default"
        if active_checklist not in checklists:
            active_checklist = next(iter(checklists))
        checksum_entries = checklists.get(active_checklist, [])

        manifest_hash = ""
        if checksum_entries:
            manifest_bytes = json.dumps(
                sorted(checksum_entries, key=lambda e: e.get("path", "")),
                ensure_ascii=False, sort_keys=True,
            ).encode("utf-8")
            manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

        verifier_config = {
            "title": self._project.get("verifier_title", "File Integrity Verifier"),
            "version": self._project.get("verifier_version", "1.0.0.0"),
            "path_rule": self._project.get("verifier_path_rule", "current_dir"),
            "subfolder": self._project.get("verifier_subfolder", ""),
            "custom_template": self._project.get("verifier_custom_template", ""),
            "checksum_entries": checksum_entries,
            "checklists": checklists,
            "active_checklist": active_checklist,
            "algorithm": self._project.get("checksum_algorithm", "sha256"),
            # Files the Builder deliberately ignored must stay ignored when the
            # verifier looks for unexpected files on the client machine.
            "exclude_rules": self._project.get("exclude_rules") or {},
            "exclude_paths": self._project.get("exclude_paths") or [],
            "signature_algorithm": self._project.get("signature_algorithm", "RSA"),
            "manifest_hash": manifest_hash,
            "enable_signature_verify": self._project.get("verifier_enable_signature_verify", True),
            "enable_antidebug": self._project.get("verifier_enable_antidebug", False),
            "enable_antisanbox": self._project.get("verifier_enable_antisanbox", False),
        }

        config_json = json.dumps(verifier_config, ensure_ascii=False, indent=2)
        lines = [
            "# Auto-generated embedded data for File Integrity Verifier",
            "# DO NOT EDIT MANUALLY",
        ]

        public_key_pem = self._project.get("public_key_pem", "")
        if public_key_pem:
            pub_b64 = base64.b64encode(public_key_pem.encode("utf-8")).decode("ascii")
            lines.append(f"EMBEDDED_PUBLIC_KEY = {json.dumps(pub_b64)}")

        if (public_key_pem
                and self._project.get("verifier_enable_signature_verify", True)
                and checksum_entries):
            private_key_pem = self._project.get("private_key_pem", "")
            try:
                signature = create_signed_payload(
                    {"manifest_hash": manifest_hash},
                    private_key_pem.encode("utf-8"),
                    self._project.get("signature_algorithm", "RSA"),
                )
                signature_b64 = base64.b64encode(signature).decode("ascii")
                lines.append(
                    f"EMBEDDED_MANIFEST_SIGNATURE = {json.dumps(signature_b64)}"
                )
            except Exception:
                # A bad private key is a Builder-side configuration error and is
                # surfaced by Step3 before packing; here we preserve a working
                # verifier and let its hash-only check remain active.
                pass

        if self._project.get("verifier_embed_encrypted", True):
            key = generate_aes_key()
            plaintext = config_json.encode("utf-8")
            if len(plaintext) > 1024:
                plaintext = zlib.compress(plaintext, level=9)
            ciphertext = aes_encrypt(plaintext, key)
            payload_b64 = base64.b64encode(ciphertext).decode("ascii")
            key_b64 = base64.b64encode(key).decode("ascii")
            lines.append(f"EMBEDDED_CONFIG_KEY = {json.dumps(key_b64)}")
            lines.append(f"EMBEDDED_CONFIG_B64 = {json.dumps(payload_b64)}")
        else:
            lines.append(f"EMBEDDED_CONFIG = {config_json}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
