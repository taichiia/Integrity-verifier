import os
import sys
import subprocess
import tempfile

from PySide6.QtCore import QThread, Signal


class PackWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, project_data: dict, parent=None):
        super().__init__(parent)
        self._project = project_data
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
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

            with tempfile.TemporaryDirectory(prefix="fit_build_") as build_tmp:
                cmd = [
                    sys.executable, "-m", "PyInstaller",
                    "--onefile",
                    "--noconsole",
                    "--clean",
                    "--name", "FileIntegrityVerifier",
                    "--distpath", output_dir,
                    "--workpath", os.path.join(build_tmp, "build"),
                    "--specpath", os.path.join(build_tmp, "spec"),
                    verifier_main,
                ]

                icon_path = self._project.get("icon_path", "")
                if icon_path and os.path.isfile(icon_path):
                    cmd.insert(4, f"--icon={icon_path}")

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=verifier_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                output_lines = []
                for line in process.stdout:
                    if self._cancelled:
                        process.terminate()
                        return
                    output_lines.append(line.strip())
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
                        self.progress.emit(95, "附加归档...")

                returncode = process.wait()

            if returncode != 0:
                self.error_occurred.emit(
                    f"PyInstaller 打包失败 (退出码 {returncode}):\n" +
                    "\n".join(output_lines[-20:])
                )
                return

            self.progress.emit(100, "打包完成!")

            exe_path = os.path.join(output_dir, "FileIntegrityVerifier.exe")
            if os.path.isfile(exe_path):
                self.finished.emit(exe_path)
            else:
                for f in os.listdir(output_dir):
                    if f.endswith(".exe"):
                        self.finished.emit(os.path.join(output_dir, f))
                        return
                self.finished.emit(output_dir)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _write_embedded_data(self, path: str):
        import json
        import base64
        from shared.crypto import aes_encrypt, generate_aes_key
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

        if self._project.get("verifier_embed_encrypted", True):
            key = generate_aes_key()
            plaintext = config_json.encode("utf-8")
            ciphertext = aes_encrypt(plaintext, key)
            payload_b64 = base64.b64encode(ciphertext).decode("ascii")
            key_b64 = base64.b64encode(key).decode("ascii")
            lines.append(f"EMBEDDED_CONFIG_KEY = {json.dumps(key_b64)}")
            lines.append(f"EMBEDDED_CONFIG_B64 = {json.dumps(payload_b64)}")
        else:
            lines.append(f"EMBEDDED_CONFIG = {config_json}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
