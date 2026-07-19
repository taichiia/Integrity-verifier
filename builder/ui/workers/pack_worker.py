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
            verifier_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "..", "verifier"
            )
            verifier_dir = os.path.normpath(verifier_dir)
            verifier_main = os.path.join(verifier_dir, "main.py")

            if not os.path.isfile(verifier_main):
                self.error_occurred.emit(f"未找到验证器源码: {verifier_main}")
                return

            self.progress.emit(5, "准备验证器源码...")

            embedded_data_path = os.path.join(verifier_dir, "_embedded_data.py")
            self._write_embedded_data(embedded_data_path)

            self.progress.emit(10, "启动 PyInstaller 打包...")

            output_dir = self._project.get("output_path", "")
            if not output_dir:
                output_dir = os.path.join(
                    os.path.dirname(verifier_dir), "output"
                )

            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--onefile",
                "--noconsole",
                "--clean",
                "--name", "FileIntegrityVerifier",
                "--distpath", output_dir,
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
        checksum_entries = self._project.get("checksum_entries", [])
        verifier_config = {
            "title": self._project.get("verifier_title", "File Integrity Verifier"),
            "version": self._project.get("verifier_version", "1.0.0.0"),
            "path_rule": self._project.get("verifier_path_rule", "current_dir"),
            "subfolder": self._project.get("verifier_subfolder", ""),
            "custom_template": self._project.get("verifier_custom_template", ""),
            "checksum_entries": checksum_entries,
            "algorithm": self._project.get("checksum_algorithm", "sha256"),
        }

        import json
        content = [
            "# Auto-generated embedded data for File Integrity Verifier",
            "# DO NOT EDIT MANUALLY",
            f"EMBEDDED_CONFIG = {json.dumps(verifier_config, indent=2)}",
        ]

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

